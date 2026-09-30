import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modless_chat_trans import translator as module
from modless_chat_trans.config import LLMServiceConfig, TranslationServiceConfig, ServiceType
from modless_chat_trans.translator import Translator, MessageType


class ParamRejected(Exception):
    status_code = 400


class RateLimited(Exception):
    status_code = 429


def llm_config(provider="OpenAI", model="test-model", api_base=None):
    return LLMServiceConfig(provider=provider, api_key="test", model=model,
                            deep_translate=True, max_tokens=500, api_base=api_base)


class JsonModeTests(unittest.TestCase):
    def setUp(self):
        module._json_mode_disabled.clear()
        module._openrouter_models_cache = None

    def tearDown(self):
        module._json_mode_disabled.clear()
        module._openrouter_models_cache = None

    def translator(self, **kwargs):
        return Translator(TranslationServiceConfig(
            service_type=ServiceType.LLM, llm=llm_config(**kwargs)), {})

    def run_deep(self, translator, completion):
        with patch.object(module, 'litellm', SimpleNamespace(completion=completion)):
            return translator.translate_with_context('hello', 'en', 'zh', MessageType.PLAYER)

    def test_known_provider_sends_response_format(self):
        calls = []

        def completion(**kwargs):
            calls.append(kwargs)
            return self._ok_response()

        self.run_deep(self.translator(), completion)
        self.assertEqual(calls[0]['response_format'], {'type': 'json_object'})

    def test_anthropic_direct_never_sends_response_format(self):
        calls = []

        def completion(**kwargs):
            calls.append(kwargs)
            return self._ok_response()

        self.run_deep(self.translator(provider='Anthropic'), completion)
        self.assertNotIn('response_format', calls[0])

    def test_rejection_falls_back_and_is_remembered(self):
        calls = []

        def completion(**kwargs):
            calls.append(kwargs)
            if 'response_format' in kwargs:
                raise ParamRejected('response_format is not supported')
            return self._ok_response()

        translator = self.translator(api_base='https://proxy.example.com/v1')
        result = self.run_deep(translator, completion)
        self.assertEqual(result['result'], 'translated')
        self.assertEqual(len(calls), 2)
        self.assertIn('response_format', calls[0])
        self.assertNotIn('response_format', calls[1])

        # 会话记忆生效：第二条消息直接跳过 JSON mode，不再探测
        calls.clear()
        self.run_deep(translator, completion)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('response_format', calls[0])

    def test_non_param_errors_propagate_without_fallback(self):
        calls = []

        def completion(**kwargs):
            calls.append(kwargs)
            raise RateLimited('quota exceeded')

        translator = self.translator(api_base='https://proxy.example.com/v1')
        with self.assertRaises(RateLimited):
            self.run_deep(translator, completion)
        self.assertEqual(len(calls), 1)
        self.assertNotIn((translator.translation_service_config.llm.provider,
                          'https://proxy.example.com/v1',
                          'test-model'), module._json_mode_disabled)

    def test_openrouter_capability_lookup(self):
        module._openrouter_models_cache = {
            'big/model': ['response_format', 'temperature'],
            'small/model': ['temperature'],
        }

        calls = []

        def completion(**kwargs):
            calls.append(kwargs)
            return self._ok_response()

        self.run_deep(self.translator(provider='OpenRouter', model='big/model'), completion)
        self.assertIn('response_format', calls[0])

        calls.clear()
        self.run_deep(self.translator(provider='OpenRouter', model='small/model'), completion)
        self.assertNotIn('response_format', calls[0])

    def test_openrouter_variant_suffix_falls_back_to_base_id(self):
        module._openrouter_models_cache = {
            'big/model': ['response_format'],
        }

        calls = []

        def completion(**kwargs):
            calls.append(kwargs)
            return self._ok_response()

        self.run_deep(self.translator(provider='OpenRouter', model='big/model:free'), completion)
        self.assertEqual(calls[0]['response_format'], {'type': 'json_object'})

    @staticmethod
    def _ok_response():
        content = json.dumps({'terms': [], 'result': 'translated'})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            model_dump=lambda: {'usage': {}})


if __name__ == '__main__':
    unittest.main()
