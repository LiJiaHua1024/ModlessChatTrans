import time
import unittest
from queue import Queue
from unittest.mock import Mock, patch

from modless_chat_trans.context_buffer import ContextBuffer, ContextEntry
from modless_chat_trans.log_monitor import OrderedProcessor


class ContextProcessingTests(unittest.TestCase):
    def test_preceding_messages_only_are_used_as_context(self):
        queue = Queue()
        for text in ('first', 'second'):
            queue.put((f'[12:00:00] [CHAT] <Steve> {text}', time.time()))
        context = ContextBuffer(strategy='fixed')
        processor = OrderedProcessor(queue, context_buffer=context)
        processor._executor.shutdown()
        jobs = []

        def submit(fn, *args):
            jobs.append((fn, args))
            processor.stop()

        processor._executor = Mock(submit=submit)
        with patch('modless_chat_trans.message_classifier.classify_lines', return_value=[True, True]), \
                patch('modless_chat_trans.web_display.allocate_slot', side_effect=[1, 2]), \
                patch('modless_chat_trans.message_processor.should_skip_message', return_value=False):
            processor._run()
        self.assertEqual(len(context), 2)
        self.assertEqual(jobs[0][1][2], '')
        self.assertIn('first', jobs[1][1][2])
        self.assertNotIn('second', jobs[1][1][2])
        context.push(ContextEntry('third', time.time()))
        with patch('modless_chat_trans.message_processor.translate_prepared',
                   return_value=('Steve', 'translated', {})) as translate, \
                patch('modless_chat_trans.web_display.fill_slot'):
            for fn, args in jobs:
                fn(*args)
        self.assertEqual(translate.call_args_list[0].kwargs['context_text'], '')
        self.assertNotIn('third', translate.call_args_list[1].kwargs['context_text'])

    def test_time_gap_resets_before_snapshot(self):
        context = ContextBuffer(strategy='time_based', context_timeout=10)
        context.push(ContextEntry('old', 100))
        self.assertEqual(context.snapshot_and_push(ContextEntry('new', 120)), '')
        self.assertEqual(len(context), 1)

    def test_stale_context_is_cleared_on_read(self):
        context = ContextBuffer(strategy='time_based', context_timeout=10)
        context.push(ContextEntry('old', time.time() - 100))
        self.assertEqual(context.get_context_messages(), '')
        self.assertEqual(len(context), 0)

    def test_fresh_context_survives_read(self):
        context = ContextBuffer(strategy='time_based', context_timeout=10)
        context.push(ContextEntry('recent', time.time() - 5))
        self.assertIn('recent', context.get_context_messages())

    def test_disabled_context_stays_empty(self):
        context = ContextBuffer(strategy='disabled')
        self.assertEqual(context.snapshot_and_push(ContextEntry('message', 100)), '')
        self.assertEqual(len(context), 0)

    def test_sliding_window_keeps_latest_entries_only(self):
        context = ContextBuffer(strategy='fixed', context_length=3)
        for index in range(5):
            context.push(ContextEntry(f'message {index}', 100 + index))
        self.assertEqual(len(context), 3)
        content = context.get_context_messages()
        self.assertIn('message 4', content)
        self.assertIn('message 2', content)
        self.assertNotIn('message 1', content)
        self.assertNotIn('message 0', content)

    def test_single_entry_window_stays_at_one(self):
        context = ContextBuffer(strategy='fixed', context_length=1)
        for index in range(3):
            context.push(ContextEntry(f'message {index}', 100 + index))
            self.assertEqual(len(context), 1)
        self.assertIn('message 2', context.get_context_messages())

    def test_unlimited_window_keeps_everything(self):
        context = ContextBuffer(strategy='fixed', context_length=0)
        for index in range(20):
            context.push(ContextEntry(f'message {index}', 100 + index))
        self.assertEqual(len(context), 20)
