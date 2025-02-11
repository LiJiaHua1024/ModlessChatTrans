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
import translators as ts
import json
import re

service_supported_languages = {
    "DeepL":['auto', 'ar', 'bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'et', 'fi', 'fr', 'hu', 'id', 'it', 'ja', 'ko',
             'lt', 'lv', 'nb', 'nl', 'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sv', 'tr', 'uk', 'zh'],
    "Bing":['auto', 'af', 'am', 'ar', 'as', 'az', 'ba', 'bg', 'bho', 'bn', 'bo', 'brx', 'bs', 'ca', 'cs', 'cy', 'da', 'de',
            'doi', 'dsb', 'dv', 'el', 'en', 'es', 'et', 'eu', 'fa', 'fi', 'fil', 'fj', 'fo', 'fr', 'fr-CA', 'ga',
            'gl', 'gom', 'gu', 'ha', 'he', 'hi', 'hne', 'hr', 'hsb', 'ht', 'hu', 'hy', 'id', 'ig', 'ikt', 'is', 'it',
            'iu', 'iu-Latn', 'ja', 'ka', 'kk', 'km', 'kmr', 'kn', 'ko', 'ks', 'ku', 'ky', 'ln', 'lo', 'lt', 'lug',
            'lv', 'lzh', 'mai', 'mg', 'mi', 'mk', 'ml', 'mn-Cyrl', 'mn-Mong', 'mr', 'ms', 'mt', 'mww', 'my', 'nb',
            'ne', 'nl', 'nso', 'nya', 'or', 'otq', 'pa', 'pl', 'prs', 'ps', 'pt', 'pt-PT', 'ro', 'ru', 'run', 'rw',
            'sd', 'si', 'sk', 'sl', 'sm', 'sn', 'so', 'sq', 'sr-Cyrl', 'sr-Latn', 'st', 'sv', 'sw', 'ta', 'te', 'th',
            'ti', 'tk', 'tlh-Latn', 'tn', 'to', 'tr', 'tt', 'ty', 'ug', 'uk', 'ur', 'uz', 'vi', 'xh', 'yo', 'yua',
            'yue', 'zh-Hans', 'zh-Hant', 'zu']
}


class Translator:
    def __init__(self, api_key=None, api_url=None, default_source_language=None,
                 default_target_language="zh-CN", enable_optimization=False):
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
        self.enable_optimization = enable_optimization

        # ts.preaccelerate_and_speedtest()

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

        if self.enable_optimization:
            # scene = "Hypixel Bedwars"
            system_prompt = (
                "You are a Minecraft-specific intelligent translation engine, "
                "focused on providing high-quality localization transformations "
                "in terms of cultural adaptation and language naturalization.\n"
                "\n"
                # f"Your translation scenario is: {scene}.\n"
                # "\n"
                "[Translation Guidelines]\n"
                "\n"
                "1. Cultural Adaptability: Identify culture-specific elements in the "
                "source text (memes, allusions, puns, etc.) and find culturally "
                "equivalent expressions in the target language.\n"
                "2. Language Modernization: Use the latest slang in the target language.\n"
                "3. Natural Language Processing:\n"
                "    - Maintain spoken sentence structures.\n"
                "    - Consider that player messages during gameplay will not be too "
                "long or have complex grammatical structures.\n"
                "    - Avoid formal language structures such as capitalization of "
                "initial letters/proper nouns and ending punctuation marks.\n"
                "    - Simulate human conversation characteristics (add appropriate "
                "filler words, reasonable repetition).\n"
                "\n"
                "[Output Specifications]\n"
                "\n"
                "Strictly follow the JSON structure below. Do not use Markdown code "
                "block markers:\n"
                "\n"
                "{\n"
                "  \"terms\": [\n"
                "    {\"term\": \"Original term\", \"meaning\": \"Definition\"} // "
                "Include game terms, slang, abbreviations, memes, puns, and other "
                "vocabulary requiring special handling.\n"
                "  ],\n"
                "  \"result\": \"Final translation result\" // Natural translation "
                "after cultural adaptation and colloquial processing.\n"
                "}"
            )

            if source_language:
                message = f"Translate this sentence from {source_language} to {target_language}: {text}"
            else:
                message = f"Translate this sentence to {target_language}: {text}"
        else:
            system_prompt = "You are a professional translation engine specializing in game translations."

            if source_language:
                message = (f"Translate from {source_language} to {target_language}. "
                           f"Do not translate player names, proper nouns, or garbled text. "
                           f"No explanations. No notes. Text: {text}")
            else:
                message = (f"Translate to {target_language}. "
                           f"Do not translate player names, proper nouns, or garbled text. "
                           f"No explanations. No notes. Text: {text}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "temperature": 0
        }

        response = requests.post(self.api_url, headers=headers, json=data)

        if response.status_code == 200:
            content_str = response.json().get("choices", [])[0].get("message", {}).get("content", "")
            if self.enable_optimization:
                try:
                    content_dict = json.loads(content_str)
                except json.JSONDecodeError:
                    try:
                        content_dict = json.loads(re.sub(r"^```json\s*([\s\S]*?)\s*```$", r"\1", content_str))
                    except json.JSONDecodeError:
                        return None

                translated_message = content_dict.get("result", None)
            else:
                translated_message = content_str

            return translated_message
        else:
            return None

    def deepl_translate(self, text, source_language=None, target_language=None):
        """
        使用 DeepL 翻译消息

        :param text: 要翻译的文字
        :param source_language: 源语言，不填则为self.default_source_language
        :param target_language: 目标语言，不填则为self.default_target_language
        :return: 翻译后的消息
        """

        source_language = source_language or self.default_source_language or "auto"
        target_language = target_language or self.default_target_language or "auto"

        if translated_message := ts.translate_text(text, translator="deepl",
                                                   from_language=source_language, to_language=target_language):
            return translated_message
        else:
            return None

    def bing_translate(self, text, source_language=None, target_language=None):
        """
        使用 Bing Translate 翻译消息

        :param text: 要翻译的文字
        :param source_language: 源语言，不填则为self.default_source_language
        :param target_language: 目标语言，不填则为self.default_target_language
        :return: 翻译后的消息
        """

        source_language = source_language or self.default_source_language or "auto"
        target_language = target_language or self.default_target_language or "auto"

        if translated_message := ts.translate_text(text, translator="bing",
                                                   from_language=source_language, to_language=target_language):
            return translated_message
        else:
            return None
