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


def initialization(output_method, **kwargs):
    if output_method == "print":
        pass
    if output_method == "graphical":
        print("Starting GUI...")
        start_gui_thread()
    elif output_method == "speech":
        global voice_engine
        voice_engine = pyttsx3.init()
    elif output_method == "httpserver":
        print("Starting HTTP server...")
        start_httpserver_thread(kwargs["http_port"])


def start_gui():
    global text_widget

    main_window = ctk.CTk()
    main_window.title("Translated Message")
    main_window.geometry("700x400")

    text_widget = ctk.CTkTextbox(main_window, font=("SimSun", 20))
    text_widget.pack(expand=True, fill="both")
    # test font
    text_widget.insert(ctk.END, "你好，世界！")
    text_widget.configure(state=ctk.DISABLED)

    main_window.mainloop()


def start_gui_thread():
    gui_thread = threading.Thread(target=start_gui)
    gui_thread.daemon = True
    gui_thread.start()


def _graphical_display(message):
    text_widget.configure(state=ctk.NORMAL)
    text_widget.insert(ctk.END, message + "\n")
    text_widget.see(ctk.END)
    text_widget.configure(state=ctk.DISABLED)


def start_httpserver(port):
    global http_messages
    flask_app = Flask(__name__)
    http_messages = []

    @flask_app.route('/')
    def home():
        return render_template_string('''
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Messages</title>
                        <meta http-equiv="refresh" content="1">
                    </head>
                    <body>
                        <h1>Messages:</h1>
                        <ul>
                        {% for message in messages %}
                            <li>{{ message }}</li>
                        {% endfor %}
                        </ul>
                    </body>
                    </html>
                ''', messages=http_messages)

    flask_app.run(debug=False, host='0.0.0.0', port=port)


def start_httpserver_thread(port):
    server_thread = threading.Thread(target=start_httpserver, args=(port, ))
    server_thread.daemon = True
    server_thread.start()
    print(f"HTTP server started on http://localhost:{port}")


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
    :param output_method: 呈现方式，目前支持print/graphical/speech
    """

    if output_method == "print":
        print(message)
    elif output_method == "graphical":
        if text_widget:
            _graphical_display(message)
    elif output_method == "speech":
        _speech_display(message)
    elif output_method == "httpserver":
        _httpserver_display(message)
    else:
        raise ValueError("Unsupported output method")
