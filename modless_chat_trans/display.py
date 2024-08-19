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

import customtkinter as ctk
import pyttsx3
import threading
from flask import Flask, render_template_string
from modless_chat_trans.i18n import _


def initialization(output_method, **kwargs):
    if output_method == "Graphical":
        start_gui_thread()
    elif output_method == "Speech":
        global voice_engine
        voice_engine = pyttsx3.init()
    elif output_method == "Httpserver":
        start_httpserver_thread(kwargs["http_port"])


def start_gui():
    global translation_result_box

    translation_display_window = ctk.CTk()
    translation_display_window.title(_("Translated Message"))
    translation_display_window.geometry("700x400")

    translation_result_box = ctk.CTkTextbox(translation_display_window, font=("SimSun", 20))
    translation_result_box.pack(expand=True, fill="both")
    translation_result_box.configure(state=ctk.DISABLED)

    translation_display_window.mainloop()


def start_gui_thread():
    gui_thread = threading.Thread(target=start_gui)
    gui_thread.daemon = True
    gui_thread.start()


def _graphical_display(message):
    translation_result_box.configure(state=ctk.NORMAL)
    translation_result_box.insert(ctk.END, message + "\n")
    translation_result_box.see(ctk.END)
    translation_result_box.configure(state=ctk.DISABLED)


def start_httpserver(port):
    global http_messages
    flask_app = Flask(__name__)
    http_messages = []

    @flask_app.route('/')
    def home():
        return render_template_string("""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>"""+_("Messages")+"""</title>
                        <meta http-equiv="refresh" content="1">
                    </head>
                    <body>
                        <h1>"""+_("Messages")+""":</h1>
                        <ul>
                        {% for message in messages %}
                            <li>{{ message }}</li>
                        {% endfor %}
                        </ul>
                    </body>
                    </html>
                """, messages=http_messages)

    flask_app.run(debug=False, host='0.0.0.0', port=port)


def start_httpserver_thread(port):
    server_thread = threading.Thread(target=start_httpserver, args=(port,))
    server_thread.daemon = True
    server_thread.start()


def _httpserver_display(message):
    global http_messages
    http_messages.append(message)


def _speech_display(message):
    voice_engine.say(message)
    voice_engine.runAndWait()


def display_message(message, output_method):
    """
    呈现消息

    :param message: 需要呈现的文字
    :param output_method: 呈现方式，目前支持 print（已弃用）/graphical/speech/httpserver
    """

    if output_method == "Graphical":
        if translation_result_box:
            _graphical_display(message)
    elif output_method == "Speech":
        _speech_display(message)
    elif output_method == "Httpserver":
        _httpserver_display(message)
    else:
        raise ValueError("Unsupported output method")
