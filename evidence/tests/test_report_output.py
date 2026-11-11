"""Native report reservation preserves existing paths and has one creator."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

from evidence.evals.report_output import reserve_new_report


class ReportOutputTests(unittest.TestCase):
    def test_existing_file_and_directory_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'report.json'
            with reserve_new_report(report) as output:
                output.write('synthetic sentinel')
            for path in (report, Path(folder)):
                with self.subTest(path=path.name), self.assertRaises(OSError):
                    with reserve_new_report(path):
                        self.fail('Existing path was opened as a new report')
            self.assertEqual(report.read_text(), 'synthetic sentinel')

    def test_competing_creators_have_one_winner(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'one-report.json'
            barrier = threading.Barrier(8)
            def create(index):
                barrier.wait(timeout=5)
                try:
                    with reserve_new_report(report) as output:
                        output.write(str(index))
                    return index
                except OSError:
                    return None
            with ThreadPoolExecutor(max_workers=8) as pool:
                winners = [value for value in pool.map(create, range(8)) if value is not None]
            self.assertEqual(len(winners), 1)
            self.assertEqual(report.read_text(), str(winners[0]))
