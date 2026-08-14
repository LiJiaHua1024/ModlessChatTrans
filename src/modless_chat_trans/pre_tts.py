# Copyright (C) 2026 LiJiaHua1024
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

import asyncio
import pickle
import random
import threading
import time
from typing import Optional

from modless_chat_trans.file_utils import cache as trans_cache, get_pre_tts_cache
from modless_chat_trans.logger import logger
from modless_chat_trans.tts_engine import TTS_AVAILABLE, infer_voice, preprocess_for_tts

try:
    import edge_tts
except ImportError:
    edge_tts = None  # type: ignore[assignment]

# 每轮最多预合成的条数
PRE_TTS_BUDGET = 200
# 聚合命中次数低于该值的译文不参与预合成（一次性噪声）
PRE_TTS_MIN_COUNT = 2
# 每条合成之间的最小间隔（秒），避免触发 Edge TTS 限流
PRE_TTS_DELAY = 0.3
# 连续失败达到该次数后中止本轮
PRE_TTS_MAX_CONSECUTIVE_FAILURES = 5
# 单条合成超时（秒）
PRE_TTS_TIMEOUT = 15.0
# 失败退避上限（秒）
PRE_TTS_BACKOFF_MAX = 30.0


class PreTTSEngine:
    """Pre-TTS 预合成引擎（手动触发，一次一轮，立即执行）。

    扫描翻译缓存，按译文聚合热度（命中率 = count / age）降序取前
    PRE_TTS_BUDGET 条，立即逐条合成音频并写入 Pre-TTS 缓存。

    每个条目的写入都是原子的：中断只会丢弃当前正在合成的条目，
    已完成的条目全部保留在缓存中。
    """

    def __init__(self):
        self._running = False
        self._stop_requested = False
        self._lock = threading.Lock()
        self.last_result: dict = {}
        self._progress_total = 0
        self._progress_done = 0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def progress(self) -> tuple:
        """返回 (已完成条目数, 总条目数)"""
        with self._lock:
            return self._progress_done, self._progress_total

    def start(self, config) -> bool:
        """触发一轮预合成；已在运行时返回 False"""
        if not TTS_AVAILABLE or edge_tts is None:
            return False
        if config is None or not hasattr(config, "tts"):
            return False
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_requested = False
            self._stop_event = None
            self.last_result = {}
            self._progress_done = 0
            self._progress_total = 0
        threading.Thread(
            target=self._worker,
            args=(config,),
            daemon=True,
            name="pre-tts",
        ).start()
        logger.info("[Pre-TTS] Cycle started")
        return True

    def stop(self):
        """请求停止当前预合成：当前条目立即取消，已完成的条目保留在缓存中"""
        with self._lock:
            self._stop_requested = True
        loop = self._loop
        if loop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(self._stop_event.set)
            except Exception:
                pass

    def _worker(self, config):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        result: dict = {}
        try:
            result = loop.run_until_complete(self._cycle(config))
        except Exception as e:
            logger.error(f"[Pre-TTS] Cycle failed: {e}")
            result = {"error": str(e)}
        finally:
            loop.close()
            self._loop = None
        with self._lock:
            self._running = False
            self.last_result = result
        logger.info(f"[Pre-TTS] Cycle finished: {result}")

    def _set_progress(self, done: int, total: int):
        with self._lock:
            self._progress_done = done
            self._progress_total = total

    def _bump_progress(self):
        with self._lock:
            self._progress_done += 1

    def _scan_and_rank(self, now: float) -> list:
        """扫描翻译缓存，按译文聚合热度（count / age）降序返回前 PRE_TTS_BUDGET 条"""
        # 解码规则（diskcache 存储格式）：
        # - key 列：str/int/float 键原样存储（raw 标记为 1），其余类型为 pickle（raw 标记为 0）
        # - value 列：mode=1 原样存储，mode=4 为 pickle，其余（文件型，≥32KB）跳过
        rows = trans_cache._sql(
            'SELECT key, value, store_time, access_count, raw, mode FROM Cache'
        )
        agg: dict = {}
        for key_blob, value_blob, store_time, access_count, raw_flag, mode in rows:
            if raw_flag == 1:
                original = key_blob
            else:
                try:
                    original = pickle.loads(key_blob)
                except Exception:
                    continue
            if not isinstance(original, str):
                continue
            if mode == 1:  # MODE_RAW
                translated = value_blob
            elif mode == 4:  # MODE_PICKLE
                try:
                    translated = pickle.loads(value_blob)
                except Exception:
                    continue
            else:
                continue
            if not isinstance(translated, str):
                continue
            text = preprocess_for_tts(translated)
            if not text:
                continue
            entry = agg.get(text)
            if entry is None:
                agg[text] = [float(access_count), float(store_time)]
            else:
                entry[0] += access_count
                if store_time < entry[1]:
                    entry[1] = store_time

        scored: list = []
        for text, (count, store_time) in agg.items():
            if count < PRE_TTS_MIN_COUNT:
                continue
            age_hours = max((now - store_time) / 3600.0, 1.0)
            scored.append((text, count / age_hours))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:PRE_TTS_BUDGET]

    async def _synthesize(self, text: str, voice: str, speed: str, pitch: str) -> Optional[bytes]:
        """合成单条音频并返回 MP3 字节"""
        communicate = edge_tts.Communicate(
            text=text, voice=voice, rate=speed, pitch=pitch
        )
        chunks = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                data = chunk.get("data")
                if data:
                    chunks.append(data)
        return b"".join(chunks)

    async def _cycle(self, config) -> dict:
        tts_cfg = config.tts
        target_language = config.message_capture.target_language
        voice = infer_voice(target_language, tts_cfg.voice)
        speed = tts_cfg.speed
        pitch = tts_cfg.pitch

        candidates = self._scan_and_rank(time.time())
        if not candidates:
            logger.debug("[Pre-TTS] No candidates from translation cache")
            return {"synthesized": 0, "skipped": 0, "total": 0, "size_bytes": 0}

        pre_cache = get_pre_tts_cache()
        synthesized = 0
        skipped = 0
        consecutive_failures = 0
        backoff = 1.0

        self._stop_event = asyncio.Event()
        if self._stop_requested:
            self._stop_event.set()

        self._set_progress(0, len(candidates))
        for text, _score in candidates:
            if self._stop_event.is_set():
                break

            key = (voice, speed, pitch, text)
            if key in pre_cache:
                skipped += 1
                self._bump_progress()
                continue

            # 合成 / 停止 / 超时三路竞速：停止时立即取消当前合成
            synth_task = asyncio.ensure_future(
                self._synthesize(text, voice, speed, pitch)
            )
            stop_task = asyncio.ensure_future(self._stop_event.wait())
            timeout_task = asyncio.ensure_future(asyncio.sleep(PRE_TTS_TIMEOUT))
            done, pending = await asyncio.wait(
                {synth_task, stop_task, timeout_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if pending:
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

            if stop_task in done:
                logger.info("[Pre-TTS] Cycle stopped by user")
                break

            if synth_task in done:
                try:
                    data = synth_task.result()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    consecutive_failures += 1
                    logger.warning(
                        f"[Pre-TTS] Synthesis failed ({consecutive_failures} consecutive): "
                        f"{text[:40]!r}: {e}"
                    )
                    self._bump_progress()
                    if consecutive_failures >= PRE_TTS_MAX_CONSECUTIVE_FAILURES:
                        logger.warning("[Pre-TTS] Aborting cycle: too many consecutive failures")
                        break
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, PRE_TTS_BACKOFF_MAX)
                    continue
                if not data or self._stop_event.is_set():
                    break
            else:
                # 超时
                consecutive_failures += 1
                logger.warning(
                    f"[Pre-TTS] Synthesis timed out ({consecutive_failures} consecutive): "
                    f"{text[:40]!r}"
                )
                self._bump_progress()
                if consecutive_failures >= PRE_TTS_MAX_CONSECUTIVE_FAILURES:
                    logger.warning("[Pre-TTS] Aborting cycle: too many consecutive failures")
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, PRE_TTS_BACKOFF_MAX)
                continue

            # 单条原子写入：中断时仅丢弃当前条目，已完成条目全部保留
            try:
                pre_cache[key] = data
            except Exception as e:
                logger.error(f"[Pre-TTS] Cache write failed: {e}")
                self._bump_progress()
                continue

            synthesized += 1
            consecutive_failures = 0
            backoff = 1.0
            self._bump_progress()
            await asyncio.sleep(PRE_TTS_DELAY + random.uniform(0, 0.2))

        total = len(pre_cache)
        size_bytes = 0
        try:
            size_bytes = pre_cache.volume()
        except Exception:
            pass
        return {
            "synthesized": synthesized,
            "skipped": skipped,
            "total": total,
            "size_bytes": size_bytes,
        }


_engine: Optional[PreTTSEngine] = None
_engine_lock = threading.Lock()


def get_pre_tts_engine() -> PreTTSEngine:
    """获取全局 Pre-TTS 引擎单例"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = PreTTSEngine()
    return _engine
