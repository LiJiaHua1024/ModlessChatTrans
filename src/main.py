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

import importlib.util
import os
import sys
import threading
import time
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════
# 核心依赖预检（Pre-flight Check）
# 必须在任何第三方模块导入之前运行，使用纯 stdlib 完成探测。
# 使用 importlib.util.find_spec 做轻量探测（不真正导入模块），
# 避免预检阶段就触发 PySide6 / qfluentwidgets 等重模块的加载。
# 若任何核心依赖缺失，显示友好错误提示并退出，而不是以崩溃方式终止。
# ═══════════════════════════════════════════════════════════════════════

# 核心依赖表：(包名, 用途说明)
_CORE_DEPS = [
    ("loguru",           "日志系统"),
    ("PySide6",          "GUI 框架（图形界面）"),
    ("qfluentwidgets",   "GUI 组件库（Fluent 风格控件）"),
    ("pydantic",         "配置验证与解析"),
    ("pydantic_settings","配置文件加载"),
    ("tomli_w",          "TOML 配置文件写入"),
    ("flask",            "WebUI 服务器（翻译结果展示）"),
    ("diskcache",        "翻译结果缓存"),
    ("requests",         "HTTP 客户端（翻译 API 请求）"),
]


def _pkg_available(pkg: str) -> bool:
    """轻量探测包是否可导入（find_spec 不触发真正的模块导入）"""
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ImportError, ValueError):
        return False


def _preflight_check() -> list[tuple[str, str, str]]:
    """探测所有核心依赖，返回缺失项列表 [(包名, 错误信息, 用途), ...]"""
    missing = []
    for pkg, purpose in _CORE_DEPS:
        if not _pkg_available(pkg):
            missing.append((pkg, "module not found", purpose))
    return missing


def _show_fatal_error_and_exit(missing: list[tuple[str, str, str]]) -> None:
    """
    以友好方式展示致命错误，按 Qt → tkinter → 控制台 顺序降级。
    展示后调用 sys.exit(1) 终止进程。
    """
    title = "ModlessChatTrans — 启动失败"
    brief = "以下核心依赖库缺失或无法导入，程序无法启动："
    detail_lines = []
    for pkg, err, purpose in missing:
        detail_lines.append(f"  • {pkg}（{purpose}）\n      {err}")
    detail = "\n".join(detail_lines)
    footer = "\n请检查安装是否完整，或重新安装程序。\n如使用可执行文件，请尝试重新下载。"
    full_msg = f"{brief}\n\n{detail}\n{footer}"

    # ── 尝试 Qt 对话框 ──────────────────────────────────────────────────
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        _app = QApplication.instance() or QApplication(sys.argv)
        box = QMessageBox()
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText(brief)
        box.setDetailedText(detail + footer)
        box.exec()
        sys.exit(1)
    except Exception:
        pass

    # ── 尝试 tkinter 对话框（stdlib，通常随 Python 安装）──────────────
    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        _root = _tk.Tk()
        _root.withdraw()
        _mb.showerror(title, full_msg)
        _root.destroy()
        sys.exit(1)
    except Exception:
        pass

    # ── 控制台兜底 ──────────────────────────────────────────────────────
    sep = "═" * 60
    print(f"\n{sep}\n[致命错误] {title}\n{sep}\n{full_msg}\n{sep}", file=sys.stderr)
    try:
        input("按 Enter 键退出...")
    except Exception:
        pass
    sys.exit(1)


_missing_core = _preflight_check()
if _missing_core:
    _show_fatal_error_and_exit(_missing_core)

# ═══════════════════════════════════════════════════════════════════════
# 启动流程
# 所有第三方模块的导入都被推迟到 main() / start_translation() 内部，
# 让启动画面（纯 PySide6）能第一时间显示，再在幕后加载重模块。
# ═══════════════════════════════════════════════════════════════════════


