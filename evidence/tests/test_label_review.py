"""Authored records test tooling only; they are not human review evidence."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import copy
from html.parser import HTMLParser
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.ai.omniroute import OmniRouteExtractor
from evidence.evals import review
from evidence.evals.plan import digest


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.inputs = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            self.images.append(attrs['src'])
        if tag in ('input', 'textarea'):
            self.inputs.append(attrs)


class LabelReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        shutil.copytree(DEFAULT_MANIFEST.parent, self.folder / 'fixtures')
        self.manifest = self.folder / 'fixtures/manifest.json'
        self.data = json.loads(self.manifest.read_text())
        self.output = self.folder / 'packet'
        self.packet = review.prepare(self.output, self.manifest)
        self.packet_path = self.output / 'packet.json'
        self.record_path = self.folder / 'synthetic-test-record.json'
        self.record = {'review_version': 'evidence-label-review-1',
                       'packet_sha256': self.packet['packet_sha256'],
                       'reviewer': 'synthetic-unit-test-only-not-a-human-review',
                       'reviewed_at_utc': '2026-11-08T00:00:00Z',
                       'reviewer_confirmed_image_review': True, 'cases': []}
        for sample, case in zip(self.packet['cases'], self.data['cases']):
            row = {'sample_id': sample['sample_id'], 'image_sha256': sample['image_sha256'], 'note': ''}
            for field in ('model', 'batch'):
                value = case['typed_entry'][field]
                row[field] = {'status': 'readable' if value is not None else 'unreadable', 'value': value}
            self.record['cases'].append(row)
        self.write_record(self.record)

    def write_record(self, record):
        self.record_path.write_text(json.dumps(record))

    def check(self):
        return review.check_review(self.packet_path, self.record_path, self.manifest)

    def test_packet_contains_checked_pixels_and_blank_fields_without_reference_answers(self):
        page = (self.output / 'review.html').read_text()
        parsed = Images()
        parsed.feed(page)
        self.assertEqual(len(parsed.images), 12)
        self.assertEqual(self.packet['manifest_sha256'], digest(self.manifest.read_bytes()))
        self.assertFalse(self.packet['holdout'])
        self.assertFalse(self.packet['human_validated'])
        for image, sample in zip(parsed.images, self.packet['cases']):
            self.assertEqual(digest(base64.b64decode(image.split(',', 1)[1])), sample['image_sha256'])
            self.assertEqual(set(sample), {'sample_id', 'image_sha256'})
        for control in parsed.inputs:
            self.assertNotIn('value', control)
            self.assertNotIn('checked', control)
        for hidden_answer in ('typed_entry', 'mock_output', 'expected_typed_decision', 'ground_truth'):
            self.assertNotIn(hidden_answer, page)
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn('<!--REVIEW_CARDS-->', page)
        self.assertNotIn('<!--PACKET_DATA-->', page)

    def test_matching_test_record_is_self_reported_and_never_changes_manifest_or_flags(self):
        before = self.manifest.read_bytes()
        self.record['cases'].reverse()  # Coverage is by opaque ID, not submitted order.
        self.write_record(self.record)
        report = self.check()
        self.assertEqual((report['cases_reviewed'], report['fields_compared']), (12, 24))
        self.assertEqual(report['disagreements_with_authored_reference'], 0)
        self.assertFalse(report['holdout'])
        self.assertFalse(report['human_validated'])
        self.assertFalse(report['reviewer_identity_verified'])
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual(report['review_record_sha256'], digest(self.record_path.read_bytes()))

    def test_disagreement_is_preserved_without_deciding_which_reference_is_correct(self):
        self.record['cases'][0]['batch']['value'] = 'B999'
        self.write_record(self.record)
        report = self.check()
        self.assertEqual(report['disagreements_with_authored_reference'], 1)
        row = next(row for row in report['results'] if not row['matches_authored_reference'])
        self.assertEqual((row['review_value'], row['authored_reference']), ('B999', 'B101'))
        self.assertIn('adjudication', report['limitation'])

    def test_incomplete_duplicate_unknown_and_mismatched_records_are_rejected(self):
        mutations = []
        def missing(record): record['cases'].pop()
        def duplicate(record): record['cases'][1] = copy.deepcopy(record['cases'][0])
        def unknown(record): record['cases'][0]['sample_id'] = 'unknown'
        def hash_change(record): record['cases'][0]['image_sha256'] = '0' * 64
        def wrong_packet(record): record['packet_sha256'] = '0' * 64
        def no_attestation(record): record['reviewer_confirmed_image_review'] = False
        def no_reviewer(record): record['reviewer'] = ' '
        def false_claim(record): record['human_validated'] = True
        def bad_time(record): record['reviewed_at_utc'] = '2026-11-08T00:00:00'
        mutations.extend((missing, duplicate, unknown, hash_change, wrong_packet, no_attestation,
                          no_reviewer, false_claim, bad_time))
        for mutate in mutations:
            record = copy.deepcopy(self.record)
            mutate(record)
            self.write_record(record)
            with self.subTest(mutation=mutate.__name__), self.assertRaises(ValueError):
                self.check()

    def test_readability_and_values_must_be_consistent(self):
        invalid = ({'status': '', 'value': None}, {'status': 'readable', 'value': ''},
                   {'status': 'readable', 'value': ' padded '}, {'status': 'readable', 'value': True},
                   {'status': 'readable', 'value': 'line\nbreak'}, {'status': [], 'value': None},
                   {'status': 'conflicting', 'value': 'B101'}, {'status': 'missing', 'value': ''})
        for field in invalid:
            record = copy.deepcopy(self.record)
            record['cases'][0]['batch'] = field
            self.write_record(record)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
        for status in ('missing', 'unreadable', 'conflicting'):
            record = copy.deepcopy(self.record)
            record['cases'][0]['batch'] = {'status': status, 'value': None}
            self.write_record(record)
            self.assertEqual(self.check()['disagreements_with_authored_reference'], 1)

    def test_dataset_and_packet_drift_fail_before_record_comparison(self):
        original = self.manifest.read_bytes()
        self.manifest.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.check()
        self.manifest.write_bytes(original)
        image = self.manifest.parent / self.data['cases'][0]['image']
        image.write_bytes(image.read_bytes() + b'changed')
        with self.assertRaises(ValueError):
            self.check()

    def test_edited_packet_claims_and_strict_json_are_rejected(self):
        for field, value in (('holdout', True), ('human_validated', True), ('holdout', 0)):
            packet = copy.deepcopy(self.packet)
            packet[field] = value
            packet['packet_sha256'] = review.fingerprint(packet)
            self.packet_path.write_text(json.dumps(packet))
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.check()
        self.packet_path.write_text(json.dumps(self.packet))
        self.record_path.write_text(json.dumps(self.record).replace('"reviewer":', '"reviewer": "duplicate", "reviewer":', 1))
        with self.assertRaises(ValueError):
            self.check()
        self.record_path.write_text('x' * (review.LIMIT + 1))
        with self.assertRaises(ValueError):
            self.check()

    def test_cli_offline_export_check_and_existing_outputs_are_preserved(self):
        candidate = self.folder / 'cli-packet'
        output = self.folder / 'report.json'
        create = ['review', 'prepare', '--manifest', str(self.manifest), '--output', str(candidate)]
        check = ['review', 'check', '--manifest', str(self.manifest), '--packet', str(self.packet_path),
                 '--review', str(self.record_path), '--output', str(output)]
        with patch('evidence.ai.omniroute.read_key') as key, patch.object(OmniRouteExtractor, 'extract') as extract, \
                redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            with patch('sys.argv', create):
                review.main()
                before = (candidate / 'review.html').read_bytes()
                with self.assertRaises(SystemExit) as error:
                    review.main()
                self.assertEqual(error.exception.code, 2)
                self.assertEqual((candidate / 'review.html').read_bytes(), before)
            with patch('sys.argv', check):
                review.main()
                before = output.read_bytes()
                with self.assertRaises(SystemExit) as error:
                    review.main()
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(output.read_bytes(), before)
        key.assert_not_called()
        extract.assert_not_called()

    def test_cli_writes_complete_disagreement_report_then_exits_nonzero(self):
        self.record['cases'][0]['batch']['value'] = 'B999'
        self.write_record(self.record)
        output = self.folder / 'disagreement.json'
        args = ['review', 'check', '--manifest', str(self.manifest), '--packet', str(self.packet_path),
                '--review', str(self.record_path), '--output', str(output)]
        with patch('sys.argv', args), redirect_stdout(StringIO()), self.assertRaises(SystemExit) as error:
            review.main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(json.loads(output.read_text())['disagreements_with_authored_reference'], 1)
