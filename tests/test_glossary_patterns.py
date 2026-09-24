import unittest
from unittest.mock import patch

from modless_chat_trans import message_processor as processor
from modless_chat_trans.glossary_patterns import VARIABLE_PATTERN


class GlossaryPatternTests(unittest.TestCase):
    def translate(self, source, target, text):
        with patch.object(processor, 'glossary', {source: target}), \
                patch.object(processor, 'glossary_compiled', False), \
                patch.object(processor, '_compiled_glossary_patterns', {}):
            return processor.match_and_translate(text)

    def test_quantifiers(self):
        for regex in (r'\d{3}', r'\d{1,3}', r'\d{2,}', r'\d+'):
            with self.subTest(regex=regex):
                source = 'ID {{id:' + regex + '}}'
                self.assertEqual(self.translate(source, 'number={{id}}', 'ID 123'), 'number=123')
                self.assertIsNotNone(VARIABLE_PATTERN.search(source))
        self.assertIsNone(self.translate(r'ID {{id:\d{3}}}', '{{id}}', 'ID 12'))

    def test_inner_groups_and_repeated_variables(self):
        source = '{{team:(red|blue)}} {{player-name}} {{player-name}} {{team}}'
        self.assertEqual(self.translate(source, '{{player-name}}:{{team}}', 'red Steve Steve red'), 'Steve:red')
        self.assertIsNone(self.translate(source, '{{team}}', 'red Steve Alex red'))
        self.assertIsNone(self.translate(source, '{{team}}', 'red Steve Steve blue'))

    def test_braces_in_character_classes_and_escapes(self):
        for regex in (r'[}]{2}', r'\}\}'):
            with self.subTest(regex=regex):
                self.assertEqual(self.translate('value {{v:' + regex + '}}', '{{v}}', 'value }}'), '}}')

    def test_plain_and_simple_variable_entries(self):
        self.assertEqual(self.translate('hello', 'hi', 'hello'), 'hi')
        self.assertEqual(self.translate('hello {{name}}', 'hi {{name}}', 'hello Steve'), 'hi Steve')

    def test_invalid_regex_and_undefined_variables_are_skipped(self):
        self.assertIsNone(self.translate('{{v:(}}', '{{v}}', 'hello'))
        self.assertIsNone(self.translate('hello {{name}}', '{{missing}}', 'hello Steve'))

    def test_captured_placeholders_are_not_substituted_again(self):
        self.assertEqual(self.translate('{{a}} / {{b}}', '{{a}} {{b}}', '{{b}} / literal'), '{{b}} literal')
