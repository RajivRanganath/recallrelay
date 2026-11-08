"""Offline reference-review packets; no provider calls or human-validation claims."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.backend.json_input import strict_json
from evidence.evals.plan import digest, load_dataset

PAGE = Path(__file__).with_name('review_page.html')
STATES = {'readable', 'missing', 'unreadable', 'conflicting'}
LIMIT = 1024 * 1024


def fingerprint(packet):
    return digest(json.dumps({key: value for key, value in packet.items() if key != 'packet_sha256'},
                             sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def packet_for(dataset, created):
    packet = {
        'packet_version': 'evidence-label-review-packet-1', 'created_at_utc': created,
        'purpose': 'development-reference-audit', 'holdout': False, 'human_validated': False,
        'dataset_version': dataset['manifest']['dataset_version'],
        'manifest_sha256': dataset['manifest_sha256'],
        'cases': [{'sample_id': f'label-{index:03d}', 'image_sha256': case['sha256']}
                  for index, case in enumerate(dataset['cases'], 1)],
    }
    packet['packet_sha256'] = fingerprint(packet)
    return packet


def prepare(output, manifest_path=DEFAULT_MANIFEST):
    dataset = load_dataset(manifest_path)
    packet = packet_for(dataset, datetime.now(timezone.utc).isoformat())
    cards = []
    for sample, image in zip(packet['cases'], dataset['images']):
        name = sample['sample_id']
        pixels = base64.b64encode(image.content).decode()
        fields = []
        for field in ('model', 'batch'):
            control = name + '-' + field
            fields.append(f'''<fieldset><legend>{field.title()}</legend>
<label for="{control}-state">{field.title()} readability</label>
<select id="{control}-state" name="{control}-state" data-value="{control}-value" required>
<option value="">Choose after viewing the image</option><option value="readable">One readable value</option>
<option value="missing">Missing</option><option value="unreadable">Unreadable / cut off</option>
<option value="conflicting">Conflicting values</option></select>
<label for="{control}-value">{field.title()} value (only when readable)</label>
<input id="{control}-value" name="{control}-value" maxlength="128" autocomplete="off" disabled></fieldset>''')
        cards.append(f'''<article aria-labelledby="{name}"><h2 id="{name}">{name}</h2>
<img src="data:{image.mime_type};base64,{pixels}" alt="Synthetic product label {name} for review">
<div class="fields">{''.join(fields)}</div><label for="{name}-note">Optional review note</label>
<textarea id="{name}-note" name="{name}-note" maxlength="1000" rows="2"></textarea></article>''')
    encoded = json.dumps(packet, allow_nan=False).replace('<', '\\u003c')
    page = PAGE.read_text().replace('<!--REVIEW_CARDS-->', ''.join(cards)).replace('<!--PACKET_DATA-->', encoded)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'packet.json').write_text(json.dumps(packet, indent=2) + '\n')
    (output / 'review.html').write_text(page)
    return packet


def bounded_bytes(path):
    with Path(path).open('rb') as source:
        raw = source.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('Review record exceeds the size limit')
    return raw


def read_json(path):
    return strict_json(bounded_bytes(path))


def utc_time(value):
    if not isinstance(value, str):
        raise ValueError('Expected a self-reported UTC timestamp')
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError('Expected a self-reported UTC timestamp') from None
    if date.utcoffset() != timedelta(0):
        raise ValueError('Expected a self-reported UTC timestamp')


def text(value, maximum):
    return (isinstance(value, str) and bool(value) and len(value) <= maximum
            and value == value.strip() and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def check_review(packet_path, review_path, manifest_path=DEFAULT_MANIFEST):
    dataset = load_dataset(manifest_path)
    packet = read_json(packet_path)
    if not isinstance(packet, dict):
        raise ValueError('Invalid review packet')
    utc_time(packet.get('created_at_utc'))
    if (packet.get('holdout') is not False or packet.get('human_validated') is not False
            or packet.get('packet_sha256') != fingerprint(packet)
            or packet != packet_for(dataset, packet['created_at_utc'])):
        raise ValueError('Packet, images or authored-reference manifest changed')
    raw_review = bounded_bytes(review_path)
    record = strict_json(raw_review)
    if (not isinstance(record, dict) or set(record) != {'review_version', 'packet_sha256',
            'reviewer', 'reviewed_at_utc', 'reviewer_confirmed_image_review', 'cases'}
            or record['review_version'] != 'evidence-label-review-1'
            or record['packet_sha256'] != packet['packet_sha256']
            or not text(record['reviewer'], 80)
            or record['reviewer_confirmed_image_review'] is not True
            or not isinstance(record['cases'], list)
            or len(record['cases']) != len(packet['cases'])):
        raise ValueError('Expected one complete self-reported image review for this packet')
    utc_time(record['reviewed_at_utc'])
    indexed = {}
    for row in record['cases']:
        if (not isinstance(row, dict) or set(row) != {'sample_id', 'image_sha256', 'model', 'batch', 'note'}
                or not isinstance(row['sample_id'], str) or row['sample_id'] in indexed
                or not isinstance(row['note'], str) or len(row['note']) > 1000):
            raise ValueError('Invalid or duplicate review row')
        for name in ('model', 'batch'):
            field = row[name]
            if (not isinstance(field, dict) or set(field) != {'status', 'value'}
                    or not isinstance(field['status'], str) or field['status'] not in STATES
                    or (field['status'] == 'readable' and not text(field['value'], 128))
                    or (field['status'] != 'readable' and field['value'] is not None)):
                raise ValueError('Complete readability choices and consistent field values are required')
        indexed[row['sample_id']] = row
    if set(indexed) != {sample['sample_id'] for sample in packet['cases']}:
        raise ValueError('Review coverage does not match the packet')
    results = []
    for sample, case in zip(packet['cases'], dataset['cases']):
        row = indexed[sample['sample_id']]
        if row['image_sha256'] != sample['image_sha256']:
            raise ValueError('Reviewed image fingerprint does not match the packet')
        for name in ('model', 'batch'):
            observed = row[name]
            reference = case['typed_entry'][name]
            results.append({'sample_id': sample['sample_id'], 'case_id': case['case_id'],
                            'field': name, 'review_status': observed['status'],
                            'review_value': observed['value'], 'authored_reference': reference,
                            'matches_authored_reference': observed['value'] == reference})
    differences = [row for row in results if not row['matches_authored_reference']]
    return {'review_kind': 'self-reported-development-reference-audit',
            'packet_sha256': packet['packet_sha256'], 'review_record_sha256': digest(raw_review),
            'holdout': False, 'human_validated': False, 'reviewer_identity_verified': False,
            'cases_reviewed': len(indexed), 'fields_compared': len(results),
            'disagreements_with_authored_reference': len(differences), 'results': results,
            'limitation': 'Structural/hash checks only. Identity, visual work and timestamp are self-reported. '
                          'Agreement does not prove correct labels, independent review or holdout status. '
                          'Disagreements require adjudication; neither side is automatically ground truth.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare', help='Export images and a blank offline review form')
    create.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    create.add_argument('--output', type=Path, required=True, help='New directory; never overwritten')
    check = commands.add_parser('check', help='Check a completed record and report reference disagreements')
    check.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    check.add_argument('--packet', type=Path, required=True)
    check.add_argument('--review', type=Path, required=True)
    check.add_argument('--output', type=Path, help='Optional new report file; never overwritten')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            packet = prepare(args.output, args.manifest)
            result = {'status': 'prepared', 'packet_sha256': packet['packet_sha256'],
                      'cases': len(packet['cases']), 'holdout': False, 'human_validated': False}
        else:
            report = check_review(args.packet, args.review, args.manifest)
            if args.output is not None:
                with args.output.open('x') as destination:
                    destination.write(json.dumps(report, indent=2) + '\n')
            result = report
    except (OSError, ValueError, TypeError, KeyError):
        parser.error('Review check/export failed; check the dataset, packet, complete record and new output path')
    print(json.dumps(result, indent=2))
    if args.command == 'check' and report['disagreements_with_authored_reference']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
