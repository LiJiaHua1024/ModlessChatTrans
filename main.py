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

from modless_chat_trans.file_utils import read_config, get_platform
from modless_chat_trans.i18n import set_language
from modless_chat_trans.logger import init_logger, logger

conf = read_config(logger_initialized=False)
init_logger(conf.debug)
set_language(conf.interface_lang)

from modless_chat_trans.display import init_display, display_message
from modless_chat_trans.log_monitor import monitor_log_file
from modless_chat_trans.message_processor import init_processor, process_message
from modless_chat_trans.translator import Translator
from modless_chat_trans.interface import ProgramInfo, MainInterfaceManager, MoreSettingsManager
from modless_chat_trans.clipboard_monitor import monitor_clipboard, modify_clipboard
from modless_chat_trans.i18n import _
from modless_chat_trans.updater import Updater

program_info = ProgramInfo(version="v2.1.2",
                           author="LiJiaHua1024",
                           email="minecraft_benli@163.com",
                           github="https://github.com/LiJiaHua1024/ModlessChatTrans",
                           license=("GNU General Public License v3.0", "https://www.gnu.org/licenses/gpl-3.0.html"))

updater = Updater(program_info.version, program_info.author, "ModlessChatTrans",
                  include_prerelease=conf.include_prerelease)

logger.info(f"ModlessChatTrans {program_info.version} started, "
            f"Platform: {'Windows' if get_platform() == 0 else 'Linux'}, "
            f"Debug mode: {conf.debug}")


def start_translation():
    config = read_config()

    def callback(data, data_type):
        # 重试5次
        for i in range(5):
            if data_type == "log":
                if processed_message := process_message(data, data_type, translator, config.trans_service,
                                                        model=config.model,
                                                        source_language=config.op_src_lang,
                                                        target_language=config.op_tgt_lang):
                    if processed_message[1]:
                        display_message(*processed_message, config.output_method)
                        if processed_message[0] != "[ERROR]":
                            break
                        else:
                            logger.error(processed_message[1])
                            return None
                    return None
                else:
                    break  # 不是聊天消息，跳过
            elif data_type == "clipboard":
                if processed_message := process_message(data, data_type, translator, config.trans_service,
                                                        model=config.model,
                                                        source_language=config.self_src_lang,
                                                        target_language=config.self_tgt_lang):
                    if type(processed_message) == str:
                        modify_clipboard(processed_message)
                        display_message("[INFO]", _("Chat messages translated, translation results in clipboard"),
                                        config.output_method)
                        return processed_message
                    elif type(processed_message) == tuple and processed_message[0] == "[ERROR]":
                        display_message(*processed_message, config.output_method)
                        return None
                    return None
                return None
            return None
        return None

    translator = Translator(api_key=config.api_key, api_url=config.api_url,
                            enable_optimization=config.enable_optimization,
                            traditional_api_key=config.traditional_api_key)

    init_display(config.output_method, main_window=main_interface_manager.main_window,
                   http_port=config.http_port, max_messages=config.max_messages,
                   always_on_top=config.always_on_top, callback=callback)

    init_processor(config.trans_sys_message, config.skip_src_lang, config.min_detect_len, config.glossary)

    monitor_thread = threading.Thread(
        target=monitor_log_file,
        args=(config.minecraft_log_folder, callback),
        kwargs={"use_high_version_fix": config.use_high_version_fix}
    )
    monitor_thread.daemon = True
    monitor_thread.start()

    if config.self_trans_enabled:
        clipboard_thread = threading.Thread(target=monitor_clipboard, args=(callback,))
        clipboard_thread.daemon = True
        clipboard_thread.start()


main_interface_manager = MainInterfaceManager(program_info, updater)
more_settings_manager = MoreSettingsManager(main_interface_manager.main_window, main_interface_manager.config)
main_interface_manager.create_main_window(start_translation=start_translation,
                                          more_settings=more_settings_manager.create_more_settings_window)
