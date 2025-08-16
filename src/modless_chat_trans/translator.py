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
import lazy_loader as lazy
from modless_chat_trans.logger import logger
from modless_chat_trans.config import ServiceType

# 新增支持的 LLM 服务商
LLM_PROVIDERS_PREFIXES = {
    "OpenAI": "openai/",
    "Anthropic": "anthropic/",
    "DeepSeek": "deepseek/",
    "Meta Llama": "meta_llama/",
    "Azure": "azure/",
    "Amazon SageMaker": "sagemaker/",
    "Amazon Bedrock": "bedrock/",
    "Google Vertex AI": "vertex_ai/",
    "Gemini": "gemini/",
    "Hugging Face": "huggingface/",
    "Mistral AI": "mistral/",
    "IBM watsonx": "watson/",
    "NVIDIA NIM": "nvidia_nim/",
    "xAI": "xai/",
    "Moonshot AI": "moonshot/",
    "LM Studio": "lm_studio/",
    "Volcengine": "volcengine/",
    "Groq": "groq/",
    "vLLM": "hosted_vllm/",
    "Github": "github/",
    "Github Copilot": "github_copilot/",
    "Together AI": "together_ai/",
    "OpenRouter": "openrouter/"
}

LLM_PROVIDERS = list(LLM_PROVIDERS_PREFIXES.keys())

# _PENDING_TOKENS = 0
# _SAVE_THRESHOLD = 5000  # 每累计5000 token 就落盘
#
#
# def flush_pending_tokens():
#     """将内存中待处理的 tokens 写入配置文件"""
#     global _PENDING_TOKENS
#     if _PENDING_TOKENS > 0:
#         try:
#             logger.info(f"Flushing {_PENDING_TOKENS} pending tokens to config.")
#             conf = read_config()
#             save_config(total_tokens=getattr(conf, "total_tokens", 0) + _PENDING_TOKENS)
#         except Exception as e:
#             logger.warning(f"Failed to flush pending tokens: {e}")
#         finally:
#             _PENDING_TOKENS = 0


# 所有可用翻译服务列表（LLM + 传统翻译服务）
TRADITIONAL_SERVICES = [
    "DeepL", "Bing", "Google", "Yandex", "Alibaba", "Caiyun", "Youdao", "Sogou", "Iflyrec"
]
services = LLM_PROVIDERS + TRADITIONAL_SERVICES

