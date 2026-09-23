import socket
import unittest
import urllib.request
from unittest.mock import Mock, patch

from modless_chat_trans import web_display as display


def _occupy_port():
    """真实占用一个本地端口用于模拟端口冲突，返回 (socket, port)。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    sock.listen(1)
    return sock, sock.getsockname()[1]


class HTTPStartupTests(unittest.TestCase):
    def test_bind_failure_reaches_caller_without_starting_thread(self):
        for error in (OSError('port busy'), SystemExit(1)):
            with self.subTest(error=error), \
                    patch.object(display, '_port_in_use', return_value=False), \
                    patch.object(display, 'make_server', side_effect=error), \
                    patch.object(display.threading, 'Thread') as thread:
                with self.assertRaisesRegex(RuntimeError, '8080'):
                    display.start_httpserver_thread(http_port=8080, callback=Mock())
                thread.assert_not_called()

    def test_thread_start_failure_releases_bound_port(self):
        with patch.object(display, '_port_in_use', return_value=False), \
                patch.object(display, 'make_server') as make, \
                patch.object(display.threading, 'Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('thread unavailable')
            with self.assertRaises(RuntimeError):
                display.start_httpserver_thread(http_port=8080, callback=Mock())
            make.return_value.server_close.assert_called_once()

    def test_occupied_port_raises_without_starting_thread(self):
        sock, port = _occupy_port()
        self.addCleanup(sock.close)
        with patch.object(display.threading, 'Thread') as thread:
            with self.assertRaisesRegex(RuntimeError, str(port)):
                display.start_httpserver_thread(http_port=port, callback=Mock())
            thread.assert_not_called()

    def test_started_server_serves_http(self):
        server = display.start_httpserver_thread(http_port=0, callback=lambda *a, **k: '')
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/', timeout=5) as resp:
            self.assertEqual(resp.status, 200)
