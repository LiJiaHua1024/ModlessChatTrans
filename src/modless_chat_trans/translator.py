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

import json
import re
import time
import uuid
import hmac
import base64
import hashlib
from email.utils import formatdate
from enum import Enum
from typing import Dict, Callable, Set
from urllib.parse import quote
import lazy_loader as lazy
from modless_chat_trans.logger import logger
from modless_chat_trans.config import ServiceType, FallbackStrategy


def _http():
    """懒加载 requests，避免拖慢程序启动"""
    import requests
    return requests


class MessageType(Enum):
    """消息类型枚举"""
    PLAYER = "player"
    SEND = "send"
    SYSTEM = "system"


class TranslationMode(Enum):
    """翻译模式枚举"""
    NORMAL = "normal"
    DEEP = "deep"
    RAGE = "rage"


# 定义每种消息类型支持的翻译模式
MESSAGE_TYPE_MODES: Dict[MessageType, Set[TranslationMode]] = {
    MessageType.SYSTEM: {TranslationMode.NORMAL},
    MessageType.PLAYER: {TranslationMode.NORMAL, TranslationMode.DEEP},
    MessageType.SEND: {TranslationMode.NORMAL, TranslationMode.DEEP, TranslationMode.RAGE},
}

_OPENROUTER_NATIVE_SUFFIXES = frozenset({"nitro", "floor"})
_OPENROUTER_SORT_KEYWORDS = frozenset({"price", "throughput", "latency"})

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

# `translators.get_languages()` obtains language lists from public web pages.
# Keep a small provider-specific fallback so a temporary web rate limit does
# not prevent the application from using a configured paid API.
TRADITIONAL_LANGUAGE_FALLBACKS = {
    "deepl": [
        "ar", "bg", "cs", "da", "de", "el", "en", "en-GB", "en-US", "es", "et", "fi",
        "fr", "hu", "id", "it", "ja", "ko", "lt", "lv", "nb", "nl", "pl", "pt",
        "pt-BR", "pt-PT", "ro", "ru", "sk", "sl", "sv", "tr", "uk", "zh", "zh-Hans", "zh-Hant"
    ],
    "bing": [
        "ar", "bg", "ca", "cs", "da", "de", "el", "en", "en-GB", "es", "fi", "fr",
        "fr-CA", "he", "hi", "hu", "id", "it", "ja", "ko", "nb", "nl", "pl", "pt",
        "pt-PT", "ro", "ru", "sk", "sr-Cyrl", "sr-Latn", "sv", "th", "tr", "uk", "vi",
        "zh-Hans", "zh-Hant"
    ],
    "google": [
        "ar", "bg", "ca", "cs", "da", "de", "el", "en", "es", "fi", "fr", "he",
        "hi", "hu", "id", "it", "ja", "ko", "nl", "no", "pl", "pt", "pt-PT", "ro",
        "ru", "sk", "sr", "sv", "th", "tr", "uk", "vi", "zh", "zh-CN", "zh-TW"
    ],
    "yandex": [
        "az", "be", "bg", "ca", "cs", "da", "de", "el", "en", "es", "et", "fi",
        "fr", "hu", "it", "ja", "kk", "ko", "lt", "lv", "mk", "nl", "no", "pl",
        "pt", "ro", "ru", "sk", "sl", "sq", "sr", "sv", "tr", "uk", "zh"
    ],
    "alibaba": [
        "ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt", "ru", "th", "tr",
        "vi", "zh", "zh-tw"
    ],
    "caiyun": [
        "ar", "de", "el", "en", "es", "fr", "id", "it", "ja", "ko", "nn", "pl",
        "pt", "ru", "sw", "th", "tr", "vi", "zh", "zh-Hant"
    ],
    "youdao": [
        "ar", "de", "en", "es", "fr", "hi", "id", "it", "ja", "ko", "nl", "pt",
        "ru", "sr-Cyrl", "sr-Latn", "th", "tr", "uk", "vi", "zh-CHS", "zh-CHT", "yue"
    ],
    "sogou": [
        "ar", "de", "en", "es", "fi", "fr", "hu", "it", "ja", "ko", "nl", "pl",
        "pt", "ru", "sv", "th", "vi", "zh-CHS", "zh-CHT"
    ],
    "iflyrec": [
        "ar", "de", "en", "es", "fr", "it", "ja", "ko", "ru", "vi", "yue", "zh"
    ],
}

import threading

ts = lazy.load("translators")
litellm = lazy.load("litellm")

# 独立锁：litellm 与 translators 可并行预加载，互不阻塞
_llm_import_lock = threading.Lock()
_ts_import_lock = threading.Lock()


def ensure_ts_loaded():
    """确保传统翻译服务依赖已加载（translators 及其使用的 requests）"""
    with _ts_import_lock:
        _ = ts.__name__
        _http()


def ensure_litellm_loaded():
    """确保 LLM 翻译服务依赖已加载（litellm）"""
    with _llm_import_lock:
        _ = litellm.__name__