ts = lazy.load("translators")
litellm = lazy.load("litellm")


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
    def __init__(self, translation_service_config):
        """
        初始化 Translator 类, 提供多种翻译相关选项及服务参数

        :param translation_service_config: config.TranslationServiceConfig
        """

        self.translation_service_config = translation_service_config

        logger.info(f"Initialized Translator")

    def translate(self, text, source_language, target_language):
        if self.translation_service_config.service_type == ServiceType.LLM:
            result = self.llm_translate(
                text,
                self.translation_service_config.llm.model,
                source_language,
                target_language,
                self.translation_service_config.llm.provider
            )
            return result
        elif self.translation_service_config.service_type == ServiceType.TRADITIONAL:
            if translation := self.traditional_translate(
                    text,
                    self.translation_service_config.traditional.provider,
                    source_language,
                    target_language
            ):
                return {"result": translation, "usage": None}
            else:
                return None

    def llm_translate(self, text, model, source_language, target_language, provider):
        """
        使用 LLM API 翻译消息

        :param text: 要翻译的文字
        :param model: 翻译使用的模型
        :param source_language: 源语言
        :param target_language: 目标语言
        :param provider: LLM 提供商 (e.g., "OpenAI", "Anthropic", "DeepSeek", etc.)
        :return: 包含翻译结果和token使用信息的字典，格式为:
                 {"result": "翻译结果", "usage": {"prompt_tokens": x, "completion_tokens": y, "total_tokens": z}}
                 失败时返回 None
        """

        if source_language.lower() == "auto":
            source_language = ""

        if self.translation_service_config.llm.deep_translate:
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

        # 使用 litellm 统一调用各类大模型
        try:
            # 针对部分 provider 做模型名前缀映射，保持与旧版调用兼容
            provider = provider or "OpenAI"

            # 为模型名添加提供商前缀（如果尚未添加）
            prefix = LLM_PROVIDERS_PREFIXES[provider]
            mapped_model = (
                model
                if model.startswith(prefix)
                else prefix + model
            )

            llm_params = {
                "model": mapped_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "temperature": 0,
                "api_key": self.translation_service_config.llm.api_key,
            }

            # API URL 留空自动
            if api_base := self.translation_service_config.llm.api_base:
                llm_params["api_base"] = api_base

            response = litellm.completion(**llm_params)

            # litellm 的返回对象与 OpenAI SDK 高度兼容
            content_str = response.choices[0].message.content or ""

            usage_info = response.model_dump().get("usage", {})

        except Exception as e:
            logger.error(f"LLM translation failed ({provider}) via litellm: {e}")
            raise

        if self.translation_service_config.llm.deep_translate:
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

        # # 更新累计 token 使用量
        # if usage_info and usage_info.get("total_tokens", None):
        #     try:
        #         global _PENDING_TOKENS
        #         _PENDING_TOKENS += usage_info["total_tokens"]
        #
        #         if _PENDING_TOKENS >= _SAVE_THRESHOLD:
        #             flush_pending_tokens()
        #     except Exception as e:
        #         # 避免因为读取或写入配置失败阻止翻译结果返回
        #         logger.warning(f"Failed to update total token usage: {e}")

        return {
            "result": translated_message,
            "usage": usage_info
        }

    def traditional_translate(self, text, service, source_language, target_language):
        """
        使用传统翻译服务翻译消息

        :param text: 要翻译的文字
        :param service: 翻译服务
        :param source_language: 源语言
        :param target_language: 目标语言
        :return: 翻译后的消息
        """

        traditional_api_key: str = self.translation_service_config.traditional.api_key
        if traditional_api_key:
            service = service.lower()

            # DeepL API
            if service == "deepl":
                if traditional_api_key.endswith(":fx"):
                    url = "https://api-free.deepl.com/v2/translate"
                else:
                    url = "https://api.deepl.com/v2/translate"

                headers = {
                    "Authorization": f"DeepL-Auth-Key {traditional_api_key}"
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
                else:
                    raise Exception(f"DeepL API translation failed: {response.status_code} {response.text}")

            # Google API
            elif service == "google":
                url = "https://translation.googleapis.com/language/translate/v2"
                params = {
                    "key": traditional_api_key,
                    "q": text,
                    "target": target_language.split("-")[0],
                }
                if source_language:
                    params["source"] = source_language.split("-")[0]

                response = requests.post(url, params=params)
                if response.status_code == 200:
                    return response.json()["data"]["translations"][0]["translatedText"]
                else:
                    raise Exception(f"Google API translation failed: {response.status_code} {response.text}")

            # Yandex API
            elif service == "yandex":
                url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
                headers = {
                    "Authorization": f"Api-Key {traditional_api_key}",
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
                else:
                    raise Exception(f"Yandex API translation failed: {response.status_code} {response.text}")

            # Alibaba (阿里云) API
            elif service == "alibaba":
                import time
                import uuid
                import hmac
                import base64
                import hashlib
                from urllib.parse import urlencode

                access_key_id, access_key_secret = traditional_api_key.split(":")

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
                else:
                    raise Exception(f"Alibaba API translation failed: {response.status_code} {response.text}")

            # Caiyun (彩云小译) API
            elif service == "caiyun":
                url = "http://api.interpreter.caiyunai.com/v1/translator"
                headers = {
                    "Content-Type": "application/json",
                    "X-Authorization": f"token {traditional_api_key}"
                }
                payload = {
                    "source": [text],
                    "trans_type": f"{source_language.split('-')[0] if source_language else 'auto'}{target_language.split('-')[0]}"
                }

                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    return response.json()["target"][0]
                else:
                    raise Exception(f"Caiyun API translation failed: {response.status_code} {response.text}")

            # Youdao (有道) API
            elif service == "youdao":
                import hashlib
                import time
                import uuid

                url = "https://openapi.youdao.com/api"
                app_key = traditional_api_key.split(":")[0]
                app_secret = traditional_api_key.split(":")[1]

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
                else:
                    raise Exception(f"Youdao API translation failed: {response.status_code} {response.text}")

            # Bing/Microsoft API
            elif service == "bing":
                endpoint = "https://api.cognitive.microsofttranslator.com/translate"
                headers = {
                    'Ocp-Apim-Subscription-Key': traditional_api_key,
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
                else:
                    raise Exception(f"Bing API translation failed: {response.status_code} {response.text}")

            else:
                raise ValueError(f"Unsupported translation service: {service}")
        else:
            if translated_message := ts.translate_text(text, translator=service.lower(),
                                                       from_language=source_language, to_language=target_language):
                return translated_message
            else:
                raise Exception(f"Traditional translation failed: {translated_message}")
