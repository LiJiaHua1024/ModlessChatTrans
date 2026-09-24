import ast
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock, patch

from modless_chat_trans import clipboard_monitor as clipboard


class ClipboardDeliveryTests(unittest.TestCase):
    def test_failed_copy_does_not_update_monitor_state(self):
        with patch.object(clipboard, 'CLIPBOARD_AVAILABLE', True), \
                patch.object(clipboard, 'previous_clipboard_content', 'original'), \
                patch.object(clipboard, 'pyperclip', SimpleNamespace(copy=Mock(side_effect=RuntimeError('busy')))):
            self.assertFalse(clipboard.modify_clipboard('translated'))
            self.assertEqual(clipboard.previous_clipboard_content, 'original')

    def test_send_callback_reports_copy_failure_and_preserves_translation(self):
        tree = ast.parse(Path('src/main.py').read_text(encoding='utf-8'))
        start = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start_translation')
        callback = next(n for n in start.body if isinstance(n, ast.FunctionDef) and n.name == 'callback')
        output = Mock()
        namespace = dict(time=time, logger=Mock(), _=lambda text: text,
                         context_buffer=SimpleNamespace(get_context_messages=lambda: []),
                         config=SimpleNamespace(message_send=SimpleNamespace(source_language='en', target_language='zh')),
                         send_translator=Mock(), process_message=lambda *a, **kw: (False, '译文', {}),
                         modify_clipboard=lambda text: False, display_message=output, fill_slot=output)
        exec(compile(ast.Module(body=[callback], type_ignores=[]), 'src/main.py', 'exec'), namespace)
        result = namespace['callback']('hello', time.time())
        self.assertIn('译文', result['error'])
        self.assertEqual(output.call_args.args[0], '[ERROR]')
        self.assertTrue(output.call_args.args[2]['send_translation_complete'])
