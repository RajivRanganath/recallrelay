"""Offline fingerprints for synthetic provider evaluations; no credentials or calls."""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re

from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.ai.omniroute import OmniRouteExtractor
from evidence.backend.assessment import assess
from evidence.backend.images import decode_image, MAX_IMAGE_BYTES
from evidence.backend.json_input import strict_json
from evidence.backend.validation import ROOT
from evidence.evals.report_output import reserve_new_report

SOURCE_FILES = (
    'evidence/ai/omniroute.py', 'evidence/ai/extraction.py',
    'evidence/ai/schemas/extraction-output.schema.json',
    'evidence/backend/assessment.py', 'evidence/backend/validation.py',
    'evidence/backend/images.py', 'evidence/backend/json_input.py',
    'evidence/backend/errors.py', 'evidence/evals/live.py', 'evidence/evals/plan.py',
    'evidence/evals/report_output.py', 'evidence/requirements.lock.txt', 'contracts/fixtures/assessment-request.json',
    'contracts/schemas/assessment-request.schema.json',
    'contracts/schemas/assessment-response.schema.json',
    'contracts/schemas/resolution-response.schema.json',
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_dataset(manifest_path=DEFAULT_MANIFEST, case_ids=None):
    """Validate references and retain checked pixels before any provider call."""
    path = Path(manifest_path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Synthetic manifest exceeds the size limit')
    raw = path.read_bytes()
    data = strict_json(raw)
    if (not isinstance(data, dict) or data.get('synthetic_only') is not True
            or data.get('dataset_version') != 'synthetic-labels-v1'
            or not isinstance(data.get('cases'), list) or not data['cases']):
        raise ValueError('Expected a non-empty frozen synthetic dataset')
    ids, hashes = set(), set()
    for case in data['cases']:
        if not isinstance(case, dict):
            raise ValueError('Invalid synthetic case')
        case_id, sha = case.get('case_id'), case.get('sha256')
        if (not isinstance(case_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,127}', case_id)
                or case_id in ids or not isinstance(sha, str)
                or not re.fullmatch(r'[0-9a-f]{64}', sha) or sha in hashes):
            raise ValueError('Case IDs and image hashes must be valid and unique')
        ids.add(case_id)
        hashes.add(sha)
    if case_ids is not None and (not case_ids or len(set(case_ids)) != len(case_ids)
                                  or not set(case_ids) <= ids):
        raise ValueError('Select unique known synthetic case IDs')
    selected = [case for case in data['cases'] if case_ids is None or case['case_id'] in case_ids]
    template = strict_json((ROOT / 'contracts/fixtures/assessment-request.json').read_bytes())
    images = []
    for case in selected:
        name = case.get('image')
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError('Fixture path escaped its directory')
        image_path = path.parent / name
        if image_path.is_symlink() or image_path.resolve().parent != path.parent.resolve():
            raise ValueError('Fixture path escaped its directory')
        if image_path.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError('Fixture exceeds the image size limit')
        pixels = image_path.read_bytes()
        if digest(pixels) != case['sha256']:
            raise ValueError('Fixture bytes changed; no provider call made')
        image = decode_image(base64.b64encode(pixels).decode(), case.get('mime_type'))
        reference = case.get('typed_entry')
        if (not isinstance(reference, dict) or set(reference) != {'model', 'batch'}
                or any(value is not None and (not isinstance(value, str) or not value.strip()
                       or value != value.strip() or len(value) > 128) for value in reference.values())):
            raise ValueError('Invalid authored typed-entry reference')
        request = copy.deepcopy(template)
        request['label'].update(confirmed_model=reference['model'] or '', confirmed_batch=reference['batch'] or '')
        if assess(request)['decision'] != case.get('expected_typed_decision'):
            raise ValueError('Authored reference decision does not match deterministic rules')
        images.append(image)
    return {'manifest': data, 'manifest_sha256': digest(raw), 'cases': selected,
            'images': images, 'template': template}


def snapshot(dataset, adapter):
    if adapter.mode != 'ai':
        raise ValueError('Provider evaluation requires an AI adapter')
    return {
        'dataset_version': dataset['manifest']['dataset_version'],
        'manifest_sha256': dataset['manifest_sha256'],
        'cases': [{'case_id': case['case_id'], 'image_sha256': case['sha256']} for case in dataset['cases']],
        'adapter': {'provider': adapter.provider_name, 'requested_model': adapter.model,
                    'base_url': getattr(adapter, 'base_url', None), 'timeout_seconds': adapter.timeout},
        'source_sha256': {name: digest((ROOT / name).read_bytes()) for name in SOURCE_FILES},
        'runtime': {'python': platform.python_version(),
                    'packages': {name: version(name) for name in ('Pillow', 'jsonschema')}},
    }


def plan_digest(plan):
    return digest(json.dumps({key: value for key, value in plan.items() if key != 'plan_sha256'},
                             sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def freeze(dataset, adapter):
    plan = {'plan_version': 'evidence-evaluation-plan-1',
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'evaluation_kind': 'provider-development-smoke', 'holdout': False,
            'human_validated': False, 'snapshot': snapshot(dataset, adapter)}
    plan['plan_sha256'] = plan_digest(plan)
    return plan


def read_plan(path):
    if Path(path).stat().st_size > 1024 * 1024:
        raise ValueError('Evaluation plan exceeds the size limit')
    plan = strict_json(Path(path).read_bytes())
    if (not isinstance(plan, dict) or set(plan) != {'plan_version', 'created_at_utc', 'evaluation_kind',
            'holdout', 'human_validated', 'snapshot', 'plan_sha256'}
            or plan.get('plan_version') != 'evidence-evaluation-plan-1'
            or plan.get('evaluation_kind') != 'provider-development-smoke'
            or plan.get('holdout') is not False or plan.get('human_validated') is not False
            or not isinstance(plan.get('created_at_utc'), str)
            or plan.get('plan_sha256') != plan_digest(plan)):
        raise ValueError('Invalid evaluation plan or fingerprint')
    captured = plan['snapshot']
    if (not isinstance(captured, dict)
            or set(captured) != {'dataset_version', 'manifest_sha256', 'cases', 'adapter', 'source_sha256', 'runtime'}
            or not isinstance(captured['adapter'], dict)
            or set(captured['adapter']) != {'provider', 'requested_model', 'base_url', 'timeout_seconds'}
            or not isinstance(captured['cases'], list) or not captured['cases']
            or any(not isinstance(case, dict) or set(case) != {'case_id', 'image_sha256'}
                   or not isinstance(case['case_id'], str) for case in captured['cases'])):
        raise ValueError('Invalid evaluation snapshot')
    return plan


def verify(plan, dataset, adapter):
    if plan['snapshot'] != snapshot(dataset, adapter):
        raise ValueError('Frozen evaluation inputs, code, configuration or runtime changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--model')
    parser.add_argument('--timeout', type=float)
    parser.add_argument('--case', action='append', dest='case_ids')
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument('--output', type=Path)
    destination.add_argument('--check', type=Path, help='Verify an existing plan offline without reading credentials')
    args = parser.parse_args()
    try:
        captured = read_plan(args.check) if args.check else None
        settings = captured['snapshot']['adapter'] if captured else {}
        model = args.model if args.model is not None else settings.get('requested_model')
        timeout = args.timeout if args.timeout is not None else settings.get('timeout_seconds', 20)
        # Validate public settings using a synthetic placeholder; no key is read.
        adapter = OmniRouteExtractor('synthetic-offline-plan', model=model, timeout=timeout)
        case_ids = args.case_ids
        if case_ids is None and captured is not None:
            case_ids = [case['case_id'] for case in captured['snapshot']['cases']]
        dataset = load_dataset(args.manifest, case_ids)
        if captured is not None:
            verify(captured, dataset, adapter)
            plan = captured
        else:
            plan = freeze(dataset, adapter)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with reserve_new_report(args.output) as file:
                file.write(json.dumps(plan, indent=2) + '\n')
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps({'status': 'verified' if args.check else 'frozen',
                      'plan_sha256': plan['plan_sha256'], 'cases': len(plan['snapshot']['cases']),
                      'holdout': False, 'human_validated': False}))


if __name__ == '__main__':
    main()
