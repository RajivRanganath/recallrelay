"""Offline evaluation freeze/preflight checks; never contact a provider."""
from contextlib import redirect_stderr, redirect_stdout
import copy
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.ai.omniroute import OmniRouteExtractor
from evidence.evals import live, plan
from test_extraction import raw_output


class EvaluationPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        shutil.copytree(DEFAULT_MANIFEST.parent, self.folder / 'fixtures')
        self.manifest = self.folder / 'fixtures/manifest.json'
        self.data = json.loads(self.manifest.read_text())
        self.adapter = OmniRouteExtractor('synthetic-unit-test-key', model='test/vision')
        self.plan_path = self.folder / 'plan.json'
        self.frozen = plan.freeze(plan.load_dataset(self.manifest, ['clear-png']), self.adapter)
        self.plan_path.write_text(json.dumps(self.frozen))

    def write_manifest(self, data):
        self.manifest.write_text(json.dumps(data))

    def planned(self, adapter=None, **kwargs):
        return live.evaluate(adapter or self.adapter, self.manifest, plan_path=self.plan_path, **kwargs)

    def test_offline_freeze_reads_no_key_makes_no_calls_and_refuses_overwrite(self):
        output = self.folder / 'offline-plan.json'
        args = ['plan', '--manifest', str(self.manifest), '--model', 'test/vision',
                '--case', 'clear-png', '--output', str(output)]
        with patch('sys.argv', args), patch('evidence.ai.omniroute.read_key') as key, \
                patch.object(OmniRouteExtractor, 'extract') as extract, redirect_stdout(StringIO()):
            plan.main()
            before = output.read_bytes()
            with patch('sys.argv', ['plan', '--manifest', str(self.manifest), '--check', str(output)]):
                plan.main()
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                plan.main()
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), before)
        key.assert_not_called()
        extract.assert_not_called()
        self.assertEqual(plan.read_plan(output)['snapshot']['cases'][0]['case_id'], 'clear-png')

    def test_planned_report_binds_snapshot_and_keeps_development_limits(self):
        with patch.object(self.adapter, 'extract', return_value=raw_output()) as extract:
            report = self.planned()
        self.assertEqual(extract.call_count, 1)
        self.assertEqual(report['plan_sha256'], self.frozen['plan_sha256'])
        self.assertEqual(report['evaluation_snapshot'], self.frozen['snapshot'])
        self.assertEqual((report['cases_attempted'], report['fields_compared']), (1, 2))
        self.assertFalse(report['holdout'])
        self.assertFalse(report['human_validated'])
        self.assertFalse(report['confidence_calibrated'])
        self.assertEqual(report['evaluation_snapshot']['adapter']['requested_model'], 'test/vision')

    def test_manifest_references_and_duplicate_cases_fail_before_calls(self):
        def duplicate_id(data):
            data['cases'][1]['case_id'] = data['cases'][0]['case_id']
        def duplicate_hash(data):
            data['cases'][1]['sha256'] = data['cases'][0]['sha256']
        def wrong_decision(data):
            data['cases'][0]['expected_typed_decision'] = 'excluded'
        def wrong_reference(data):
            data['cases'][0]['typed_entry'] = {'model': [], 'batch': 'B101'}
        def empty(data):
            data['cases'] = []
        for mutate in (duplicate_id, duplicate_hash, wrong_decision, wrong_reference, empty):
            data = copy.deepcopy(self.data)
            mutate(data)
            self.write_manifest(data)
            with self.subTest(mutation=mutate.__name__), patch.object(self.adapter, 'extract') as extract:
                with self.assertRaises(ValueError):
                    live.evaluate(self.adapter, self.manifest)
                extract.assert_not_called()

    def test_duplicate_json_keys_and_bad_selection_fail_before_calls(self):
        self.manifest.write_text(json.dumps(self.data).replace('"synthetic_only": true',
                                 '"synthetic_only": true, "synthetic_only": true'))
        with self.assertRaises(ValueError):
            plan.load_dataset(self.manifest)
        self.write_manifest(self.data)
        for ids in ([], ['clear-png', 'clear-png'], ['unknown']):
            with self.subTest(ids=ids), patch.object(self.adapter, 'extract') as extract:
                with self.assertRaises(ValueError):
                    live.evaluate(self.adapter, self.manifest, case_ids=ids)
                extract.assert_not_called()

    def test_frozen_manifest_and_reference_edits_fail_before_calls(self):
        for kind in ('formatting', 'reference'):
            self.write_manifest(self.data)
            if kind == 'formatting':
                # Use the exact bytes from the frozen manifest, then alter only whitespace.
                self.manifest.write_bytes(DEFAULT_MANIFEST.read_bytes() + b'\n')
            else:
                data = copy.deepcopy(self.data)
                data['cases'][0]['typed_entry']['batch'] = 'B999'
                data['cases'][0]['expected_typed_decision'] = 'excluded'
                self.write_manifest(data)
            with self.subTest(kind=kind), patch.object(self.adapter, 'extract') as extract:
                with self.assertRaisesRegex(ValueError, 'Frozen evaluation'):
                    self.planned()
                extract.assert_not_called()

    def test_changed_model_timeout_and_selection_fail_before_calls(self):
        for adapter, ids in ((OmniRouteExtractor('synthetic-key', model='test/other'), None),
                             (OmniRouteExtractor('synthetic-key', model='test/vision', timeout=1), None),
                             (self.adapter, ['clear-jpeg'])):
            with self.subTest(model=adapter.model, timeout=adapter.timeout, ids=ids), \
                    patch.object(adapter, 'extract') as extract:
                with self.assertRaisesRegex(ValueError, 'Frozen evaluation'):
                    self.planned(adapter, case_ids=ids)
                extract.assert_not_called()

    def test_changed_code_and_runtime_fail_before_calls(self):
        root = self.folder / 'source-copy'
        for name in plan.SOURCE_FILES:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(plan.ROOT / name, target)
        changed = root / 'evidence/ai/omniroute.py'
        changed.write_bytes(changed.read_bytes() + b'\n')
        with patch('evidence.evals.plan.ROOT', root), patch.object(self.adapter, 'extract') as extract:
            with self.assertRaisesRegex(ValueError, 'Frozen evaluation'):
                self.planned()
            extract.assert_not_called()
        with patch('evidence.evals.plan.platform.python_version', return_value='different-runtime'), \
                patch.object(self.adapter, 'extract') as extract:
            with self.assertRaisesRegex(ValueError, 'Frozen evaluation'):
                self.planned()
            extract.assert_not_called()

    def test_changed_pixels_paths_and_mime_fail_before_calls(self):
        link = self.manifest.parent / 'linked.png'
        link.symlink_to(self.manifest.parent / 'clear-png.png')
        for value in ('../clear-png.png', 'linked.png'):
            data = copy.deepcopy(self.data)
            data['cases'][0]['image'] = value
            self.write_manifest(data)
            with self.subTest(path=value), self.assertRaises(ValueError):
                plan.load_dataset(self.manifest)
        self.write_manifest(self.data)
        data = copy.deepcopy(self.data)
        data['cases'][0]['mime_type'] = 'image/jpeg'
        self.write_manifest(data)
        with self.assertRaises(ValueError):
            plan.load_dataset(self.manifest)
        self.write_manifest(self.data)
        (self.manifest.parent / 'clear-png.png').write_bytes(b'changed pixels')
        with patch.object(self.adapter, 'extract') as extract:
            with self.assertRaisesRegex(ValueError, 'Fixture bytes changed'):
                self.planned()
            extract.assert_not_called()

    def test_edited_plan_and_false_review_claims_are_rejected(self):
        for change, resign in (({'plan_sha256': '0' * 64}, False),
                               ({'holdout': True}, True), ({'human_validated': True}, True),
                               ({'snapshot': []}, True), ({'snapshot': {'adapter': None}}, True)):
            data = copy.deepcopy(self.frozen)
            data.update(change)
            if resign:
                data['plan_sha256'] = plan.plan_digest(data)
            self.plan_path.write_text(json.dumps(data))
            with self.subTest(change=change), patch.object(self.adapter, 'extract') as extract:
                with self.assertRaises(ValueError):
                    self.planned()
                extract.assert_not_called()

    def test_cli_preflight_fails_before_key_read_and_keeps_existing_report(self):
        output = self.folder / 'existing.json'
        output.write_text('preserve this report')
        args = ['live', '--manifest', str(self.manifest), '--plan', str(self.plan_path), '--output', str(output)]
        for extra in ([], ['--model', 'test/changed']):
            with patch('sys.argv', args + extra), patch('evidence.evals.live.read_key') as key, \
                    patch.object(OmniRouteExtractor, 'extract') as extract, redirect_stderr(StringIO()):
                with self.assertRaises(SystemExit) as error:
                    live.main()
                self.assertEqual(error.exception.code, 2)
                key.assert_not_called()
                extract.assert_not_called()
                self.assertEqual(output.read_text(), 'preserve this report')

    def test_planned_cli_uses_frozen_model_timeout_and_cases(self):
        output = self.folder / 'new-report.json'
        args = ['live', '--manifest', str(self.manifest), '--plan', str(self.plan_path), '--output', str(output)]
        with patch('sys.argv', args), patch('evidence.evals.live.read_key', return_value='synthetic-test-key'), \
                patch.object(OmniRouteExtractor, 'extract', return_value=raw_output()) as extract, \
                redirect_stdout(StringIO()):
            live.main()
        self.assertEqual(extract.call_count, 1)
        report = json.loads(output.read_text())
        self.assertEqual(report['plan_sha256'], self.frozen['plan_sha256'])
        self.assertEqual(report['requested_model'], 'test/vision')
        self.assertEqual(report['request_config']['timeout_seconds'], 20)

    def test_offline_check_detects_changed_configuration_without_credentials(self):
        args = ['plan', '--manifest', str(self.manifest), '--check', str(self.plan_path),
                '--timeout', '1']
        with patch('sys.argv', args), patch('evidence.ai.omniroute.read_key') as key, \
                patch.object(OmniRouteExtractor, 'extract') as extract, redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as error:
                plan.main()
            self.assertEqual(error.exception.code, 2)
            key.assert_not_called()
            extract.assert_not_called()
