# Copyright (C) 2024-2025 LiJiaHua1024
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
import time
import threading
import locale
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, Callable



# ──────────────────────────────
# 可选依赖：watchdog
# 导入失败时降级为兼容（轮询）模式
# ──────────────────────────────
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError as _wd_exc:
    Observer = None  # type: ignore[assignment,misc]
    FileSystemEventHandler = object  # type: ignore[assignment,misc]
    WATCHDOG_AVAILABLE = False
    import logging as _logging
    _logging.getLogger(__name__).warning(
        f"[LogMonitor] 'watchdog' not available, efficient mode disabled: {_wd_exc}"
    )

from modless_chat_trans.file_utils import find_latest_log
from modless_chat_trans.logger import logger
from modless_chat_trans.config import MonitorMode, MessageCaptureConfig


# ------------------------------
# 有序处理器：并发翻译 + slot 预分配保序
# ------------------------------

class OrderedProcessor:
    """
    并发处理器：将日志行批量提交到线程池并发翻译。

    工作原理（两阶段）：
    1. 阻塞等待第一条消息（零额外延迟）
    2. 非阻塞排空队列（零等待机会性打包）
    3. 阶段1（单线程）：prepare → allocate_slot → context_buffer.push
    4. 阶段2（多线程）：translate_prepared → fill_slot
    """

    MAX_BATCH_SIZE = 20
    MAX_WORKERS = 8  # 翻译线程池大小

    def __init__(
        self,
        line_queue: Queue,
        callback: Callable,
        batch_callback: Callable,
        context_buffer=None,
        translator=None,
        source_language: str = "",
        target_language: str = "",
        replace_garbled_chars: bool = False,
        tts_engine=None,
    ):
        """
        :param line_queue:      生产者写入的队列，元素为 (line: str, arrival_time: float)
        :param callback:        单条处理回调 callback(line, arrival_time, data_type='log')
        :param batch_callback:  批量处理回调 batch_callback(items: list[(line, float)], data_type='log')
        :param context_buffer:  上下文缓冲区（用于 prepare 阶段 push 原文）
        :param translator:      翻译器实例
        :param source_language: 源语言
        :param target_language: 目标语言
        :param replace_garbled_chars: 是否替换乱码
        :param tts_engine:      TTS 引擎（可选）
        """
        self._queue = line_queue
        self._callback = callback
        self._batch_callback = batch_callback
        self._context_buffer = context_buffer
        self._translator = translator
        self._source_language = source_language
        self._target_language = target_language
        self._replace_garbled_chars = replace_garbled_chars
        self._tts_engine = tts_engine
        self._stop = False
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS,
            thread_name_prefix="trans-worker"
        )
        self._thread = threading.Thread(
            target=self._run,
            name="ordered-processor",
            daemon=True
        )

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop = True

    def join(self, timeout=None):
        self._thread.join(timeout=timeout)
        self._executor.shutdown(wait=False)

    def _run(self):
        from modless_chat_trans.web_display import allocate_slot, fill_slot
        from modless_chat_trans.message_processor import prepare
        from modless_chat_trans.context_buffer import ContextEntry, extract_log_time

        while not self._stop:
            # 1. 阻塞等待第一条
            try:
                first = self._queue.get(timeout=1.0)
            except Empty:
                continue

            batch = [first]

            # 2. 非阻塞排空（零等待）
            while len(batch) < self.MAX_BATCH_SIZE:
                try:
                    batch.append(self._queue.get_nowait())
                except Empty:
                    break

            # ========== 阶段1：单线程 prepare + allocate_slot + push ==========
            # 顺序执行，保证 context_buffer 顺序更新
            # 后面的消息必须等前面的消息 push 完才能动
            items = []  # [(prepared, slot_id, log_time)]
            for line, arrival_time in batch:
                # 非 CHAT 行直接提交
                if "[CHAT]" not in line:
                    self._executor.submit(self._callback, line, arrival_time, None, data_type="log")
                    continue

                # prepare（解析+过滤，极快）
                prepared = prepare(line, "log", self._replace_garbled_chars)
                if prepared is None:
                    # 被过滤掉，分配 slot 后立即清除
                    slot_id = allocate_slot(arrival_time=arrival_time)
                    fill_slot(slot_id, "", "", {})
                    continue

                # 分配 slot（保证顺序）
                slot_id = allocate_slot(name=prepared.name, arrival_time=arrival_time)
                log_time = extract_log_time(line, arrival_time)

                # 立即 push 原文到 context_buffer（翻译前）
                # 这样后续消息的 context_messages 就能看到这条原文
                if self._context_buffer:
                    self._context_buffer.push(ContextEntry(
                        original=prepared.original,
                        timestamp=log_time,
                        player_name=prepared.name or "",
                    ))

                items.append((prepared, slot_id, log_time))

            if not items:
                continue

            # ========== 阶段2：多线程 translate + fill_slot ==========
            for prepared, slot_id, log_time in items:
                self._executor.submit(
                    self._translate_and_fill,
                    prepared, slot_id, log_time,
                )

    def _translate_and_fill(self, prepared, slot_id, log_time):
        """在线程池中执行：翻译 + fill_slot + TTS"""
        from modless_chat_trans.web_display import fill_slot
        from modless_chat_trans.message_processor import translate_prepared

        start_time = time.time()

        # 获取上下文（此时 context_buffer 已包含所有 prepare 阶段 push 的原文）
        ctx_messages = []
        if self._context_buffer:
            ctx_messages = self._context_buffer.get_context_messages()

        # 翻译（含重试）
        for attempt in range(5):
            name, translated, info = translate_prepared(
                prepared,
                translator=self._translator,
                source_language=self._source_language,
                target_language=self._target_language,
                context_messages=ctx_messages,
            )

            if name != "[ERROR]":
                duration = time.time() - start_time
                fill_slot(slot_id, name or "", translated or "", info, duration=duration, original=prepared.original)

                # TTS
                if self._tts_engine and self._tts_engine.enabled and translated:
                    self._tts_engine.enqueue(
                        name or "", translated,
                        self._target_language,
                    )
                return
            else:
                logger.error(translated)
                if attempt >= 4:
                    duration = time.time() - start_time
                    fill_slot(slot_id, name or "", translated or "", info, duration=duration, original=prepared.original)
                    return



