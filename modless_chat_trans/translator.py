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

services = ["LLM", "DeepL", "Bing", "Google", "Yandex", "Alibaba", "Caiyun", "Youdao"]


def get_supported_languages(service):
    return sorted(ts.get_languages(service.lower()).keys())


class _LazyLanguageDict(dict):
    def __getitem__(self, key):
        if key not in self:
            try:
                lang_list = get_supported_languages(key)
                lang_list.insert(0, "auto")
            except Exception as e:
                lang_list = ["[ERROR]", str(e)]
            super().__setitem__(key, lang_list)
        return super().__getitem__(key)


service_supported_languages = _LazyLanguageDict()


class Translator:
    def __init__(self, api_key=None, api_url=None, default_source_language=None,
                 default_target_language="zh-CN", enable_optimization=False,
                 traditional_api_key=None):
        """
        初始化翻译器

        :param api_key: LLM API 的密钥
        :param api_url: LLM API 的网址(不用可以不填)
        :param default_source_language: 源语言，默认自动识别，如果识别错误可指定
        :param default_target_language: 目标语言，默认是简体中文
        :param enable_optimization: 是否启用翻译质量优化
        :param traditional_api_key: 传统翻译服务 API 的密钥
        """

        self.api_key = api_key
        self.api_url = api_url
        self.default_source_language = default_source_language
        self.default_target_language = default_target_language
        self.enable_optimization = enable_optimization
        self.traditional_api_key = traditional_api_key

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

    def traditional_translate(self, text, service, source_language=None, target_language=None):
        """
        使用传统翻译服务翻译消息

        :param text: 要翻译的文字
        :param service: 翻译服务
        :param source_language: 源语言，不填则为self.default_source_language
        :param target_language: 目标语言，不填则为self.default_target_language
        :return: 翻译后的消息
        """

        source_language = source_language or self.default_source_language
        target_language = target_language or self.default_target_language

        if self.traditional_api_key:
            service = service.lower()

            # DeepL API
            if service == "deepl":
                if self.traditional_api_key.endswith(":fx"):
                    url = "https://api-free.deepl.com/v2/translate"
                else:
                    url = "https://api.deepl.com/v2/translate"

                headers = {
                    "Authorization": f"DeepL-Auth-Key {self.traditional_api_key}"
                }
                data = {
                    "text": [text],
                    "target_lang": target_language.split("-")[0].upper(),
                }
                if source_language:
                    data["source_lang"] = source_language.split("-")[0].upper()

                response = requests.post(url, headers=headers, data=data)
                if response.status_code == 200:
                    return response.json()["translations"][0]["text"]
                return None

            # Google API
            elif service == "google":
                url = "https://translation.googleapis.com/language/translate/v2"
                params = {
                    "key": self.traditional_api_key,
                    "q": text,
                    "target": target_language.split("-")[0],
                }
                if source_language:
                    params["source"] = source_language.split("-")[0]

                response = requests.post(url, params=params)
                if response.status_code == 200:
                    return response.json()["data"]["translations"][0]["translatedText"]
                return None

            # Yandex API
            elif service == "yandex":
                url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
                headers = {
                    "Authorization": f"Api-Key {self.traditional_api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "texts": [text],
                    "targetLanguageCode": target_language.split("-")[0],
                }
                if source_language:
                    data["sourceLanguageCode"] = source_language.split("-")[0]

                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    return response.json()["translations"][0]["text"]
                return None

            # Alibaba (阿里云) API
            elif service == "alibaba":
                import time
                import uuid
                import hmac
                import base64
                import hashlib
                from urllib.parse import urlencode

                access_key_id, access_key_secret = self.traditional_api_key.split(":")

                url = "https://mt.cn-hangzhou.aliyuncs.com/"

                # 准备请求参数
                parameters = {
                    'AccessKeyId': access_key_id,
                    'Action': 'TranslateGeneral',
                    'Format': 'JSON',
                    'SignatureMethod': 'HMAC-SHA1',
                    'SignatureNonce': str(uuid.uuid4()),
                    'SignatureVersion': '1.0',
                    'SourceLanguage': source_language.split("-")[0] if source_language else "auto",
                    'SourceText': text,
                    'TargetLanguage': target_language.split("-")[0],
                    'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    'Version': '2018-10-12'
                }

                # 按照参数名称的字典顺序排序
                sorted_parameters = sorted(parameters.items(), key=lambda x: x[0])

                # 构造规范化请求字符串
                canonicalized_query_string = urlencode(sorted_parameters)

                # 构造待签名字符串
                string_to_sign = 'GET&%2F&' + urlencode(sorted_parameters).replace('&', '%26').replace('=', '%3D')

                # 计算签名
                h = hmac.new((access_key_secret + '&').encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
                signature = base64.b64encode(h.digest()).decode('utf-8')

                # 添加签名到参数中
                parameters['Signature'] = signature

                # 发送请求
                response = requests.get(url, params=parameters)

                if response.status_code == 200:
                    return response.json().get("Data", {}).get("Translated")
                return None

            # Caiyun (彩云小译) API
            elif service == "caiyun":
                url = "http://api.interpreter.caiyunai.com/v1/translator"
                headers = {
                    "Content-Type": "application/json",
                    "X-Authorization": f"token {self.traditional_api_key}"
                }
                payload = {
                    "source": [text],
                    "trans_type": f"{source_language.split('-')[0] if source_language else 'auto'}{target_language.split('-')[0]}"
                }

                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    return response.json()["target"][0]
                return None

            # Youdao (有道) API
            elif service == "youdao":
                import hashlib
                import time
                import uuid

                url = "https://openapi.youdao.com/api"
                app_key = self.traditional_api_key.split(":")[0]
                app_secret = self.traditional_api_key.split(":")[1]

                def encrypt(sign_str):
                    hash_algorithm = hashlib.sha256()
                    hash_algorithm.update(sign_str.encode('utf-8'))
                    return hash_algorithm.hexdigest()

                def truncate(q):
                    if q is None:
                        return None
                    size = len(q)
                    return q if size <= 20 else q[0:10] + str(size) + q[size - 10:size]

                salt = str(uuid.uuid1())
                curtime = str(int(time.time()))
                sign = encrypt(app_key + truncate(text) + salt + curtime + app_secret)

                data = {
                    'q': text,
                    'from': source_language.split("-")[0] if source_language else "auto",
                    'to': target_language.split("-")[0],
                    'appKey': app_key,
                    'salt': salt,
                    'sign': sign,
                    'signType': "v3",
                    'curtime': curtime,
                }

                response = requests.post(url, data=data)
                if response.status_code == 200:
                    return response.json()["translation"][0]
                return None

            # Bing/Microsoft API
            elif service == "bing":
                endpoint = "https://api.cognitive.microsofttranslator.com/translate"
                headers = {
                    'Ocp-Apim-Subscription-Key': self.traditional_api_key,
                    'Ocp-Apim-Subscription-Region': 'global',
                    'Content-type': 'application/json'
                }
                params = {
                    'api-version': '3.0',
                    'to': target_language.split("-")[0]
                }
                if source_language:
                    params['from'] = source_language.split("-")[0]

                body = [{'text': text}]
                response = requests.post(endpoint, headers=headers, params=params, json=body)
                if response.status_code == 200:
                    return response.json()[0]["translations"][0]["text"]
                return None

            else:
                raise ValueError(f"Unsupported translation service: {service}")
        else:
            if translated_message := ts.translate_text(text, translator=service.lower(),
                                                       from_language=source_language, to_language=target_language):
                return translated_message
            else:
                return None
