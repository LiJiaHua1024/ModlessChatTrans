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

import requests
import json
import re
import importlib
from modless_chat_trans.logger import logger
from modless_chat_trans.file_utils import read_config, save_config

# 新增支持的 LLM 服务商
LLM_PROVIDERS = ["OpenAI", "Claude", "Gemini", "DeepSeek"]


_PENDING_TOKENS = 0
_SAVE_THRESHOLD = 5000   # 每累计5000 token 就落盘


def flush_pending_tokens():
    """将内存中待处理的 tokens 写入配置文件"""
    global _PENDING_TOKENS
    if _PENDING_TOKENS > 0:
        try:
            logger.info(f"Flushing {_PENDING_TOKENS} pending tokens to config.")
            conf = read_config()
            save_config(total_tokens=getattr(conf, "total_tokens", 0) + _PENDING_TOKENS)
        except Exception as e:
            logger.warning(f"Failed to flush pending tokens: {e}")
        finally:
            _PENDING_TOKENS = 0


# 所有可用翻译服务列表（LLM + 传统翻译服务）
services = LLM_PROVIDERS + [
    "DeepL", "Bing", "Google", "Yandex", "Alibaba", "Caiyun", "Youdao", "Sogou", "Iflyrec"
]


class LazyTranslatorModule:
    def __init__(self):
        self._module = None

    def _ensure_module_loaded(self):
        if self._module is None:
            logger.debug("Lazily importing 'translators' library now...")
            try:
                self._module = importlib.import_module("translators")
                # logger.info("Running pre-acceleration for 'translators' library...")
                # self._module.preaccelerate_and_speedtest()
            except ImportError as e:
                logger.error(f"Failed to import 'translators' library: {e}")
                raise
            logger.info("'translators' library imported successfully.")

    def __getattr__(self, name):
        self._ensure_module_loaded()
        if self._module:
            return getattr(self._module, name)
        raise RuntimeError(f"Lazy loading of 'translators' failed.")


ts = LazyTranslatorModule()


def get_supported_languages(service):
    return sorted(ts.get_languages(service.lower()).keys())