def start_translation(config):
    # 重模块延迟到「开始翻译」时才导入，避免拖慢窗口出现时间
    from modless_chat_trans.logger import logger
    from modless_chat_trans.i18n import _
    from modless_chat_trans.config import ServiceType
    from modless_chat_trans.context_buffer import ContextBuffer, ContextEntry, extract_log_time
    from modless_chat_trans.web_display import start_httpserver_thread, display_message, allocate_slot, fill_slot
    from modless_chat_trans.log_monitor import start_log_monitor
    from modless_chat_trans import message_processor
    from modless_chat_trans.message_processor import (
        init_processor, init_blacklist, process_message, parse_message,
        is_user_in_blacklist, is_message_blocked, sanitize_hypixel_name,
    )
    from modless_chat_trans.translator import Translator, MessageType
    from modless_chat_trans.clipboard_monitor import monitor_clipboard, modify_clipboard
    try:
        from modless_chat_trans.tts_engine import TTSEngine, TTS_AVAILABLE
    except Exception as _tts_exc:
        TTSEngine = None  # type: ignore[assignment,misc]
        TTS_AVAILABLE = False
        logger.warning(f"[Startup] TTS module failed to load, TTS will be disabled: {_tts_exc}")

    # 初始化上下文缓冲区
    ctx_cfg = config.context
    context_buffer = ContextBuffer(
        strategy=ctx_cfg.strategy,
        context_length=ctx_cfg.context_length,
        context_timeout=ctx_cfg.context_timeout,
        block_truncation_size=ctx_cfg.block_truncation_size,
    )

    # 初始化 TTS 朗读引擎（若依赖库不可用则使用 no-op stub）
    if TTS_AVAILABLE and TTSEngine is not None:
        tts_engine = TTSEngine(config.tts)
        if config.tts.enabled:
            tts_engine.start()
    else:
        class _NoOpTTS:
            enabled = False
            def enqueue(self, *a, **kw): pass
            def start(self): pass
            def stop(self): pass
        tts_engine = _NoOpTTS()

    def callback(line, arrival_time, slot_id=None, data_type="log", rage_mode=False):
        """
        并发翻译单条回调。
        slot_id 为已预分配的 WebUI 展示位置。
        """
        start_time = time.time()

        def report_error(error_message, info=None):
            """确保失败也能结束 pending slot，并通知 WebUI 结束发送状态。"""
            error_info = dict(info) if isinstance(info, dict) else {}
            if data_type in ("clipboard", "webui"):
                error_info["send_translation_complete"] = True

            duration = time.time() - start_time
            if slot_id is not None:
                fill_slot(slot_id, "[ERROR]", error_message, error_info, duration=duration)
            else:
                display_message("[ERROR]", error_message, error_info, duration=duration)

        def finish_error(error_message, info=None):
            report_error(error_message, info)
            if data_type == "webui":
                return {"error": error_message}
            return None

        if data_type == "log":
            # 提取日志时间或用行到达时间
            try:
                log_time = extract_log_time(line, arrival_time)
                ctx_messages = context_buffer.get_context_messages()
            except Exception as error:
                logger.exception(f"[Log] Failed to prepare translation context: {error}")
                report_error(f"{_('翻译失败，错误：')} {error}")
                return

            if "[CHAT]" not in line:
                if slot_id is not None:
                    fill_slot(slot_id, "", "", {})
                return

            chat_content = line.split("[CHAT]")[1].strip()
            if config.message_capture.replace_garbled_chars:
                chat_content = chat_content.replace("\ufffd\ufffd", "\u00A7")
            try:
                processed_message = process_message(
                    line,
                    data_type,
                    player_translator,
                    source_language=config.message_capture.source_language,
                    target_language=config.message_capture.target_language,
                    context_messages=ctx_messages,
                )
            except Exception as error:
                logger.exception(f"[Log] Unexpected translation failure: {error}")
                report_error(f"{_('翻译失败，错误：')} {error}")
                return

            if not processed_message:
                # 过滤掉了（筛选或黑名单），清除占位 slot
                if slot_id is not None:
                    fill_slot(slot_id, "", "", {})
                return

            name, translated, info = processed_message
            duration = time.time() - start_time
            if name == "[ERROR]":
                logger.error(translated)
                report_error(translated, info)
                return

            original_for_display = chat_content
            if slot_id is not None:
                fill_slot(slot_id, name or "", translated or "", info, duration=duration, original=original_for_display)
            else:
                display_message(name, translated or "", info, duration=duration, original=original_for_display)

            if translated and chat_content:
                context_buffer.push(ContextEntry(
                    original=chat_content,
                    translated=translated,
                    timestamp=log_time,
                    player_name=name or "",
                ))
            # TTS 朗读
            if tts_engine.enabled and translated:
                tts_engine.enqueue(
                    name or "", translated,
                    config.message_capture.target_language
                )

        elif data_type in ("clipboard", "webui"):
            try:
                ctx_messages = context_buffer.get_context_messages()
                processed_message = process_message(
                    line,
                    data_type,
                    send_translator,
                    source_language=config.message_send.source_language,
                    target_language=config.message_send.target_language,
                    rage_mode=rage_mode,
                    context_messages=ctx_messages,
                )
            except Exception as error:
                logger.exception(f"[Clipboard/WebUI] Unexpected translation failure: {error}")
                return finish_error(f"{_('翻译失败，错误：')} {error}")

            if not processed_message:
                return finish_error(_("翻译失败，未生成翻译结果。"))

            is_error, translated, info = processed_message
            if not is_error and translated:
                modify_clipboard(translated)
                duration = time.time() - start_time
                info = dict(info) if isinstance(info, dict) else {}
                info["send_translation_complete"] = True
                if slot_id is not None:
                    fill_slot(slot_id, "[INFO]", _("要发送的消息翻译完成，翻译结果已复制到剪切板"), info, duration=duration)
                else:
                    display_message(
                        "[INFO]",
                        _("要发送的消息翻译完成，翻译结果已复制到剪切板"),
                        info,
                        duration=duration
                    )
                return translated

            logger.error(f"[Clipboard/WebUI] Translation failed: {translated}")
            return finish_error(translated or _("翻译失败，未生成翻译结果。"), info)

    def batch_callback(items, data_type="log"):
        """
        批量回调。items 为 [(line, arrival_time, slot_id), ...]。
        slot_id 已由 OrderedProcessor 预分配。
        """
        if data_type != "log":
            for line, arrival_time, slot_id in items:
                callback(line, arrival_time, slot_id=slot_id, data_type=data_type)
            return

        start_time = time.time()

        # Step 1: 解析每条，过滤非聊天行
        # parsed: [(i_in_items, line, arrival_time, slot_id, chat_content, log_time, player_name)]
        parsed = []
        dismiss_slots = []

        for i, (line, arrival_time, slot_id) in enumerate(items):
            if "[CHAT]" not in line:
                dismiss_slots.append(slot_id)
                continue

            name, chat_content, msg_type = parse_message(line, "log", config.message_capture.replace_garbled_chars)

            should_dismiss = False
            if not chat_content:
                should_dismiss = True
            elif msg_type != MessageType.SEND:
                if name:
                    s_name = sanitize_hypixel_name(name)
                    if is_user_in_blacklist(s_name):
                        should_dismiss = True
                if is_message_blocked(chat_content):
                    should_dismiss = True

            if message_processor.filter_server_messages and not name:
                should_dismiss = True

            if should_dismiss:
                dismiss_slots.append(slot_id)
                continue

            log_time = extract_log_time(line, arrival_time)
            parsed.append((i, line, arrival_time, slot_id, chat_content, log_time, name))

        # 移除被过滤的 slot 的占位符
        for sid in dismiss_slots:
            fill_slot(sid, "", "", {})

        if not parsed:
            return

        # Step 2: 逐条检查缓存和术语表
        from modless_chat_trans.file_utils import cache as trans_cache
        from modless_chat_trans.message_processor import match_and_translate

        need_translate_indices = []
        cached_results = {}

        for i, (item_i, line, arrival_time, slot_id, chat_content, log_time, player_name) in enumerate(parsed):
            if glossary_result := match_and_translate(chat_content):
                cached_results[i] = glossary_result
            elif chat_content in trans_cache:
                cached_results[i] = trans_cache[chat_content]
            else:
                need_translate_indices.append(i)

        # Step 3: 批量翻译未命中的条目
        ctx_messages = context_buffer.get_context_messages()
        batch_results = {}
        fallback_to_single = False

        if need_translate_indices:
            texts_to_translate = [parsed[i][4] for i in need_translate_indices]

            translations = player_translator.translate_batch_with_context(
                texts=texts_to_translate,
                source_language=config.message_capture.source_language,
                target_language=config.message_capture.target_language,
                context_messages=ctx_messages,
            )

            if translations is not None:
                for j, pi in enumerate(need_translate_indices):
                    batch_results[pi] = translations[j]
                    chat_content = parsed[pi][4]
                    if translations[j]:
                        trans_cache[chat_content] = translations[j]
            else:
                fallback_to_single = True

        if fallback_to_single:
            logger.info("[BatchCallback] Batch failed, falling back to single-item processing.")
            for item_i, line, arrival_time, slot_id, chat_content, log_time, player_name in parsed:
                callback(line, arrival_time, slot_id=slot_id, data_type="log")
            return

        # Step 4: 按原序填充 slot 并更新上下文
        duration = time.time() - start_time
        batch_entries = []

        for i, (item_i, line, arrival_time, slot_id, chat_content, log_time, player_name) in enumerate(parsed):
            translated = cached_results.get(i) or batch_results.get(i, "")

            fill_slot(slot_id, player_name, translated or "", {}, duration=duration / len(parsed), original=chat_content)

            if translated:
                batch_entries.append(ContextEntry(
                    original=chat_content,
                    translated=translated,
                    timestamp=log_time,
                    player_name=player_name,
                ))

        if batch_entries:
            context_buffer.push_batch(batch_entries)

        # TTS 朗读批量消息
        if tts_engine.enabled:
            for entry in batch_entries:
                tts_engine.enqueue(
                    entry.player_name, entry.translated,
                    config.message_capture.target_language
                )

    player_translator = Translator(
        config.player_translation,
        config.glossary,
        fallback_llm_config=config.player_translation.fallback_llm,
        fallback_strategy=config.player_translation.fallback_strategy,
    )
    if config.send_translation_independent:
        send_translator = Translator(
            config.send_translation,
            config.glossary,
            fallback_llm_config=config.send_translation.fallback_llm,
            fallback_strategy=config.send_translation.fallback_strategy,
        )
    else:
        send_translator = player_translator

    start_httpserver_thread(
        http_port=config.message_presentation.web_port,
        callback=lambda data, data_type="webui", rage_mode=False: callback(
            data, time.time(), slot_id=allocate_slot(name="[INFO]", arrival_time=time.time()), data_type=data_type, rage_mode=rage_mode
        ),
        tts_engine=tts_engine
    )

    init_processor(
        config.message_capture,
        config.glossary
    )
    init_blacklist(config.blacklist)

    monitor_thread = threading.Thread(
        target=start_log_monitor,
        args=(
            config.message_capture,
            callback,
            batch_callback,
            context_buffer,
            player_translator,
            config.message_capture.source_language,
            config.message_capture.target_language,
            config.message_capture.replace_garbled_chars,
            tts_engine,
        )
    )
    monitor_thread.daemon = True
    monitor_thread.start()

    if config.message_send.monitor_clipboard:
        def clipboard_callback(data, data_type="clipboard"):
            return callback(
                data, time.time(), slot_id=allocate_slot(name="[INFO]", arrival_time=time.time()), data_type=data_type
            )

        clipboard_thread = threading.Thread(target=monitor_clipboard, args=(clipboard_callback,))
        clipboard_thread.daemon = True
        clipboard_thread.start()

    from modless_chat_trans.translator import ensure_litellm_loaded, ensure_ts_loaded

    services_to_load = {config.player_translation.service_type}
    if config.send_translation_independent:
        services_to_load.add(config.send_translation.service_type)

    if ServiceType.LLM in services_to_load:
        threading.Thread(target=ensure_litellm_loaded, daemon=True).start()
    if ServiceType.TRADITIONAL in services_to_load:
        threading.Thread(target=ensure_ts_loaded, daemon=True).start()


