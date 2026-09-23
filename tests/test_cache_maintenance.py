import tempfile
import time
import unittest
from unittest.mock import patch

from diskcache import Cache
from modless_chat_trans import pre_tts


class CacheMaintenanceTests(unittest.TestCase):
    def test_pre_tts_selects_hot_translations_in_the_requested_language(self):
        with tempfile.TemporaryDirectory() as directory, Cache(
            directory, eviction_policy='least-frequently-used'
        ) as cache:
            for key, value in [(('hello', 'Japanese'), 'こんにちは'),
                               (('hello', 'English'), 'Hello'), ('legacy', 'Old')]:
                cache[key] = value
                for _ in range(3):
                    cache[key]
            with patch.object(pre_tts, 'trans_cache', cache):
                ranked = pre_tts.PreTTSEngine()._scan_and_rank(time.time(), 'Japanese')
            self.assertEqual([text for text, score in ranked], ['こんにちは'])
