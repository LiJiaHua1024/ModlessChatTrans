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

import time
import json
from flask import Flask, render_template, Response, request, jsonify
from datetime import datetime
from modless_chat_trans.i18n import _
from modless_chat_trans.file_utils import get_path
from modless_chat_trans.logger import logger

http_messages = []
sse_clients = []


def start_httpserver(port, callback):
    global http_messages, sse_clients
    logger.info(f"Starting HTTP server on port {port}")

    try:
        flask_app = Flask(__name__)
        flask_app.template_folder = get_path("templates")
        logger.debug(f"Template folder set to: {get_path('templates')}")

        http_messages = []
        sse_clients = []

        @flask_app.route('/')
        def home():
            logger.debug("Serving home page")
            return render_template('index.html', _=_)

        @flask_app.route('/send-message', methods=['POST'])
        def handle_user_input():
            try:
                data = request.json
                logger.debug(
                    f"Received message from web client: {data['message'][:30]}..." if len(data['message']) > 30 else
                    data['message'])
                translated = callback(data['message'], data_type="clipboard")
                logger.debug("Message translated successfully")
                return jsonify({'translated': translated})
            except Exception as e:
                logger.error(f"Error handling user input: {str(e)}")
                return jsonify({'error': str(e)}), 500

        @flask_app.route('/clear-messages', methods=['POST'])
        def clear_messages():
            try:
                global http_messages
                logger.debug("Clearing all messages")
                http_messages = []
                return jsonify({'success': True})
            except Exception as e:
                logger.error(f"Error clearing messages: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @flask_app.route('/stream')
        def stream():
            logger.debug("Client connected to SSE stream")

            def event_stream():
                global sse_clients, http_messages
                message_index = 0
                last_message_count = 0

                try:
                    logger.debug("Starting event stream for client")
                    while True:
                        time.sleep(1)
                        current_message_count = len(http_messages)

                        if current_message_count > last_message_count:
                            logger.debug(f"Sending {current_message_count - last_message_count} new messages to client")
                            while message_index < current_message_count:
                                message_tuple = http_messages[message_index]
                                name = message_tuple[0]
                                message = message_tuple[1]
                                timestamp = message_tuple[2]
                                duration = message_tuple[3]
                                info = message_tuple[4]

                                message_data = {
                                    "name": name,
                                    "message": message,
                                    "time": timestamp,  # 添加时间信息到JSON数据中
                                    "duration": duration,  # 耗时
                                    "glossary_match": info.get("glossary_match", False),
                                    "skip_src_lang": info.get("skip_src_lang", False),
                                    "cache_hit": info.get("cache_hit", False)
                                }

                                json_message = json.dumps(message_data, ensure_ascii=False)

                                yield f"data: {json_message}\n\n"

                                message_index += 1

                            last_message_count = current_message_count

                except GeneratorExit:
                    logger.debug("Client disconnected from event stream")

            return Response(event_stream(), mimetype="text/event-stream")

        logger.info(f"HTTP server starting on 0.0.0.0:{port}")
        flask_app.run(debug=False, host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {str(e)}")


def httpserver_display(name, message, duration, info):
    global http_messages
    try:
        current_time = datetime.now().strftime("%H:%M")
        logger.debug(f"Adding message from {name if name else 'System'} to HTTP server queue")
        http_messages.append((name, message, current_time, duration, info))
    except Exception as e:
        logger.error(f"Error adding message to HTTP server: {str(e)}")
