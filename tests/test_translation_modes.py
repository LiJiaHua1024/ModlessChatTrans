import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from modless_chat_trans import translator as module
from modless_chat_trans.config import LLMServiceConfig, TranslationServiceConfig, ServiceType
from modless_chat_trans.translator import Translator, MessageType


def llm_config(deep, model='primary'):
    return LLMServiceConfig(provider='OpenAI', api_key='test', model=model,
                            deep_translate=deep, max_tokens=500)


class TranslationModeTests(unittest.TestCase):
    def translator(self, deep, fallback=None):
        return Translator(TranslationServiceConfig(
            service_type=ServiceType.LLM, llm=llm_config(deep), fallback_llm=fallback), {})

    def completion(self, **kwargs):
        self.requests.append(kwargs)
        if self.fail_primary and kwargs['model'].endswith('primary'):
            raise RuntimeError('primary unavailable')
        deep = kwargs['messages'][0]['content'] == 'deep'
        content = json.dumps({'result': 'translated'}) if deep else 'translated'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                               model_dump=lambda: {'usage': {}})

    def run_translation(self, translator, message_type=MessageType.PLAYER, rage=False, fail_primary=False):
        self.requests = []
        self.fail_primary = fail_primary
        with patch.object(module, 'litellm', SimpleNamespace(completion=self.completion)), \
                patch.object(translator, '_build_system_prompt', side_effect=lambda mode, *a, **kw: mode.value):
            if rage:
                result = translator.translate_with_profanity('hello', 'en', 'zh', message_type)
            else:
                result = translator.translate_with_context('hello', 'en', 'zh', message_type)
        self.assertEqual(result['result'], 'translated')

    def test_primary_switch_controls_prompt_and_json_parsing(self):
        for deep in (False, True):
            for message_type in (MessageType.PLAYER, MessageType.SEND):
                with self.subTest(deep=deep, message_type=message_type):
                    self.run_translation(self.translator(deep), message_type)
                    self.assertEqual(self.requests[0]['messages'][0]['content'], 'deep' if deep else 'normal')
                    self.assertEqual(self.requests[0]['max_tokens'], 1000 if deep else 500)

    def test_system_messages_remain_normal(self):
        self.run_translation(self.translator(True), MessageType.SYSTEM)
        self.assertEqual(self.requests[0]['messages'][0]['content'], 'normal')

    def test_rage_mode_takes_precedence_over_deep_switch(self):
        self.run_translation(self.translator(True, llm_config(True, 'fallback')),
                             MessageType.SEND, rage=True, fail_primary=True)
        self.assertEqual([r['messages'][0]['content'] for r in self.requests], ['rage', 'rage'])

    def test_fallback_uses_its_own_switch(self):
        for deep in (False, True):
            with self.subTest(primary_deep=deep):
                self.run_translation(self.translator(deep, llm_config(not deep, 'fallback')), fail_primary=True)
                self.assertEqual([r['messages'][0]['content'] for r in self.requests],
                                 ['deep', 'normal'] if deep else ['normal', 'deep'])
