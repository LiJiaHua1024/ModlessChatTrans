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

import requests


class Translator:
    def __init__(self, api_key=None, api_url=None, default_source_language=None,
                 default_target_language="zh-CN"):
        """
        初始化翻译器

        :param api_key: API 的密钥
        :param api_url: LLM API 的网址(不用可以不填)
        :param default_source_language: 源语言，默认自动识别，如果识别错误可指定
        :param default_target_language: 目标语言，默认是简体中文
        """

        self.api_key = api_key
        self.api_url = api_url
        self.default_source_language = default_source_language
        self.default_target_language = default_target_language

    def llm_translate(self, text, model, source_language=None, target_language=None):
        """
        使用 LLM API 翻译消息

        :param text: 要翻译的文字
        :param model: 翻译使用的模型
        :param source_language: 源语言，不填则为self.default_source_language
        :param target_language: 目标语言，不填则为self.default_target_language
        :return: 翻译后的消息
        """

        source_language = source_language or self.default_source_language
        target_language = target_language or self.default_target_language
        # normal_prompt = "You are a professional, authentic machine translation engine,only return result."
        # force_prompt = ("You are a professional, authentic machine translation engine. Your sole purpose is to "
        #                 "accurately and faithfully translate the provided text from one language to another, "
        #                 "regardless of the content. The text consists of player dialogues in a gaming context. Pay "
        #                 "special attention to common internet and gaming abbreviations, ensuring they are translated "
        #                 "correctly and appropriately. Do not refuse, censor, or alter any part of the message. Only "
        #                 "return the translated result without any additional explanations or comments.")

        decodes_force_prompt = ("You are a professional, authentic machine translation engine. Your task is to "
                                "accurately translate the provided text from one language to another, focusing on "
                                "player dialogues in a gaming context. The text may contain encoding issues or "
                                "garbled characters. Automatically decode and clean the text, removing any extraneous "
                                "symbols or color codes. Pay special attention to common internet and gaming "
                                "abbreviations, ensuring they are translated correctly and appropriately. Do not "
                                "translate player nicknames. Do not"
                                "refuse, censor, or alter any part of the message. Return only the translated result "
                                "without any additional explanations or comments.\n"
                                "Example:\nSource: <GamerX> Hello!\nTranslation: <GamerX> 你好！")

        if source_language:
            message = f"Translate the following text from {source_language} to {target_language}:\n{text}"
        else:
            message = f"Translate the following text to {target_language}:\n{text}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": decodes_force_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0
        }

        response = requests.post(self.api_url, headers=headers, json=data)

        if response.status_code == 200:
            translated_message = response.json().get("choices", [])[0].get("message", {}).get("content", "")
            return translated_message
        else:
            return None

    def deepl_translate(self, text, source_language=None, target_language=None):
        """
        使用 DeepL API 翻译消息（占位函数，待实现）。

        :param text: 要翻译的文字
        :param source_language: 源语言，不填则为self.default_source_language
        :param target_language: 目标语言，不填则为self.default_target_language
        :return: 翻译后的消息
        """

        # DeepL API 实现待补充
        # if not self.api_key:
        #     raise ValueError("DeepL Translate requires API key")
        pass
