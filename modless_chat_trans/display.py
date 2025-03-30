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

import pyttsx3
import threading
from modless_chat_trans.interface import ChatInterfaceManager
from modless_chat_trans.web_display import start_httpserver, httpserver_display
from modless_chat_trans.logger import logger


def initialization(output_method, **kwargs):
    logger.info(f"Initializing display with output method: {output_method}")
    try:
        if output_method == "Graphical":
            global chat_interface_manager
            logger.debug(f"Creating graphical interface with max_messages={kwargs.get('max_messages')}")
            chat_interface_manager = ChatInterfaceManager(main_window=kwargs["main_window"],
                                                          max_messages=kwargs["max_messages"],
                                                          always_on_top=kwargs["always_on_top"])
            chat_interface_manager.start()
            logger.info("Graphical chat interface started successfully")
        elif output_method == "Speech":
            global voice_engine
            logger.debug("Initializing speech engine")
            voice_engine = pyttsx3.init()
            logger.info("Speech engine initialized successfully")
        elif output_method == "Httpserver":
            logger.debug(f"Starting HTTP server on port: {kwargs.get('http_port')}")
            start_httpserver_thread(kwargs["http_port"], kwargs["callback"])
            logger.info(f"HTTP server started on port {kwargs.get('http_port')}")
        else:
            logger.error(f"Unsupported output method: {output_method}")
    except Exception as e:
        logger.error(f"Display initialization failed: {str(e)}")
        raise e


def start_httpserver_thread(port, callback):
    try:
        server_thread = threading.Thread(target=start_httpserver, args=(port, callback))
        server_thread.daemon = True
        server_thread.start()
    except Exception as e:
        logger.error(f"Failed to start HTTP server thread: {str(e)}")
        raise e


def _speech_display(message):
    try:
        logger.debug(f"Speaking message: {message[:30]}..." if len(message) > 30 else message)
        voice_engine.say(message)
        voice_engine.runAndWait()
        logger.debug("Message spoken successfully")
    except Exception as e:
        logger.error(f"Error in speech display: {str(e)}")
        raise e


def display_message(name, message, output_method):
    """
    呈现消息

    :param name: 名称
    :param message: 消息内容
    :param output_method: 呈现方式，目前支持 graphical/speech/httpserver
    """
    try:
        logger.debug(f"Displaying message from '{name if name else 'System'}' using {output_method}")

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
            error_msg = f"Unsupported output method: {output_method}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Error displaying message: {str(e)}")
        raise
