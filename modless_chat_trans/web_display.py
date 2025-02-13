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

import time
import json
from flask import Flask, render_template, Response
from modless_chat_trans.i18n import _
from modless_chat_trans.file_utils import get_path

http_messages = []
sse_clients = []


def start_httpserver(port):
    global http_messages, sse_clients
    flask_app = Flask(__name__)
    flask_app.template_folder = get_path("templates")
    http_messages = []
    sse_clients = []

    @flask_app.route('/')
    def home():
        return render_template('index.html', _=_)

    @flask_app.route('/stream')
    def stream():
        def event_stream():
            global sse_clients, http_messages
            message_index = 0
            last_message_count = 0

            try:
                while True:
                    time.sleep(1)
                    current_message_count = len(http_messages)
                    if current_message_count > last_message_count:
                        while message_index < current_message_count:
                            message_tuple = http_messages[message_index]
                            name = message_tuple[0]
                            message = message_tuple[1]

                            message_data = {
                                "name": name,
                                "message": message
                            }
                            json_message = json.dumps(message_data, ensure_ascii=False)

                            yield f"data: {json_message}\n\n"

                            message_index += 1

                        last_message_count = current_message_count

            except GeneratorExit:
                pass

        return Response(event_stream(), mimetype="text/event-stream")

    flask_app.run(debug=False, host='0.0.0.0', port=port)


def httpserver_display(name, message):
    global http_messages
    http_messages.append((name, message))