def get_supported_languages(service):
    service_lower = service.lower()
    try:
        languages = ts.get_languages(service_lower)
        language_codes = sorted(
            code for code in languages.keys() if str(code).lower() != "auto"
        )
        if language_codes:
            return language_codes
    except Exception as error:
        fallback = TRADITIONAL_LANGUAGE_FALLBACKS.get(service_lower)
        if fallback:
            logger.warning(
                f"Failed to load online language list for {service}; using built-in fallback: {error}"
            )
            return sorted(fallback)
        raise

    fallback = TRADITIONAL_LANGUAGE_FALLBACKS.get(service_lower)
    if fallback:
        logger.warning(f"Online language list for {service} was empty; using built-in fallback.")
        return sorted(fallback)
    raise ValueError(f"No supported languages found for traditional service '{service}'")


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
    MAX_TRANSLATION_SECONDS = 10.0

    def __init__(self, translation_service_config, glossary,
                 fallback_llm_config=None, fallback_strategy=None):
        """
        初始化 Translator 类, 提供多种翻译相关选项及服务参数

        :param translation_service_config: config.TranslationServiceConfig
        :param glossary: config.glossary
        :param fallback_llm_config: 备用 LLM 配置（可选）
        :param fallback_strategy: 备用模型切换策略
        """

        self.translation_service_config = translation_service_config
        self.glossary = glossary
        self.fallback_llm_config = (
            fallback_llm_config
            if fallback_llm_config is not None
            else getattr(translation_service_config, "fallback_llm", None)
        )
        self.fallback_strategy = (
            fallback_strategy
            if fallback_strategy is not None
            else getattr(translation_service_config, "fallback_strategy", FallbackStrategy.DIRECT)
        )
        fallback_provider = getattr(self.fallback_llm_config, "provider", "") if self.fallback_llm_config else ""
        fallback_model = getattr(self.fallback_llm_config, "model", "") if self.fallback_llm_config else ""
        if not self.fallback_llm_config or not fallback_provider.strip() or not fallback_model.strip():
            logger.info("Fallback LLM disabled: no complete fallback configuration.")
        else:
            logger.info(
                f"Fallback LLM enabled: {self.fallback_llm_config.provider}/"
                f"{self.fallback_llm_config.model}, strategy={self.fallback_strategy}"
            )
        # 单个请求和整条翻译链路都不能超过 10 秒；备用策略会在此预算内分配时间。
        self.timeout = self.MAX_TRANSLATION_SECONDS
        self.translation_deadline = self.MAX_TRANSLATION_SECONDS
        self._variable_pattern = re.compile(r"\{\{([a-zA-Z0-9_-]+)(?::[^}]+)?\}\}")
        self._literal_glossary = {
            k: v for k, v in self.glossary.items()
            if not self._variable_pattern.search(str(k))
        }

        # 判断是否为 Anthropic 模型
        provider = getattr(translation_service_config.llm, 'provider', None) or ""
        model = getattr(translation_service_config.llm, 'model', None) or ""
        self._is_anthropic = (
                provider.lower() == "anthropic"
                or "claude" in model.lower()
                or "anthropic" in model.lower()
        )

        # 判断是否为 Gemini 3 系列模型
        self._is_gemini3 = "gemini-3" in model.lower()

        logger.info(f"Initialized Translator")
        logger.debug(f"Literal glossary terms loaded: {len(self._literal_glossary)}")

    def translate(self, text, source_language, target_language, message_type: MessageType = MessageType.PLAYER):
        """
        Public API: Standard translation (or Deep Translate if configured).

        :param text: 待翻译文本
        :param source_language: 源语言
        :param target_language: 目标语言
        :param message_type: 消息类型，决定可用的翻译模式
        """
        return self._dispatch_translation(
            text, source_language, target_language,
            mode=TranslationMode.NORMAL,
            message_type=message_type
        )

    def translate_with_context(
            self,
            text: str,
            source_language: str,
            target_language: str,
            message_type: MessageType = MessageType.PLAYER,
            context_messages: list = None,
    ) -> dict | None:
        """
        Public API: 带历史上下文的单条翻译。

        :param text: 待翻译文本
        :param source_language: 源语言
        :param target_language: 目标语言
        :param message_type: 消息类型
        :param context_messages: 历史上下文 messages 列表（可直接拼入 litellm），为 None/[] 则退化为无上下文
        """
        context_messages = context_messages or []
        return self._dispatch_translation(
            text, source_language, target_language,
            mode=TranslationMode.NORMAL,
            message_type=message_type,
            context_messages=context_messages,
        )

    def translate_batch_with_context(
            self,
            texts: list[str],
            source_language: str,
            target_language: str,
            message_type: MessageType = MessageType.PLAYER,
            context_messages: list = None,
    ) -> list[str] | None:
        """
        Public API: 将多条消息打包为一个 request，返回按顺序对应的译文列表。

        :param texts: 待翻译文本列表
        :param source_language: 源语言
        :param target_language: 目标语言
        :param message_type: 消息类型
        :param context_messages: 历史上下文 messages 列表
        :return: 与 texts 等长的译文列表，或 None（失败，调用方应降级处理）
        """
        if not texts:
            return []
        context_messages = context_messages or []

        # 仅 LLM 服务支持批量翻译；传统服务返回 None→降级
        if self.translation_service_config.service_type != ServiceType.LLM:
            return None

        # Deep 模式输出结构与批量数组冲突，不参与打包
        effective_mode = self._get_effective_mode(TranslationMode.NORMAL, message_type)
        if effective_mode == TranslationMode.DEEP:
            return None

        try:
            return self._execute_llm_batch_translation(
                texts, source_language, target_language,
                message_type, context_messages
            )
        except Exception as e:
            logger.warning(f"Batch translation failed, will fallback to single: {e}")
            return None

    def translate_with_profanity(self, text, source_language, target_language,
                                 message_type: MessageType = MessageType.SEND):
        """
        Public API: Rage Mode translation.

        :param text: 待翻译文本
        :param source_language: 源语言
        :param target_language: 目标语言
        :param message_type: 消息类型，决定可用的翻译模式
        """
        return self._dispatch_translation(
            text, source_language, target_language,
            mode=TranslationMode.RAGE,
            message_type=message_type
        )

    def _dispatch_translation(self, text, source_language, target_language, mode: TranslationMode,
                              message_type: MessageType, context_messages: list = None):
        """
        Internal Dispatcher: Coordinates prompt building and execution.

        :param text: 待翻译文本
        :param source_language: 源语言
        :param target_language: 目标语言
        :param mode: 请求的翻译模式
        :param message_type: 消息类型，用于验证可用模式并选择正确的prompt
        :param context_messages: 历史上下文 messages（将内嵌入 LLM 请求）
        """
        context_messages = context_messages or []
        if self.translation_service_config.service_type == ServiceType.LLM:
            # 1. 验证模式是否对当前消息类型可用，如果不可用则降级
            effective_mode = self._get_effective_mode(mode, message_type)

            # 2. Prompt Factory - 构建 system prompt（含上下文指导）
            system_prompt = self._build_system_prompt(
                effective_mode, message_type,
                has_context=bool(context_messages)
            )

            # 3. Execution Engine Configuration
            # 'deep' mode expects JSON output; others expect plain text currently
            expect_json = (effective_mode == TranslationMode.DEEP)

            include_terms = (effective_mode != TranslationMode.RAGE)

            return self._execute_with_fallback(
                text,
                self.translation_service_config.llm.model,
                source_language,
                target_language,
                self.translation_service_config.llm.provider,
                system_prompt,
                expect_json,
                include_terms,
                message_type,
                context_messages=context_messages,  # 传入 user prompt
            )

        elif self.translation_service_config.service_type == ServiceType.TRADITIONAL:
            # 验证模式是否对当前消息类型可用
            effective_mode = self._get_effective_mode(mode, message_type)

            if effective_mode == TranslationMode.RAGE:
                # Fallback logic for Rage Mode on Traditional services
                logger.warning(
                    f"Rage mode not supported for traditional service ({self.translation_service_config.traditional.provider}). Falling back to standard translation.")
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

    def _get_effective_mode(self, requested_mode: TranslationMode, message_type: MessageType) -> TranslationMode:
        """
        根据消息类型验证并调整翻译模式。

        :param requested_mode: 请求的翻译模式
        :param message_type: 消息类型
        :return: 有效的翻译模式（如果请求的模式不可用则降级）
        """
        available_modes = MESSAGE_TYPE_MODES.get(message_type, {TranslationMode.NORMAL})

        # 如果请求的模式可用，直接返回
        if requested_mode in available_modes:
            return requested_mode

        # 如果请求的是NORMAL但不可用（理论上不应该发生），返回NORMAL
        if requested_mode == TranslationMode.NORMAL:
            return TranslationMode.NORMAL

        # 对于其他情况，降级到NORMAL（如果可用）
        if TranslationMode.NORMAL in available_modes:
            logger.debug(
                f"Mode {requested_mode.value} not available for message type {message_type.value}, "
                f"falling back to normal mode"
            )
            return TranslationMode.NORMAL

        # 兜底：返回该消息类型的第一个可用模式
        return next(iter(available_modes))

    def _execute_llm_translation(self, text, model, source_language, target_language, provider, system_prompt,
                                 expect_json, include_terms, message_type: MessageType = MessageType.PLAYER,
                                 context_messages: list = None,
                                 llm_config_override=None, request_timeout=None):
        """
        Execution Engine: Handles API calls and response parsing.

        :param text: 待翻译文本
        :param model: 模型名称
        :param source_language: 源语言
        :param target_language: 目标语言
        :param provider: 模型提供商
        :param system_prompt: 系统提示词
        :param expect_json: 是否期望JSON格式输出
        :param include_terms: 是否包含术语表
        :param message_type: 消息类型
        :param context_messages: 历史上下文 messages
        :param llm_config_override: 可选的 LLMS erviceConfig 覆盖（用于备用模型）
        :param request_timeout: 当前请求剩余的超时时间（秒）
        """
        context_messages = context_messages or []
        # 选择有效的 LLM 配置（备用模型配置或主模型配置）
        llm_cfg = llm_config_override or self.translation_service_config.llm
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

        # 构建 user message
        # 如果有历史上下文，先拼接历史，再拼接翻译指令
        if context_messages:
            history_content = context_messages[0].get("content", "")
            if self._is_anthropic:
                # Anthropic 使用 XML 标签
                history_block = f"<recent_chat_history>\n{history_content}\n</recent_chat_history>\n\n"
            else:
                history_block = f"=== Recent Chat History ===\n{history_content}\n=== End of History ===\n\n---\n\n"
        else:
            history_block = ""

        if is_provider_anthropic:
            base_prompt += f".\n<text_to_translate>{text}</text_to_translate>\n\n"
        else:
            base_prompt += f":\n{text}\n\n"

        message = history_block + base_prompt + self._terminology_block(matched_terms, self._is_anthropic)

        # 使用 litellm 统一调用各类大模型
        try:
            # 针对部分 provider 做模型名前缀映射，保持与旧版调用兼容
            provider = provider or "OpenAI"

            # ── OpenRouter 扩展 Model ID 语法解析 ──────────────────────────
            # 官方原生后缀: :nitro, :floor -> 保持原样，由 OpenRouter 自行处理
            # 扩展排序后缀: :price, :throughput, :latency -> 通过 extra_body 传递 provider.sort
            # 自定义 Provider: :amazon-bedrock 或 :amazon-bedrock,google-vertex -> 通过 extra_body 传递 provider.order

            extra_body = None

            if provider == "OpenRouter" and ":" in model:
                base_model, suffix = model.split(":", 1)
                suffix_stripped = suffix.strip()
                suffix_lower = suffix_stripped.lower()

                if suffix_lower in _OPENROUTER_NATIVE_SUFFIXES:
                    # 官方原生后缀，保持 model 不变，无需额外处理
                    pass
                elif suffix_lower in _OPENROUTER_SORT_KEYWORDS:
                    # 扩展排序语法 -> provider.sort
                    model = base_model
                    extra_body = {"provider": {"sort": suffix_lower}}
                else:
                    # 自定义 Provider 指定（支持逗号分隔多个）-> provider.order
                    model = base_model
                    provider_order = [s for p in suffix_stripped.split(",") if (s := p.strip())]
                    extra_body = {"provider": {"order": provider_order}}

            # Gemini 3 系列是原生思考模型，思考无法关闭且默认消耗大量输出 token
            # 显式降级 reasoning 到 minimal effort，避免译文被思考 token 截断
            if self._is_gemini3 and provider == "OpenRouter":
                # OpenRouter 通过 extra_body 透传 reasoning 参数
                extra_body = {**{"reasoning": {"effort": "minimal"}}, **(extra_body or {})}
                logger.debug(
                    f"Gemini 3 model ({model}) detected: capping reasoning to minimal effort"
                )

            # 为模型名添加提供商前缀（如果尚未添加）
            prefix = LLM_PROVIDERS_PREFIXES[provider]
            mapped_model = (
                model
                if model.startswith(prefix)
                else prefix + model
            )

            # GPT-5 系列只接受 temperature=1；其它模型继续使用确定性翻译参数。
            temperature = 1 if re.match(r"^(?:openai/)?gpt-5(?:[-.]|$)", model.lower()) else 0
            llm_params = {
                "model": mapped_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "temperature": temperature,
                "max_tokens": llm_cfg.max_tokens * (2 if expect_json else 1),
                "api_key": llm_cfg.api_key,
                "num_retries": 0,
            }

            if self._is_gemini3 and provider != "OpenRouter":
                llm_params["reasoning_effort"] = "minimal"
                llm_params["drop_params"] = True
                logger.debug(
                    f"Gemini 3 model ({model}) detected: sending reasoning_effort=minimal"
                )

            # API URL 留空自动
            if api_base := llm_cfg.api_base:
                llm_params["api_base"] = api_base

            llm_params["timeout"] = request_timeout if request_timeout is not None else self.timeout

            # 注入 OpenRouter 扩展路由参数
            if extra_body:
                llm_params["extra_body"] = extra_body

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
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content_str)
                    content_dict = json.loads(m.group(1) if m else content_str)
                except json.JSONDecodeError as e2:
                    logger.warning("Failed to parse optimized translation JSON even after cleaning")
                    raise ValueError("Failed to parse optimized translation JSON") from e2

            translated_message = content_dict.get("result", None)
        else:
            translated_message = content_str

        if not translated_message:
            raise ValueError("LLM returned an empty translation")

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

    def _execute_with_fallback(self, text, model, source_language, target_language,
                               provider, system_prompt, expect_json, include_terms,
                               message_type: MessageType = MessageType.PLAYER,
                               context_messages: list = None):
        """
        带备用模型策略的 LLM 翻译执行。

        根据 fallback_strategy 决定主模型失败后的行为：
        - DIRECT: 主模型失败 → 立即使用备用模型
        - RETRY_EXHAUSTED: 主模型重试全部失败 → 使用备用模型
        - RACE_ON_FAILURE: 主模型首次失败 → 并发竞速主模型和备用模型
        - ALWAYS_RACE: 始终并发请求两者，取最快返回结果
        """
        context_messages = context_messages or []
        has_fallback = (
                self.fallback_llm_config is not None
                and bool((self.fallback_llm_config.provider or "").strip())
                and bool((self.fallback_llm_config.model or "").strip())
        )
        try:
            strategy = FallbackStrategy(self.fallback_strategy)
        except ValueError:
            logger.warning(
                f"Unknown fallback strategy {self.fallback_strategy!r}; using direct fallback."
            )
            strategy = FallbackStrategy.DIRECT

        deadline = time.monotonic() + self.translation_deadline

        def remaining_time():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Translation exceeded the {self.translation_deadline:g}-second deadline"
                )
            return remaining

        def call_primary(request_timeout):
            return self._execute_llm_translation(
                text, model, source_language, target_language, provider,
                system_prompt, expect_json, include_terms, message_type,
                context_messages=context_messages,
                request_timeout=request_timeout,
            )

        def call_fallback(request_timeout):
            return self._execute_llm_translation(
                text, self.fallback_llm_config.model,
                source_language, target_language,
                self.fallback_llm_config.provider,
                system_prompt, expect_json, include_terms,
                message_type, context_messages=context_messages,
                llm_config_override=self.fallback_llm_config,
                request_timeout=request_timeout,
            )

        # Strategy D: Always race — 始终并发竞速
        if has_fallback and strategy == FallbackStrategy.ALWAYS_RACE:
            logger.info("Fallback strategy: ALWAYS_RACE — concurrently requesting primary and fallback")
            return self._race_primary_fallback(
                text, source_language, target_language, provider,
                system_prompt, expect_json, include_terms,
                message_type, context_messages, deadline
            )

        # Strategy B: Retry exhausted — 在总预算内平均分配每次尝试的时间。
        if strategy == FallbackStrategy.RETRY_EXHAUSTED:
            # 生产环境最多尝试两次：首次请求失败后只再重试一次。
            primary_attempts = 2
            last_primary_error = None
            for attempt in range(primary_attempts):
                attempts_left = primary_attempts - attempt + (1 if has_fallback else 0)
                try:
                    return call_primary(remaining_time() / attempts_left)
                except Exception as retry_error:
                    last_primary_error = retry_error
                    logger.warning(
                        f"Primary attempt {attempt + 1}/{primary_attempts} failed: {retry_error}"
                    )

            if not has_fallback:
                raise last_primary_error

            logger.info(
                "Fallback strategy: RETRY_EXHAUSTED — primary retries exhausted, "
                "switching to fallback within the remaining deadline"
            )
            try:
                return call_fallback(remaining_time())
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Primary model and retries failed (last error: {last_primary_error}); "
                    f"fallback model failed: {fallback_error}"
                ) from fallback_error

        # 其它策略先给主模型一半预算，确保备用模型仍有时间接管。
        primary_timeout = remaining_time() / 2 if has_fallback else remaining_time()
        try:
            return call_primary(primary_timeout)
        except Exception as primary_error:
            logger.warning(f"Primary model ({provider}/{model}) failed: {primary_error}")
            if not has_fallback:
                raise

            # Strategy A: Direct fallback — 主模型失败立即使用备用
            if strategy == FallbackStrategy.DIRECT:
                logger.info("Fallback strategy: DIRECT — switching to fallback model immediately")
                try:
                    return call_fallback(remaining_time())
                except Exception as fallback_error:
                    raise RuntimeError(
                        f"Primary model failed: {primary_error}; fallback model failed: {fallback_error}"
                    ) from fallback_error

            # Strategy C: Race on first failure — 首次失败后并发竞速
            if strategy == FallbackStrategy.RACE_ON_FAILURE:
                logger.info(
                    "Fallback strategy: RACE_ON_FAILURE — primary failed, "
                    "racing primary vs fallback within the remaining deadline"
                )
                return self._race_primary_fallback(
                    text, source_language, target_language, provider,
                    system_prompt, expect_json, include_terms,
                    message_type, context_messages, deadline
                )

            raise  # 未知策略，不应到达

    def _race_primary_fallback(self, text, source_language, target_language,
                               provider, system_prompt, expect_json, include_terms,
                               message_type: MessageType = MessageType.PLAYER,
                               context_messages: list = None,
                               deadline: float = None):
        """
        并发请求主模型和备用模型，返回最先成功的结果。
        如果两者都失败，抛出异常。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

        context_messages = context_messages or []

        if deadline is None:
            deadline = time.monotonic() + self.translation_deadline
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"Translation exceeded the {self.translation_deadline:g}-second deadline"
            )

        request_timeout = min(self.timeout, remaining)

        def call_primary():
            return self._execute_llm_translation(
                text, self.translation_service_config.llm.model,
                source_language, target_language, provider,
                system_prompt, expect_json, include_terms,
                message_type, context_messages=context_messages,
                request_timeout=request_timeout,
            )

        def call_fallback():
            return self._execute_llm_translation(
                text, self.fallback_llm_config.model,
                source_language, target_language,
                self.fallback_llm_config.provider,
                system_prompt, expect_json, include_terms,
                message_type, context_messages=context_messages,
                llm_config_override=self.fallback_llm_config,
                request_timeout=request_timeout,
            )

        executor = ThreadPoolExecutor(max_workers=2)
        futures = {
            executor.submit(call_primary): "primary",
            executor.submit(call_fallback): "fallback",
        }
        errors = []
        try:
            for future in as_completed(futures, timeout=remaining):
                try:
                    result = future.result()
                    logger.info(f"Race won by: {futures[future]}")
                    return result
                except Exception as e:
                    errors.append((futures[future], str(e)))
                    logger.warning(f"Race contender {futures[future]} failed: {e}")
            # 两者都失败
            error_details = "; ".join(f"{name}: {err}" for name, err in errors)
            raise Exception(f"Both primary and fallback models failed: {error_details}")
        except FuturesTimeoutError as timeout_error:
            raise TimeoutError(
                f"Primary and fallback models exceeded the {self.translation_deadline:g}-second deadline"
            ) from timeout_error
        finally:
            # wait=False prevents blocking on the slower model; cancel_futures cancels pending tasks.
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _context_awareness_block() -> str:
        """公共的上下文感知指导文本"""
        return (
            "\n## Context Awareness\n\n"
            "A recent chat history is provided in the user message. "
            "Use it to understand ongoing conversations and maintain translation consistency.\n"
            "Note: Messages closer to the end are more likely to be relevant. "
            "Earlier messages may be unrelated to the current one — use your judgment.\n"
        )

    def _build_system_prompt(self, mode: TranslationMode, message_type: MessageType,
                             has_context: bool = False) -> str:
        """
        Prompt Factory: Returns the system prompt for the specified mode and message type.

        :param mode: 翻译模式
        :param message_type: 消息类型
        :param has_context: 是否有历史上下文
        :return: 系统提示词
        """
        # System消息使用正式的Normal prompt（独立于player/send的normal）
        if message_type == MessageType.SYSTEM:
            return self._build_system_normal_prompt(has_context)
        # Player/Send消息的Normal mode使用标准口语化prompt
        elif mode == TranslationMode.NORMAL:
            return self._build_player_normal_prompt(has_context)
        # Deep mode
        elif mode == TranslationMode.DEEP:
            return self._build_deep_prompt(has_context)
        # Rage mode
        elif mode == TranslationMode.RAGE:
            return self._build_rage_prompt(has_context)
        else:
            raise ValueError(f"Invalid mode: {mode}")

    def _build_system_normal_prompt(self, has_context: bool = False) -> str:
        """
        System消息专用的极简Normal prompt。
        利用LLM默认的正式语气，仅针对格式安全和术语进行硬性约束。
        """
        prompt = (
            "You are a Minecraft server localization engine. "
            "Translate server announcements, game notifications, and plugin messages.\n"
        )

        if has_context:
            prompt += self._context_awareness_block()

        prompt += (
            "\nRules:\n"
            "1. Priority: You MUST use mappings from `Custom Terms` if provided.\n"
            "2. Safety: STRICTLY preserve all formatting codes (e.g., `§a`, `§l`) and "
            "symbols. Do NOT translate command syntax (e.g., `/help`).\n"
            "3. Output: Output ONLY the translation result."
        )
        return prompt

    def _build_player_normal_prompt(self, has_context: bool = False) -> str:
        """
        Player/Send消息专用的Normal prompt（口语化风格）。
        """
        prompt = (
            "You are a Minecraft-specific intelligent translation engine, focused on providing "
            "high-quality localization transformations in terms of cultural adaptation and "
            "language naturalization.\n"
        )

        if has_context:
            prompt += self._context_awareness_block()

        prompt += (
            "\n## Translation Guidelines\n\n"
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
        return prompt

    def _build_deep_prompt(self, has_context: bool = False) -> str:
        """
        Deep mode prompt（CoT思维链模式）。
        """
        prompt = (
            "You are a Minecraft-specific intelligent translation engine, focused on providing "
            "high-quality localization transformations in terms of cultural adaptation and "
            "language naturalization.\n"
        )

        if has_context:
            prompt += self._context_awareness_block()

        prompt += (
            "\n## Translation Guidelines\n\n"
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
            "Strictly return a valid JSON object that conforms EXACTLY to the following "
            "TypeScript interface. Do not wrap the output in Markdown code blocks (e.g., ```json), "
            "and do not output any explanations or additional text.\n\n"
        )

        if has_context:
            prompt += (
                "interface TranslationOutput {\n"
                "  // Analysis of the recent chat history and how it relates to the current message\n"
                "  context_analysis: {\n"
                "    // Summary of the ongoing conversation or topic from the history\n"
                "    conversation_summary: string;\n"
                "    // How the history affects interpretation of the current message\n"
                "    // (e.g., follow-up to a joke, response to a question, continuation of a topic)\n"
                "    relevance: string;\n"
                "  };\n"
                "  // List of vocabulary requiring special handling (game terms, slang, abbreviations, memes, puns, etc.)\n"
                "  terms: {\n"
                "    // The original term found in the source text\n"
                "    term: string;\n"
                "    // Definition, explanation, or context of the term\n"
                "    meaning: string;\n"
                "  }[];\n"
                "  // Final natural translation result after cultural adaptation and colloquial processing\n"
                "  // The translation MUST take into account the context_analysis above\n"
                "  result: string;\n"
                "}"
            )
        else:
            prompt += (
                "interface TranslationOutput {\n"
                "  // List of vocabulary requiring special handling (game terms, slang, abbreviations, memes, puns, etc.)\n"
                "  terms: {\n"
                "    // The original term found in the source text\n"
                "    term: string;\n"
                "    // Definition, explanation, or context of the term\n"
                "    meaning: string;\n"
                "  }[];\n"
                "  // Final natural translation result after cultural adaptation and colloquial processing\n"
                "  result: string;\n"
                "}"
            )

        return prompt

    def _build_rage_prompt(self, has_context: bool = False) -> str:
        """
        Rage mode prompt（红温模式）。
        """
        prompt = (
            "You are the embodiment of a toxic, tilted, and aggressive Minecraft PVPer. "
            "You are NOT a polite translator. Your job is to translate chat messages into "
            "the most emotionally charged, sarcastic, and 'salty' version possible.\n"
        )

        if has_context:
            prompt += (
                "\n## Context Awareness\n\n"
                "A recent chat history is provided in the user message. "
                "Use it to understand who you're trash-talking and what started the beef.\n"
                "Note: Messages closer to the end are more likely to be relevant. "
                "Earlier messages may be unrelated — use your judgment.\n"
            )

        prompt += (
            "\n## Core Personality & Guidelines\n\n"
            "1. AGGRESSION INJECTION: If input is mild (e.g., 'lag'), INJECT rage and blame (server, teammates). "
            "Make it sound like you are smashing the keyboard.\n"
            "2. TRASH TALK & SLANG: Amplify hostility. Use internet slang and memes. "
            "(e.g., 'ez' -> '有手就行', 'you suck' -> '菜就多练').\n"
            "3. MANDATORY ABBREVIATIONS: Never type full formal phrases. Use acronyms to save time.\n"
            "    - Use 'wtf', 'stfu', 'omg', 'idk', 'af' (as fuck) instead of full words.\n"
            "    - Example: 'u are bad af' instead of 'you are bad as fuck'.\n"
            "4. GAMER TYPING STYLE (CRITICAL):\n"
            "    - STRICTLY LOWERCASE: No Shift key. No capitalization.\n"
            "    - NO SPACES BEFORE PUNCTUATION: 'why?' (CORRECT) vs 'why ?' (WRONG). "
            "Attach punctuation directly to the last letter.\n"
            "    - NO MARKDOWN: No bold (**), no italics. Just raw text.\n"
            "5. NO CENSORSHIP: Do NOT filter profanity. Use the most stinging vocabulary.\n\n"
            "## Output Requirement\n\n"
            "Your response MUST ONLY contain the final translated text. No explanations."
        )
        return prompt

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

    def _execute_llm_batch_translation(
            self,
            texts: list[str],
            source_language: str,
            target_language: str,
            message_type: MessageType,
            context_messages: list,
    ) -> list[str]:
        """
        将多条消息打包成一个 LLM request。

        :param texts: 待翻译文本列表（已过滤空值）
        :param source_language: 源语言
        :param target_language: 目标语言
        :param message_type: 消息类型
        :param context_messages: 历史上下文 messages
        :return: 与 texts 等长的译文列表
        :raises: 任何异常（调用方捕获后降级为单条翻译）
        """
        if source_language.lower() == "auto":
            source_language = ""

        n = len(texts)
        if source_language:
            intro = f"Translate the following {n} messages from {source_language} to {target_language}."
        else:
            intro = f"Translate the following {n} messages to {target_language}."

        numbered = "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))
        user_message = (
            f"{intro}\n"
            f"Return ONLY a JSON array with exactly {n} translated strings in the same order. "
            f"No explanations, no extra keys.\n\n"
            f"{numbered}"
        )

        # 如果有历史上下文，拼接到 user message 前面
        if context_messages:
            history_content = context_messages[0].get("content", "")
            if self._is_anthropic:
                user_message = f"<recent_chat_history>\n{history_content}\n</recent_chat_history>\n\n{user_message}"
            else:
                user_message = f"=== Recent Chat History ===\n{history_content}\n=== End of History ===\n\n---\n\n{user_message}"

        provider = self.translation_service_config.llm.provider or "OpenAI"
        model = self.translation_service_config.llm.model

        extra_body = None
        if provider == "OpenRouter" and ":" in model:
            base_model, suffix = model.split(":", 1)
            suffix_stripped = suffix.strip()
            suffix_lower = suffix_stripped.lower()
            if suffix_lower in _OPENROUTER_NATIVE_SUFFIXES:
                pass
            elif suffix_lower in _OPENROUTER_SORT_KEYWORDS:
                model = base_model
                extra_body = {"provider": {"sort": suffix_lower}}
            else:
                model = base_model
                provider_order = [s for p in suffix_stripped.split(",") if (s := p.strip())]
                extra_body = {"provider": {"order": provider_order}}

        # Gemini 3 系列是原生思考模型，显式降级 reasoning 到 minimal effort，避免思考 token 挤占批量译文输出
        if self._is_gemini3 and provider == "OpenRouter":
            extra_body = {**{"reasoning": {"effort": "minimal"}}, **(extra_body or {})}
            logger.debug(
                f"Gemini 3 model ({model}) detected: capping reasoning to minimal effort"
            )

        prefix = LLM_PROVIDERS_PREFIXES[provider]
        mapped_model = model if model.startswith(prefix) else prefix + model

        # 构建 system prompt（含上下文指导）
        system_prompt = self._build_batch_system_prompt(has_context=bool(context_messages))

        temperature = 1 if re.match(r"^(?:openai/)?gpt-5(?:[-.]|$)", model.lower()) else 0
        llm_params = {
            "model": mapped_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": self.translation_service_config.llm.max_tokens * n,
            "api_key": self.translation_service_config.llm.api_key,
            "num_retries": 0,
            "timeout": self.timeout,
        }
        if api_base := self.translation_service_config.llm.api_base:
            llm_params["api_base"] = api_base

        if self._is_gemini3 and provider != "OpenRouter":
            llm_params["reasoning_effort"] = "minimal"
            llm_params["drop_params"] = True
            logger.debug(
                f"Gemini 3 model ({model}) detected: sending reasoning_effort=minimal"
            )

        if extra_body:
            llm_params["extra_body"] = extra_body

        response = litellm.completion(**llm_params)
        content_str = (response.choices[0].message.content or "").strip()

        # 尝试解析 JSON 数组
        try:
            result = json.loads(content_str)
        except json.JSONDecodeError:
            # 清理可能的 markdown 代码块
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content_str)
            cleaned = m.group(1) if m else content_str
            result = json.loads(cleaned)

        if not isinstance(result, list) or len(result) != n:
            raise ValueError(
                f"Batch translation returned {type(result)} with length "
                f"{len(result) if isinstance(result, list) else 'N/A'}, expected list of {n}"
            )

        return [str(item) for item in result]

    def _build_batch_system_prompt(self, has_context: bool = False) -> str:
        """
        批量翻译专用 system prompt：要求模型返回严格的 JSON 数组。
        """
        prompt = (
            "You are a Minecraft-specific intelligent translation engine. "
            "You will receive a numbered list of chat messages. "
            "Translate each message naturally, preserving gaming slang, cultural nuances, "
            "and Minecraft formatting codes (e.g., §a, §l) exactly.\n"
        )

        if has_context:
            prompt += (
                "\n## Context Awareness\n\n"
                "A recent chat history is provided in the user message. "
                "Use it to understand ongoing conversations and maintain translation consistency.\n"
                "Note: Messages closer to the end are more likely to be relevant. "
                "Earlier messages may be unrelated — use your judgment.\n"
            )

        prompt += (
            "\nOutput Rules:\n"
            "1. Return ONLY a valid JSON array of strings.\n"
            "2. The array must contain exactly the same number of elements as the input messages, "
            "in the same order.\n"
            "3. Do NOT add explanations, keys, or any text outside the JSON array.\n"
            "4. Do NOT translate player names, server names, or Minecraft commands.\n"
            "5. For untranslatable content (e.g., keyboard mashing), keep the original text."
        )
        return prompt

    def _execute_traditional_translation(self, text, service, source_language, target_language):
        """
        Executes translation using the specified traditional service provider.

        Acts as a dispatcher to specific provider implementations (e.g., DeepL, Google).
        """

        traditional_config = self.translation_service_config.traditional
        traditional_api_key = (getattr(traditional_config, "api_key", None) or "").strip()
        service_lower = (service or "").strip().lower()

        dispatch_map: Dict[str, Callable[[str, str, str, str], str]] = {
            "deepl": self._translate_deepl,
            "google": self._translate_google,
            "yandex": self._translate_yandex,
            "alibaba": self._translate_alibaba,
            "caiyun": self._translate_caiyun,
            "youdao": self._translate_youdao,
            "bing": self._translate_bing,
            "sogou": self._translate_sogou,
            "iflyrec": self._translate_iflyrec,
        }

        if traditional_api_key and service_lower in dispatch_map:
            return dispatch_map[service_lower](text, traditional_api_key, source_language, target_language)
        else:
            translated_message = ts.translate_text(text, translator=service_lower,
                                                   from_language=source_language, to_language=target_language)
            if translated_message:
                return translated_message
            else:
                raise Exception(f"Traditional translation failed (no result returned from '{service}')")

    @staticmethod
    def _clean_language_code(language: str) -> str:
        return (language or "").strip()

    @classmethod
    def _is_auto_language(cls, language: str) -> bool:
        cleaned = cls._clean_language_code(language)
        return not cleaned or cleaned.lower() == "auto"

    @classmethod
    def _source_language_or_auto(cls, language: str) -> str:
        return "auto" if cls._is_auto_language(language) else cls._clean_language_code(language)

    @staticmethod
    def _parse_json_response(response, service: str):
        if response.status_code != 200:
            raise RuntimeError(
                f"{service} API translation failed: {response.status_code} {response.text}"
            )
        try:
            return response.json()
        except ValueError as error:
            raise RuntimeError(f"{service} API returned invalid JSON: {response.text}") from error

    @staticmethod
    def _split_api_key(api_key: str, parts: int, service: str) -> list[str]:
        values = api_key.split(":", parts - 1)
        if len(values) != parts or any(not value.strip() for value in values):
            raise ValueError(
                f"{service} API key must contain {parts} colon-separated fields. "
                "Please check your configuration."
            )
        return [value.strip() for value in values]

    def _translate_deepl(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        if api_key.endswith(":fx"):
            url = "https://api-free.deepl.com/v2/translate"
        else:
            url = "https://api.deepl.com/v2/translate"

        headers = {
            "Authorization": f"DeepL-Auth-Key {api_key}"
        }
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("DeepL target language cannot be empty")
        data = {
            "text": [text],
            "target_lang": target_language.upper(),
        }
        if not self._is_auto_language(source_language):
            data["source_lang"] = self._clean_language_code(source_language).upper()

        response = _http().post(url, headers=headers, data=data, timeout=timeout)
        body = self._parse_json_response(response, "DeepL")
        translations = body.get("translations") if isinstance(body, dict) else None
        if not translations or not translations[0].get("text"):
            raise RuntimeError(f"DeepL API returned no translation: {body}")
        return translations[0]["text"]

    def _translate_google(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        url = "https://translation.googleapis.com/language/translate/v2"
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Google target language cannot be empty")
        params = {
            "key": api_key,
            "q": text,
            "target": target_language,
            "format": "text",
        }
        if not self._is_auto_language(source_language):
            params["source"] = self._clean_language_code(source_language)

        response = _http().post(url, params=params, timeout=timeout)
        body = self._parse_json_response(response, "Google")
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(f"Google API returned an error: {body['error']}")
        try:
            translated = body["data"]["translations"][0]["translatedText"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"Google API returned no translation: {body}") from error
        if not translated:
            raise RuntimeError("Google API returned an empty translation")
        return translated

    def _translate_yandex(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        url = "https://translate.api.cloud.yandex.net/translate/v2/translate"
        folder_id = (
            getattr(self.translation_service_config.traditional, "folder_id", None) or ""
        ).strip()
        if not folder_id:
            raise ValueError(
                "Yandex Cloud folder ID is required for the paid API. "
                "Please configure it together with the API key."
            )
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Yandex target language cannot be empty")
        headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "folderId": folder_id,
            "texts": [text],
            "targetLanguageCode": target_language,
        }
        if not self._is_auto_language(source_language):
            data["sourceLanguageCode"] = self._clean_language_code(source_language)

        response = _http().post(url, headers=headers, json=data, timeout=timeout)
        body = self._parse_json_response(response, "Yandex")
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(f"Yandex API returned an error: {body['error']}")
        try:
            translated = body["translations"][0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"Yandex API returned no translation: {body}") from error
        if not translated:
            raise RuntimeError("Yandex API returned an empty translation")
        return translated

    def _translate_alibaba(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        access_key_id, access_key_secret = self._split_api_key(api_key, 2, "Alibaba")

        url = "https://mt.cn-hangzhou.aliyuncs.com/"
        source_language = self._source_language_or_auto(source_language)
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Alibaba target language cannot be empty")

        # 准备请求参数
        parameters = {
            'AccessKeyId': access_key_id,
            'Action': 'TranslateGeneral',
            'Format': 'JSON',
            'FormatType': 'text',
            'Scene': 'general',
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureNonce': str(uuid.uuid4()),
            'SignatureVersion': '1.0',
            'SourceLanguage': source_language,
            'SourceText': text,
            'TargetLanguage': target_language,
            'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'Version': '2018-10-12'
        }

        # RPC V2 requires RFC3986 encoding for each pair and then encoding the
        # complete canonical query string once more in the string to sign.
        sorted_parameters = sorted(parameters.items(), key=lambda item: item[0])
        canonicalized_query_string = "&".join(
            f"{quote(str(key), safe='-_.~')}={quote(str(value), safe='-_.~')}"
            for key, value in sorted_parameters
        )
        string_to_sign = "GET&%2F&" + quote(canonicalized_query_string, safe="-_.~")

        # 计算签名
        h = hmac.new((access_key_secret + '&').encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        signature = base64.b64encode(h.digest()).decode('utf-8')

        # 添加签名到参数中
        parameters['Signature'] = signature

        # 发送请求
        response = _http().get(url, params=parameters, timeout=timeout)
        body = self._parse_json_response(response, "Alibaba")
        if str(body.get("Code", "200")) != "200":
            raise RuntimeError(f"Alibaba API returned an error: {body}")
        translated = body.get("Data", {}).get("Translated")
        if not translated:
            raise RuntimeError(f"Alibaba API returned no translation: {body}")
        return translated

    def _translate_caiyun(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        url = "https://api.interpreter.caiyunai.com/v1/translator"
        source_language = self._source_language_or_auto(source_language)
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Caiyun target language cannot be empty")
        headers = {
            "Content-Type": "application/json",
            "X-Authorization": f"token {api_key}"
        }
        payload = {
            "source": [text],
            "trans_type": f"{source_language}2{target_language}",
        }
        if source_language == "auto":
            payload["detect"] = True

        response = _http().post(url, headers=headers, json=payload, timeout=timeout)
        body = self._parse_json_response(response, "Caiyun")
        if isinstance(body, dict) and body.get("code") not in (None, 0, "0"):
            raise RuntimeError(f"Caiyun API returned an error: {body}")
        try:
            translated = body["target"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"Caiyun API returned no translation: {body}") from error
        if not translated:
            raise RuntimeError("Caiyun API returned an empty translation")
        return translated

    def _translate_youdao(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        url = "https://openapi.youdao.com/api"
        app_key, app_secret = self._split_api_key(api_key, 2, "Youdao")
        source_language = self._source_language_or_auto(source_language)
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Youdao target language cannot be empty")

        def encrypt(sign_str):
            hash_algorithm = hashlib.sha256()
            hash_algorithm.update(sign_str.encode('utf-8'))
            return hash_algorithm.hexdigest()

        def truncate(q):
            if q is None:
                return None
            size = len(q)
            return q if size <= 20 else q[0:10] + str(size) + q[size - 10:size]

        salt = str(uuid.uuid4())
        curtime = str(int(time.time()))
        sign = encrypt(app_key + truncate(text) + salt + curtime + app_secret)

        data = {
            'q': text,
            'from': source_language,
            'to': target_language,
            'appKey': app_key,
            'salt': salt,
            'sign': sign,
            'signType': "v3",
            'curtime': curtime,
        }

        response = _http().post(url, data=data, timeout=timeout)
        body = self._parse_json_response(response, "Youdao")
        if str(body.get("errorCode", "0")) != "0":
            raise RuntimeError(f"Youdao API returned an error: {body}")
        try:
            translated = body["translation"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"Youdao API returned no translation: {body}") from error
        if not translated:
            raise RuntimeError("Youdao API returned an empty translation")
        return translated

    def _translate_bing(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        timeout = self.timeout
        endpoint = "https://api.cognitive.microsofttranslator.com/translate"
        headers = {
            'Ocp-Apim-Subscription-Key': api_key,
            'Content-type': 'application/json'
        }
        region = (getattr(self.translation_service_config.traditional, "region", None) or "").strip()
        if region:
            headers['Ocp-Apim-Subscription-Region'] = region
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Bing target language cannot be empty")
        params = {
            'api-version': '3.0',
            'to': target_language,
        }
        if not self._is_auto_language(source_language):
            params['from'] = self._clean_language_code(source_language)

        body = [{'text': text}]
        response = _http().post(endpoint, headers=headers, params=params, json=body, timeout=timeout)
        response_body = self._parse_json_response(response, "Bing")
        try:
            translated = response_body[0]["translations"][0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError(f"Bing API returned no translation: {response_body}") from error
        if not translated:
            raise RuntimeError("Bing API returned an empty translation")
        return translated

    def _translate_sogou(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        """Call the Sogou DeepI paid text translation API."""
        pid, secret_key = self._split_api_key(api_key, 2, "Sogou")
        salt = str(uuid.uuid4())
        source_language = self._source_language_or_auto(source_language)
        target_language = self._clean_language_code(target_language)
        if not target_language:
            raise ValueError("Sogou target language cannot be empty")
        sign = hashlib.md5(f"{pid}{text}{salt}{secret_key}".encode("utf-8")).hexdigest()
        response = _http().post(
            "https://fanyi.sogou.com/reventondc/api/sogouTranslate",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "q": text,
                "from": source_language,
                "to": target_language,
                "pid": pid,
                "salt": salt,
                "sign": sign,
            },
            timeout=self.timeout,
        )
        body = self._parse_json_response(response, "Sogou")
        if str(body.get("errorCode", "0")) != "0":
            raise RuntimeError(f"Sogou API returned an error: {body}")
        translated = body.get("translation")
        if isinstance(translated, list):
            translated = "".join(str(item) for item in translated)
        if not translated:
            raise RuntimeError(f"Sogou API returned no translation: {body}")
        return str(translated)

    def _translate_iflyrec(self, text: str, api_key: str, source_language: str, target_language: str) -> str:
        """Call the iFLYTEK Machine Translation v1 paid HTTP API.

        The traditional service field uses ``app_id:api_key:api_secret`` as
        its compact credential format because the UI has one API key field.
        """
        app_id, api_key_value, api_secret = self._split_api_key(api_key, 3, "Iflyrec")
        if len(text) > 5000:
            raise ValueError("Iflyrec API accepts at most 5000 characters per request")

        def convert_language(language: str) -> str:
            language = self._clean_language_code(language)
            if not language:
                raise ValueError("Iflyrec language cannot be empty")
            if language.lower() == "auto":
                raise ValueError("Iflyrec paid API requires an explicit source language")
            return "cn" if language.lower() in {"zh", "zh-cn", "zh-hans"} else language

        source_language = convert_language(source_language)
        target_language = convert_language(target_language)
        body = {
            "header": {
                "app_id": app_id,
                "status": 3,
            },
            "parameter": {
                "its": {
                    "from": source_language,
                    "to": target_language,
                    "result": {},
                }
            },
            "payload": {
                "input_data": {
                    "encoding": "utf8",
                    "status": 3,
                    "text": base64.b64encode(text.encode("utf-8")).decode("ascii"),
                }
            },
        }

        host = "itrans.xf-yun.com"
        path = "/v1/its"
        date = formatdate(usegmt=True)
        request_line = "POST /v1/its HTTP/1.1"
        signature_origin = f"host: {host}\ndate: {date}\n{request_line}"
        signature = base64.b64encode(
            hmac.new(
                api_secret.encode("utf-8"),
                signature_origin.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("ascii")
        authorization_origin = (
            f'api_key="{api_key_value}",algorithm="hmac-sha256",'
            f'headers="host date request-line",signature="{signature}"'
        )
        params = {
            "authorization": base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii"),
            "host": host,
            "date": date,
        }
        response = _http().post(
            f"https://{host}{path}",
            params=params,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json,version=1.0",
            },
            json=body,
            timeout=self.timeout,
        )
        response_body = self._parse_json_response(response, "Iflyrec")
        response_header = response_body.get("header", {})
        if str(response_header.get("code", "0")) != "0":
            raise RuntimeError(f"Iflyrec API returned an error: {response_body}")
        try:
            encoded_result = response_body["payload"]["result"]["text"]
            result = json.loads(base64.b64decode(encoded_result).decode("utf-8"))
            translated = result["trans_result"]["dst"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Iflyrec API returned no translation: {response_body}") from error
        if not translated:
            raise RuntimeError("Iflyrec API returned an empty translation")
        return translated
