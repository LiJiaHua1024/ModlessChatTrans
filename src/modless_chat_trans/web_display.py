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
import threading
from collections import deque
from itertools import count
from flask import Flask, render_template, Response, request, jsonify
from datetime import datetime
from modless_chat_trans.i18n import _
from modless_chat_trans.file_utils import get_path
from modless_chat_trans.logger import logger

http_messages = deque()
messages_by_id = {}
message_condition = threading.Condition()
message_id_counter = count(1)
MAX_HTTP_MESSAGES = 2000
clear_revision = 0
sse_clients = []


def start_httpserver_thread(**kwargs):
    """启动HTTP服务器线程"""
    try:
        server_thread = threading.Thread(
            target=start_httpserver,
            args=(kwargs["http_port"], kwargs["callback"], kwargs.get("tts_engine"))
        )
        server_thread.daemon = True
        server_thread.start()
        logger.info(f"HTTP server thread started on port {kwargs['http_port']}")
    except Exception as e:
        logger.error(f"Failed to start HTTP server thread: {str(e)}")
        raise e


def start_httpserver(port, callback, tts_engine=None):
    global http_messages, messages_by_id, message_id_counter, clear_revision, sse_clients
    logger.info(f"Starting HTTP server on port {port}")

    try:
        template_dir = get_path("templates")
        static_dir = get_path("static")

        # 同时指定模板文件夹和静态文件夹
        flask_app = Flask(
            __name__,
            template_folder=template_dir,
            static_folder=static_dir
        )

        logger.debug(f"Template folder set to: {template_dir}")
        logger.debug(f"Static folder set to: {static_dir}")

        with message_condition:
            http_messages.clear()
            messages_by_id.clear()
            message_id_counter = count(1)
            clear_revision = 0
        sse_clients = []

        @flask_app.route('/')
        def home():
            theme_name = request.args.get('theme', 'base')
            logger.debug(f"Serving home page with theme: {theme_name}")

            # 将主题对应的CSS文件名传递给模板
            # 我们约定CSS文件名和主题名一致（例如 theme=material -> material.css）
            return render_template('index.html', _=_, theme_css=theme_name)

        @flask_app.route('/send-message', methods=['POST'])
        def handle_user_input():
            try:
                data = request.json
                preview = data['message']
                rage_mode = data.get('rage_mode', False)
                logger.debug(
                    f"Received message from web client (Rage Mode: {rage_mode}): "
                    f"{preview[:30]}..." if len(preview) > 30 else preview
                )
                translated = callback(data['message'], data_type="webui", rage_mode=rage_mode)
                logger.debug("Message translated successfully")
                return jsonify({'translated': translated})
            except Exception as e:
                logger.error(f"Error handling user input: {str(e)}")
                return jsonify({'error': str(e)}), 500

        @flask_app.route('/clear-messages', methods=['POST'])
        def clear_messages():
            global http_messages, messages_by_id, message_id_counter, clear_revision
            try:
                with message_condition:
                    http_messages.clear()
                    messages_by_id.clear()
                    message_id_counter = count(1)
                    clear_revision += 1
                    message_condition.notify_all()
                logger.debug("Cleared all messages from server queue")
                return jsonify({'success': True})
            except Exception as e:
                logger.error(f"Error clearing messages: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @flask_app.route('/read-aloud', methods=['POST'])
        def read_aloud():
            if tts_engine is None:
                return jsonify({'success': False, 'error': 'TTS engine is not available'}), 503
            try:
                data = request.json
                text = data.get('text', '')
                if not text:
                    return jsonify({'success': False, 'error': 'Empty text'}), 400
                    
                target_lang = getattr(tts_engine._config, 'target_language', '') # fallback if possible
                tts_engine.interrupt_and_read(text, target_lang)
                return jsonify({'success': True})
            except Exception as e:
                logger.error(f"Error in /read-aloud: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @flask_app.route('/stream')
        def stream():
            logger.debug("Client connected to SSE stream")

            # 在生成器外部提前获取请求数据,避免请求上下文失效
            last_event_id_header = request.headers.get('Last-Event-ID')
            last_event_id_param = request.args.get('last_event_id')

            def event_stream(last_event_id_header, last_event_id_param):
                retry_timeout_ms = 3000
                yield f"retry: {retry_timeout_ms}\n\n"

                heartbeat_interval = 15
                last_heartbeat_sent = time.time()

                last_event_id = None

                for candidate in (last_event_id_header, last_event_id_param):
                    if candidate:
                        try:
                            last_event_id = int(candidate)
                            break
                        except ValueError:
                            continue

                with message_condition:
                    current_clear_revision = clear_revision
                    if http_messages:
                        lowest_available_id = http_messages[0]['id']
                    else:
                        lowest_available_id = None

                if last_event_id is None:
                    if lowest_available_id is not None:
                        next_event_id = lowest_available_id
                    else:
                        next_event_id = 1
                else:
                    if lowest_available_id is not None and last_event_id + 1 < lowest_available_id:
                        next_event_id = lowest_available_id
                    else:
                        next_event_id = last_event_id + 1

                try:
                    while True:
                        send_clear_signal = False
                        new_messages = []

                        with message_condition:
                            if clear_revision != current_clear_revision:
                                current_clear_revision = clear_revision
                                send_clear_signal = True
                                next_event_id = http_messages[0]['id'] if http_messages else 1

                            while True:
                                if http_messages and next_event_id < http_messages[0]['id']:
                                    next_event_id = http_messages[0]['id']

                                message = messages_by_id.get(next_event_id)
                                if not message:
                                    break
                                # 跳过 pending slot，等待 fill_slot 完成后继续
                                if message.get('pending'):
                                    if time.time() - message.get('created_at', 0) > 10.0:
                                        logger.warning(f"Pending message slot {next_event_id} timed out. Skipping.")
                                        message['pending'] = False
                                        message['message'] = ""
                                    else:
                                        break

                                next_event_id = message['id'] + 1
                                # 跳过被过滤的空消息（slot 已 fill 但无内容）
                                if not message.get('message'):
                                    continue

                                new_messages.append(message)

                            if not send_clear_signal and not new_messages:
                                message_condition.wait(timeout=heartbeat_interval)

                        if send_clear_signal:
                            yield 'data: {"clear": true}\n\n'
                            last_heartbeat_sent = time.time()

                        if new_messages:
                            for message in new_messages:
                                info_payload = message.get('info') or {}
                                message_data = {
                                    "id": message['id'],
                                    "name": message['name'],
                                    "message": message['message'],
                                    "time": message['time'],
                                    "duration": message['duration'],
                                    "glossary_match": info_payload.get("glossary_match", False),
                                    "skip_src_lang": info_payload.get("skip_src_lang", False),
                                    "cache_hit": info_payload.get("cache_hit", False),
                                    "usage": info_payload.get("usage"),
                                    "original": message.get("original"),
                                    "send_translation_complete": info_payload.get("send_translation_complete", False)
                                }
                                json_message = json.dumps(message_data, ensure_ascii=False)
                                yield f"id: {message['id']}\n"
                                yield f"data: {json_message}\n\n"
                            last_heartbeat_sent = time.time()

                        if time.time() - last_heartbeat_sent >= heartbeat_interval:
                            heartbeat_payload = json.dumps({"ts": time.time()})
                            yield "event: heartbeat\n"
                            yield f"data: {heartbeat_payload}\n\n"
                            last_heartbeat_sent = time.time()

                except GeneratorExit:
                    logger.debug("Client disconnected from event stream")
                except Exception as e:
                    logger.error(f"SSE stream error: {str(e)}")

            response = Response(event_stream(last_event_id_header, last_event_id_param), mimetype="text/event-stream")
            response.headers["Cache-Control"] = "no-cache"
            response.headers["X-Accel-Buffering"] = "no"
            response.headers["Connection"] = "keep-alive"
            return response

        logger.info(f"HTTP server starting on 0.0.0.0:{port}")
        flask_app.run(debug=False, host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {str(e)}")


def display_message(name, message, info, duration=None, original=None):
    """
    呼现消息到Web页面

    :param name: 名称
    :param message: 消息内容
    :param info: 相关信息（如是否命中缓存、消耗token等）
    :param duration: 消息处理耗时（秒）
    :param original: 原文内容（可选）
    """
    global http_messages, messages_by_id, message_id_counter

    if duration is not None:
        if duration < 0.001:
            duration = "instant"
        elif duration < 1:
            duration = f"{round(duration * 1000)}ms"
        else:
            duration = f"{round(duration, 2)}s"

    try:
        current_time = datetime.now().strftime("%H:%M")
        info_payload = dict(info) if isinstance(info, dict) else {}
        message_id = next(message_id_counter)
        message_record = {
            "id": message_id,
            "name": name,
            "message": message,
            "time": current_time,
            "duration": duration,
            "info": info_payload,
            "original": original
        }

        with message_condition:
            http_messages.append(message_record)
            messages_by_id[message_id] = message_record

            if len(http_messages) > MAX_HTTP_MESSAGES:
                removed = http_messages.popleft()
                messages_by_id.pop(removed['id'], None)

            message_condition.notify_all()

        logger.debug(f"Adding message from {name if name else 'System'} to HTTP server queue")
    except Exception as e:
        logger.error(f"Error adding message to HTTP server: {str(e)}")


def allocate_slot(name="", arrival_time=None):
    """
    预分配一个带固定序号的展示 slot，保证并发翻译时显示顺序正确。

    :param name: 发送者名（可为空）
    :param arrival_time: 行到达时刻（epoch）
    :return: message_id (int)
    """
    global http_messages, messages_by_id, message_id_counter

    current_time = datetime.now().strftime("%H:%M")
    message_id = next(message_id_counter)

    record = {
        "id": message_id,
        "name": name,
        "message": None,
        "time": current_time,
        "duration": None,
        "info": {},
        "pending": True,
        "created_at": time.time(),
    }

    with message_condition:
        http_messages.append(record)
        messages_by_id[message_id] = record

        if len(http_messages) > MAX_HTTP_MESSAGES:
            removed = http_messages.popleft()
            messages_by_id.pop(removed['id'], None)

        message_condition.notify_all()

    logger.debug(f"Slot allocated: id={message_id} name={name or 'System'}")
    return message_id


def fill_slot(message_id: int, name: str, message: str, info: dict, duration=None, original=None):
    """
    填充已预分配的 slot。若 slot 已被淘汰则降级为 display_message。

    :param message_id: allocate_slot() 返回的 id
    :param name: 发送者名
    :param message: 译文
    :param info: 相关信息字典
    :param duration: 处理耗时（秒）
    :param original: 原文内容（可选）
    """
    global http_messages, messages_by_id

    if duration is not None:
        if duration < 0.001:
            duration_str = "instant"
        elif duration < 1:
            duration_str = f"{round(duration * 1000)}ms"
        else:
            duration_str = f"{round(duration, 2)}s"
    else:
        duration_str = None

    info_payload = dict(info) if isinstance(info, dict) else {}

    with message_condition:
        record = messages_by_id.get(message_id)
        if record is None:
            logger.warning(f"fill_slot: id={message_id} not found, falling back to display_message")
            display_message(name, message, info, duration, original)
            return

        record["name"] = name
        record["message"] = message
        record["duration"] = duration_str
        record["info"] = info_payload
        record["pending"] = False
        record["original"] = original
        message_condition.notify_all()

    logger.debug(f"Slot filled: id={message_id} name={name or 'System'} msg={message[:30] if message else ''}")
