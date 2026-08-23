# Copyright (C) 2026 LiJiaHua1024
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

"""轻量 LLM 网关：以最小依赖实现 litellm.completion() 的兼容子集。

仅实现本项目实际使用的同步、非流式 chat completion 路径，并覆盖
``translator.LLM_PROVIDERS_PREFIXES`` 声明的全部 provider 前缀。
请求经 ``requests`` 直接发送到各服务商 HTTP API，响应归一化为与
litellm 兼容的对象（``choices[0].message.content`` 与
``model_dump()["usage"]``）。

与 litellm 的差异（有意为之，均不缩减 provider 覆盖范围）：
- 不支持 streaming / 回调 / 工具调用（本项目未使用）。
- 错误消息文案与 litellm 不同，但异常类型同样是 Exception 子类，
  上层 ``message_processor`` 的通用捕获逻辑不变。
- ``watson/`` 前缀在 litellm 中实际不被识别（当前版本直接报错），
  此处按 watsonx.ai 的 HTTP API 正确实现。
- github_copilot 不再触发交互式设备授权流：无 API Key 时直接报错。
- 其余 provider 的端点、认证头、请求体与响应解析均按 litellm 1.96 的
  非流式 chat 路径移植（见各 handler 注释中的对应源码位置）。
"""

import hashlib
import hmac
import json
import os
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

# ═══════════════════════════════════════════════════════════════════════
# 响应对象
# ═══════════════════════════════════════════════════════════════════════


class _GatewayMessage:
    def __init__(self, content: str):
        self.content = content


class _GatewayChoice:
    def __init__(self, content: str):
        self.message = _GatewayMessage(content)


class ModelResponse:
    """litellm ``ModelResponse`` 的兼容子集。

    本项目只读取 ``choices[0].message.content`` 与
    ``model_dump().get("usage")``。
    """

    def __init__(self, content: str, usage: Optional[dict] = None,
                 model: Optional[str] = None, finish_reason: Optional[str] = None):
        self.choices = [_GatewayChoice(content or "")]
        self.usage = usage or {}
        self.model = model
        self._finish_reason = finish_reason

    def model_dump(self) -> dict:
        choice = {
            "message": {"content": self.choices[0].message.content},
            "finish_reason": self._finish_reason,
        }
        return {
            "choices": [choice],
            "usage": self.usage,
            "model": self.model,
        }


class GatewayError(Exception):
    """LLM 请求失败（HTTP 错误、超时、缺少凭证等）。"""


class GatewayAuthenticationError(GatewayError):
    """缺少或无法使用 API 凭证。"""


# ═══════════════════════════════════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════════════════════════════════

def _strip_model_prefix(model: str, prefix: str) -> str:
    if model.startswith(prefix):
        return model[len(prefix):]
    return model


def _clean_messages(messages: list) -> list:
    """仅保留本项目使用的字符串内容消息，其余内容块原样透传。"""
    return [dict(m) for m in (messages or []) if isinstance(m, dict)]


def _env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _http_post(url: str, *, headers: dict, payload: dict, timeout: float) -> dict:
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise GatewayError(f"LLM request timed out after {timeout:g}s: {url}") from exc
    except requests.exceptions.RequestException as exc:
        raise GatewayError(f"LLM request failed: {exc}") from exc
    if response.status_code >= 400:
        raise GatewayError(
            f"LLM request failed (HTTP {response.status_code}): "
            f"{response.text[:500]}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise GatewayError(
            f"LLM returned an invalid response (HTTP {response.status_code}): "
            f"{response.text[:300]}"
        ) from exc


def _usage(usage: Optional[dict]) -> dict:
    usage = usage or {}
    return {k: v for k, v in usage.items() if v is not None}


# ═══════════════════════════════════════════════════════════════════════
# OpenAI 兼容路径
# （端点与认证信息对齐 litellm 1.96：constants.py openai_compatible_endpoints /
#  get_llm_provider_logic.py base_url 映射 / 各 llms/<provider>/chat/transformation.py）
# ═══════════════════════════════════════════════════════════════════════

