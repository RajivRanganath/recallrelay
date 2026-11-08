"""Output-path failures and competing CLI runs must precede credential/provider use."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from evidence.ai.omniroute import OmniRouteExtractor
from evidence.evals import live, plan
from test_extraction import raw_output


class EvaluationOutputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.plan = self.folder / 'plan.json'
        adapter = OmniRouteExtractor('synthetic-test-key', model='test/vision')
        self.plan.write_text(json.dumps(plan.freeze(plan.load_dataset(case_ids=['clear-png']), adapter)))

    def arguments(self, output, planned=False):
        args = ['live', '--model', 'test/vision', '--case', 'clear-png', '--output', str(output)]
        return args + (['--plan', str(self.plan)] if planned else [])

    def rejected_before_calls(self, output, planned=False):
        with patch('sys.argv', self.arguments(output, planned)), \
                patch('evidence.evals.live.read_key', return_value='synthetic-test-key') as key, \
                patch.object(OmniRouteExtractor, 'extract', return_value=raw_output()) as extract, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as error:
                live.main()
            self.assertEqual(error.exception.code, 2)
            key.assert_not_called()
            extract.assert_not_called()

    def test_unplanned_existing_report_is_never_overwritten(self):
        output = self.folder / 'historical.json'
        output.write_text('preserve historical bytes')
        self.rejected_before_calls(output)
        self.assertEqual(output.read_text(), 'preserve historical bytes')

    def test_invalid_parent_is_rejected_before_keys_or_extraction_in_both_modes(self):
        parent = self.folder / 'not-a-directory'
        parent.write_text('sentinel')
        for planned in (False, True):
            with self.subTest(planned=planned):
                self.rejected_before_calls(parent / 'report.json', planned)
        self.assertEqual(parent.read_text(), 'sentinel')

    def test_existing_and_dangling_output_symlinks_are_rejected_in_both_modes(self):
        existing = self.folder / 'existing-target.json'
        existing.write_text('preserve target bytes')
        missing = self.folder / 'missing-target.json'
        for planned in (False, True):
            for target in (existing, missing):
                output = self.folder / f'link-{planned}-{target.stem}.json'
                output.symlink_to(target)
                with self.subTest(planned=planned, target=target.stem):
                    self.rejected_before_calls(output, planned)
                    self.assertTrue(output.is_symlink())
        self.assertEqual(existing.read_text(), 'preserve target bytes')
        self.assertFalse(missing.exists())

    def test_output_is_reserved_before_key_read_and_success_still_writes_complete_report(self):
        for planned in (False, True):
            output = self.folder / f'nested-{planned}/report.json'
            def key(_env_file=None):
                self.assertTrue(output.is_file(), 'Output is not reserved before reading a key')
                self.assertEqual(output.read_bytes(), b'')
                with self.assertRaises(FileExistsError):
                    with output.open('x'):
                        pass
                return 'synthetic-test-key'
            with self.subTest(planned=planned), patch('sys.argv', self.arguments(output, planned)), \
                    patch('evidence.evals.live.read_key', side_effect=key), \
                    patch.object(OmniRouteExtractor, 'extract', return_value=raw_output()) as extract, \
                    redirect_stdout(StringIO()):
                live.main()
            self.assertEqual(extract.call_count, 1)
            report = json.loads(output.read_text())
            self.assertEqual((report['cases_attempted'], report['proposals'], report['unavailable']), (1, 1, 0))

    def test_competing_runs_cannot_both_read_keys_or_call_provider_for_one_output(self):
        output = self.folder / 'shared.json'
        started, release = threading.Event(), threading.Event()
        failures = []
        call_lock = threading.Lock()
        calls = [0]
        def extract(image):
            with call_lock:
                calls[0] += 1
                number = calls[0]
            if number == 1:
                started.set()
                if not release.wait(5):
                    raise RuntimeError('Authored test wait expired')
            return raw_output()
        def run():
            try:
                live.main()
            except BaseException as error:
                failures.append(error)
        with patch('sys.argv', self.arguments(output)), \
                patch('evidence.evals.live.read_key', return_value='synthetic-test-key') as key, \
                patch.object(OmniRouteExtractor, 'extract', side_effect=extract), \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            worker = threading.Thread(target=run)
            worker.start()
            try:
                self.assertTrue(started.wait(5))
                with self.assertRaises(SystemExit) as error:
                    live.main()
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(key.call_count, 1)
                self.assertEqual(calls[0], 1)
            finally:
                release.set()
                worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(json.loads(output.read_text())['cases_attempted'], 1)

    def test_credential_failure_closes_reservation_without_extraction(self):
        output = self.folder / 'key-failure.json'
        opened = []
        original = Path.open
        def capture(path, *args, **kwargs):
            file = original(path, *args, **kwargs)
            if path == output and args and args[0] == 'x':
                opened.append(file)
            return file
        with patch('sys.argv', self.arguments(output)), patch.object(Path, 'open', capture), \
                patch('evidence.evals.live.read_key', side_effect=ValueError('synthetic key error')), \
                patch.object(OmniRouteExtractor, 'extract') as extract, redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as error:
                live.main()
            self.assertEqual(error.exception.code, 2)
        extract.assert_not_called()
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)
        self.assertEqual(output.read_bytes(), b'')

    def test_write_or_close_failure_after_calls_is_visible_and_does_not_retry(self):
        output = self.folder / 'write-failure.json'
        original = Path.open
        opened = []
        class FailingWriter:
            def __init__(self, file): self.file = file
            def __enter__(self): return self
            def __exit__(self, *args):
                self.file.close()
                raise OSError('private synthetic close detail')
            def write(self, value): raise OSError('private synthetic write detail')
        def capture(path, *args, **kwargs):
            file = original(path, *args, **kwargs)
            if path == output and args and args[0] == 'x':
                opened.append(file)
                return FailingWriter(file)
            return file
        errors = StringIO()
        with patch('sys.argv', self.arguments(output)), patch.object(Path, 'open', capture), \
                patch('evidence.evals.live.read_key', return_value='synthetic-test-key') as key, \
                patch.object(OmniRouteExtractor, 'extract', return_value=raw_output()) as extract, \
                redirect_stdout(StringIO()), redirect_stderr(errors):
            with self.assertRaises(SystemExit) as error:
                live.main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual((key.call_count, extract.call_count), (1, 1))
        self.assertTrue(opened[0].closed)
        self.assertIn('incomplete', errors.getvalue())
        self.assertNotIn('private synthetic', errors.getvalue())
