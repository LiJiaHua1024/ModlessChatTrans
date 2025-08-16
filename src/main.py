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

import threading
import time
from importlib.metadata import version
from datetime import datetime

from modless_chat_trans.file_utils import get_platform
from modless_chat_trans.config import read_config, MonitorMode, ServiceType
from modless_chat_trans.i18n import set_language
from modless_chat_trans.logger import init_logger, logger

cfg = read_config()
init_logger(cfg.settings.debug)
set_language(cfg.settings.interface_language)

from modless_chat_trans.web_display import start_httpserver_thread, display_message
from modless_chat_trans.log_monitor import start_log_monitor
from modless_chat_trans.message_processor import init_processor, process_message
from modless_chat_trans.translator import Translator, ts, litellm
from modless_chat_trans.interface import ProgramInfo, MainWindow, QApplication
from modless_chat_trans.clipboard_monitor import monitor_clipboard, modify_clipboard
from modless_chat_trans.i18n import _
from modless_chat_trans.updater import Updater

program_info = ProgramInfo(
    version=f"v{version('ModlessChatTrans')}",
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


def start_translation(config):
    def callback(data, data_type):
        start_time = time.time()
        # 重试5次
        for i in range(5):
            if data_type == "log":
                if processed_message := process_message(
                        data,
                        data_type,
                        player_translator,
                        source_language=config.message_capture.source_language,
                        target_language=config.message_capture.target_language
                ):
                    if processed_message[1]:
                        duration = time.time() - start_time
                        display_message(
                            *processed_message,
                            duration=duration
                        )
                        if processed_message[0] != "[ERROR]":
                            break
                        else:
                            logger.error(processed_message[1])
                            return None
                    return None
                else:
                    break  # 不是聊天消息，跳过
            elif data_type == "clipboard":
                if processed_message := process_message(
                        data,
                        data_type,
                        send_translator,
                        source_language=config.message_send.source_language,
                        target_language=config.message_send.target_language
                ):
                    if not processed_message[0]:
                        modify_clipboard(processed_message[1])
                        duration = time.time() - start_time
                        display_message(
                            "[INFO]",
                            _("要发送的消息翻译完成，翻译结果已复制到剪切板"),
                            processed_message[2],
                            duration=duration
                        )
                        return processed_message[1]
                    else:
                        display_message(*processed_message)
                        return None
                return None
            return None
        return None

    player_translator = Translator(config.player_translation)
    if config.send_translation_independent:
        send_translator = Translator(config.send_translation)
    else:
        send_translator = player_translator

    start_httpserver_thread(
        http_port=config.message_presentation.web_port,
        callback=callback
    )

    init_processor(
        config.message_capture,
        config.glossary
    )

    monitor_thread = threading.Thread(
        target=start_log_monitor,
        args=(
            config.message_capture,
            callback
        )
    )
    monitor_thread.daemon = True
    monitor_thread.start()

    if config.message_send.monitor_clipboard:
        clipboard_thread = threading.Thread(target=monitor_clipboard, args=(callback,))
        clipboard_thread.daemon = True
        clipboard_thread.start()

    def load_litellm():
        litellm_name = litellm.__name__
        logger.info(f"'litellm'(name: {litellm_name}) library preloaded")

    def load_translators():
        ts_version = ts.__version__
        logger.info(f"'translators'(version: {ts_version}) library preloaded")

    services_to_load = {config.player_translation.service_type}
    if config.send_translation_independent:
        services_to_load.add(config.send_translation.service_type)

    if ServiceType.LLM in services_to_load:
        threading.Thread(target=load_litellm, daemon=True).start()
    if ServiceType.TRADITIONAL in services_to_load:
        threading.Thread(target=load_translators, daemon=True).start()


def run_scheduled_update_check(update_check_func):
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


def main():
    app = QApplication([])
    main_window = MainWindow(program_info, updater, cfg, start_translation)
    run_scheduled_update_check(main_window.setting_interface.check_for_updates)
    main_window.show()
    app.exec()


if __name__ == "__main__":
    main()