class _OpenAICompatProvider:
    """OpenAI 兼容的 chat/completions 调用。"""

    def __init__(self, name: str, base_url: Optional[str], *,
                 env_keys: tuple = (), fake_key: bool = False,
                 openrouter: bool = False, copilot: bool = False,
                 hf: bool = False, ensure_v1: bool = False):
        self.name = name
        self.base_url = base_url
        self.env_keys = env_keys
        self.fake_key = fake_key          # LM Studio / hosted_vllm 无 key，用占位符
        self.openrouter = openrouter      # 追加 HTTP-Referer / X-Title 与 usage.include
        self.copilot = copilot            # GitHub Copilot 专用头
        self.hf = hf                      # HuggingFace 路由 URL 构造
        self.ensure_v1 = ensure_v1        # mistral：base 无 /v1 时追加

    def complete(self, model: str, messages: list, *, temperature, max_tokens,
                 api_key: Optional[str], api_base: Optional[str], timeout: float,
                 extra_body: Optional[dict], reasoning_effort: Optional[str] = None,
                 **kwargs) -> ModelResponse:
        key = (api_key or "").strip() or _env(*self.env_keys) or ""
        if not key and not self.fake_key:
            raise GatewayAuthenticationError(
                f"Missing API key for provider '{self.name}'. "
                f"Set it in the configuration or the {self.env_keys[0]} environment variable."
            )
        if self.fake_key and not key:
            key = "fake-api-key"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        if self.copilot:
            headers.update(_copilot_headers())
            headers["X-Initiator"] = "user" if _copilot_is_user_initiated(messages) else "agent"
            messages = _copilot_transform_messages(messages)
        if self.openrouter:
            headers.setdefault("HTTP-Referer", _env("OR_SITE_URL") or "https://litellm.ai")
            headers.setdefault("X-Title", _env("OR_APP_NAME") or "liteLLM")

        payload: Dict[str, Any] = {
            "model": _strip_model_prefix(model, self.name + "/"),
            "messages": _clean_messages(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if reasoning_effort is not None and self.name == "openai":
            payload["reasoning_effort"] = reasoning_effort
        if self.openrouter:
            payload["usage"] = {"include": True}
        if extra_body:
            payload.update(extra_body)

        url = self._build_url(model, api_base)
        body = _http_post(url, headers=headers, payload=payload, timeout=timeout)
        return _parse_openai_response(body, model)

    def _build_url(self, model: str, api_base: Optional[str]) -> str:
        base = (api_base or "").strip() or self.base_url
        if self.hf:
            stripped = _strip_model_prefix(model, self.name + "/")
            if stripped.startswith(("http://", "https://")):
                base = stripped
            elif not (api_base or "").strip():
                base = _build_hf_url(stripped)
        if not base:
            raise GatewayError(
                f"Provider '{self.name}' requires an api_base URL to be configured."
            )
        if self.ensure_v1 and not base.rstrip("/").endswith("/v1"):
            base = base.rstrip("/") + "/v1"
        if self.hf:
            return _build_chat_completion_url(base)
        return f"{base.rstrip('/')}/chat/completions"


def _build_chat_completion_url(base: str) -> str:
    """HuggingFace：与 litellm 的 _build_chat_completion_url 一致。"""
    base = base.rstrip("/")
    if base.endswith("/v1"):
        return base + "/chat/completions"
    if not base.endswith("/chat/completions"):
        return base + "/v1/chat/completions"
    return base


def _build_hf_url(model: str) -> str:
    """HuggingFace 无显式 api_base 时的路由 URL（litellm get_complete_url）。"""
    if "/" in model:
        provider, remaining = model.split("/", 1)
        if "/" in remaining:
            if provider == "hf-inference":
                return f"https://router.huggingface.co/{provider}/models/{model}/v1/chat/completions"
            if provider == "novita":
                return f"https://router.huggingface.co/{provider}/v3/openai/chat/completions"
            if provider == "fireworks-ai":
                return f"https://router.huggingface.co/{provider}/inference/v1/chat/completions"
            return f"https://router.huggingface.co/{provider}/v1/chat/completions"
    return "https://router.huggingface.co/v1/chat/completions"


def _copilot_headers() -> dict:
    """GitHub Copilot 默认头（litellm github_copilot/common_utils.py）。"""
    return {
        "content-type": "application/json",
        "copilot-integration-id": "vscode-chat",
        "editor-version": "vscode/1.95.0",
        "editor-plugin-version": "copilot-chat/0.26.7",
        "user-agent": "GitHubCopilotChat/0.26.7",
        "openai-intent": "conversation-panel",
        "x-github-api-version": "2025-04-01",
        "x-request-id": _uuid4(),
        "x-vscode-user-agent-library-version": "electron-fetch",
    }


def _copilot_transform_messages(messages: list) -> list:
    """GitHub Copilot 默认将 system 消息转为 assistant 消息。"""
    transformed = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "system":
            item["role"] = "assistant"
        transformed.append(item)
    return transformed


def _copilot_is_user_initiated(messages: list) -> bool:
    """X-Initiator：存在 assistant/tool 消息时为 agent，否则 user。"""
    for message in messages:
        if message.get("role") in ("tool", "assistant"):
            return False
    return True


def _uuid4() -> str:
    try:
        return str(_uuid_module.uuid4())
    except Exception:
        return f"{int(time.time() * 1000)}-{id(object())}"


def _parse_openai_response(body: dict, model: str) -> ModelResponse:
    """标准 OpenAI chat/completions 响应解析。"""
    try:
        content = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise GatewayError(f"LLM returned an unparsable response: {json.dumps(body)[:300]}") from exc
    usage = body.get("usage")
    return ModelResponse(content=content, usage=_usage(usage), model=model,
                         finish_reason=body.get("choices", [{}])[0].get("finish_reason"))


# ═══════════════════════════════════════════════════════════════════════
# Anthropic（litellm/llms/anthropic/chat/transformation.py）
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_ANTHROPIC_MAX_TOKENS = 4096


def _anthropic_complete(model: str, messages: list, *, temperature, max_tokens,
                        api_key: Optional[str], api_base: Optional[str], timeout: float,
                        **kwargs) -> ModelResponse:
    key = (api_key or "").strip() or _env("ANTHROPIC_API_KEY")
    if not key:
        raise GatewayAuthenticationError(
            "Missing API key for provider 'Anthropic'. "
            "Set it in the configuration or the ANTHROPIC_API_KEY environment variable."
        )

    base = (api_base or "").strip() or _env("ANTHROPIC_API_BASE", "ANTHROPIC_BASE_URL")
    base = base or "https://api.anthropic.com/v1/messages"
    if not base.rstrip("/").endswith("/v1/messages"):
        base = base.rstrip("/") + "/v1/messages"

    headers = {
        "anthropic-version": "2023-06-01",
        "accept": "application/json",
        "content-type": "application/json",
    }
    if key.startswith("sk-ant-") and not key.startswith("sk-ant-oauth"):
        headers["x-api-key"] = key
    else:
        headers["authorization"] = f"Bearer {key}"
        headers["anthropic-dangerous-direct-browser-access"] = "true"

    system_parts, anthropic_messages = _anthropic_messages(messages)
    payload: Dict[str, Any] = {
        "model": _strip_model_prefix(model, "anthropic/"),
        "messages": anthropic_messages,
        "max_tokens": max_tokens or _DEFAULT_ANTHROPIC_MAX_TOKENS,
    }
    if system_parts:
        payload["system"] = system_parts
    if temperature is not None:
        payload["temperature"] = temperature

    body = _http_post(base, headers=headers, payload=payload, timeout=timeout)
    content = "".join(
        block.get("text", "")
        for block in body.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    )
    usage_raw = body.get("usage") or {}
    usage = {
        "prompt_tokens": usage_raw.get("input_tokens"),
        "completion_tokens": usage_raw.get("output_tokens"),
        "total_tokens": None,
    }
    usage = {k: v for k, v in usage.items() if v is not None}
    if "prompt_tokens" in usage and "completion_tokens" in usage:
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return ModelResponse(content=content, usage=usage, model=model,
                         finish_reason=body.get("stop_reason"))


def _anthropic_messages(messages: list) -> tuple[Optional[list], list]:
    """OpenAI messages → (system, anthropic messages)。

    system 提取为顶层数组；user/assistant 连续同角色合并。
    """
    system_texts: List[str] = []
    result: List[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if isinstance(content, str):
                system_texts.append(content)
            continue
        if role not in ("user", "assistant"):
            continue
        text = content if isinstance(content, str) else (
            "".join(part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("type") == "text")
            if isinstance(content, list) else str(content or "")
        )
        if not text:
            continue
        if result and result[-1]["role"] == role:
            result[-1]["content"] += f"\n\n{text}"
        else:
            result.append({"role": role, "content": text})
    system_parts = [{"type": "text", "text": text} for text in system_texts] or None
    return system_parts, result


# ═══════════════════════════════════════════════════════════════════════
# Azure OpenAI（litellm/llms/azure/azure.py + openai/lib/azure.py）
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_AZURE_API_VERSION = "2025-02-01-preview"


def _azure_complete(model: str, messages: list, *, temperature, max_tokens,
                    api_key: Optional[str], api_base: Optional[str], timeout: float,
                    **kwargs) -> ModelResponse:
    key = (api_key or "").strip() or _env("AZURE_OPENAI_API_KEY", "AZURE_API_KEY")
    if not key:
        raise GatewayAuthenticationError(
            "Missing API key for provider 'Azure'. "
            "Set it in the configuration or the AZURE_OPENAI_API_KEY environment variable."
        )
    base = (api_base or "").strip() or _env("AZURE_API_BASE")
    if not base:
        raise GatewayError(
            "Provider 'Azure' requires an api_base URL (Azure resource endpoint)."
        )
    deployment = _strip_model_prefix(model, "azure/")
    if "/openai/deployments/" in base:
        url = f"{base.rstrip('/')}/chat/completions"
    else:
        url = (f"{base.rstrip('/')}/openai/deployments/"
               f"{urllib.parse.quote(deployment, safe='')}/chat/completions")
    api_version = _env("AZURE_API_VERSION") or _DEFAULT_AZURE_API_VERSION
    url += f"?api-version={urllib.parse.quote(api_version, safe='')}"

    headers = {"Content-Type": "application/json", "api-key": key}
    payload: Dict[str, Any] = {
        "model": deployment,
        "messages": _clean_messages(messages),
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    body = _http_post(url, headers=headers, payload=payload, timeout=timeout)
    return _parse_openai_response(body, model)


# ═══════════════════════════════════════════════════════════════════════
# Gemini（AI Studio）
# （litellm/llms/gemini/ 的 payload 转换）
# ═══════════════════════════════════════════════════════════════════════

# 常量对齐 litellm constants.py
_REASONING_EFFORT_THINKING_BUDGET = {
    "minimal": 128,
    "low": 640,
    "medium": 2048,
    "high": 4096,
    "disable": 0,
    "none": 0,
}
_REASONING_EFFORT_BUDGET_GEMINI_2_5_FLASH = 1
_REASONING_EFFORT_BUDGET_GEMINI_2_5_PRO = 128


def _is_gemini_3(model: str) -> bool:
    return "gemini-3" in (model or "").lower()


def _gemini_payload(model: str, messages: list, *, temperature, max_tokens,
                    reasoning_effort: Optional[str]) -> dict:
    contents, system_text = _gemini_contents(messages)
    payload: Dict[str, Any] = {}
    if system_text:
        payload["system_instruction"] = {"parts": [{"text": system_text}]}
    payload["contents"] = contents
    generation_config: Dict[str, Any] = {}
    if temperature is not None:
        generation_config["temperature"] = temperature
    if max_tokens is not None:
        generation_config["maxOutputTokens"] = max_tokens
    if reasoning_effort:
        thinking_config = _gemini_thinking_config(model, reasoning_effort)
        if thinking_config:
            generation_config["thinkingConfig"] = thinking_config
    if generation_config:
        payload["generationConfig"] = generation_config
    return payload


def _gemini_thinking_config(model: str, reasoning_effort: str) -> Optional[dict]:
    """reasoning_effort → thinkingConfig（对齐 litellm 的
    _map_reasoning_effort_to_thinking_level / _map_reasoning_effort_to_thinking_budget）。"""
    effort = reasoning_effort.lower()
    if effort not in _REASONING_EFFORT_THINKING_BUDGET:
        raise GatewayError(f"Invalid reasoning effort: {reasoning_effort}")
    if _is_gemini_3(model):
        is_flash = "flash" in model.lower() and "gemini-3" in model.lower()
        if effort == "minimal":
            # 部分 Gemini 3 型号（如 gemini-3.7-flash）不支持 MINIMAL 思考档，统一映射为全系可用的 low
            level = "low"
        elif effort == "medium":
            level = "medium" if (is_flash or "gemini-3.1-pro-preview" in model.lower()) else "high"
        else:
            level = effort
        include_thoughts = effort not in ("disable", "none")
        return {"thinkingLevel": level, "includeThoughts": include_thoughts}
    if effort == "minimal":
        if "gemini-2.5-flash-lite" in model.lower():
            budget = _REASONING_EFFORT_BUDGET_GEMINI_2_5_FLASH
        elif "gemini-2.5-pro" in model.lower():
            budget = _REASONING_EFFORT_BUDGET_GEMINI_2_5_PRO
        elif "gemini-2.5-flash" in model.lower():
            budget = _REASONING_EFFORT_BUDGET_GEMINI_2_5_FLASH
        else:
            budget = 128
    else:
        budget = _REASONING_EFFORT_THINKING_BUDGET[effort]
    return {"thinkingBudget": budget, "includeThoughts": effort not in ("disable", "none")}


def _gemini_contents(messages: list) -> tuple[list, str]:
    """OpenAI messages → Gemini contents（role user/model，连续同角色合并）。"""
    system_texts: List[str] = []
    contents: List[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if isinstance(content, str):
                system_texts.append(content)
            continue
        gemini_role = "model" if role == "assistant" else "user"
        if isinstance(content, list):
            parts = [{"text": part.get("text", "")} for part in content
                     if isinstance(part, dict) and part.get("text")]
        else:
            parts = [{"text": content or " "}]
        if contents and contents[-1]["role"] == gemini_role:
            for part in parts:
                contents[-1]["parts"].append(part)
        else:
            contents.append({"role": gemini_role, "parts": parts})
    if not contents:
        contents.append({"role": "user", "parts": [{"text": " "}]})
    return contents, "\n\n".join(system_texts)


def _gemini_complete(model: str, messages: list, *, temperature, max_tokens,
                     api_key: Optional[str], api_base: Optional[str], timeout: float,
                     reasoning_effort: Optional[str] = None, **kwargs) -> ModelResponse:
    key = (api_key or "").strip() or _env("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not key:
        raise GatewayAuthenticationError(
            "Missing API key for provider 'Gemini'. "
            "Set it in the configuration or the GEMINI_API_KEY environment variable."
        )
    model_name = _strip_model_prefix(model, "gemini/")
    api_version = "v1alpha" if _is_gemini_3(model_name) else "v1beta"
    base = (api_base or "").strip()
    if base:
        url = f"{base.rstrip('/')}/models/{urllib.parse.quote(model_name, safe='-_.')}:generateContent"
    else:
        url = (f"https://generativelanguage.googleapis.com/{api_version}/models/"
               f"{urllib.parse.quote(model_name, safe='-_.')}:generateContent")
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    payload = _gemini_payload(model_name, messages, temperature=temperature,
                              max_tokens=max_tokens, reasoning_effort=reasoning_effort)
    body = _http_post(url, headers=headers, payload=payload, timeout=timeout)
    return _parse_gemini_response(body, model)


def _parse_gemini_response(body: dict, model: str) -> ModelResponse:
    try:
        parts = body["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GatewayError(f"Gemini returned an unparsable response: {json.dumps(body)[:300]}") from exc
    content = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    meta = body.get("usageMetadata") or {}
    usage = {
        "prompt_tokens": meta.get("promptTokenCount"),
        "completion_tokens": meta.get("candidatesTokenCount"),
        "total_tokens": meta.get("totalTokenCount"),
    }
    usage = {k: v for k, v in usage.items() if v is not None}
    finish_reason = None
    try:
        finish_reason = body["candidates"][0].get("finishReason")
    except (KeyError, IndexError, TypeError):
        pass
    return ModelResponse(content=content, usage=usage, model=model, finish_reason=finish_reason)


# ═══════════════════════════════════════════════════════════════════════
# AWS SigV4（botocore SigV4Auth 的纯标准库实现，用于 Bedrock / SageMaker）
# ═══════════════════════════════════════════════════════════════════════

def _aws_credentials(api_key: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """返回 (access_key, secret_key, session_token)。

    与 litellm 一致：仅读取环境变量（AWS_ACCESS_KEY_ID 等），
    api_key 参数不作为 AWS 静态凭证使用。
    """
    access_key = _env("AWS_ACCESS_KEY_ID")
    secret_key = _env("AWS_SECRET_ACCESS_KEY")
    session_token = _env("AWS_SESSION_TOKEN")
    return access_key, secret_key, session_token


def _aws_region(model: str) -> str:
    region = _env("AWS_REGION_NAME", "AWS_REGION")
    if region:
        return region
    parts = model.split(":")
    if len(parts) > 3 and parts[3]:
        return parts[3]
    return "us-west-2"


def _sigv4_headers(method: str, url: str, body: bytes, *,
                   access_key: str, secret_key: str, session_token: Optional[str],
                   region: str, service: str, extra_headers: Optional[dict] = None) -> dict:
    """SigV4 签名（botocore SigV4Auth 算法）。"""
    parsed = urllib.parse.urlsplit(url)
    host = parsed.netloc
    path = parsed.path or "/"
    query = parsed.query

    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers = {
        "host": host,
        "content-type": "application/json",
        "x-amz-date": amz_date,
    }
    if session_token:
        headers["x-amz-security-token"] = session_token
    if extra_headers:
        for name, value in extra_headers.items():
            if name.lower() not in ("host", "content-type", "x-amz-date", "x-amz-security-token"):
                headers[name.lower()] = value

    payload_hash = hashlib.sha256(body).hexdigest()
    signed_headers = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))

    canonical_request = (
        f"{method}\n{path}\n{query}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )

    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_key).encode(), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    result = {
        "Authorization": authorization,
        "x-amz-date": amz_date,
        "Content-Type": "application/json",
    }
    if session_token:
        result["x-amz-security-token"] = session_token
    return result


# ═══════════════════════════════════════════════════════════════════════
# Bedrock（litellm/llms/bedrock/）
# ═══════════════════════════════════════════════════════════════════════

_BEDROCK_CONVERSE_MODEL_KEYWORDS = ("anthropic.claude", "amazon.nova")
_INVOKE_PROVIDERS = ("anthropic", "cohere", "ai21", "mistral", "meta", "llama", "amazon", "deepseek_r1")


def _bedrock_route(model: str) -> str:
    """与 litellm get_bedrock_route 对齐：显式前缀 → converse 列表 → invoke。"""
    stripped = _strip_model_prefix(model, "bedrock/")
    if stripped.startswith("converse/"):
        return "converse"
    if stripped.startswith("invoke/"):
        return "invoke"
    if stripped.startswith("openai/"):
        return "openai"
    if stripped.startswith("nova-2/") or stripped.startswith("nova/"):
        return "converse"
    if ":application-inference-profile/" in stripped:
        return "converse"
    base_model = stripped.split(":")[0].split("/")[-1]
    if base_model.startswith(_BEDROCK_CONVERSE_MODEL_KEYWORDS):
        return "converse"
    return "invoke"


def _bedrock_complete(model: str, messages: list, *, temperature, max_tokens,
                      api_key: Optional[str], api_base: Optional[str], timeout: float,
                      **kwargs) -> ModelResponse:
    access_key, secret_key, session_token = _aws_credentials(api_key)
    if not access_key or not secret_key:
        raise GatewayAuthenticationError(
            "Missing AWS credentials for provider 'Bedrock'. Set AWS_ACCESS_KEY_ID "
            "and AWS_SECRET_ACCESS_KEY environment variables."
        )
    region = _aws_region(model)
    route = _bedrock_route(model)
    model_id = _strip_model_prefix(model, "bedrock/")
    if model_id.startswith(("converse/", "invoke/", "openai/")):
        model_id = model_id.split("/", 1)[1]

    endpoint = (api_base or "").strip() or _env("AWS_BEDROCK_RUNTIME_ENDPOINT")
    endpoint = endpoint or f"https://bedrock-runtime.{region}.amazonaws.com"
    endpoint = endpoint.rstrip("/")

    if route == "converse":
        url = f"{endpoint}/model/{urllib.parse.quote(model_id, safe='')}/converse"
        payload = _bedrock_converse_payload(model_id, messages, temperature=temperature,
                                            max_tokens=max_tokens)
        body, response_headers = _aws_post(url, payload, access_key, secret_key,
                                           session_token, region, "bedrock", timeout)
        return _parse_bedrock_converse_response(body, model)
    if route == "openai":
        url = f"{endpoint}/model/{urllib.parse.quote(model_id, safe='')}/invoke"
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": _clean_messages(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        body, response_headers = _aws_post(url, payload, access_key, secret_key,
                                           session_token, region, "bedrock", timeout)
        return _parse_openai_response(body, model)
    # invoke 路径
    provider = _bedrock_invoke_provider(model_id)
    url = f"{endpoint}/model/{urllib.parse.quote(model_id, safe='')}/invoke"
    if provider == "anthropic":
        payload = _bedrock_claude_invoke_payload(model_id, messages,
                                                 temperature=temperature, max_tokens=max_tokens)
    else:
        prompt = _bedrock_invoke_prompt(model_id, messages)
        payload = {"prompt": prompt}
        if provider == "amazon":
            payload = {"inputText": prompt, "textGenerationConfig": {}}
            if max_tokens is not None:
                payload["textGenerationConfig"]["maxTokenCount"] = max_tokens
            if temperature is not None:
                payload["textGenerationConfig"]["temperature"] = temperature
        else:
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature
    body, response_headers = _aws_post(url, payload, access_key, secret_key,
                                       session_token, region, "bedrock", timeout)
    return _parse_bedrock_invoke_response(body, model, provider, response_headers)


def _aws_post(url: str, payload: dict, access_key: str, secret_key: str,
              session_token: Optional[str], region: str, service: str,
              timeout: float) -> tuple[dict, dict]:
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = _sigv4_headers("POST", url, body_bytes, access_key=access_key,
                             secret_key=secret_key, session_token=session_token,
                             region=region, service=service)
    try:
        response = requests.post(url, headers=headers, data=body_bytes, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise GatewayError(f"LLM request failed: {exc}") from exc
    if response.status_code >= 400:
        raise GatewayError(
            f"LLM request failed (HTTP {response.status_code}): {response.text[:500]}"
        )
    try:
        return response.json(), dict(response.headers)
    except ValueError as exc:
        raise GatewayError(f"LLM returned an invalid response: {response.text[:300]}") from exc


def _bedrock_converse_payload(model: str, messages: list, *, temperature, max_tokens) -> dict:
    """Bedrock Converse API payload。"""
    system_blocks = []
    bedrock_messages: List[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "system":
            if isinstance(content, str) and content:
                system_blocks.append({"text": content})
            continue
        if role not in ("user", "assistant"):
            continue
        text = content if isinstance(content, str) else (
            "".join(part.get("text", "") for part in content
                    if isinstance(part, dict) and part.get("text"))
            if isinstance(content, list) else str(content or "")
        )
        if not text:
            continue
        if bedrock_messages and bedrock_messages[-1]["role"] == role:
            bedrock_messages[-1]["content"].append({"text": text})
        else:
            bedrock_messages.append({"role": role, "content": [{"text": text}]})
    payload: Dict[str, Any] = {"messages": bedrock_messages}
    inference: Dict[str, Any] = {}
    if temperature is not None:
        inference["temperature"] = temperature
    if max_tokens is not None:
        inference["maxTokens"] = max_tokens
    if inference:
        payload["inferenceConfig"] = inference
    if system_blocks:
        payload["system"] = system_blocks
    return payload


def _parse_bedrock_converse_response(body: dict, model: str) -> ModelResponse:
    try:
        blocks = body["output"]["message"]["content"]
        content = "".join(block.get("text", "") for block in blocks
                          if isinstance(block, dict))
    except (KeyError, TypeError) as exc:
        raise GatewayError(f"Bedrock returned an unparsable response: {json.dumps(body)[:300]}") from exc
    usage_raw = body.get("usage") or {}
    prompt_tokens = usage_raw.get("inputTokens")
    completion_tokens = usage_raw.get("outputTokens")
    usage = {}
    if prompt_tokens is not None:
        usage["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        usage["completion_tokens"] = completion_tokens
    if "prompt_tokens" in usage and "completion_tokens" in usage:
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return ModelResponse(content=content, usage=usage, model=model,
                         finish_reason=body.get("stopReason"))


def _bedrock_invoke_provider(model_id: str) -> str:
    """从模型名推断 invoke provider（litellm get_bedrock_invoke_provider）。"""
    candidate = model_id
    if candidate.startswith("invoke/"):
        candidate = candidate[7:]
    parts = candidate.split(".")
    if parts[0] in _INVOKE_PROVIDERS:
        return parts[0]
    if "nova" in candidate.lower():
        return "nova"
    for provider in _INVOKE_PROVIDERS:
        if provider in candidate:
            return provider
    return "anthropic" if "claude" in candidate.lower() else parts[0]


def _bedrock_claude_invoke_payload(model: str, messages: list, *, temperature, max_tokens) -> dict:
    """Anthropic Messages 格式（invoke/anthropic.claude-*）。"""
    system_parts, anthropic_messages = _anthropic_messages(messages)
    payload: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": anthropic_messages,
        "max_tokens": max_tokens or 4096,
    }
    if system_parts:
        payload["system"] = system_parts
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content
                       if isinstance(part, dict) and part.get("text"))
    return content or ""


def _anthropic_invoke_prompt(messages: list) -> str:
    """anthropic_pt：\\n\\nHuman:/\\n\\nAssistant: 模板。"""
    prompt = ""
    for idx, message in enumerate(messages):
        role = message.get("role")
        content = _message_text(message.get("content"))
        if role == "user":
            prompt += f"\n\nHuman: {content}"
        elif role == "system":
            prompt += f"\n\nHuman: <admin>{content}</admin>"
        else:
            prompt += f"\n\nAssistant: {content}"
        if idx == 0 and role == "assistant":
            prompt = "\n\nHuman: " + prompt
    if not messages or messages[-1].get("role") != "assistant":
        prompt += "\n\nAssistant: "
    return prompt


def _titan_invoke_prompt(messages: list) -> str:
    """amazon_titan_pt：\\n\\nUser:/\\n\\nBot: 模板。"""
    prompt = ""
    for idx, message in enumerate(messages):
        role = message.get("role")
        content = _message_text(message.get("content"))
        if role == "user":
            prompt += f"\n\nUser: {content}"
        elif role == "system":
            prompt += f"\n\nUser: <admin>{content}</admin>"
        else:
            prompt += f"\n\nBot: {content}"
        if idx == 0 and role == "assistant":
            prompt = "\n\nUser: " + prompt
    if not messages or messages[-1].get("role") != "assistant":
        prompt += "\n\nBot: "
    return prompt


def _custom_prompt(messages: list, role_dict: dict, *,
                   initial_prompt_value: str = "", final_prompt_value: str = "",
                   bos_token: str = "", eos_token: str = "") -> str:
    """litellm custom_prompt 的忠实移植。"""
    prompt = bos_token + initial_prompt_value
    bos_open = True
    for message in messages:
        role = message.get("role")
        content = _message_text(message.get("content"))
        if role in ("system", "human") and not bos_open:
            prompt += bos_token
            bos_open = True
        pre = role_dict.get(role, {}).get("pre_message", "")
        post = role_dict.get(role, {}).get("post_message", "")
        prompt += pre + content + post
        if role == "assistant":
            prompt += eos_token
            bos_open = False
    prompt += final_prompt_value
    return prompt


def _mistral_invoke_prompt(messages: list) -> str:
    """mistral_instruct_pt。"""
    return _custom_prompt(
        messages,
        role_dict={
            "system": {"pre_message": "[INST] \n", "post_message": " [/INST]\n"},
            "user": {"pre_message": "[INST] ", "post_message": " [/INST]\n"},
            "assistant": {"pre_message": " ", "post_message": "</s> "},
        },
        initial_prompt_value="<s>",
    )


def _llama2_invoke_prompt(messages: list) -> str:
    """llama_2_chat_pt。"""
    return _custom_prompt(
        messages,
        role_dict={
            "system": {"pre_message": "[INST] <<SYS>>\n", "post_message": "\n<</SYS>>\n [/INST]\n"},
            "user": {"pre_message": "[INST] ", "post_message": " [/INST]\n"},
            "assistant": {"post_message": "\n"},
        },
        bos_token="<s>",
        eos_token="</s>",
    )


def _bedrock_invoke_prompt(model: str, messages: list) -> str:
    """invoke 非 Claude 模型的 prompt 模板（litellm prompt_factory bedrock 分支）。"""
    lower = model.lower()
    if "amazon.titan-text" in lower:
        return _titan_invoke_prompt(messages)
    if "mistral." in lower:
        return _mistral_invoke_prompt(messages)
    if "llama2" in lower and "chat" in lower:
        return _llama2_invoke_prompt(messages)
    if ("llama3" in lower or "llama4" in lower) and "instruct" in lower:
        return _llama3_template(messages)
    # 默认 anthropic Human:/Assistant:
    return _anthropic_invoke_prompt(messages)


def _llama3_template(messages: list) -> str:
    """Meta-Llama-3 chat template（hf_chat_template 的固定模板）。"""
    prompt = ""
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content
                              if isinstance(part, dict) and part.get("text"))
        content = content or ""
        if role == "system":
            prompt += "<|begin_of_text|>"
        prompt += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
    prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
    return prompt


def _parse_bedrock_invoke_response(body: dict, model: str, provider: str,
                                   headers: dict) -> ModelResponse:
    content = ""
    if provider == "anthropic":
        content = "".join(block.get("text", "") for block in body.get("content", [])
                          if isinstance(block, dict) and block.get("type") == "text")
    elif provider == "cohere":
        if "text" in body:
            content = body["text"]
        elif body.get("generations"):
            content = body["generations"][0].get("text", "")
    elif provider == "ai21":
        try:
            content = body["completions"][0]["data"]["text"]
        except (KeyError, IndexError, TypeError):
            content = ""
    elif provider in ("meta", "llama", "deepseek_r1"):
        content = body.get("generation", "")
    elif provider == "mistral":
        outputs = body.get("outputs") or []
        content = outputs[0].get("text", "") if outputs else ""
    elif provider == "amazon":
        results = body.get("results") or []
        content = results[0].get("outputText", "") if results else ""
    if not content:
        raise GatewayError(f"Bedrock returned no translation: {json.dumps(body)[:300]}")
    usage = {}
    try:
        prompt_tokens = int(headers.get("x-amzn-bedrock-input-token-count", 0) or 0)
        completion_tokens = int(headers.get("x-amzn-bedrock-output-token-count", 0) or 0)
    except (TypeError, ValueError):
        prompt_tokens = completion_tokens = 0
    if prompt_tokens or completion_tokens:
        usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                 "total_tokens": prompt_tokens + completion_tokens}
    return ModelResponse(content=content, usage=usage, model=model)


# ═══════════════════════════════════════════════════════════════════════
# SageMaker（litellm/llms/sagemaker/chat/transformation.py）
# ═══════════════════════════════════════════════════════════════════════

def _sagemaker_complete(model: str, messages: list, *, temperature, max_tokens,
                        api_key: Optional[str], api_base: Optional[str], timeout: float,
                        **kwargs) -> ModelResponse:
    access_key, secret_key, session_token = _aws_credentials(api_key)
    if not access_key or not secret_key:
        raise GatewayAuthenticationError(
            "Missing AWS credentials for provider 'SageMaker'. Set AWS_ACCESS_KEY_ID "
            "and AWS_SECRET_ACCESS_KEY environment variables."
        )
    region = _aws_region(model)
    endpoint_name = _strip_model_prefix(model, "sagemaker/")
    url = (api_base or "").strip() or _env("SAGEMAKER_BASE_URL")
    url = url or (f"https://runtime.sagemaker.{region}.amazonaws.com/endpoints/"
                  f"{endpoint_name}/invocations")
    payload: Dict[str, Any] = {
        "model": endpoint_name,
        "messages": _clean_messages(messages),
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    body, _ = _aws_post(url, payload, access_key, secret_key, session_token,
                        region, "sagemaker", timeout)
    return _parse_openai_response(body, model)


# ═══════════════════════════════════════════════════════════════════════
# IBM watsonx.ai（litellm/llms/watsonx/，前缀 watson/）
# ═══════════════════════════════════════════════════════════════════════

_watson_token_cache: Dict[str, Any] = {}
_watson_token_lock = threading.Lock()
_WATSONX_DEFAULT_API_VERSION = "2024-03-13"


def _watson_token(api_key: str) -> str:
    """获取（并缓存）IBM IAM 访问令牌。"""
    now = time.time()
    with _watson_token_lock:
        cached = _watson_token_cache.get(api_key)
        if cached and cached["expires"] > now + 30:
            return cached["token"]
    iam_url = _env("WATSONX_IAM_URL") or "https://iam.cloud.ibm.com/identity/token"
    try:
        response = requests.post(
            iam_url,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Accept": "application/json"},
            data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
            timeout=30,
        )
    except requests.exceptions.RequestException as exc:
        raise GatewayError(f"Failed to obtain IBM IAM token: {exc}") from exc
    if response.status_code >= 400:
        raise GatewayError(
            f"Failed to obtain IBM IAM token (HTTP {response.status_code}): {response.text[:300]}"
        )
    try:
        data = response.json()
        token = data["access_token"]
        expires = now + int(data.get("expires_in", 3600)) - 10
    except (KeyError, ValueError) as exc:
        raise GatewayError("IBM IAM token response was invalid") from exc
    with _watson_token_lock:
        _watson_token_cache[api_key] = {"token": token, "expires": expires}
    return token


def _watson_complete(model: str, messages: list, *, temperature, max_tokens,
                     api_key: Optional[str], api_base: Optional[str], timeout: float,
                     **kwargs) -> ModelResponse:
    key = (api_key or "").strip() or _env("WATSONX_APIKEY", "WATSONX_API_KEY", "WX_API_KEY")
    if not key:
        raise GatewayAuthenticationError(
            "Missing API key for provider 'watsonx'. "
            "Set it in the configuration or the WATSONX_API_KEY environment variable."
        )
    base = (api_base or "").strip() or _env("WATSONX_API_BASE", "WATSONX_URL", "WX_URL", "WML_URL")
    if not base:
        raise GatewayError(
            "Provider 'watsonx' requires an api_base URL (Watsonx URL). "
            "Set it in the configuration or the WATSONX_API_BASE environment variable."
        )
    token = _watson_token(key)
    project_id = (kwargs.get("project_id") or kwargs.get("watsonx_project")
                  or _env("WATSONX_PROJECT_ID", "WX_PROJECT_ID", "PROJECT_ID"))
    space_id = (kwargs.get("space_id")
                or _env("WATSONX_DEPLOYMENT_SPACE_ID", "WATSONX_SPACE_ID", "WX_SPACE_ID", "SPACE_ID"))

    model_name = _strip_model_prefix(model, "watson/")
    url = f"{base.rstrip('/')}/ml/v1/text/chat?version={_WATSONX_DEFAULT_API_VERSION}"
    payload: Dict[str, Any] = {
        "model_id": model_name,
        "messages": _clean_messages(messages),
    }
    if model_name.startswith("deployment/"):
        pass
    elif project_id:
        payload["project_id"] = project_id
    elif space_id:
        payload["space_id"] = space_id
    else:
        raise GatewayError(
            "Provider 'watsonx' requires a project_id (set WATSONX_PROJECT_ID) or space_id."
        )
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    body = _http_post(url, headers={"Content-Type": "application/json",
                                    "Accept": "application/json",
                                    "Authorization": f"Bearer {token}"},
                      payload=payload, timeout=timeout)
    return _parse_openai_response(body, model)


# ═══════════════════════════════════════════════════════════════════════
# 路由表与入口
# ═══════════════════════════════════════════════════════════════════════

_OPENAI_COMPAT = {
    "openai": _OpenAICompatProvider("openai", "https://api.openai.com/v1",
                                    env_keys=("OPENAI_API_KEY",)),
    "deepseek": _OpenAICompatProvider("deepseek", "https://api.deepseek.com/beta",
                                      env_keys=("DEEPSEEK_API_KEY",)),
    "xai": _OpenAICompatProvider("xai", "https://api.x.ai/v1",
                                 env_keys=("XAI_API_KEY",)),
    "moonshot": _OpenAICompatProvider("moonshot", "https://api.moonshot.ai/v1",
                                      env_keys=("MOONSHOT_API_KEY",)),
    "lm_studio": _OpenAICompatProvider("lm_studio", None, fake_key=True),
    "volcengine": _OpenAICompatProvider("volcengine", "https://ark.cn-beijing.volces.com/api/v3",
                                        env_keys=("VOLCENGINE_API_KEY",)),
    "groq": _OpenAICompatProvider("groq", "https://api.groq.com/openai/v1",
                                  env_keys=("GROQ_API_KEY",)),
    "hosted_vllm": _OpenAICompatProvider("hosted_vllm", None, fake_key=True),
    "github": _OpenAICompatProvider("github", "https://models.inference.ai.azure.com",
                                    env_keys=("GITHUB_API_KEY",)),
    "github_copilot": _OpenAICompatProvider("github_copilot", "https://api.githubcopilot.com",
                                            env_keys=("GITHUB_COPILOT_API_KEY",),
                                            copilot=True),
    "together_ai": _OpenAICompatProvider("together_ai", "https://api.together.xyz/v1",
                                         env_keys=("TOGETHER_API_KEY", "TOGETHER_AI_API_KEY",
                                                   "TOGETHERAI_API_KEY")),
    "openrouter": _OpenAICompatProvider("openrouter", "https://openrouter.ai/api/v1",
                                        env_keys=("OPENROUTER_API_KEY", "OR_API_KEY"),
                                        openrouter=True),
    "nvidia_nim": _OpenAICompatProvider("nvidia_nim", "https://integrate.api.nvidia.com/v1",
                                        env_keys=("NVIDIA_NIM_API_KEY",)),
    "mistral": _OpenAICompatProvider("mistral", "https://api.mistral.ai/v1",
                                     env_keys=("MISTRAL_API_KEY",), ensure_v1=True),
    "meta_llama": _OpenAICompatProvider("meta_llama", "https://api.llama.com/compat/v1",
                                        env_keys=("LLAMA_API_KEY",)),
    "huggingface": _OpenAICompatProvider("huggingface", "https://router.huggingface.co",
                                         env_keys=("HF_TOKEN", "HUGGINGFACE_API_KEY"), hf=True),
}

_SPECIAL = {
    "anthropic": _anthropic_complete,
    "azure": _azure_complete,
    "gemini": _gemini_complete,
    "bedrock": _bedrock_complete,
    "sagemaker": _sagemaker_complete,
    "watson": _watson_complete,
}


def completion(model, messages, *, temperature=None, max_tokens=None,
               api_key=None, api_base=None, num_retries=0, timeout=None,
               extra_body=None, reasoning_effort=None, drop_params=False,
               **kwargs):
    """litellm.completion() 的兼容子集（仅同步非流式）。

    参数行为与 litellm 一致：``model`` 携带 provider 前缀（如
    ``openai/gpt-4o``）；``num_retries`` 恒为 0（不做重试）；
    ``drop_params`` 已隐含满足（本网关只发送各 provider 支持的参数）。
    """
    if not isinstance(model, str) or "/" not in model:
        raise GatewayError(f"Invalid model name: {model!r}")
    provider, _ = model.split("/", 1)
    if provider not in _OPENAI_COMPAT and provider not in _SPECIAL:
        raise GatewayError(f"Unknown LLM provider: {provider!r}")

    request_timeout = float(timeout if timeout is not None else 10.0)

    handler = _OPENAI_COMPAT.get(provider)
    if handler is not None:
        return handler.complete(
            model, messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            api_base=api_base,
            timeout=request_timeout,
            extra_body=extra_body,
            reasoning_effort=reasoning_effort,
        )

    return _SPECIAL[provider](
        model, messages,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        api_base=api_base,
        timeout=request_timeout,
        reasoning_effort=reasoning_effort,
    )


# 兼容 litellm 模块引用的最小命名空间（供外部代码在两者间透明切换）
__all__ = ["completion", "ModelResponse", "GatewayError", "GatewayAuthenticationError"]


# 延迟导入 uuid（避免不必要的模块加载成本）
try:
    import uuid as _uuid_module
except Exception:  # pragma: no cover
    _uuid_module = None
