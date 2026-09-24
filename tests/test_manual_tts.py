import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modless_chat_trans import web_display as display
from modless_chat_trans.config import TTSConfig
from modless_chat_trans.tts_engine import infer_voice


class ManualTTSTests(unittest.TestCase):
    def read(self, target_language, voice='auto'):
        engine = SimpleNamespace(_config=TTSConfig(enabled=True, voice=voice), interrupt_and_read=Mock())
        app = display.create_http_app(lambda *args, **kwargs: '', engine, target_language)
        with app.test_client() as client:
            response = client.post('/read-aloud', json={'text': 'test message'})
        self.assertEqual(response.status_code, 200)
        engine.interrupt_and_read.assert_called_once_with('test message', target_language)
        return infer_voice(engine.interrupt_and_read.call_args.args[1], engine._config.voice)

    def tearDown(self):
        display.clear_message_history()

    def test_manual_reading_uses_capture_target_language(self):
        for language, voice in [('Japanese', 'ja-JP-NanamiNeural'),
                                ('en-US', 'en-US-JennyNeural'),
                                ('zh-TW', 'zh-TW-HsiaoChenNeural')]:
            with self.subTest(language=language):
                self.assertEqual(self.read(language), voice)

    def test_language_codes_map_to_matching_voices(self):
        for language, voice in [('es', 'es-ES-ElviraNeural'),
                                ('es-MX', 'es-ES-ElviraNeural'),
                                ('zh-Hant', 'zh-TW-HsiaoChenNeural'),
                                ('zh-CHT', 'zh-TW-HsiaoChenNeural'),
                                ('zh-Hant-HK', 'zh-TW-HsiaoChenNeural'),
                                ('zh-Hans', 'zh-CN-XiaoxiaoNeural'),
                                ('ja', 'ja-JP-NanamiNeural')]:
            with self.subTest(language=language):
                self.assertEqual(infer_voice(language, 'auto'), voice)

    def test_explicit_voice_still_takes_precedence(self):
        self.assertEqual(self.read('Japanese', 'en-US-JennyNeural'), 'en-US-JennyNeural')

    def test_server_thread_forwards_target_language(self):
        callback = Mock()
        engine = Mock()
        with patch.object(display.threading, 'Thread') as thread, \
                patch.object(display, 'create_http_app') as create_app, \
                patch.object(display, '_port_in_use', return_value=False), \
                patch.object(display, 'make_server'):
            display.start_httpserver_thread(http_port=8080, callback=callback,
                                            tts_engine=engine, target_language='Japanese')
        create_app.assert_called_once_with(callback, engine, 'Japanese')
        thread.return_value.start.assert_called_once()
