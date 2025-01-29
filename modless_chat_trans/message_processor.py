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
from json import JSONDecodeError
from requests.exceptions import HTTPError
from modless_chat_trans.i18n import _


def process_decorator(function):
    """
    为process_message添加翻译步骤
    """

    def wrapper(data, data_type, translator, translation_service,
                model=None, source_language=None, target_language=None):
        """
        处理日志文件中的一行（包括翻译）

        :param data: 需要处理的数据
        :param data_type: 数据类型
        :param translator: Translator类的实例
        :param translation_service: 翻译服务
        :param model: 模型名称
        :param source_language: 源语言
        :param target_language: 目标语言
        :return: 元组 (玩家名称, 消息内容) 或 消息内容
        """

        name, original_chat_message = function(data, data_type)
        translated_chat_message: str = ""
        if original_chat_message:
            try:
                if translation_service == "LLM":
                    translated_chat_message = translator.llm_translate(original_chat_message, model=model,
                                                                       source_language=source_language,
                                                                       target_language=target_language)
                elif translation_service == "Bing":
                    translated_chat_message = translator.bing_translate(original_chat_message,
                                                                        source_language=source_language,
                                                                        target_language=target_language)
                elif translation_service == "DeepL":
                    translated_chat_message = translator.deepl_translate(original_chat_message,
                                                                         source_language=source_language,
                                                                         target_language=target_language)
            except HTTPError as http_err:
                response = getattr(http_err, "response", None)
                if response:
                    if response.status_code == 429:
                        # 请求过多
                        return "[ERROR]", _("Translation failed: Too many requests. Please try again later.")
                    elif 500 <= response.status_code < 600:
                        # 服务器错误
                        return "[ERROR]", _("Translation failed: Server error. Please try again later.")
                    else:
                        # 其他 HTTP 错误
                        return "[ERROR]", _("Translation failed: HTTP error occurred.")
                else:
                    # 无法获取响应对象，可能是网络问题
                    return "[ERROR]", _("Translation failed: Network issue or HTTP error occurred.")
            except JSONDecodeError:
                # JSON 解码错误，可能是网络问题或服务器返回了非 JSON 数据
                return "[ERROR]", _("Translation failed: Invalid response from server. Please check your network connection.")
            except Exception as e:
                # 捕获其他未知错误
                return "[ERROR]", f"{_('Translation failed, error:')} {e}"

            if name:
                return name, translated_chat_message
            if data_type == "clipboard":
                return translated_chat_message
            return "", translated_chat_message

    return wrapper


@process_decorator
def process_message(data, data_type):
    """
    处理日志文件中的一行

    :param data: 需要处理的数据
    :param data_type: 数据类型
    :return: 元组 (玩家名称, 聊天内容)
    """

    chat_message: str = ""
    if data_type == "log":
        if "[CHAT]" in data:
            chat_message = data.split("[CHAT]")[1].strip()
    elif data_type == "clipboard":
        return "", data
    else:
        return "", ""

    if chat_message.startswith("<"):
        name, text = chat_message[1:].split(">", 1)
    else:  # Hypixel Chat
        if ":" not in chat_message:
            return "", chat_message.strip()

        name, text = chat_message.split(":", 1)

    name = name.strip()
    text = text.strip()

    return name, text