def run_scheduled_update_check(update_check_func, cfg):
    from modless_chat_trans.logger import logger
    if cfg.settings.debug:
        logger.debug("Skipping scheduled update check: debug mode is enabled")
        return
    acuf = cfg.settings.auto_check_update_frequency
    luct = cfg.settings.last_update_check_time
    now = datetime.now()
    luct_date = datetime.fromisoformat(luct)
    if (
            (acuf == "daily" and now.date() > luct_date.date()) or
            (acuf == "weekly" and (now - luct_date).days >= 7) or
            (acuf == "monthly" and (now - luct_date).days >= 30)
    ):
        update_check_func(silent=True)


def _dismiss_nuitka_splash():
    """关闭 Nuitka onefile 原生启动画面（删除反馈文件，由 qfw 启动画面接力）"""
    if "NUITKA_ONEFILE_PARENT" not in os.environ:
        return
    try:
        splash_filename = os.path.join(
            os.environ.get("TEMP", os.environ.get("TMP", "/tmp")),
            f"onefile_{int(os.environ['NUITKA_ONEFILE_PARENT'])}_splash_feedback.tmp",
        )
        if os.path.exists(splash_filename):
            os.unlink(splash_filename)
    except Exception:
        pass


def _start_background_preload(cfg):
    """
    主窗口显示后，在后台线程按配置预加载翻译服务与 TTS 依赖。
    与懒加载配合：启动关键路径不被拖慢，第一条翻译消息到来时依赖已就绪。
    翻译服务与 TTS 使用独立线程并行预加载，互不拖累。
    """
    def _preload_services():
        try:
            from modless_chat_trans.config import ServiceType
            from modless_chat_trans.logger import logger
            from modless_chat_trans.translator import ensure_litellm_loaded, ensure_ts_loaded

            services_to_load = {cfg.player_translation.service_type}
            if cfg.send_translation_independent:
                services_to_load.add(cfg.send_translation.service_type)

            # llm_gateway 与 free_translators 使用独立锁，可并行预加载
            if ServiceType.LLM in services_to_load:
                ensure_litellm_loaded()
            if ServiceType.TRADITIONAL in services_to_load:
                ensure_ts_loaded()
        except Exception as _preload_exc:
            from modless_chat_trans.logger import logger
            logger.warning(f"[Startup] Translation service preload failed: {_preload_exc}")

    def _preload_tts():
        try:
            if getattr(cfg.tts, "enabled", False):
                from modless_chat_trans.logger import logger
                from modless_chat_trans.tts_engine import ensure_tts_dependencies
                ensure_tts_dependencies()
        except Exception as _preload_exc:
            from modless_chat_trans.logger import logger
            logger.warning(f"[Startup] TTS preload failed: {_preload_exc}")

    threading.Thread(target=_preload_services, daemon=True, name="startup-preload-services").start()
    threading.Thread(target=_preload_tts, daemon=True, name="startup-preload-tts").start()


