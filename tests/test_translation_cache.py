import tempfile
import unittest
from unittest.mock import Mock, patch

from diskcache import Cache
from modless_chat_trans import message_processor as processor
from modless_chat_trans.file_utils import remove_legacy_translation_entries


class TranslationCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = {}
        self.patchers = [patch.object(processor, 'cache', self.cache),
                         patch.object(processor, 'match_and_translate', return_value=None)]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.translator = Mock()
        self.translator.translate_with_context.side_effect = (
            lambda text, **kw: {'result': kw['target_language'] + ':' + text})
        self.message = processor.PreparedMessage('Steve', 'hello', processor.MessageType.PLAYER)

    def translate(self, target, **kwargs):
        return processor.translate_prepared(self.message, self.translator, 'en', target, **kwargs)

    def test_different_targets_do_not_share_results(self):
        self.assertEqual(self.translate('zh')[1], 'zh:hello')
        self.message.message_type = processor.MessageType.SEND
        self.assertEqual(self.translate('ja')[1], 'ja:hello')
        self.assertEqual(self.translator.translate_with_context.call_count, 2)

    def test_context_and_service_changes_still_reuse_translation(self):
        self.translate('zh', context_messages=[{'content': 'first context'}])
        self.translator = Mock()
        result = self.translate('zh', context_messages=[{'content': 'another context'}])
        self.assertEqual(result[1], 'zh:hello')
        self.assertTrue(result[2]['cache_hit'])
        self.translator.translate_with_context.assert_not_called()

    def test_rage_mode_does_not_read_or_overwrite_cache(self):
        self.translate('zh')
        self.translator.translate_with_profanity.return_value = {'result': 'rage'}
        self.assertEqual(self.translate('zh', rage_mode=True)[1], 'rage')
        self.assertEqual(self.translate('zh')[1], 'zh:hello')

    def test_legacy_cleanup_preserves_new_entries_and_other_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            with Cache(directory) as cache, Cache(directory + '/jev') as classifier_cache:
                cache['hello'] = 'legacy'
                cache[('hello', 'zh')] = 'new'
                classifier_cache['hello'] = True
                self.assertEqual(remove_legacy_translation_entries(cache), 1)
                self.assertEqual(remove_legacy_translation_entries(cache), 0)
                self.assertEqual(cache[('hello', 'zh')], 'new')
                self.assertTrue(classifier_cache['hello'])
