import os
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

from modless_chat_trans.log_monitor import EfficientLogMonitor, CompatiblePollingMonitor


class LogRotationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.path = self.directory / 'latest.log'
        self.path.write_text('[CHAT] <Steve> existing history ' + 'x' * 300 + '\n', encoding='utf-8')
        self.queue = Queue()

    def monitor(self, directory=False):
        monitor = EfficientLogMonitor(str(self.directory if directory else self.path), 'utf-8', self.queue)
        self.addCleanup(monitor.close)
        return monitor

    def event(self, path=None):
        return SimpleNamespace(src_path=str(path or self.path))

    def test_initial_history_is_skipped_and_append_is_read_once(self):
        monitor = self.monitor()
        monitor.on_modified(self.event())
        self.assertTrue(self.queue.empty())
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write('[CHAT] <Steve> appended\n')
        monitor.on_modified(self.event())
        monitor.on_modified(self.event())
        self.assertEqual(self.queue.qsize(), 1)
        self.assertIn('appended', self.queue.get()[0])

    def test_truncation_restarts_from_beginning(self):
        monitor = self.monitor(directory=True)
        self.path.write_text('[CHAT] <Steve> new session\n', encoding='utf-8')
        monitor.on_modified(self.event())
        self.assertEqual(self.queue.qsize(), 1)
        self.assertIn('new session', self.queue.get()[0])

    def test_same_path_replacement_is_detected_even_when_larger(self):
        monitor = self.monitor()
        replacement = self.directory / 'replacement.tmp'
        replacement.write_text('[CHAT] <Steve> replacement ' + 'y' * 600 + '\n', encoding='utf-8')
        self.path.rename(self.directory / 'archived.tmp')
        os.replace(replacement, self.path)
        monitor.on_modified(self.event())
        self.assertEqual(self.queue.qsize(), 1)
        self.assertIn('replacement', self.queue.get()[0])

    def test_deleted_file_can_be_recreated_at_same_path(self):
        monitor = self.monitor()
        self.path.unlink()
        monitor.on_deleted(self.event())
        monitor.on_modified(self.event())
        self.path.write_text('[CHAT] <Steve> recreated\n', encoding='utf-8')
        monitor.on_created(self.event())
        self.assertEqual(self.queue.qsize(), 1)
        self.assertIn('recreated', self.queue.get()[0])

    def test_new_directory_log_is_read_without_later_modified_event(self):
        monitor = self.monitor(directory=True)
        newer = self.directory / 'new.log'
        newer.write_text('[CHAT] <Steve> new file\n', encoding='utf-8')
        later = self.path.stat().st_mtime + 10
        os.utime(newer, (later, later))
        monitor.on_created(self.event(newer))
        self.assertEqual(self.queue.qsize(), 1)
        self.assertIn('new file', self.queue.get()[0])

    def test_moved_file_is_read_at_fixed_destination(self):
        monitor = self.monitor()
        replacement = self.directory / 'replacement.tmp'
        replacement.write_text('[CHAT] <Steve> moved\n', encoding='utf-8')
        self.path.rename(self.directory / 'archived.tmp')
        os.replace(replacement, self.path)
        monitor.on_moved(SimpleNamespace(src_path=str(replacement), dest_path=str(self.path)))
        self.assertEqual(self.queue.qsize(), 1)
        self.assertIn('moved', self.queue.get()[0])

    def test_compatible_mode_still_detects_truncation(self):
        monitor = CompatiblePollingMonitor(str(self.path), 'utf-8', self.queue)
        self.addCleanup(monitor.close)
        self.path.write_text('[CHAT] <Steve> truncated\n', encoding='utf-8')
        self.assertTrue(monitor._check_rotation_or_truncate())
        self.assertIn('truncated', monitor.fp.readline())
