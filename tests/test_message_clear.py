import unittest
from unittest.mock import patch

from modless_chat_trans import web_display as display


class MessageClearTests(unittest.TestCase):
    def setUp(self):
        self.client = display.create_http_app(lambda *args, **kwargs: '').test_client()
        self.addCleanup(display.clear_message_history)

    def test_old_task_cannot_overwrite_new_slot(self):
        old = display.allocate_slot('old')
        self.assertEqual(self.client.post('/clear-messages').status_code, 200)
        new = display.allocate_slot('new')
        self.assertGreater(new, old)
        display.fill_slot(old, 'old', 'old result', {})
        self.assertTrue(display.messages_by_id[new]['pending'])
        self.assertEqual(len(display.http_messages), 1)
        display.fill_slot(new, 'new', 'new result', {})
        self.assertEqual(display.messages_by_id[new]['message'], 'new result')

    def test_cleared_task_does_not_reappear_without_new_messages(self):
        old = display.allocate_slot()
        self.client.post('/clear-messages')
        display.fill_slot(old, 'old', 'late result', {})
        self.assertEqual(len(display.http_messages), 0)

    def test_timeout_and_eviction_still_publish_late_results(self):
        timed_out = display.allocate_slot()
        display.messages_by_id[timed_out]['timed_out'] = True
        display.fill_slot(timed_out, 'Steve', 'late timeout result', {})
        self.assertEqual(display.http_messages[-1]['message'], 'late timeout result')
        with patch.object(display, 'MAX_HTTP_MESSAGES', 1):
            display.clear_message_history()
            evicted = display.allocate_slot()
            display.allocate_slot()
            display.fill_slot(evicted, 'Steve', 'late evicted result', {})
            self.assertEqual(display.http_messages[-1]['message'], 'late evicted result')

    def test_stream_reconnect_after_clear_delivers_new_message(self):
        old = display.allocate_slot()
        self.client.post('/clear-messages')
        display.display_message('Steve', 'new result', {})
        response = self.client.get(f'/stream?last_event_id={old}', buffered=False)
        try:
            chunks = iter(response.response)
            self.assertIn(b'retry:', next(chunks))
            self.assertIn(b'id:', next(chunks))
            self.assertIn(b'new result', next(chunks))
        finally:
            response.close()