def main():
    # ══ 1. QApplication（qfw 启动画面随主窗口显示，见 MainWindow.showEvent）══
    from PySide6.QtWidgets import QApplication
    app = QApplication([])

    # ══ 2. 配置 / 日志 / i18n（pydantic 等重依赖在启动画面背后加载）══
    from modless_chat_trans.config import read_config
    from modless_chat_trans.file_utils import get_platform
    from modless_chat_trans.i18n import set_language
    from modless_chat_trans.logger import init_logger, logger

    cfg = read_config()
    init_logger(cfg.settings.debug)
    set_language(cfg.settings.interface_language)

    # ══ 3. GUI 主窗口（qfluentwidgets 最重，splash 期间加载）══
    from modless_chat_trans.interface import ProgramInfo, MainWindow
    from modless_chat_trans.updater import Updater
    from modless_chat_trans._version import get_version_string

    program_info = ProgramInfo(
        version=get_version_string(),
        author="LiJiaHua1024",
        email="minecraft_benli@163.com",
        github="https://github.com/LiJiaHua1024/ModlessChatTrans",
        license=("GNU General Public License v3.0", "https://www.gnu.org/licenses/gpl-3.0.html")
    )

    updater = Updater(
        program_info.version,
        program_info.author,
        "ModlessChatTrans",
        include_prerelease=cfg.settings.include_prerelease
    )

    logger.info(f"ModlessChatTrans {program_info.version} started, "
                f"Platform: {'Windows' if get_platform() == 0 else 'Linux'}, "
                f"Debug mode: {cfg.settings.debug}")

    main_window = MainWindow(program_info, updater, cfg, start_translation)
    run_scheduled_update_check(main_window.setting_interface.check_for_updates, cfg)
    main_window.show()
    # Nuitka onefile 原生 splash 保持到主窗口就位，由 qfw 启动画面接力
    _dismiss_nuitka_splash()
    # 窗口已就绪，后台预热翻译服务/TTS，避免第一条消息现场加载
    _start_background_preload(cfg)
    app.exec()


if __name__ == "__main__":
    main()
