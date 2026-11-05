"""Offline fixture-policy replay, NOT an image-recognition accuracy benchmark."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import platform

from evidence.ai.extraction import ExtractionService, POLICY_VERSION
from evidence.ai.fixture_extractor import DEFAULT_MANIFEST, FixtureExtractor
from evidence.backend.assessment import assess
from evidence.backend.images import decode_image
from evidence.backend.validation import ROOT


def evaluate(manifest_path=DEFAULT_MANIFEST):
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text())
    service = ExtractionService(FixtureExtractor(manifest_path))
    template = json.loads((ROOT / 'contracts/fixtures/assessment-request.json').read_text())
    results, failures = [], []
    for case in data['cases']:
        image_path = manifest_path.parent / case['image']
        if image_path.parent.resolve() != manifest_path.parent.resolve():
            raise ValueError('Fixture path escaped its directory')
        raw = image_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != case['sha256']:
            raise ValueError('Fixture bytes changed; review and regenerate manifest explicitly')
        image = decode_image(base64.b64encode(raw).decode(), case['mime_type'])
        proposal = service.propose(image)
        observed = {field: proposal[field] for field in ('model', 'batch')}
        checks = {'proposal_fields': observed == case['expected_proposal']}
        before_confirmation = copy.deepcopy(template)
        before_confirmation['label'].update(confirmed_model='', confirmed_batch='')
        checks['unconfirmed_stays_unresolved'] = assess(before_confirmation)['decision'] == 'needs_information'
        decisions = {}
        for path, fields, expected in [('typed', case['typed_entry'], case['expected_typed_decision']),
                                        ('proposal_after_confirmation', observed, case['expected_proposal_decision'])]:
            request = copy.deepcopy(template)
            request['label'].update(confirmed_model=fields['model'] or '', confirmed_batch=fields['batch'] or '')
            decisions[path] = assess(request)['decision']
            checks[path] = decisions[path] == expected
        expected_missing = [name for name in ('model', 'batch') if case['expected_proposal'][name] is None]
        checks['clarification'] = (proposal['uncertain_fields'] == expected_missing
                                  and bool(proposal['clarification']) == bool(expected_missing))
        failed = [name for name, passed in checks.items() if not passed]
        failures.extend({'case_id': case['case_id'], 'check': name} for name in failed)
        results.append({'case_id': case['case_id'], 'mode': proposal['mode'], 'observed_fields': observed,
                        'decisions': decisions, 'checks': checks})
    return {'evaluation_kind': 'fixture-policy-replay', 'dataset_version': data['dataset_version'],
            'policy_version': POLICY_VERSION, 'adapter': 'synthetic-fixture-lookup-v1', 'mode': 'mock',
            'runtime': platform.python_version(), 'image_recognition_measured': False,
            'confidence_calibrated': False, 'cases': len(results),
            'checks': sum(len(row['checks']) for row in results), 'failures': failures,
            'limitation': 'Known-image lookup with authored outputs; checks policy/plumbing only. No model, OCR, human study, extraction accuracy or user-savings evidence.',
            'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = evaluate(args.manifest)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, indent=2))
    if args.check and report['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
