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
import time
import uuid
import hmac
import base64
import hashlib
from typing import Dict, Callable
from urllib.parse import urlencode
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
    def __init__(self, translation_service_config, glossary):
        """
        初始化 Translator 类, 提供多种翻译相关选项及服务参数

        :param translation_service_config: config.TranslationServiceConfig
        :param glossary: config.glossary
        """

        self.translation_service_config = translation_service_config
        self.glossary = glossary
        self._variable_pattern = re.compile(r"\{\{([a-zA-Z0-9_-]+)(?::[^}]+)?\}\}")
        self._literal_glossary = {
            k: v for k, v in self.glossary.items()
            if not self._variable_pattern.search(str(k))
        }

        logger.info(f"Initialized Translator")
        logger.debug(f"Literal glossary terms loaded: {len(self._literal_glossary)}")

    def translate(self, text, source_language, target_language):
        """
        Public API: Standard translation (or Deep Translate if configured).
        """
        return self._dispatch_translation(text, source_language, target_language, mode="standard")

    def translate_with_profanity(self, text, source_language, target_language):
        """
        Public API: Rage Mode translation.
        """
        return self._dispatch_translation(text, source_language, target_language, mode="rage")

    def _dispatch_translation(self, text, source_language, target_language, mode):
        """
        Internal Dispatcher: Coordinates prompt building and execution.
        """
        if self.translation_service_config.service_type == ServiceType.LLM:
            # Determine effective mode based on config and requested mode
            effective_mode = mode
            if mode == "standard" and self.translation_service_config.llm.deep_translate:
                effective_mode = "deep"

            # 1. Prompt Factory
            system_prompt = self._build_system_prompt(effective_mode)

            # 2. Execution Engine Configuration
            # 'deep' mode expects JSON output; others expect plain text currently
            expect_json = (effective_mode == "deep")

            include_terms = (effective_mode != "rage")

            return self._execute_llm_translation(
                text,
                self.translation_service_config.llm.model,
                source_language,
                target_language,
                self.translation_service_config.llm.provider,
                system_prompt,
                expect_json,
                include_terms
            )

        elif self.translation_service_config.service_type == ServiceType.TRADITIONAL:
            if mode == "rage":
                # Fallback logic for Rage Mode on Traditional services
                logger.warning(f"Rage mode not supported for traditional service ({self.translation_service_config.traditional.provider}). Falling back to standard translation.")
                # We just proceed with standard traditional translation

            if translation := self._execute_traditional_translation(
                    text,
                    self.translation_service_config.traditional.provider,
                    source_language,
                    target_language
            ):
                return {"result": translation, "usage": None}
            else:
                return None

    def _execute_llm_translation(self, text, model, source_language, target_language, provider, system_prompt, expect_json, include_terms):
        """
        Execution Engine: Handles API calls and response parsing.
        """
        if source_language.lower() == "auto":
            source_language = ""

        if source_language:
            base_prompt = f"Translate the following text from {source_language} to {target_language}"
        else:
            base_prompt = f"Translate the following text to {target_language}"

        matched_terms = []
        if include_terms:
            try:
                matched_terms = self._collect_in_text_terms(text)
            except Exception as _e:
                logger.warning(f"Collect in-text terms failed: {_e}")
                matched_terms = []
        else:
            logger.debug("Skipping terminology collection for this translation mode.")

        is_provider_anthropic = provider == "Anthropic"

        if is_provider_anthropic:
            base_prompt += f".\n<text_to_translate>{text}</text_to_translate>\n\n"
        else:
            base_prompt += f":\n{text}\n\n"

        message = base_prompt + self._terminology_block(matched_terms, is_provider_anthropic)

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

        if expect_json:
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

    def _build_system_prompt(self, mode: str) -> str:
        """
        Prompt Factory: Returns the system prompt for the specified mode.
        """
        if mode == "deep":
            return (
                "You are a Minecraft-specific intelligent translation engine, focused on providing "
                "high-quality localization transformations in terms of cultural adaptation and "
                "language naturalization.\n\n"
                "## Translation Guidelines\n\n"
                "1. Custom Term Priority: If a `Custom Terms` section is provided in the user's "
                "prompt, its mappings are mandatory and take the highest priority. You MUST use "
                "the specified translation for any term found in this section, overriding all "
                "other guidelines or your own knowledge.\n"
                "2. Cultural Adaptability: Identify culture-specific elements in the source text "
                "(memes, allusions, puns, etc.) and find culturally equivalent expressions in "
                "the target language.\n"
                "3. Language Modernization: Use the latest slang in the target language.\n"
                "4. Natural Language Processing:\n"
                "    - Maintain spoken sentence structures.\n"
                "    - Consider that player messages during gameplay will not be too long or have "
                "complex grammatical structures.\n"
                "    - Avoid formal language structures such as capitalization of initial letters/"
                "proper nouns and ending punctuation marks.\n"
                "    - Simulate human conversation characteristics (add appropriate filler words, "
                "reasonable repetition).\n"
                "5. Formatting Code Preservation (CRITICAL): Minecraft formatting codes (e.g., "
                "`§l`, `§c`, `§1`, `§k`) must be preserved exactly as they appear in the source "
                "text. These codes must NEVER be translated, modified, or removed.\n"
                "6. Proper Nouns and Player Names: Do not translate player IDs, server names, or "
                "non-standard game terms without a widely accepted translation.\n"
                "7. Untranslatable Content: For meaningless keyboard mashing (e.g., \"asdasd\") "
                "or garbled text, keep the original text as is.\n\n"
                "## Output Specifications\n\n"
                "Strictly follow the JSON structure below. Your entire response MUST be *only* "
                "this JSON object. Do not use Markdown code block markers, and absolutely do not "
                "add any introductory text, concluding remarks, explanations, apologies, or any "
                "other content outside of the specified JSON structure.\n\n"
                "{\n"
                "\"terms\": [\n"
                "{\"term\": \"Original term\", \"meaning\": \"Definition\"} // Include game terms, "
                "slang, abbreviations, memes, puns, and other vocabulary requiring special handling.\n"
                "],\n"
                "\"result\": \"Final translation result\" // Natural translation after cultural "
                "adaptation and colloquial processing.\n"
                "}"
            )
        elif mode == "rage":
            return (
                "You are the embodiment of a toxic, tilted, and aggressive Minecraft PVPer. "
                "You are NOT a polite translator. Your job is to translate chat messages into "
                "the most emotionally charged, sarcastic, and 'salty' version possible.\n\n"
                "## Core Personality & Guidelines\n\n"
                "1. AGGRESSION INJECTION: If input is mild (e.g., 'lag'), INJECT rage and blame (server, teammates). "
                "Make it sound like you are smashing the keyboard.\n"
                "2. TRASH TALK & SLANG: Amplify hostility. Use internet slang and memes. "
                "(e.g., 'ez' -> '有手就行', 'you suck' -> '菜就多练').\n"
                "3. MANDATORY ABBREVIATIONS: Never type full formal phrases. Use acronyms to save time.\n"
                "    - Use 'wtf', 'stfu', 'omg', 'idk', 'af' (as fuck) instead of full words.\n"
                "    - Example: 'u are bad af' instead of 'you are bad as fuck'.\n"
                "4. GAMER TYPING STYLE (CRITICAL):\n"
                "    - STRICTLY LOWERCASE: No Shift key. No capitalization.\n"
                "    - NO SPACES BEFORE PUNCTUATION: 'why???' (CORRECT) vs 'why ???' (WRONG). "
                "Attach punctuation directly to the last letter.\n"
                "    - SPAM PUNCTUATION: Use '???' or '!!!!' freely for anger, but NO formal periods.\n"
                "    - NO MARKDOWN: No bold (**), no italics. Just raw text.\n"
                "5. NO CENSORSHIP: Do NOT filter profanity. Use the most stinging vocabulary.\n\n"
                "## Output Requirement\n\n"
                "Your response MUST ONLY contain the final translated text. No explanations."
            )
        elif mode == "standard":
            return (
                "You are a Minecraft-specific intelligent translation engine, focused on providing "
                "high-quality localization transformations in terms of cultural adaptation and "
                "language naturalization.\n\n"
                "## Translation Guidelines\n\n"
                "1. Custom Term Priority: If a `Custom Terms` section is provided in the user's "
                "prompt, its mappings are mandatory and take the highest priority. You MUST use "
                "the specified translation for any term found in this section, overriding all "
                "other guidelines or your own knowledge.\n"
                "2. Cultural Adaptability: Identify culture-specific elements in the source text "
                "(memes, allusions, puns, etc.) and find culturally equivalent expressions in "
                "the target language.\n"
                "3. Language Modernization: Use the latest slang in the target language.\n"
                "4. Natural Language Processing:\n"
                "    - Maintain spoken sentence structures.\n"
                "    - Consider that player messages during gameplay will not be too long or have "
                "complex grammatical structures.\n"
                "    - Avoid formal language structures such as capitalization of initial letters/"
                "proper nouns and ending punctuation marks.\n"
                "    - Simulate human conversation characteristics (add appropriate filler words, "
                "reasonable repetition).\n"
                "5. Formatting Code Preservation (CRITICAL): Minecraft formatting codes (e.g., "
                "`§l`, `§c`, `§1`, `§k`) must be preserved exactly as they appear in the source "
                "text. These codes must NEVER be translated, modified, or removed.\n"
                "6. Proper Nouns and Player Names: Do not translate player IDs, server names, or "
                "non-standard game terms without a widely accepted translation.\n"
                "7. Untranslatable Content: For meaningless keyboard mashing (e.g., \"asdasd\") "
                "or garbled text, keep the original text as is.\n\n"
                "## Output Requirement\n\n"
                "Your response MUST ONLY contain the final translated text. Do not add any "
                "prefixes, suffixes, explanations, or notes."
            )
        else:
            raise ValueError(f"Invalid prompt mode: {mode}")

    def _collect_in_text_terms(self, text: str, max_terms: int = 50):
        """
        从纯文本术语表中筛选“在 text 中出现过”的术语，按出现顺序返回 [(src, tgt), ...]
        为了控制提示长度，默认最多取前 max_terms 项。
        """
        if not text or not self._literal_glossary:
            return []

        matches = []
        for src, tgt in self._literal_glossary.items():
            try:
                if src and src in text:
                    pos = text.index(src)
                    matches.append((pos, src, tgt))
            except Exception:
                # 极少数情况下 index 可能抛异常，忽略即可
                continue

        if not matches:
            return []

        # 按首次出现位置排序，去重并截断
        matches.sort(key=lambda x: x[0])
        result, seen = [], set()
        for _, src, tgt in matches:
            if src not in seen:
                result.append((src, tgt))
                seen.add(src)
            if len(result) >= max_terms:
                break
        return result

    def _terminology_block(self, matched_terms, is_provider_anthropic=False):
        """
        根据匹配到的术语列表，生成用于Prompt的XML格式术语块。

        Args:
            matched_terms: 一个元组列表，每个元组包含 (source_term, target_term)
                           例如: [("gg", "打得不错"), ("afk", "挂机")]
            is_provider_anthropic: 是否为Anthropic模型

        Returns:
            一个格式化好的Markdown列表格式术语块，格式为: - "source": "target"
            如果为Anthropic模型，返回XML格式
        """
        if not matched_terms:
            return ""

        if is_provider_anthropic:
            entries_str = "".join(
                f"<entry><source>{src}</source><target>{tgt}</target></entry>"
                for src, tgt in matched_terms
            )
            return f"<custom_terms>{entries_str}</custom_terms>"
        else:
            entries_str = "\n".join(
                f'- "{src}": "{tgt}"'
                for src, tgt in matched_terms
            )
            return (
                "Custom Terms:\n"
                f"{entries_str}"
            )

    def _execute_traditional_translation(self, text, service, source_language, target_language):
        """
        Executes translation using the specified traditional service provider.

        Acts as a dispatcher to specific provider implementations (e.g., DeepL, Google).
        """

        traditional_api_key: str = self.translation_service_config.traditional.api_key
        if traditional_api_key:
            service = service.lower()

            dispatch_map: Dict[str, Callable[[str, str, str, str], str]] = {
                "deepl": self._translate_deepl,
                "google": self._translate_google,
                "yandex": self._translate_yandex,
                "alibaba": self._translate_alibaba,
                "caiyun": self._translate_caiyun,
                "youdao": self._translate_youdao,
                "bing": self._translate_bing
            }

            if service in dispatch_map:
                return dispatch_map[service](text, traditional_api_key, source_language, target_language)
            else:
                raise ValueError(f"Unsupported translation service: {service}")
        else:
            if translated_message := ts.translate_text(text, translator=service.lower(),
                                                       from_language=source_language, to_language=target_language):
                return translated_message
            else:
                raise Exception(f"Traditional translation failed: {translated_message}")

    def _translate_deepl(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        if api_key.endswith(":fx"):
            url = "https://api-free.deepl.com/v2/translate"
        else:
            url = "https://api.deepl.com/v2/translate"

        headers = {
            "Authorization": f"DeepL-Auth-Key {api_key}"
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

    def _translate_google(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {
            "key": api_key,
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

    def _translate_yandex(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
        headers = {
            "Authorization": f"Api-Key {api_key}",
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

    def _translate_alibaba(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        access_key_id, access_key_secret = api_key.split(":")

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

    def _translate_caiyun(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        url = "http://api.interpreter.caiyunai.com/v1/translator"
        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"token {api_key}"
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

    def _translate_youdao(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        url = "https://openapi.youdao.com/api"
        app_key = api_key.split(":")[0]
        app_secret = api_key.split(":")[1]

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

    def _translate_bing(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        headers = {
            'Ocp-Apim-Subscription-Key': api_key,
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