# ------------------------------
# 编码策略：BOM > 严格 UTF-8 > 区域回退（唯一回退）> 兜底 replace
# ------------------------------

def _has_bom(raw: bytes) -> Optional[str]:
    if raw.startswith(b"\xEF\xBB\xBF"):
        return "utf-8-sig"
    if raw.startswith(b"\xFF\xFE\x00\x00"):
        return "utf-32-le"
    if raw.startswith(b"\x00\x00\xFE\xFF"):
        return "utf-32-be"
    if raw.startswith(b"\xFF\xFE"):
        return "utf-16-le"
    if raw.startswith(b"\xFE\xFF"):
        return "utf-16-be"
    # UTF-7 极少见
    if raw.startswith(b"\x2B\x2F\x76"):
        return "utf-7"
    return None


def _is_ascii_only(raw: bytes) -> bool:
    return all(b < 0x80 for b in raw)


def _looks_like_utf8(raw: bytes) -> bool:
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _parse_lang_region() -> Tuple[Optional[str], Optional[str]]:
    lang_code = None
    try:
        # 可能返回如 'zh_CN'、'ru_RU'
        lang_code, _ = locale.getdefaultlocale()
    except Exception:
        pass
    if not lang_code:
        env = os.environ.get("LC_ALL") or os.environ.get("LANG") or os.environ.get("LC_CTYPE") or ""
        lang_code = env.split(".", 1)[0] if env else ""
    lang = region = None
    if lang_code:
        parts = lang_code.replace("-", "_").split("_")
        if parts:
            lang = parts[0].lower()
        if len(parts) >= 2:
            region = parts[1].upper()
    return lang, region


def _fallback_encoding_by_locale() -> str:
    lang, region = _parse_lang_region()
    if lang == "zh":
        # 繁体偏 Big5，其余 GB18030
        if region in {"TW", "HK", "MO"}:
            return "big5"
        return "gb18030"
    if lang == "ja":
        return "cp932"  # Shift_JIS
    if lang == "ko":
        return "cp949"  # EUC-KR 超集
    if lang in {"ru", "uk", "bg", "sr"}:
        return "cp1251"  # 西里尔
    if lang == "el":
        return "cp1253"
    if lang == "tr":
        return "cp1254"
    if lang in {"ar", "fa", "ur"}:
        return "cp1256"
    if lang == "vi":
        return "cp1258"
    if lang == "th":
        return "cp874"
    if lang in {"pl", "cs", "sk", "hu", "ro", "hr", "sl", "bs"}:
        return "cp1250"  # 中东欧
    return "cp1252"  # 西欧拉丁（默认）


