"""Synthetic rows exercise reporting mechanics; no human observations are supplied."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence.evals import study_report as study


class StudyReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.sessions = self.folder / 'sessions.csv'
        self.trials = self.folder / 'trials.csv'
        self.dataset = study.load_dataset()
        self.session = dict.fromkeys(next(csv.reader((study.TEMPLATES / 'sessions.csv').read_text().splitlines())), '')
        self.session.update(session_id='synthetic-session', participant_alias='synthetic-tooling-not-human',
                            protocol_version='rajiv-human-evaluation-1', protocol_commit='a' * 40,
                            evidence_commit='b' * 40, consent_recorded='true', prior_image_exposure='known',
                            prior_app_experience='tooling only', started_at_utc='2026-11-08T00:00:00Z',
                            reference_version='synthetic-labels-v1', reference_scoring_status='provisional',
                            extraction_mode='mock', provider='fixture', requested_model='na', browser='test',
                            device='test', condition_order='typed_first', case_order='manifest_then_reverse',
                            warmup_completed='true', notes='PRIVATE-NOTE-DO-NOT-EXPORT')
        self.write([], [])

    def trial(self, condition='typed', case_index=0, **overrides):
        case = self.dataset['cases'][case_index]
        row = dict.fromkeys(next(csv.reader((study.TEMPLATES / 'trials.csv').read_text().splitlines())), '')
        row.update(session_id=self.session['session_id'], participant_alias=self.session['participant_alias'],
                   case_id=case['case_id'], image_sha256=case['sha256'], condition=condition,
                   extraction_mode='mock', position='1' if condition == 'typed' else '2', attempt='1',
                   elapsed_seconds='10' if condition == 'typed' else '7', outcome='completed',
                   final_model=case['typed_entry']['model'] or 'null', final_batch=case['typed_entry']['batch'] or 'null',
                   final_decision=case['expected_typed_decision'], clarification_field='na',
                   clarification_appropriate='na', clarification_rounds='0',
                   suggested_identifier_fields_edited='na' if condition == 'typed' else '0',
                   extraction_unavailable='false', reference_version='synthetic-labels-v1',
                   reference_scoring_status='provisional', notes='PRIVATE-TRIAL-NOTE')
        row.update(overrides)
        return row

    def write(self, sessions, trials):
        for path, rows in ((self.sessions, sessions), (self.trials, trials)):
            headers = next(csv.reader((study.TEMPLATES / path.name).read_text().splitlines()))
            with path.open('w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)

    def report(self):
        return study.report(self.sessions, self.trials)

    def test_blank_templates_never_become_human_observations(self):
        with patch('evidence.ai.omniroute.read_key', side_effect=AssertionError('No credentials')):
            result = self.report()
        self.assertEqual(result['status'], 'no_observations')
        self.assertEqual(result['recorded_attempts'], 0)
        self.assertEqual(result['sessions'], [])
        self.assertFalse(result['human_validated'])
        self.assertFalse(result['holdout'])
        self.write([self.session], [])
        summary = self.report()['sessions'][0]
        self.assertEqual(summary['unrecorded_first_attempts'], 24)
        self.assertIsNone(summary['paired_typed_minus_assisted_seconds']['median'])

    def test_first_attempt_failures_and_retries_are_not_replaced_or_hidden(self):
        failed = self.trial('assisted', outcome='failed', elapsed_seconds='', extraction_unavailable='true')
        retry = self.trial('assisted', position='3', attempt='2')
        self.write([self.session], [self.trial(), failed, retry])
        summary = self.report()['sessions'][0]
        assisted = summary['conditions']['assisted']
        self.assertEqual(assisted['first_attempts']['outcomes']['failed'], 1)
        self.assertEqual(assisted['first_attempts']['reported_extraction_unavailable'], 1)
        self.assertIsNone(assisted['first_attempts']['completed_elapsed_seconds']['median'])
        self.assertEqual(assisted['retries']['completed_elapsed_seconds']['median'], 7)
        self.assertEqual(summary['completed_first_attempt_pairs'], [])
        self.assertEqual(summary['unpaired_cases'][0]['assisted'], 'failed')

    def test_pairing_is_by_same_session_case_and_first_attempt(self):
        typed, assisted = self.trial(), self.trial('assisted')
        self.write([self.session], [assisted, typed])  # CSV row order is not task identity.
        result = self.report()
        summary = result['sessions'][0]
        self.assertEqual(summary['paired_typed_minus_assisted_seconds']['median'], 3)
        self.assertEqual(summary['paired_typed_minus_assisted_seconds']['count'], 1)
        self.assertEqual(len(summary['unpaired_cases']), 11)
        self.assertFalse(summary['first_attempt_order_matches_protocol_prefix'])
        rendered = json.dumps(result)
        for hidden in (self.session['participant_alias'], 'PRIVATE-NOTE', 'PRIVATE-TRIAL', 'final_model', 'final_batch'):
            self.assertNotIn(hidden, rendered)

    def test_sessions_and_ai_mode_stay_separate_without_opening_provenance_paths(self):
        ai = copy.deepcopy(self.session)
        ai.update(session_id='second-session', extraction_mode='ai', provider='omniroute',
                  requested_model='synthetic-test-model', served_model_provenance_path='/not-read/model.json',
                  configuration_record_path='/not-read/settings.json')
        rows = [self.trial(), self.trial('assisted'),
                self.trial(session_id=ai['session_id'], extraction_mode='ai', elapsed_seconds='20'),
                self.trial('assisted', session_id=ai['session_id'], extraction_mode='ai', elapsed_seconds='30')]
        self.write([self.session, ai], rows)
        with patch('evidence.ai.omniroute.OmniRouteExtractor.__init__', side_effect=AssertionError('No provider')):
            result = self.report()
        self.assertEqual([s['paired_typed_minus_assisted_seconds']['median'] for s in result['sessions']], [3, -10])
        self.assertEqual([s['extraction_mode'] for s in result['sessions']], ['mock', 'ai'])
        self.assertNotIn('/not-read/', json.dumps(result))

    def test_error_scores_are_recomputed_against_authored_references(self):
        excluded_index = next(i for i, c in enumerate(self.dataset['cases']) if c['expected_typed_decision'] == 'excluded')
        row = self.trial(case_index=excluded_index, final_model='LAMP-100', final_batch='B101', final_decision='eligible')
        self.write([self.session], [row])
        scores = self.report()['sessions'][0]['conditions']['typed']['first_attempts']
        self.assertEqual(scores['completed_fields_compared'], 2)
        self.assertGreater(scores['completed_field_errors'], 0)
        self.assertEqual(scores['false_eligible_against_authored_reference'], 1)
        row['false_eligible_against_reference'] = 'false'
        self.write([self.session], [row])
        with self.assertRaises(ValueError): self.report()

    def test_guessed_absent_and_blank_readable_fields_have_distinct_counts(self):
        missing = next(i for i, c in enumerate(self.dataset['cases']) if c['case_id'] == 'missing-batch')
        guessed = self.trial(case_index=missing, final_batch='B101', final_decision='eligible')
        blank = self.trial(position='2', final_model='null', final_batch='null', final_decision='needs_information')
        self.write([self.session], [guessed, blank])
        summary = self.report()['sessions'][0]['conditions']['typed']['first_attempts']
        self.assertEqual(summary['guessed_absent_fields'], 1)
        self.assertEqual(summary['blank_readable_fields'], 2)
        self.assertEqual(summary['completed_field_errors'], 3)
        self.assertEqual(summary['completed_fields_compared'], 4)
        self.assertEqual(summary['false_eligible_against_authored_reference'], 1)

    def test_unknown_hash_alias_mode_missing_attempts_and_duplicate_rows_are_rejected(self):
        for changes in ({'image_sha256': '0' * 64}, {'participant_alias': 'wrong'},
                        {'session_id': 'unknown'}, {'extraction_mode': 'ai'}, {'attempt': '2'},
                        {'reference_scoring_status': 'adjudicated'}, {'final_batch': ''}):
            with self.subTest(changes=changes):
                self.write([self.session], [self.trial(**changes)])
                with self.assertRaises(ValueError): self.report()
        self.write([self.session], [self.trial(), self.trial()])
        with self.assertRaises(ValueError): self.report()
        self.write([self.session], [self.trial(position='2'), self.trial(position='1', attempt='2')])
        with self.assertRaises(ValueError): self.report()
        self.write([self.session, self.session], [])
        with self.assertRaises(ValueError): self.report()

    def test_nonfinite_times_and_invalid_sessions_are_rejected_but_timeouts_retained(self):
        for value in ('NaN', 'inf', '-1', '1e308', 'not-a-time', '', '121'):
            self.write([self.session], [self.trial(elapsed_seconds=value)])
            with self.subTest(value=value), self.assertRaises(ValueError): self.report()
        row = self.trial(outcome='timed_out', elapsed_seconds='120')
        self.write([self.session], [row])
        summary = self.report()['sessions'][0]['conditions']['typed']['first_attempts']
        self.assertEqual(summary['outcomes']['timed_out'], 1)
        self.assertEqual(summary['completed_fields_compared'], 0)
        self.assertIsNone(summary['completed_elapsed_seconds']['median'])
        for change in ({'consent_recorded': 'false'}, {'started_at_utc': '2026-11-08'},
                       {'protocol_commit': 'short'}, {'reference_scoring_status': 'validated'}):
            self.write([{**self.session, **change}], [])
            with self.subTest(change=change), self.assertRaises(ValueError): self.report()

    def test_ragged_duplicate_headers_and_oversized_inputs_are_rejected(self):
        original = self.trials.read_bytes()
        for content in (original + b'only-one-column\n', b'case_id,case_id\n', b'x' * (1024 * 1024 + 1)):
            self.trials.write_bytes(content)
            with self.assertRaises(ValueError): self.report()
        self.trials.write_bytes(b'\xef\xbb\xbf' + original)
        self.assertEqual(self.report()['status'], 'no_observations')

    def test_cli_preserves_existing_output_and_rejects_invalid_data_before_creating_report(self):
        output = self.folder / 'report.json'
        args = ['study_report', '--sessions', str(self.sessions), '--trials', str(self.trials), '--output', str(output)]
        with patch('sys.argv', args), redirect_stdout(StringIO()): study.main()
        before = output.read_bytes()
        with patch('sys.argv', args), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            study.main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(output.read_bytes(), before)
        output.unlink()
        self.trials.write_text('invalid\n')
        with patch('sys.argv', args), redirect_stderr(StringIO()), self.assertRaises(SystemExit): study.main()
        self.assertFalse(output.exists())