class _LazyLanguageDict(dict):
    def __getitem__(self, key):
        if key not in self:
            try:
                lang_list = get_supported_languages(key)
                lang_list.insert(0, "auto")
            except Exception as e:
                logger.error(f"Failed to get supported languages for {key}: {str(e)}")
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

        logger.info(f"Initialized Translator with optimization {'enabled' if enable_optimization else 'disabled'}")

    def llm_translate(self, text, model, provider="OpenAI", source_language=None, target_language=None):
        """
        使用 LLM API 翻译消息

        :param text: 要翻译的文字
        :param model: 翻译使用的模型
        :param provider: LLM 提供商 (OpenAI / Claude / Gemini / DeepSeek)
        :param source_language: 源语言，不填则为self.default_source_language
        :param target_language: 目标语言，不填则为self.default_target_language
        :return: 包含翻译结果和token使用信息的字典，格式为:
                 {"result": "翻译结果", "usage": {"prompt_tokens": x, "completion_tokens": y, "total_tokens": z}}
                 失败时返回 None
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
                "4. Minecraft Formatting Codes: Minecraft formatting codes (e.g., `§l`, "
                "`§c`, `§1`, `§k`) must be preserved exactly as they appear in the "
                "source text. These codes should not be translated, modified, or "
                "removed. They are instructions for text display, not content to be "
                "translated.\n"
                "\n"
                "[Output Specifications]\n"
                "\n"
                "Strictly follow the JSON structure below. Your entire response MUST be "
                "*only* this JSON object. Do not use Markdown code block markers, and "
                "absolutely do not add any introductory text, concluding remarks, "
                "explanations, apologies, or any other content outside of the "
                "specified JSON structure.\n"
                "\n"
                "{\n"
                '  "terms": [\n'
                '    {"term": "Original term", "meaning": "Definition"} // '
                "Include game terms, slang, abbreviations, memes, puns, and other "
                "vocabulary requiring special handling.\n"
                "  ],\n"
                '  "result": "Final translation result" // Natural translation '
                "after cultural adaptation and colloquial processing.\n"
                "}"
            )

            if source_language:
                message = f"Translate this sentence from {source_language} to {target_language}: {text}"
            else:
                message = f"Translate this sentence to {target_language}: {text}"
        else:
            system_prompt = (
                "You are a top-tier game localization expert, specializing in providing "
                "high-quality, stylistically natural real-time chat translations for "
                "the Minecraft community.\n"
                "\n"
                "[Translation Guidelines]\n"
                "\n"
                "1. Style and Context: Use colloquial and internet slang that is "
                "natural within the target language's player community. Avoid stiff, "
                "formal language. Sentences are often short and simple.\n"
                "2. Formatting Code Preservation (CRITICAL): You MUST completely "
                "preserve all Minecraft formatting codes (e.g., `§c`, `§l`). These "
                "codes must NEVER be translated, modified, or removed.\n"
                "3. Proper Nouns and Player Names: Do not translate player IDs, "
                "server names, or non-standard game terms without a widely accepted "
                "translation.\n"
                "4. Untranslatable Content: For meaningless keyboard mashing (e.g., "
                "\"asdasd\") or garbled text, keep the original text as is.\n"
                "\n"
                "[Output Requirement]\n"
                "\n"
                "Your response MUST ONLY contain the final translated text. Do not "
                "add any prefixes, suffixes, explanations, or notes."
            )

            # User Prompt 采用 XML 风格标签
            if source_language:
                message = (
                    f"Translate the following text from {source_language} to {target_language}.\n\n"
                    f"<text_to_translate>\n"
                    f"{text}\n"
                    f"</text_to_translate>"
                )
            else:
                message = (
                    f"Translate the following text to {target_language}.\n\n"
                    f"<text_to_translate>\n"
                    f"{text}\n"
                    f"</text_to_translate>"
                )

        # 根据不同提供商组织请求
        if provider == "OpenAI" or provider == "DeepSeek":
            # OpenAI/DeepSeek 接口基本兼容
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

        elif provider == "Claude":
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            data = {
                "model": model,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": message}
                ],
                "temperature": 0
            }
            response = requests.post(self.api_url, headers=headers, json=data)

        elif provider == "Gemini":
            # Gemini API 规则：/v1beta/models/{model}:generateContent?key=KEY
            # 允许用户提供完整 URL，或仅提供基础 host。若未提供则使用官方默认 host。

            if self.api_url:  # 用户自定义
                if "/models/" in self.api_url:  # 已包含模型段
                    base_url = self.api_url.rstrip("?")  # 移除可能的结尾 ?
                else:  # 仅提供 host，需拼接 models 段
                    base_url = f"{self.api_url.rstrip('/')}/models/{model}:generateContent"
            else:
                # 默认 Google host
                base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

            # 拼接 API Key
            separator = "&" if "?" in base_url else "?"
            url = f"{base_url}{separator}key={self.api_key}"

            headers = {
                "Content-Type": "application/json"
            }
            data = {
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": message}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0
                }
            }
            response = requests.post(url, headers=headers, json=data)

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        if response.status_code == 200:
            response_data = response.json()

            # 根据不同提供商解析响应
            if provider in ("OpenAI", "DeepSeek"):
                content_str = (
                    response_data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                usage_info = response_data.get("usage", {})

            elif provider == "Claude":
                # Claude 将内容放在 content 列表中，每项包含 type 与 text
                content_items = response_data.get("content", [])
                content_str = "".join(item.get("text", "") for item in content_items)
                if raw_usage := response_data.get("usage", {}):
                    pt = raw_usage.get("input_tokens", 0)
                    ct = raw_usage.get("output_tokens", 0)
                    usage_info = {
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "total_tokens": pt + ct
                    }
                else:
                    usage_info = {}

            elif provider == "Gemini":
                candidates = response_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    content_str = "".join(part.get("text", "") for part in parts)
                else:
                    content_str = ""
                if raw_usage := response_data.get("usageMetadata", {}):
                    usage_info = {
                        "prompt_tokens": raw_usage.get("promptTokenCount", 0),
                        "completion_tokens": raw_usage.get("candidatesTokenCount", 0),
                        "total_tokens": raw_usage.get("totalTokenCount", 0)
                    }
                else:
                    usage_info = {}
            else:
                content_str = ""
                usage_info = {}

            if self.enable_optimization:
                try:
                    content_dict = json.loads(content_str)
                except json.JSONDecodeError as e1:
                    logger.info(f"Initial JSON parsing failed ({e1}), attempting to clean and retry...")

                    try:
                        content_dict = json.loads(re.sub(r"^```json\s*([\s\S]*?)\s*```$", r"\1", content_str))
                    except json.JSONDecodeError as e2:
                        logger.warning("Failed to parse optimized translation JSON even after cleaning")
                        raise ValueError("Failed to parse optimized translation JSON") from e2

                translated_message = content_dict.get("result", None)
            else:
                translated_message = content_str

            # 更新累计 token 使用量
            if usage_info and usage_info.get("total_tokens", None):
                try:
                    global _PENDING_TOKENS
                    _PENDING_TOKENS += usage_info["total_tokens"]

                    if _PENDING_TOKENS >= _SAVE_THRESHOLD:
                        flush_pending_tokens()
                except Exception as e:
                    # 避免因为读取或写入配置失败阻止翻译结果返回
                    logger.warning(f"Failed to update total token usage: {e}")

            return {
                "result": translated_message,
                "usage": usage_info
            }
        else:
            logger.error(f"LLM translation failed ({provider}): {response.status_code} - {response.text}")
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
