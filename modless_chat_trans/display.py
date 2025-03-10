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

import pyttsx3
import threading
from modless_chat_trans.interface import ChatInterfaceManager
from modless_chat_trans.web_display import start_httpserver, httpserver_display


def initialization(output_method, **kwargs):
    if output_method == "Graphical":
        global chat_interface_manager
        chat_interface_manager = ChatInterfaceManager(main_window=kwargs["main_window"],
                                                      max_messages=kwargs["max_messages"],
                                                      always_on_top=kwargs["always_on_top"])
        chat_interface_manager.start()
    elif output_method == "Speech":
        global voice_engine
        voice_engine = pyttsx3.init()
    elif output_method == "Httpserver":
        start_httpserver_thread(kwargs["http_port"], kwargs["callback"])


def start_httpserver_thread(port, callback):
    server_thread = threading.Thread(target=start_httpserver, args=(port, callback))
    server_thread.daemon = True
    server_thread.start()


def _speech_display(message):
    voice_engine.say(message)
    voice_engine.runAndWait()


def display_message(name, message, output_method):
    """
    呈现消息

    :param name: 名称
    :param message: 消息内容
    :param output_method: 呈现方式，目前支持 graphical/speech/httpserver
    """

    if name:
        text = f"{name}: {message}"
    else:
        text = message

    if output_method == "Graphical":
        chat_interface_manager.display(name, message)
    elif output_method == "Speech":
        _speech_display(text)
    elif output_method == "Httpserver":
        httpserver_display(name, message)
    else:
        raise ValueError("Unsupported output method")
