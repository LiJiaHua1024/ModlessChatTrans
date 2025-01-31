# Copyright (C) 2024 LiJiaHua1024
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

from modless_chat_trans.file_utils import read_config
from modless_chat_trans.i18n import set_language
set_language(read_config().interface_lang)

from modless_chat_trans.display import initialization, display_message
from modless_chat_trans.log_monitor import monitor_log_file
from modless_chat_trans.message_processor import process_message
from modless_chat_trans.translator import Translator
from modless_chat_trans.interface import ProgramInfo, InterfaceManager
from modless_chat_trans.clipboard_monitor import monitor_clipboard, modify_clipboard
from modless_chat_trans.i18n import _
from modless_chat_trans.updater import Updater


program_info = ProgramInfo(version="v2.0.0",
                           author="LiJiaHua1024",
                           email="minecraft_benli@163.com",
                           github="https://github.com/LiJiaHua1024/ModlessChatTrans",
                           license=("GNU General Public License v3.0", "https://www.gnu.org/licenses/gpl-3.0.html"))

updater = Updater(program_info.version, program_info.author, "ModlessChatTrans")
if new_version := updater.check_update():
    program_info.version += f" [New version available: {new_version}]"


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
                    display_message(*processed_message, config.output_method)
                    break
            elif data_type == "clipboard":
                if processed_message := process_message(data, data_type, translator, config.trans_service,
                                                        model=config.model,
                                                        source_language=config.self_src_lang,
                                                        target_language=config.self_tgt_lang):
                    modify_clipboard(processed_message)
                    display_message("[INFO]", _("Chat messages translated, translation results in clipboard"),
                                    config.output_method)
                    return processed_message

    translator = Translator(api_key=config.api_key, api_url=config.api_url)

    initialization(config.output_method, main_window=interface_manager.main_window,
                   http_port=config.http_port, max_messages=config.max_messages, always_on_top=config.always_on_top)

    monitor_thread = threading.Thread(target=monitor_log_file, args=(config.minecraft_log_folder, callback))
    monitor_thread.daemon = True
    monitor_thread.start()

    if config.self_trans_enabled:
        clipboard_thread = threading.Thread(target=monitor_clipboard, args=(callback,))
        clipboard_thread.daemon = True
        clipboard_thread.start()


interface_manager = InterfaceManager(program_info)
interface_manager.create_main_window(start_translation)
