import unittest

from modless_chat_trans.translator import _openrouter_model_options


class OpenRouterOptionsTests(unittest.TestCase):
    def test_native_variants_are_preserved(self):
        for suffix in ('free', 'nitro', 'floor', 'exacto', 'online', 'extended', 'thinking',
                       'free:nitro'):
            model = 'vendor/model:' + suffix
            self.assertEqual(_openrouter_model_options(model), (model, None))

    def test_custom_providers_preserve_model_variants(self):
        self.assertEqual(_openrouter_model_options('vendor/model:free:amazon-bedrock, google-vertex'),
                         ('vendor/model:free', {'provider': {'order': ['amazon-bedrock', 'google-vertex']}}))
        self.assertEqual(_openrouter_model_options('vendor/model:amazon-bedrock'),
                         ('vendor/model', {'provider': {'order': ['amazon-bedrock']}}))

    def test_legacy_sort_aliases_use_official_variants(self):
        for legacy, native in [('price', 'floor'), ('throughput', 'nitro')]:
            self.assertEqual(_openrouter_model_options('vendor/model:' + legacy),
                             ('vendor/model:' + native, None))
        self.assertEqual(_openrouter_model_options('vendor/model:latency'),
                         ('vendor/model', {'provider': {'sort': 'latency'}}))
