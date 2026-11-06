"""Opt-in OmniRoute development smoke on frozen synthetic fixtures, not a holdout."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

from evidence.ai.extraction import ExtractionService, ExtractionUnavailable, POLICY_VERSION
from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.ai.omniroute import OmniRouteExtractor, read_key
from evidence.backend.assessment import assess
from evidence.backend.images import decode_image
from evidence.backend.validation import ROOT


def evaluate(adapter, manifest_path=DEFAULT_MANIFEST, case_ids=None, progress=None):
    if adapter.mode != 'ai':
        raise ValueError('Provider smoke requires an AI adapter, never fixture lookup')
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('dataset_version') != 'synthetic-labels-v1' or not manifest.get('synthetic_only'):
        raise ValueError('Expected the frozen synthetic dataset')
    known_ids = {case['case_id'] for case in manifest['cases']}
    if case_ids and not set(case_ids) <= known_ids:
        raise ValueError('Unknown synthetic case ID')
    selected = [case for case in manifest['cases'] if not case_ids or case['case_id'] in case_ids]
    # Validate all selected bytes before any provider call.
    images = []
    for case in selected:
        path = manifest_path.parent / case['image']
        if path.resolve().parent != manifest_path.parent.resolve():
            raise ValueError('Fixture path escaped its directory')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != case['sha256']:
            raise ValueError('Fixture bytes changed; no provider call made')
        images.append(decode_image(base64.b64encode(raw).decode(), case['mime_type']))
    template = json.loads((ROOT / 'contracts/fixtures/assessment-request.json').read_text())
    service = ExtractionService(adapter)
    results = []
    for case, image in zip(selected, images):
        start = time.monotonic()
        row = {'case_id': case['case_id'], 'image_sha256': case['sha256'],
               'typed_entry': case['typed_entry'], 'typed_decision': case['expected_typed_decision']}
        try:
            proposal = service.propose(image)
            fields = {name: proposal[name] for name in ('model', 'batch')}
            request = copy.deepcopy(template)
            request['label'].update(confirmed_model=fields['model'] or '', confirmed_batch=fields['batch'] or '')
            decision = assess(request)['decision']
            row.update(status='proposal', observed_fields=fields, confidence=proposal['confidence'],
                       source=proposal.get('source'), clarification=proposal['clarification'],
                       simulated_confirmation_decision=decision,
                       field_matches={name: fields[name] == case['typed_entry'][name] for name in fields},
                       guessed_reference_missing=[name for name in fields if case['typed_entry'][name] is None and fields[name] is not None],
                       false_eligible_against_authored_reference=decision == 'eligible' and case['expected_typed_decision'] != 'eligible')
        except ExtractionUnavailable as error:
            row.update(status='unavailable', failure_code=error.code, error='Extraction unavailable; no proposal or assessment persisted.')
        row['elapsed_seconds'] = round(time.monotonic() - start, 3)
        results.append(row)
        if progress:
            progress(row['case_id'], row['status'])
    successful = [row for row in results if row['status'] == 'proposal']
    return {
        'evaluation_kind': 'provider-development-smoke', 'mode': 'ai',
        'provider': adapter.provider_name, 'requested_model': adapter.model,
        'dataset_version': manifest['dataset_version'], 'policy_version': POLICY_VERSION,
        'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'python_version': platform.python_version(),
        'holdout': False, 'human_validated': False, 'confidence_calibrated': False,
        'request_config': {'temperature': 0, 'max_tokens': 2048, 'reasoning_effort': 'none', 'stream': False,
                           'timeout_seconds': adapter.timeout, 'client_retries': 0},
        'cases_attempted': len(results), 'proposals': len(successful),
        'unavailable': len(results) - len(successful),
        'fields_compared': 2 * len(successful),
        'fields_matching_authored_typed_reference': sum(sum(row['field_matches'].values()) for row in successful),
        'false_eligible_against_authored_reference': sum(row['false_eligible_against_authored_reference'] for row in successful),
        'limitation': 'Previously visible synthetic development fixtures with authored references; not a reviewed holdout or human study. Simulated confirmation does not establish safe autonomous eligibility. Missing-reference guesses and every unavailable call are reported. Auto routing and model self-reported confidence are not controlled/calibrated.',
        'results': results
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--omniroute-env', type=Path)
    parser.add_argument('--model', default='auto/smart')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        adapter = OmniRouteExtractor(read_key(args.omniroute_env), model=args.model)
    except (OSError, ValueError):
        parser.error('Could not load the OmniRoute key/model configuration')
    report = evaluate(adapter, case_ids=args.case_ids,
                      progress=lambda case, status: print(case + ': ' + status, flush=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, indent=2))
    if (report['unavailable'] or report['false_eligible_against_authored_reference']
            or report['fields_matching_authored_typed_reference'] != report['fields_compared']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
