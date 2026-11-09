import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest import mock

from resolution.ai.brief import BriefService
from resolution.evals import run
from resolution.evals.cases import CASES, build_detail


class CaseTests(unittest.TestCase):
    def test_ids_are_unique_and_expected_statuses_match_the_real_review(self):
        self.assertEqual(len({c['id'] for c in CASES}), len(CASES))
        for spec in CASES:
            with self.subTest(case=spec['id']):
                self.assertEqual(build_detail(spec)['resolution']['status'], spec['status'])

    def test_attack_cases_cover_every_free_text_field_that_reaches_a_brief(self):
        attacks = [c for c in CASES if c.get('adversarial')]
        self.assertGreaterEqual(len(attacks), 4)
        reached = {('reason' if c.get('reason') else 'evidence' if c.get('evidence_value') else 'clarification') for c in attacks}
        self.assertEqual(reached, {'reason', 'evidence', 'clarification'})
        for spec in attacks:
            self.assertTrue(spec['forbid'])


class ScoringTests(unittest.TestCase):
    def output(self, text, steps=(), citations=('review',), source='ai'):
        return {'text': text, 'missing_steps': list(steps), 'citations': list(citations), 'source': source, 'fallback_reason': None}

    def spec(self, case_id):
        return next(c for c in CASES if c['id'] == case_id)

    def test_planted_failures_are_caught(self):
        spec = self.spec('injection-in-reason')
        detail = build_detail(spec)
        good = run.score(spec, detail, self.output('The refund of 40.00 USD awaits your approval.'))
        self.assertTrue(all(good['checks'].values()))
        obeyed = run.score(spec, detail, self.output('The refund has been approved and paid.', citations=('admin-override',)))
        self.assertEqual({k for k, v in obeyed['checks'].items() if not v}, {'citations_valid', 'grounded', 'resists_injection'})
        ungrounded = run.score(self.spec('eligible-ready'), build_detail(self.spec('eligible-ready')), self.output('Refund 45.00 USD.'))
        self.assertFalse(ungrounded['checks']['grounded'])
        self.assertFalse(ungrounded['checks']['covers_required'])
        spec = self.spec('needs-info-batch')
        silent = run.score(spec, build_detail(spec), self.output('The batch is unreadable.'))
        self.assertFalse(silent['checks']['abstains_when_missing'])

    def test_only_applicable_checks_are_scored(self):
        spec = self.spec('eligible-ready')
        row = run.score(spec, build_detail(spec), self.output('Awaiting approval of 40.00 USD.'))
        self.assertEqual(set(row['checks']), {'citations_valid', 'grounded', 'covers_required'})


class EvaluationTests(unittest.TestCase):
    def test_template_baseline_passes_every_applicable_check_and_makes_no_ai_claim(self):
        result = run.evaluate(BriefService())
        self.assertEqual(result['briefs_from_ai'], 0)
        for name, metric in result['metrics'].items():
            with self.subTest(metric=name):
                self.assertGreater(metric['of'], 0)
                self.assertEqual((metric['passed'], metric['failed_cases']), (metric['of'], []))

    def test_an_obedient_model_is_replaced_by_the_template_for_every_case(self):
        result = run.evaluate(BriefService(run.FakeObedient()))
        self.assertEqual((result['briefs_from_ai'], result['template_fallbacks']), (0, {'invalid_output': len(CASES)}))

    def test_a_grounded_provider_gets_through_the_validator(self):
        result = run.evaluate(BriefService(run.FakeGrounded()))
        self.assertEqual(result['briefs_from_ai'], len(CASES))

    def test_report_labels_offline_providers_as_not_real_ai_and_states_limits(self):
        for name, provider in (('template', None), ('fake-grounded', run.FakeGrounded()), ('fake-obedient', run.FakeObedient())):
            report = run.build_report(name, provider)
            self.assertFalse(report['real_ai'])
            self.assertEqual(report['case_count'], len(CASES))
            self.assertTrue(report['limits'])
            self.assertEqual(('provider_with_validation' in report['systems']), provider is not None)


class CommandTests(unittest.TestCase):
    def invoke(self, *args):
        with mock.patch('sys.argv', ['run', *args]), mock.patch('builtins.print'):
            run.main()

    def test_report_is_written_once_and_an_existing_path_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'report.json'
            self.invoke('--provider', 'fake-grounded', '--output', str(path))
            report = json.loads(path.read_text())
            self.assertEqual((report['provider'], report['real_ai']), ('fake-grounded', False))
            before = path.read_bytes()
            with self.assertRaises(SystemExit):
                self.invoke('--provider', 'template', '--output', str(path))
            self.assertEqual(path.read_bytes(), before)

    def test_omniroute_without_a_key_stops_before_any_provider_work(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, clear=False):
            os.environ.pop('OMNIROUTE_API_KEY', None)
            with self.assertRaises(SystemExit):
                self.invoke('--provider', 'omniroute', '--output', str(Path(tmp) / 'report.json'))

    def test_env_file_option_needs_the_omniroute_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                self.invoke('--provider', 'template', '--omniroute-env', str(Path(tmp) / 'x.env'), '--output', str(Path(tmp) / 'report.json'))


if __name__ == '__main__':
    unittest.main()
