"""Portable pipe readiness, bounded startup, and cleanup of owned processes."""
from contextlib import contextmanager
import io
from pathlib import Path
import socket
import subprocess
import tempfile
from unittest.mock import patch
import unittest
from urllib.error import URLError
from urllib.request import urlopen

from evidence import integrated
from evidence.demo import DemoSession


class StartupTests(unittest.TestCase):
    def failed_start(self, program, deadline=3):
        original = subprocess.Popen
        children = []
        def spawn(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(integrated, 'MERCHANT', program), \
                patch.object(integrated, 'READY_TIMEOUT', deadline), \
                patch.object(integrated.subprocess, 'Popen', side_effect=spawn):
            with self.assertRaises(RuntimeError):
                with integrated.merchant_process(Path(folder)):
                    self.fail('Invalid or silent startup must fail')
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdout.closed)

    def test_silent_or_partial_startup_times_out_and_reaps_the_child(self):
        for program in ('import time; time.sleep(20)',
                        'import sys,time; sys.stdout.write("{"); sys.stdout.flush(); time.sleep(20)'):
            with self.subTest(program=program):
                self.failed_start(program, deadline=.5)

    def test_eof_malformed_and_invalid_port_fail_cleanly(self):
        for program in ('pass', 'print("not-json", flush=True)',
                        'print(\'{"port": true}\', flush=True)', 'print(\'{"port": 0}\', flush=True)'):
            with self.subTest(program=program):
                self.failed_start(program)

    def test_occupied_port_does_not_stop_the_existing_listener(self):
        with socket.socket() as occupied, tempfile.TemporaryDirectory() as folder:
            occupied.bind(('127.0.0.1', 0))
            occupied.listen()
            address = occupied.getsockname()
            with self.assertRaises(RuntimeError):
                with integrated.merchant_process(Path(folder), address[1]):
                    self.fail('Occupied merchant port must fail startup')
            self.assertEqual(occupied.getsockname(), address)
            self.assertGreaterEqual(occupied.fileno(), 0)

    def test_customer_startup_failure_stops_the_owned_merchant(self):
        original = integrated.merchant_process
        urls = []
        @contextmanager
        def tracked(*args, **kwargs):
            with original(*args, **kwargs) as url:
                urls.append(url)
                yield url
        with patch.object(integrated, 'merchant_process', tracked), \
                patch.object(integrated, 'make_server', side_effect=OSError('synthetic occupied customer port')):
            with self.assertRaises(OSError):
                with integrated.integrated_session():
                    self.fail('Customer startup must fail')
        self.assertEqual(len(urls), 1)
        with self.assertRaises((URLError, OSError)):
            with urlopen(urls[0] + '/health', timeout=1):
                self.fail('Merchant was left running after customer startup failed')

    def test_cli_instructions_work_with_a_windows_legacy_console_encoding(self):
        buffer = io.BytesIO()
        console = io.TextIOWrapper(buffer, encoding='cp1252')
        session = DemoSession('http://127.0.0.1:8101', 'http://127.0.0.1:8102', 'mock', Path('.'))
        with patch.object(integrated, 'integrated_session') as factory, \
                patch.object(integrated.threading, 'Event') as event, \
                patch('sys.argv', ['evidence.integrated']), patch('sys.stdout', console):
            factory.return_value.__enter__.return_value = session
            event.return_value.wait.side_effect = KeyboardInterrupt
            integrated.main()
        console.flush()
        self.assertIn('approve fake refund', buffer.getvalue().decode('cp1252'))
        console.close()
