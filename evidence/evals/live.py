"""Opt-in OmniRoute development smoke on frozen synthetic fixtures, not a holdout."""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import time

from evidence.ai.extraction import ExtractionService, ExtractionUnavailable, POLICY_VERSION
from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.ai.omniroute import OmniRouteExtractor, read_key
from evidence.backend.assessment import assess
from evidence.evals.plan import load_dataset, read_plan, snapshot, verify
from evidence.evals.report_output import reserve_new_report


def evaluate(adapter, manifest_path=DEFAULT_MANIFEST, case_ids=None, progress=None, plan_path=None):
    if adapter.mode != 'ai':
        raise ValueError('Provider smoke requires an AI adapter, never fixture lookup')
    plan = read_plan(plan_path) if plan_path is not None else None
    if case_ids is None and plan is not None:
        case_ids = [case['case_id'] for case in plan['snapshot']['cases']]
    return _evaluate(adapter, load_dataset(manifest_path, case_ids), plan, progress)


def _evaluate(adapter, dataset, plan=None, progress=None):
    if plan is not None:
        verify(plan, dataset, adapter)
    identity = snapshot(dataset, adapter)
    manifest, selected, images, template = (dataset[key] for key in ('manifest', 'cases', 'images', 'template'))
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
        'evaluation_snapshot': identity, 'plan_sha256': plan['plan_sha256'] if plan else None,
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
    parser.add_argument('--model')
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--plan', type=Path, help='Verify an offline frozen evaluation plan before reading credentials')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = read_plan(args.plan) if args.plan else None
        settings = plan['snapshot']['adapter'] if plan else {}
        model = args.model if args.model is not None else settings.get('requested_model', 'auto/smart')
        timeout = args.timeout if args.timeout is not None else settings.get('timeout_seconds', 20)
        case_ids = args.case_ids
        if case_ids is None and plan is not None:
            case_ids = [case['case_id'] for case in plan['snapshot']['cases']]
        dataset = load_dataset(args.manifest, case_ids)
        public_adapter = OmniRouteExtractor('synthetic-offline-preflight', model=model, timeout=timeout)
        if plan is not None:
            verify(plan, dataset, public_adapter)
    except (OSError, ValueError, TypeError, KeyError):
        parser.error('Evaluation preflight failed; check the dataset, plan, model, timeout and output path')
    try:
        # Reserve the final path before credentials or quota-consuming work. Both
        # planned and legacy runs must preserve any existing file or symlink.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        destination = reserve_new_report(args.output)
    except (OSError, ValueError):
        parser.error('Could not reserve a new report file; check its parent and choose an unused path')
    try:
        with destination:
            try:
                adapter = OmniRouteExtractor(read_key(args.omniroute_env), model=model, timeout=timeout)
            except (OSError, ValueError):
                parser.error('Could not load the OmniRoute configuration; the reserved output is not a completed report')
            report = _evaluate(adapter, dataset, plan,
                               progress=lambda case, status: print(case + ': ' + status, flush=True))
            destination.write(json.dumps(report, indent=2) + '\n')
            destination.flush()
    except OSError:
        parser.error('Could not complete the report; the reserved output is incomplete and calls may have occurred')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, indent=2))
    if (report['unavailable'] or report['false_eligible_against_authored_reference']
            or report['fields_matching_authored_typed_reference'] != report['fields_compared']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
