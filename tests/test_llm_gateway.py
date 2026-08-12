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

"""LLM 网关回归测试。

用本地 HTTP mock 服务器验证 23 个 provider 的请求构造（URL、headers、
payload）与响应解析，不依赖真实服务商凭据。AWS SigV4 签名与
AWS 文档公开测试向量交叉验证。
"""

import hashlib
import hmac
import json
import threading
import unittest
import unittest.mock
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

import modless_chat_trans.llm_gateway as gateway


class MockHandler(BaseHTTPRequestHandler):
    """记录请求并按剧本返回响应。"""

    responses = []
    recorded = []

    def _handle(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        self.__class__.recorded.append({
            "method": self.command,
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "headers_lower": {k.lower(): v for k, v in self.headers.items()},
            "body": body.decode("utf-8", errors="replace"),
            "body_json": json.loads(body) if body and self.headers.get("Content-Type", "").startswith("application/json") else None,
            "form": parse_qs(body.decode()) if body and "form-urlencoded" in self.headers.get("Content-Type", "") else None,
        })
        status, payload, extra_headers = self.__class__.responses.pop(0)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *args):
        pass


class MockServer:
    def __init__(self):
        self.handler = MockHandler
        self.handler.responses = []
        self.handler.recorded = []
        self.server = HTTPServer(("127.0.0.1", 0), MockHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    @property
    def recorded(self):
        return self.handler.recorded

    def queue(self, payload, status=200, headers=None):
        self.handler.responses.append((status, payload, headers))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def openai_response(content="hello", usage=None):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": usage or {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    }


class OpenAICompatTests(unittest.TestCase):
    """覆盖 openai/deepseek/xai/moonshot/volcengine/groq/github/together_ai/
    nvidia_nim/mistral/meta_llama/lm_studio/hosted_vllm 的通用路径。"""

    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def _call(self, provider, model="gpt-4o", api_key="sk-test", api_base=None, **kw):
        self.server.queue(openai_response())
        result = gateway.completion(
            f"{provider}/{model}",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            temperature=0, max_tokens=256, api_key=api_key,
            api_base=api_base or f"{self.server.base_url}/v1",
            timeout=5, **kw,
        )
        return result, self.server.recorded[-1]

    def assert_openai_shape(self, record, model_name):
        self.assertEqual(record["path"], "/v1/chat/completions")
        self.assertEqual(record["headers_lower"]["authorization"], "Bearer sk-test")
        self.assertEqual(record["body_json"]["model"], model_name)
        self.assertEqual(record["body_json"]["temperature"], 0)
        self.assertEqual(record["body_json"]["max_tokens"], 256)
        self.assertEqual(record["body_json"]["messages"][0]["role"], "system")

    def test_all_openai_compat_providers(self):
        for provider, model in [
            ("openai", "gpt-4o"), ("deepseek", "deepseek-chat"),
            ("xai", "grok-3"), ("moonshot", "kimi-k2"),
            ("volcengine", "doubao-pro"), ("groq", "llama-3.3-70b"),
            ("github", "gpt-4o"), ("together_ai", "meta-llama/Llama-3.3-70B"),
            ("nvidia_nim", "meta/llama-3.3-70b"), ("mistral", "mistral-large-latest"),
            ("meta_llama", "llama-4-scout-17b"),
        ]:
            with self.subTest(provider=provider):
                result, record = self._call(provider, model)
                self.assertEqual(result.choices[0].message.content, "hello")
                self.assertEqual(result.model_dump()["usage"]["total_tokens"], 7)
                self.assert_openai_shape(record, model)

    def test_lm_studio_and_hosted_vllm_use_fake_key_and_require_base(self):
        for provider in ("lm_studio", "hosted_vllm"):
            with self.subTest(provider=provider):
                self.server.queue(openai_response())
                gateway.completion(f"{provider}/local-model",
                                   [{"role": "user", "content": "hi"}],
                                   api_key="", api_base=f"{self.server.base_url}/v1", timeout=5)
                self.assertEqual(
                    self.server.recorded[0]["headers"]["Authorization"], "Bearer fake-api-key"
                )
                with self.assertRaises(gateway.GatewayError):
                    gateway.completion(f"{provider}/local-model",
                                       [{"role": "user", "content": "hi"}],
                                       api_key="", api_base="", timeout=5)

    def test_missing_api_key_raises(self):
        with self.assertRaises(gateway.GatewayAuthenticationError):
            gateway.completion("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                               api_key="", timeout=5)

    def test_mistral_appends_v1(self):
        self.server.queue(openai_response())
        gateway.completion("mistral/mistral-large", [{"role": "user", "content": "hi"}],
                           api_key="k", api_base=f"{self.server.base_url}", timeout=5)
        self.assertEqual(self.server.recorded[0]["path"], "/v1/chat/completions")

    def test_openai_reasoning_effort_passthrough(self):
        self.server.queue(openai_response())
        gateway.completion("openai/gemini-3-flash", [{"role": "user", "content": "hi"}],
                           api_key="k", api_base=f"{self.server.base_url}/v1", timeout=5,
                           reasoning_effort="minimal", drop_params=True)
        self.assertEqual(self.server.recorded[0]["body_json"]["reasoning_effort"], "minimal")

    def test_http_error_raises_gateway_error(self):
        self.server.queue({"error": "boom"}, status=429)
        with self.assertRaisesRegex(gateway.GatewayError, "429"):
            gateway.completion("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                               api_key="k", api_base=f"{self.server.base_url}/v1", timeout=5)

    def test_unknown_provider_raises(self):
        with self.assertRaisesRegex(gateway.GatewayError, "Unknown"):
            gateway.completion("notaprovider/x", [{"role": "user", "content": "hi"}],
                               api_key="k", timeout=5)


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_openrouter_headers_usage_and_extra_body(self):
        self.server.queue(openai_response())
        gateway.completion(
            "openrouter/anthropic/claude-3.5-sonnet",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            temperature=0, max_tokens=256, api_key="or-key",
            api_base=f"{self.server.base_url}/api/v1", timeout=5,
            extra_body={"provider": {"sort": "price"}},
        )
        record = self.server.recorded[0]
        self.assertEqual(record["headers_lower"]["http-referer"], "https://litellm.ai")
        self.assertEqual(record["headers_lower"]["x-title"], "liteLLM")
        self.assertEqual(record["body_json"]["model"], "anthropic/claude-3.5-sonnet")
        self.assertEqual(record["body_json"]["usage"], {"include": True})
        self.assertEqual(record["body_json"]["provider"], {"sort": "price"})
        self.assertEqual(record["path"], "/api/v1/chat/completions")


class GitHubCopilotTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_copilot_headers_and_system_conversion(self):
        self.server.queue(openai_response())
        gateway.completion(
            "github_copilot/gpt-4o",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            api_key="copilot-token", api_base=f"{self.server.base_url}", timeout=5,
        )
        record = self.server.recorded[-1]
        headers = record["headers_lower"]
        self.assertEqual(headers["authorization"], "Bearer copilot-token")
        self.assertEqual(headers["copilot-integration-id"], "vscode-chat")
        self.assertEqual(headers["openai-intent"], "conversation-panel")
        self.assertEqual(headers["x-github-api-version"], "2025-04-01")
        self.assertEqual(headers["x-initiator"], "user")
        roles = [m["role"] for m in record["body_json"]["messages"]]
        self.assertEqual(roles, ["assistant", "user"])
        self.assertEqual(record["path"], "/chat/completions")


class HuggingFaceTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_hf_with_api_base_appends_v1(self):
        self.server.queue(openai_response())
        gateway.completion("huggingface/mistralai/Mistral-7B-Instruct-v0.3",
                           [{"role": "user", "content": "hi"}], api_key="hf-key",
                           api_base=f"{self.server.base_url}", timeout=5)
        self.assertEqual(self.server.recorded[0]["path"], "/v1/chat/completions")
        self.assertEqual(self.server.recorded[0]["body_json"]["model"],
                         "mistralai/Mistral-7B-Instruct-v0.3")

    def test_hf_default_router_url(self):
        captured = []

        def fake_post(url, **kwargs):
            captured.append(url)
            return openai_response()

        original_post = gateway._http_post
        gateway._http_post = fake_post
        try:
            # 单斜杠模型（org/model）走默认 router URL（与 litellm 一致）
            gateway.completion("huggingface/mistralai/Mistral-7B-Instruct-v0.3",
                               [{"role": "user", "content": "hi"}], api_key="hf-key",
                               api_base="", timeout=5)
            # 双斜杠模型（provider/org/model）按 provider 路由
            gateway.completion("huggingface/novita/mistralai/Mistral-7B",
                               [{"role": "user", "content": "hi"}], api_key="hf-key",
                               api_base="", timeout=5)
        finally:
            gateway._http_post = original_post
        self.assertEqual(captured[0],
                         "https://router.huggingface.co/v1/chat/completions")
        self.assertEqual(captured[1],
                         "https://router.huggingface.co/novita/v3/openai/chat/completions")


class AnthropicTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_anthropic_default_endpoint(self):
        anthropic_response = {
            "content": [{"type": "text", "text": "你好"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 11, "output_tokens": 3},
        }
        self.server.queue(anthropic_response)
        result = gateway.completion(
            "anthropic/claude-3-5-sonnet-20241022",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            temperature=0, max_tokens=256, api_key="sk-ant-test", timeout=5, api_base=self.server.base_url + "/v1/messages",
        )
        record = self.server.recorded[0]
        self.assertEqual(record["path"], "/v1/messages")
        self.assertEqual(record["headers_lower"]["x-api-key"], "sk-ant-test")
        self.assertEqual(record["headers_lower"]["anthropic-version"], "2023-06-01")
        self.assertEqual(record["body_json"]["model"], "claude-3-5-sonnet-20241022")
        self.assertEqual(record["body_json"]["max_tokens"], 256)
        self.assertEqual(record["body_json"]["system"], [{"type": "text", "text": "sys"}])
        self.assertEqual(record["body_json"]["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(result.choices[0].message.content, "你好")
        usage = result.model_dump()["usage"]
        self.assertEqual(usage["prompt_tokens"], 11)
        self.assertEqual(usage["completion_tokens"], 3)
        self.assertEqual(usage["total_tokens"], 14)

    def test_anthropic_custom_base_appends_messages_path(self):
        self.server.queue({"content": [{"type": "text", "text": "ok"}], "usage": {}})
        gateway.completion("anthropic/claude-3-5-haiku",
                           [{"role": "user", "content": "hi"}], api_key="sk-ant-oauth123",
                           api_base=f"{self.server.base_url}/v1", timeout=5)
        record = self.server.recorded[0]
        self.assertEqual(record["path"], "/v1/v1/messages")
        self.assertEqual(record["headers_lower"]["authorization"], "Bearer sk-ant-oauth123")
        self.assertEqual(record["headers_lower"]["anthropic-dangerous-direct-browser-access"], "true")

    def test_anthropic_default_max_tokens(self):
        self.server.queue({"content": [{"type": "text", "text": "ok"}], "usage": {}})
        gateway.completion("anthropic/claude-3-5-haiku",
                           [{"role": "user", "content": "hi"}], api_key="sk-ant-test",
                           api_base=f"{self.server.base_url}/v1/messages", timeout=5)
        self.assertEqual(self.server.recorded[0]["body_json"]["max_tokens"], 4096)


class AzureTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_azure_url_and_headers(self):
        self.server.queue(openai_response())
        gateway.completion("azure/gpt-4o-deployment",
                           [{"role": "user", "content": "hi"}], api_key="azure-key",
                           api_base=f"{self.server.base_url}", timeout=5)
        record = self.server.recorded[-1]
        path, query = record["path"].split("?", 1)
        self.assertEqual(path, "/openai/deployments/gpt-4o-deployment/chat/completions")
        self.assertEqual(query, "api-version=2025-02-01-preview")
        self.assertEqual(record["headers_lower"]["api-key"], "azure-key")
        self.assertEqual(record["body_json"]["model"], "gpt-4o-deployment")

    def test_azure_requires_api_base(self):
        with self.assertRaises(gateway.GatewayError):
            gateway.completion("azure/gpt-4o", [{"role": "user", "content": "hi"}],
                               api_key="k", api_base="", timeout=5)


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()
        self.captured = {}

        def fake_post(url, **kwargs):
            self.captured["url"] = url
            self.captured["headers"] = kwargs["headers"]
            self.captured["payload"] = kwargs["payload"]
            return self.response

        self.original_post = gateway._http_post
        self.response = None
        gateway._http_post = fake_post

    def tearDown(self):
        gateway._http_post = self.original_post
        self.server.close()

    def test_gemini_request_and_response(self):
        self.response = {
            "candidates": [{"content": {"parts": [{"text": "你好"}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 4,
                              "totalTokenCount": 14},
        }
        result = gateway.completion(
            "gemini/gemini-2.5-flash",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            temperature=0, max_tokens=256, api_key="g-key", timeout=5,
        )
        self.assertEqual(self.captured["url"],
                         "https://generativelanguage.googleapis.com/v1beta/models/"
                         "gemini-2.5-flash:generateContent")
        self.assertEqual(self.captured["headers"]["x-goog-api-key"], "g-key")
        body = self.captured["payload"]
        self.assertEqual(body["system_instruction"], {"parts": [{"text": "sys"}]})
        self.assertEqual(body["contents"], [{"role": "user", "parts": [{"text": "hi"}]}])
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 256)
        self.assertEqual(body["generationConfig"]["temperature"], 0)
        self.assertEqual(result.choices[0].message.content, "你好")
        usage = result.model_dump()["usage"]
        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 4)
        self.assertEqual(usage["total_tokens"], 14)

    def test_gemini3_uses_v1alpha_and_thinking_level(self):
        self.response = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                         "usageMetadata": {}}
        gateway.completion(
            "gemini/gemini-3-flash-preview",
            [{"role": "user", "content": "hi"}],
            api_key="g-key", timeout=5, reasoning_effort="minimal", drop_params=True,
        )
        self.assertEqual(self.captured["url"],
                         "https://generativelanguage.googleapis.com/v1alpha/models/"
                         "gemini-3-flash-preview:generateContent")
        self.assertEqual(self.captured["payload"]["generationConfig"]["thinkingConfig"],
                         {"thinkingLevel": "minimal", "includeThoughts": True})

    def test_gemini3_pro_uses_low_thinking_level(self):
        self.response = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                         "usageMetadata": {}}
        gateway.completion("gemini/gemini-3-pro-preview",
                           [{"role": "user", "content": "hi"}],
                           api_key="g-key", timeout=5, reasoning_effort="minimal")
        self.assertEqual(
            self.captured["payload"]["generationConfig"]["thinkingConfig"]["thinkingLevel"], "low")

    def test_gemini2_5_uses_thinking_budget(self):
        self.response = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                         "usageMetadata": {}}
        gateway.completion("gemini/gemini-2.5-flash",
                           [{"role": "user", "content": "hi"}],
                           api_key="g-key", timeout=5, reasoning_effort="minimal")
        config = self.captured["payload"]["generationConfig"]["thinkingConfig"]
        self.assertEqual(config["thinkingBudget"], 1)

    def test_gemini_missing_key(self):
        with self.assertRaises(gateway.GatewayAuthenticationError):
            gateway.completion("gemini/gemini-2.5-flash",
                               [{"role": "user", "content": "hi"}], api_key="", timeout=5)


class VertexAITests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()
        self.original_credentials = gateway._vertex_credentials
        self.original_token = gateway._google_access_token

    def tearDown(self):
        gateway._vertex_credentials = self.original_credentials
        gateway._google_access_token = self.original_token
        self.server.close()

    def test_vertex_request_shape(self):
        self.server.queue({"candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                           "usageMetadata": {}})
        gateway._vertex_credentials = lambda: {
            "type": "service_account", "client_email": "sa@proj.iam.gserviceaccount.com",
            "project_id": "my-project", "private_key": "x",
        }
        gateway._google_access_token = lambda creds: "fake-token"
        result = gateway.completion(
            "vertex_ai/gemini-2.5-flash",
            [{"role": "user", "content": "hi"}], api_key="",
            api_base=self.server.base_url, timeout=5,
        )
        record = self.server.recorded[-1]
        self.assertEqual(record["path"], "/models/gemini-2.5-flash:generateContent")
        self.assertEqual(record["headers_lower"]["authorization"], "Bearer fake-token")
        self.assertEqual(record["body_json"]["contents"][0]["role"], "user")
        self.assertEqual(result.choices[0].message.content, "ok")

    def test_vertex_region_from_env(self):
        captured = {}

        def fake_post(url, **kwargs):
            captured["url"] = url
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}], "usageMetadata": {}}

        original_post = gateway._http_post
        gateway._http_post = fake_post
        try:
            gateway._vertex_credentials = lambda: {
                "type": "service_account", "client_email": "sa@proj.iam.gserviceaccount.com",
                "project_id": "my-project", "private_key": "x",
            }
            gateway._google_access_token = lambda creds: "fake-token"
            with unittest.mock.patch.dict("os.environ", {"VERTEXAI_LOCATION": "europe-west4"}, clear=False):
                gateway.completion("vertex_ai/gemini-2.5-flash",
                                   [{"role": "user", "content": "hi"}], api_key="", timeout=5)
        finally:
            gateway._http_post = original_post
        self.assertEqual(
            captured["url"],
            "https://europe-west4-aiplatform.googleapis.com/v1/projects/my-project/"
            "locations/europe-west4/publishers/google/models/gemini-2.5-flash:generateContent",
        )

    def test_vertex_requires_credentials(self):
        gateway._vertex_credentials = lambda: None
        with self.assertRaises(gateway.GatewayAuthenticationError):
            gateway.completion("vertex_ai/gemini-2.5-flash",
                               [{"role": "user", "content": "hi"}], api_key="", timeout=5)


class SigV4Tests(unittest.TestCase):
    def test_aws_get_vanilla_test_vector(self):
        """AWS 文档公开测试向量（get-vanilla）交叉验证。"""

        class FakeDateTime:
            @staticmethod
            def now(tz):
                return datetime(2015, 8, 30, 12, 36, 0)

        original = gateway.datetime
        gateway.datetime = FakeDateTime
        try:
            headers = gateway._sigv4_headers(
                "GET", "https://example.amazonaws.com/", b"",
                access_key="AKIDEXAMPLE",
                secret_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                session_token=None, region="us-east-1", service="service",
            )
        finally:
            gateway.datetime = original

        authorization = headers["Authorization"]
        self.assertIn("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request",
                      authorization)
        self.assertEqual(headers["x-amz-date"], "20150830T123600Z")

        # 独立参考实现（按 AWS 文档结构重写，交叉验证格式化正确性）
        parsed = urlsplit("https://example.amazonaws.com/")
        canonical_request = (
            "GET\n/\n\n"
            "content-type:application/json\n"
            "host:example.amazonaws.com\n"
            "x-amz-date:20150830T123600Z\n\n"
            "content-type;host;x-amz-date\n"
            + hashlib.sha256(b"").hexdigest()
        )
        scope = "20150830/us-east-1/service/aws4_request"
        string_to_sign = (
            "AWS4-HMAC-SHA256\n20150830T123600Z\n" + scope + "\n"
            + hashlib.sha256(canonical_request.encode()).hexdigest()
        )

        def sign(key, msg):
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = sign(("AWS4" + "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY").encode(), "20150830")
        k_region = sign(k_date, "us-east-1")
        k_service = sign(k_region, "service")
        k_signing = sign(k_service, "aws4_request")
        expected = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
        self.assertIn(f"Signature={expected}", authorization)
        self.assertEqual(parsed.path, "/")


class BedrockTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()
        self.env = unittest.mock.patch.dict(
            "os.environ",
            {"AWS_ACCESS_KEY_ID": "AKIDEXAMPLE",
             "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"},
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.close()

    def test_bedrock_claude_converse(self):
        response = {
            "output": {"message": {"role": "assistant",
                                   "content": [{"text": "你好"}]}},
            "stopReason": "end_turn",
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }
        self.server.queue(response)
        result = gateway.completion(
            "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            temperature=0, max_tokens=256, api_key="", timeout=5,
            api_base=self.server.base_url,
        )
        record = self.server.recorded[-1]
        self.assertEqual(
            record["path"],
            "/model/anthropic.claude-3-5-sonnet-20241022-v2%3A0/converse",
        )
        self.assertIn("AWS4-HMAC-SHA256", record["headers_lower"]["authorization"])
        self.assertIn("us-west-2", record["headers_lower"]["authorization"])
        body = record["body_json"]
        self.assertEqual(body["inferenceConfig"], {"temperature": 0, "maxTokens": 256})
        self.assertEqual(body["system"], [{"text": "sys"}])
        self.assertEqual(result.choices[0].message.content, "你好")
        self.assertEqual(result.model_dump()["usage"]["prompt_tokens"], 10)

    def test_bedrock_invoke_claude(self):
        response = {
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 2},
        }
        self.server.queue(response, headers={
            "x-amzn-bedrock-input-token-count": "5",
            "x-amzn-bedrock-output-token-count": "2",
        })
        result = gateway.completion(
            "bedrock/invoke/anthropic.claude-3-haiku-20240307-v1:0",
            [{"role": "user", "content": "hi"}], temperature=0, max_tokens=256,
            api_key="", timeout=5, api_base=self.server.base_url,
        )
        record = self.server.recorded[-1]
        self.assertEqual(
            record["path"], "/model/anthropic.claude-3-haiku-20240307-v1%3A0/invoke")
        self.assertEqual(record["body_json"]["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(record["body_json"]["max_tokens"], 256)
        self.assertEqual(result.choices[0].message.content, "ok")
        self.assertEqual(result.model_dump()["usage"]["completion_tokens"], 2)

    def test_bedrock_invoke_llama3_prompt_template(self):
        self.server.queue({"generation": "ok"})
        gateway.completion(
            "bedrock/meta.llama3-70b-instruct-v1:0",
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            api_key="", timeout=5, api_base=self.server.base_url,
        )
        prompt = self.server.recorded[-1]["body_json"]["prompt"]
        self.assertIn("<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nsys<|eot_id|>", prompt)
        self.assertIn("<|start_header_id|>user<|end_header_id|>\n\nhi<|eot_id|>", prompt)
        self.assertTrue(prompt.endswith("<|start_header_id|>assistant<|end_header_id|>\n\n"))

    def test_bedrock_invoke_titan(self):
        self.server.queue({"results": [{"outputText": "ok"}]})
        gateway.completion(
            "bedrock/amazon.titan-text-express-v1",
            [{"role": "user", "content": "hi"}], api_key="", timeout=5,
            api_base=self.server.base_url,
        )
        body = self.server.recorded[-1]["body_json"]
        self.assertEqual(body["inputText"], "\n\nUser: hi\n\nBot: ")

    def test_bedrock_missing_credentials(self):
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(gateway.GatewayAuthenticationError):
                gateway.completion("bedrock/anthropic.claude-3-5-sonnet",
                                   [{"role": "user", "content": "hi"}], api_key="", timeout=5)


class SageMakerTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()
        self.env = unittest.mock.patch.dict(
            "os.environ",
            {"AWS_ACCESS_KEY_ID": "AKIDEXAMPLE",
             "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"},
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.server.close()

    def test_sagemaker_chat(self):
        self.server.queue(openai_response())
        result = gateway.completion(
            "sagemaker/my-endpoint-name",
            [{"role": "user", "content": "hi"}], temperature=0, max_tokens=256,
            api_key="", timeout=5,
            api_base=f"{self.server.base_url}/endpoints/my-endpoint-name/invocations",
        )
        record = self.server.recorded[-1]
        self.assertEqual(record["path"], "/endpoints/my-endpoint-name/invocations")
        self.assertIn("us-west-2", record["headers_lower"]["authorization"])
        body = record["body_json"]
        self.assertEqual(body["model"], "my-endpoint-name")
        self.assertEqual(body["temperature"], 0)
        self.assertEqual(body["max_tokens"], 256)
        self.assertEqual(result.choices[0].message.content, "hello")


class WatsonTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_watson_iam_token_and_chat(self):
        # 第一个响应：IAM token；第二个：chat 响应
        self.server.queue({"access_token": "iam-token-1", "expires_in": 3600})
        self.server.queue(openai_response())
        with unittest.mock.patch.dict(
            "os.environ",
            {"WATSONX_IAM_URL": f"{self.server.base_url}/identity/token",
             "WATSONX_PROJECT_ID": "proj-123"},
        ):
            result = gateway.completion(
                "watson/ibm-granite-13b-chat-v2",
                [{"role": "user", "content": "hi"}], api_key="wx-key",
                api_base=f"{self.server.base_url}", timeout=5,
            )
        token_call, chat_call = self.server.recorded[0], self.server.recorded[-1]
        self.assertEqual(token_call["path"], "/identity/token")
        self.assertEqual(token_call["form"]["grant_type"],
                         ["urn:ibm:params:oauth:grant-type:apikey"])
        self.assertEqual(token_call["form"]["apikey"], ["wx-key"])
        self.assertEqual(chat_call["path"], "/ml/v1/text/chat?version=2024-03-13")
        self.assertEqual(chat_call["headers_lower"]["authorization"], "Bearer iam-token-1")
        body = chat_call["body_json"]
        self.assertEqual(body["model_id"], "ibm-granite-13b-chat-v2")
        self.assertEqual(body["project_id"], "proj-123")
        self.assertEqual(result.choices[0].message.content, "hello")

    def test_watson_requires_project_id(self):
        self.server.queue({"access_token": "t", "expires_in": 3600})
        with unittest.mock.patch.dict("os.environ", {"WATSONX_IAM_URL": self.server.base_url}, clear=False), \
                self.assertRaisesRegex(gateway.GatewayError, "project_id"):
            gateway.completion("watson/ibm-granite-13b-chat-v2",
                               [{"role": "user", "content": "hi"}], api_key="wx-key",
                               api_base=f"{self.server.base_url}", timeout=5)


class TranslatorIntegrationTests(unittest.TestCase):
    """Translator（translator.py）与 LLM 网关的集成验证。"""

    def setUp(self):
        self.server = MockServer()

    def tearDown(self):
        self.server.close()

    def test_translator_llm_translation_through_gateway(self):
        from types import SimpleNamespace

        from modless_chat_trans.config import FallbackStrategy, ServiceType
        from modless_chat_trans.translator import Translator

        self.server.queue(openai_response(content="你好，世界"))
        config = SimpleNamespace(
            service_type=ServiceType.LLM,
            llm=SimpleNamespace(
                provider="OpenAI",
                model="gpt-4o",
                api_key="sk-test",
                api_base=f"{self.server.base_url}/v1",
                deep_translate=False,
            ),
            traditional=None,
            fallback_llm=None,
            fallback_strategy=FallbackStrategy.DIRECT,
        )
        translator = Translator(config, {})
        result = translator.translate("hello world", "auto", "zh-CN")
        self.assertEqual(result["result"], "你好，世界")
        self.assertEqual(result["usage"]["total_tokens"], 7)

        record = self.server.recorded[-1]
        self.assertEqual(record["body_json"]["model"], "gpt-4o")
        self.assertEqual(record["body_json"]["max_tokens"], 256)
        self.assertIn("Translate the following text to zh-CN",
                      record["body_json"]["messages"][1]["content"])

    def test_translator_fallback_strategy_direct(self):
        from types import SimpleNamespace

        from modless_chat_trans.config import FallbackStrategy, ServiceType
        from modless_chat_trans.translator import Translator

        # 主模型失败 → 备用模型（Anthropic 格式响应）
        self.server.queue({"error": "boom"}, status=500)
        self.server.queue({"content": [{"type": "text", "text": "fallback-ok"}],
                           "usage": {"input_tokens": 3, "output_tokens": 2}})
        config = SimpleNamespace(
            service_type=ServiceType.LLM,
            llm=SimpleNamespace(provider="OpenAI", model="gpt-4o",
                                api_key="k1", api_base=f"{self.server.base_url}/v1",
                                deep_translate=False),
            traditional=None,
            fallback_llm=SimpleNamespace(provider="Anthropic", model="claude-3-haiku",
                                         api_key="k2", api_base=f"{self.server.base_url}/v1",
                                         deep_translate=False),
            fallback_strategy=FallbackStrategy.DIRECT,
        )
        translator = Translator(config, {})
        result = translator.translate("hello", "en", "zh")
        self.assertEqual(result["result"], "fallback-ok")
        models = [r["body_json"]["model"] for r in self.server.recorded]
        self.assertEqual(models, ["gpt-4o", "claude-3-haiku"])


    def test_translator_batch_translation(self):
        from types import SimpleNamespace

        from modless_chat_trans.config import FallbackStrategy, ServiceType
        from modless_chat_trans.translator import Translator

        self.server.queue(openai_response(
            content='["a","b"]',
            usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
        ))
        config = SimpleNamespace(
            service_type=ServiceType.LLM,
            llm=SimpleNamespace(provider="OpenAI", model="gpt-4o",
                                api_key="sk-test", api_base=f"{self.server.base_url}/v1",
                                deep_translate=False),
            traditional=None,
            fallback_llm=None,
            fallback_strategy=FallbackStrategy.DIRECT,
        )
        translator = Translator(config, {})
        results = translator.translate_batch_with_context(["hello", "world"], "en", "zh")
        self.assertEqual(results, ["a", "b"])
        body = self.server.recorded[-1]["body_json"]
        self.assertGreaterEqual(body["max_tokens"], 2048)

    def test_translator_deep_mode_json_parsing(self):
        from types import SimpleNamespace

        from modless_chat_trans.config import FallbackStrategy, ServiceType
        from modless_chat_trans.translator import Translator

        self.server.queue(openai_response(
            content='```json\n{"context_analysis": {"conversation_summary": "s",'
                    ' "relevance": "r"}, "terms": [], "result": "你好"}\n```',
        ))
        config = SimpleNamespace(
            service_type=ServiceType.LLM,
            llm=SimpleNamespace(provider="OpenAI", model="gpt-4o",
                                api_key="sk-test", api_base=f"{self.server.base_url}/v1",
                                deep_translate=True),
            traditional=None,
            fallback_llm=None,
            fallback_strategy=FallbackStrategy.DIRECT,
        )
        translator = Translator(config, {})
        result = translator._execute_llm_translation(
            "hi", "gpt-4o", "en", "zh", "OpenAI", "system prompt",
            expect_json=True, include_terms=True,
        )
        self.assertEqual(result["result"], "你好")
        body = self.server.recorded[-1]["body_json"]
        self.assertEqual(body["max_tokens"], 512)


if __name__ == "__main__":
    unittest.main()