def _sniff_encoding(file_path: str, sample_size: int = 262144) -> str:
    """
    确定性判定：
    1) BOM
    2) ASCII-only 则 UTF-8
    3) 严格 UTF-8 校验
    4) 区域回退
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read(sample_size)
    except Exception:
        # 文件暂不可读，先用 UTF-8
        return "utf-8"

    enc = _has_bom(raw)
    if enc:
        return enc
    if _is_ascii_only(raw):
        return "utf-8"
    if _looks_like_utf8(raw):
        return "utf-8"
    return _fallback_encoding_by_locale()


# ------------------------------
# 高效模式（watchdog 事件驱动）
# ------------------------------

class EfficientLogMonitor(FileSystemEventHandler):
    """
    事件驱动监控：适合能触发文件修改事件的环境
    """

    def __init__(self, log_path: str, user_encoding: Optional[str], line_queue: Queue):
        super().__init__()
        self._queue = line_queue

        # 路径解析：目录 -> 跟随最新日志；文件 -> 固定该文件
        if os.path.isdir(log_path):
            self.base_dir = os.path.abspath(log_path)
            self.follow_latest = True
            self.current_file = None
        else:
            self.base_dir = os.path.abspath(os.path.dirname(log_path) or ".")
            self.follow_latest = False
            self.current_file = os.path.abspath(log_path)

        # 编码策略
        self.user_encoding_specified = bool(user_encoding and user_encoding.lower() != "auto")
        self.user_encoding = user_encoding if self.user_encoding_specified else None
        self.fallback_encoding = _fallback_encoding_by_locale()
        self.decided_encoding = None
        self.errors_mode = "strict"  # auto 模式下初始严格；用户指定时使用 'replace'

        self.fp = None
        self.line_count = 0

        self._resolve_initial_file()
        self._open_file(start_at_end=True)

    def _resolve_initial_file(self):
        if self.follow_latest:
            while True:
                latest = find_latest_log(self.base_dir)
                if latest:
                    self.current_file = latest
                    break
                logger.info(f"[Efficient] No .log file found in {self.base_dir}. Retry in 5s...")
                time.sleep(5)
        else:
            while not os.path.isfile(self.current_file):
                logger.info(f"[Efficient] File not found: {self.current_file}. Retry in 5s...")
                time.sleep(5)
        logger.info(f"[Efficient] Monitoring initial file: {self.current_file}")

    def _decide_open_params(self, file_path: str) -> Tuple[str, str]:
        if self.user_encoding_specified:
            # 坚持用户编码，防止中断采用 replace
            return self.user_encoding, "replace"
        enc = _sniff_encoding(file_path)
        self.decided_encoding = enc
        return enc, "strict"

    def _open_file(self, start_at_end: bool):
        if self.fp:
            try:
                self.fp.close()
            except Exception:
                pass
            self.fp = None

        try:
            enc, errors = self._decide_open_params(self.current_file)
            self.errors_mode = errors
            self.fp = open(self.current_file, "r", encoding=enc, errors=errors)
            if start_at_end:
                self.fp.seek(0, os.SEEK_END)
            self.line_count = 0
            logger.info(f"[Efficient] Opened {self.current_file} with encoding={enc}, errors={errors}")
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"[Efficient] Cannot open {self.current_file}: {e}. Retry in 2s...")
            time.sleep(2)
            self._resolve_initial_file()
            self._open_file(start_at_end=start_at_end)
        except Exception as e:
            logger.exception(f"[Efficient] Unexpected error opening {self.current_file}: {e}")
            time.sleep(2)
            self._open_file(start_at_end=start_at_end)

    def _switch_encoding_after_error(self):
        # 用户指定编码：坚持用户编码，升级 errors='replace'（已经是 replace 则继续）
        if self.user_encoding_specified:
            if self.errors_mode != "replace":
                logger.info(f"[Efficient] Switching errors to 'replace' for user encoding {self.user_encoding}")
            self._open_file(start_at_end=True)
            return

        # 自动模式：先切到区域回退编码；如果已在回退编码，改用 replace 兜底
        target = self.fallback_encoding
        if (self.decided_encoding or "").lower() != target.lower():
            logger.info(f"[Efficient] Decode error; switching encoding to {target}")
            self.decided_encoding = target
            try:
                if self.fp:
                    self.fp.close()
                self.fp = open(self.current_file, "r", encoding=target, errors="strict")
                self.fp.seek(0, os.SEEK_END)  # 跳过问题行，继续追新
                self.errors_mode = "strict"
            except Exception as e:
                logger.warning(f"[Efficient] Failed to switch to {target}: {e}. Using replace fallback.")
                self.fp = open(self.current_file, "r", encoding=target, errors="replace")
                self.fp.seek(0, os.SEEK_END)
                self.errors_mode = "replace"
        else:
            if self.errors_mode != "replace":
                logger.info(f"[Efficient] Still failing under {target}; switching errors='replace'")
            try:
                if self.fp:
                    self.fp.close()
                self.fp = open(self.current_file, "r", encoding=target, errors="replace")
                self.fp.seek(0, os.SEEK_END)
                self.errors_mode = "replace"
            except Exception as e:
                logger.error(f"[Efficient] Fallback replace failed: {e}")

    def _read_new_lines(self):
        if not self.fp:
            logger.warning("[Efficient] File pointer is None; cannot read.")
            return
        try:
            for line in self.fp:
                if "[CHAT]" not in line:
                    continue
                self.line_count += 1
                arrival_time = time.time()
                self._queue.put((line, arrival_time))
        except UnicodeDecodeError:
            self._switch_encoding_after_error()
        except Exception as e:
            logger.warning(f"[Efficient] Read error: {e}")

    # watchdog 回调
    def on_modified(self, event):
        try:
            if os.path.abspath(event.src_path) == os.path.abspath(self.current_file):
                self._read_new_lines()
        except Exception as e:
            logger.debug(f"[Efficient] on_modified exception: {e}")

    def on_created(self, event):
        # 跟随最新 .log
        if not self.follow_latest:
            return
        try:
            if event.src_path.endswith(".log"):
                latest = find_latest_log(self.base_dir) or event.src_path
                if latest and os.path.abspath(latest) != os.path.abspath(self.current_file):
                    logger.info(f"[Efficient] Newer log detected: {latest}. Switching.")
                    self.current_file = latest
                    self._open_file(start_at_end=False)
        except Exception as e:
            logger.debug(f"[Efficient] on_created exception: {e}")

    def close(self):
        """关闭资源：文件句柄"""
        if self.fp:
            try:
                self.fp.close()
            except Exception:
                pass
            self.fp = None


# ------------------------------
# 兼容模式（轮询 tail）
# ------------------------------

class CompatiblePollingMonitor:
    """
    简单轮询 tail，适用于高版本 MC 优化导致 watchdog 不触发行级事件的情况
    """

    def __init__(self, log_path: str, user_encoding: Optional[str], line_queue: Queue, interval: float = 0.2):
        self._queue = line_queue
        self.interval = max(0.05, float(interval))

        # 路径策略：目录 -> 固定 latest.log；文件 -> 固定该文件
        if os.path.isdir(log_path):
            self.current_file = os.path.abspath(os.path.join(log_path, "latest.log"))
        else:
            self.current_file = os.path.abspath(log_path)
        self.user_encoding_specified = bool(user_encoding and user_encoding.lower() != "auto")
        self.user_encoding = user_encoding if self.user_encoding_specified else None
        self.fallback_encoding = _fallback_encoding_by_locale()
        self.decided_encoding = None
        self.errors_mode = "strict"

        # 文件状态
        self.fp = None
        self.current_inode = None
        self.last_size = 0
        self._stop = False

        self._resolve_initial_file()
        self._open_file(start_at_end=True)

    def _resolve_initial_file(self):
        # latest.log 不存在时等待
        while not os.path.exists(self.current_file):
            base_dir = os.path.dirname(self.current_file)
            logger.info(f"[Compat] Waiting for {self.current_file} in {base_dir} ... retry in 5s")
            time.sleep(5)
        logger.info(f"[Compat] Polling file: {self.current_file}")

    def _decide_open_params(self, file_path: str) -> Tuple[str, str]:
        if self.user_encoding_specified:
            return self.user_encoding, "replace"  # 坚持用户编码，但容错 replace
        enc = _sniff_encoding(file_path)
        self.decided_encoding = enc
        return enc, "strict"

    def _open_file(self, start_at_end: bool):
        if self.fp:
            try:
                self.fp.close()
            except Exception:
                pass
            self.fp = None

        try:
            enc, errors = self._decide_open_params(self.current_file)
            self.errors_mode = errors
            self.fp = open(self.current_file, "r", encoding=enc, errors=errors)
            if start_at_end:
                self.fp.seek(0, os.SEEK_END)
            st = os.stat(self.current_file)
            self.current_inode = getattr(st, "st_ino", None)
            self.last_size = st.st_size
            logger.info(f"[Compat] Opened {self.current_file} with encoding={enc}, errors={errors}")
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"[Compat] Cannot open {self.current_file}: {e}. Retry in 2s...")
            time.sleep(2)
            self._resolve_initial_file()
            self._open_file(start_at_end=start_at_end)
        except Exception as e:
            logger.exception(f"[Compat] Unexpected error opening {self.current_file}: {e}")
            time.sleep(2)
            self._open_file(start_at_end=start_at_end)

    def _switch_encoding_after_error(self):
        if self.user_encoding_specified:
            if self.errors_mode != "replace":
                logger.info(f"[Compat] Switching errors to 'replace' for user encoding {self.user_encoding}")
            self._open_file(start_at_end=True)
            return

        target = self.fallback_encoding
        if (self.decided_encoding or "").lower() != target.lower():
            logger.info(f"[Compat] Decode error; switching encoding to {target}")
            self.decided_encoding = target
            try:
                if self.fp:
                    self.fp.close()
                self.fp = open(self.current_file, "r", encoding=target, errors="strict")
                self.fp.seek(0, os.SEEK_END)
                self.errors_mode = "strict"
            except Exception as e:
                logger.warning(f"[Compat] Failed to switch to {target}: {e}. Using replace fallback.")
                self.fp = open(self.current_file, "r", encoding=target, errors="replace")
                self.fp.seek(0, os.SEEK_END)
                self.errors_mode = "replace"
        else:
            if self.errors_mode != "replace":
                logger.info(f"[Compat] Still failing under {target}; switching errors='replace'")
            try:
                if self.fp:
                    self.fp.close()
                self.fp = open(self.current_file, "r", encoding=target, errors="replace")
                self.fp.seek(0, os.SEEK_END)
                self.errors_mode = "replace"
            except Exception as e:
                logger.error(f"[Compat] Fallback replace failed: {e}")

    def _check_rotation_or_truncate(self) -> bool:
        try:
            st = os.stat(self.current_file)
        except FileNotFoundError:
            logger.warning(f"[Compat] File missing: {self.current_file}. Waiting to reappear...")
            time.sleep(max(self.interval, 0.5))
            self._resolve_initial_file()
            self._open_file(start_at_end=False)
            return True

        inode = getattr(st, "st_ino", None)
        size = st.st_size
        rotated = False
        if self.current_inode is not None and inode is not None and inode != self.current_inode:
            rotated = True
        if size < self.last_size:
            rotated = True

        self.current_inode = inode
        self.last_size = size

        if rotated:
            logger.info(f"[Compat] Log rotated or truncated: {self.current_file}. Reopening from start.")
            self._open_file(start_at_end=False)
            return True
        return False

    def run(self):
        try:
            while not self._stop:
                try:
                    while True:
                        line = self.fp.readline()
                        if not line:
                            break
                        if "[CHAT]" not in line:
                            continue
                        arrival_time = time.time()
                        self._queue.put((line, arrival_time))
                except UnicodeDecodeError:
                    self._switch_encoding_after_error()
                except Exception as e:
                    logger.debug(f"[Compat] Read loop exception: {e}")

                if not self._check_rotation_or_truncate():
                    # 兼容模式固定跟 latest.log 或指定文件，不做其它切换
                    pass

                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("[Compat] KeyboardInterrupt received, stopping polling...")
        except Exception as e:
            logger.error(f"[Compat] Unexpected error in polling loop: {e}")
        finally:
            self.close()

    def close(self):
        """关闭资源：文件句柄"""
        if self.fp:
            try:
                self.fp.close()
            except Exception:
                pass
            self.fp = None

    def stop(self):
        self._stop = True


# ------------------------------
# 入口函数
# ------------------------------

def start_log_monitor(
    config: MessageCaptureConfig,
    callback,
    batch_callback=None,
    context_buffer=None,
    translator=None,
    source_language: str = "",
    target_language: str = "",
    replace_garbled_chars: bool = False,
    tts_engine=None,
):
    """
    启动日志监控。
    - config.minecraft_log_path: 日志目录或文件路径
    - config.log_encoding: 用户编码；为空或 "auto" 则自动判定
    - config.monitor_mode: MonitorMode.EFFICIENT / MonitorMode.COMPATIBLE
    - callback:       单条回调 callback(line, arrival_time, data_type='log')
    - batch_callback: 批量回调 batch_callback(items, data_type='log')
                      为 None 时单条批量均走 callback
    - context_buffer: 上下文缓冲区
    - translator:     翻译器实例
    - source_language / target_language: 翻译语言
    - replace_garbled_chars: 是否替换乱码
    - tts_engine:     TTS 引擎
    """

    mode = config.monitor_mode

    user_encoding = config.log_encoding
    if not user_encoding or (isinstance(user_encoding, str) and user_encoding.lower() == "auto"):
        user_encoding = None

    log_path = config.minecraft_log_path
    if not log_path:
        raise ValueError("minecraft_log_path must not be empty")

    logger.info(f"Starting log monitoring at: {log_path} with mode={mode.value}")

    # 如果没有专属批量回调，用单条回调包装一下
    if batch_callback is None:
        def batch_callback(items, data_type="log"):
            for line, arrival_time, slot_id in items:
                callback(line, arrival_time, slot_id, data_type=data_type)

    # 共享队列（生产者写入，OrderedProcessor 读取）
    line_queue: Queue = Queue(maxsize=500)

    # 启动有序处理器
    processor = OrderedProcessor(
        line_queue=line_queue,
        callback=callback,
        batch_callback=batch_callback,
        context_buffer=context_buffer,
        translator=translator,
        source_language=source_language,
        target_language=target_language,
        replace_garbled_chars=replace_garbled_chars,
        tts_engine=tts_engine,
    )
    processor.start()
    logger.info("[OrderedProcessor] Started ordered consumer thread.")

    if mode == MonitorMode.COMPATIBLE:
        # 兼容模式：轮询 tail
        poller = CompatiblePollingMonitor(
            log_path=log_path,
            user_encoding=user_encoding,
            line_queue=line_queue,
            interval=0.2
        )
        try:
            poller.run()
        finally:
            processor.stop()
            processor.join(timeout=5)
        return

    # 高效模式：watchdog 事件驱动
    if not WATCHDOG_AVAILABLE:
        logger.warning(
            "[LogMonitor] watchdog not available; falling back to compatible (polling) mode automatically."
        )
        poller = CompatiblePollingMonitor(
            log_path=log_path,
            user_encoding=user_encoding,
            line_queue=line_queue,
            interval=0.2
        )
        import atexit
        def poller_cleanup():
            logger.info("[Compat] Performing atexit cleanup...")
            poller.stop()
            processor.stop()
            processor.join(timeout=5)
        atexit.register(poller_cleanup)
        try:
            poller.run()
        finally:
            atexit.unregister(poller_cleanup)
            processor.stop()
            processor.join(timeout=5)
        return

    handler = EfficientLogMonitor(
        log_path=log_path,
        user_encoding=user_encoding,
        line_queue=line_queue
    )
    observer = Observer()
    observer.schedule(handler, handler.base_dir, recursive=False)
    logger.info(f"[Efficient] Observer scheduled for directory: {handler.base_dir}. Starting observer.")
    observer.start()

    import atexit
    def observer_cleanup():
        logger.info("[Efficient] Performing atexit cleanup...")
        observer.stop()
        observer.join()
        try:
            handler.close()
        except Exception:
            pass
        processor.stop()
        processor.join(timeout=5)
    atexit.register(observer_cleanup)

    try:
        observer.join()
    except KeyboardInterrupt:
        logger.info("[Efficient] KeyboardInterrupt received. Stopping observer...")
        observer.stop()
    except Exception as e:
        logger.error(f"[Efficient] Unexpected error in monitoring loop: {e}")
        observer.stop()
        logger.error("[Efficient] Observer stopped due to unexpected error.")

    observer.join()
    atexit.unregister(observer_cleanup)
    logger.info("Log monitoring stopped.")
    try:
        handler.close()
    except Exception:
        pass
    processor.stop()
    processor.join(timeout=5)
