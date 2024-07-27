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

def process_decorator(function):
    """
    为process_message添加翻译步骤
    """

    def wrapper(input_data, translator, model=None, source_language=None, target_language=None):
        """
        处理日志文件中的一行（包括翻译）

        :param input_data: 需要处理的数据（可能是日志行或网络数据包）
        :param translator: Translator类的实例
        :param model: 模型名称
        :return: 处理完的消息
        """

        original_chat_message = function(input_data, data_type="log")

        translated_chat_message = ""
        if original_chat_message:
            translated_chat_message = translator.llm_translate(original_chat_message, model=model,
                                                               source_language=source_language,
                                                               target_language=target_language)
        return translated_chat_message

    return wrapper


@process_decorator
def process_message(data, data_type):
    """
    处理日志文件中的一行

    :param data: 需要处理的数据
    :param data_type: 数据的类型
    :return: 处理完的消息
    """
    if data_type == "log":
        if "[CHAT]" in data:
            chat_message = data.split("[CHAT]")[1].strip()
        # if "[GAME]" in line:
            # chat_message = line.split("[GAME]")[1].strip()
            return chat_message

    return None
