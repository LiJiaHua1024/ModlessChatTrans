import time
import unittest
from queue import Queue
from unittest.mock import Mock, patch

from modless_chat_trans.context_buffer import ContextBuffer, ContextEntry
from modless_chat_trans.log_monitor import OrderedProcessor


class ContextProcessingTests(unittest.TestCase):
    def test_batch_uses_only_preceding_messages(self):
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
        self.assertEqual(jobs[0][1][2], [])
        self.assertIn('first', jobs[1][1][2][0]['content'])
        self.assertNotIn('second', jobs[1][1][2][0]['content'])
        context.push(ContextEntry('third', time.time()))
        with patch('modless_chat_trans.message_processor.translate_prepared',
                   return_value=('Steve', 'translated', {})) as translate, \
                patch('modless_chat_trans.web_display.fill_slot'):
            for fn, args in jobs:
                fn(*args)
        self.assertEqual(translate.call_args_list[0].kwargs['context_messages'], [])
        self.assertNotIn('third', translate.call_args_list[1].kwargs['context_messages'][0]['content'])

    def test_time_gap_resets_before_snapshot(self):
        context = ContextBuffer(strategy='time_based', context_timeout=10)
        context.push(ContextEntry('old', 100))
        self.assertEqual(context.snapshot_and_push(ContextEntry('new', 120)), [])
        self.assertEqual(len(context), 1)

    def test_disabled_context_stays_empty(self):
        context = ContextBuffer(strategy='disabled')
        self.assertEqual(context.snapshot_and_push(ContextEntry('message', 100)), [])
        self.assertEqual(len(context), 0)
