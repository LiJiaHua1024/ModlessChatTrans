import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modless_chat_trans import web_display as display
from modless_chat_trans.config import TTSConfig
from modless_chat_trans.tts_engine import infer_voice


class ManualTTSTests(unittest.TestCase):
    def read(self, target_language, voice='auto'):
        engine = SimpleNamespace(_config=TTSConfig(enabled=True, voice=voice), interrupt_and_read=Mock())
        apps = []
        with patch('flask.Flask.run', lambda app, **kwargs: apps.append(app)):
            display.start_httpserver(0, lambda *args, **kwargs: '', engine, target_language)
        with apps[0].test_client() as client:
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

    def test_explicit_voice_still_takes_precedence(self):
        self.assertEqual(self.read('Japanese', 'en-US-JennyNeural'), 'en-US-JennyNeural')

    def test_server_thread_forwards_target_language(self):
        callback = Mock()
        engine = Mock()
        with patch.object(display.threading, 'Thread') as thread:
            display.start_httpserver_thread(http_port=8080, callback=callback,
                                            tts_engine=engine, target_language='Japanese')
        self.assertEqual(thread.call_args.kwargs['args'], (8080, callback, engine, 'Japanese'))
        thread.return_value.start.assert_called_once()
