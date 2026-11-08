"""Offline descriptive reporting of self-reported development timing records."""
import argparse
from collections import Counter
import copy
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
from statistics import median

from evidence.ai.fixture_extractor import DEFAULT_MANIFEST
from evidence.backend.assessment import assess
from evidence.evals.plan import load_dataset

TEMPLATES = Path(__file__).with_name('study')
OUTCOMES = {'completed', 'timed_out', 'failed', 'withdrawn'}
DECISIONS = {'eligible', 'excluded', 'needs_information'}


def read_csv(path, template):
    with Path(path).open('rb') as source:
        raw = source.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('CSV exceeds the 1 MiB limit')
    expected = next(csv.reader((TEMPLATES / template).read_text().splitlines()))
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
        if reader.fieldnames != expected:
            raise ValueError('CSV headers must match the committed template exactly')
        rows = list(reader)
    except (UnicodeError, csv.Error):
        raise ValueError('Invalid UTF-8 CSV') from None
    if any(set(row) != set(expected) or any(value is None for value in row.values()) for row in rows):
        raise ValueError('CSV row width does not match the template')
    return rows, hashlib.sha256(raw).hexdigest()


def text(value, maximum=128):
    return (isinstance(value, str) and 0 < len(value) <= maximum and value == value.strip()
            and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def integer(value, minimum=0, maximum=10000):
    if not re.fullmatch(r'0|[1-9][0-9]*', value) or not minimum <= int(value) <= maximum:
        raise ValueError('Invalid count, position or attempt')
    return int(value)


def stats(values):
    return {'count': len(values), 'median': median(values) if values else None,
            'minimum': min(values) if values else None, 'maximum': max(values) if values else None}


def validate_session(row, version):
    for name in ('session_id', 'participant_alias', 'prior_image_exposure', 'prior_app_experience',
                 'browser', 'device', 'case_order'):
        if not text(row[name]):
            raise ValueError('Complete session identity, exposure and environment fields')
    for name in ('protocol_commit', 'evidence_commit'):
        if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', row[name]):
            raise ValueError('Record full protocol and evidence commit hashes')
    if (row['protocol_version'] != 'rajiv-human-evaluation-1' or row['consent_recorded'] != 'true'
            or row['reference_version'] != version or row['reference_scoring_status'] != 'provisional'
            or row['warmup_completed'] not in ('true', 'false')
            or row['condition_order'] not in ('typed_first', 'assisted_first')
            or row['extraction_mode'] not in ('mock', 'ai')):
        raise ValueError('Invalid session protocol, consent, mode or provisional reference status')
    try:
        started = datetime.fromisoformat(row['started_at_utc'])
        if started.utcoffset() is None or started.utcoffset().total_seconds() != 0:
            raise ValueError()
    except ValueError:
        raise ValueError('Record a self-reported UTC session timestamp') from None
    if row['extraction_mode'] == 'mock':
        if row['provider'] != 'fixture' or row['requested_model'] != 'na':
            raise ValueError('Mock sessions use fixture provider and na model')
    elif (row['provider'] != 'omniroute' or not text(row['requested_model'])
          or not text(row['served_model_provenance_path'], 1000)
          or not text(row['configuration_record_path'], 1000)):
        raise ValueError('AI sessions require self-reported model/configuration provenance pointers')
    if row['warmup_completed'] == 'false' and not row['notes'].strip():
        raise ValueError('Document an omitted warm-up')


def validate_trial(row, session, case, template):
    if (row['participant_alias'] != session['participant_alias']
            or row['reference_version'] != session['reference_version']
            or row['reference_scoring_status'] != 'provisional'
            or row['extraction_mode'] != session['extraction_mode']
            or row['image_sha256'] != case['sha256']
            or row['condition'] not in ('typed', 'assisted') or row['outcome'] not in OUTCOMES):
        raise ValueError('Trial does not match its session, image, condition or outcome')
    row = dict(row)
    row['position'] = integer(row['position'], 1)
    row['attempt'] = integer(row['attempt'], 1)
    duration = row['elapsed_seconds']
    if duration:
        try:
            duration = float(duration)
        except ValueError:
            raise ValueError('Invalid elapsed seconds') from None
        if not math.isfinite(duration) or not 0 <= duration <= 86400:
            raise ValueError('Elapsed seconds must be finite and between zero and one day')
    else:
        duration = None
    if row['outcome'] == 'completed' and duration is None:
        raise ValueError('Completed trials require an observed duration')
    if ((row['outcome'] == 'completed' and duration > 120)
            or (row['outcome'] == 'timed_out' and (duration is None or duration < 120))):
        if not row['deviation'].strip():
            raise ValueError('Document a deviation from the 120-second stop rule')
    if (duration is None or row['outcome'] in ('failed', 'withdrawn')) and not row['notes'].strip():
        raise ValueError('Document unknown timing, failures or withdrawals')
    row['elapsed_seconds'] = duration
    if row['extraction_unavailable'] not in ('true', 'false', ''):
        raise ValueError('Extraction availability must be true, false or unknown')
    if row['condition'] == 'typed':
        if row['extraction_unavailable'] != 'false' or row['suggested_identifier_fields_edited'] != 'na':
            raise ValueError('Typed entry has no extraction attempt or suggested-field edits')
    elif row['suggested_identifier_fields_edited'] not in ('', 'na'):
        integer(row['suggested_identifier_fields_edited'], 0, 2)
    if row['clarification_field'] not in ('model', 'batch', 'na', ''):
        raise ValueError('Invalid clarification field')
    if row['clarification_appropriate'] not in ('true', 'false', 'na', ''):
        raise ValueError('Invalid self-reported clarification judgment')
    if row['clarification_rounds'] not in ('', 'na'):
        integer(row['clarification_rounds'])
    row['scores'] = None
    if row['outcome'] == 'completed':
        if row['final_decision'] not in DECISIONS:
            raise ValueError('Completed trials require the displayed decision')
        fields = {}
        for name in ('model', 'batch'):
            value = row['final_' + name]
            if not text(value):
                raise ValueError('Record observed identifiers, using literal null for absence')
            fields[name] = None if value == 'null' else value
        request = copy.deepcopy(template)
        request['label'].update(confirmed_model=fields['model'] or '', confirmed_batch=fields['batch'] or '')
        scores = {name + '_matches_reference': fields[name] == case['typed_entry'][name]
                  for name in fields}
        scores['false_eligible_against_reference'] = (row['final_decision'] == 'eligible'
                                                      and case['expected_typed_decision'] != 'eligible')
        for name, observed in scores.items():
            if row[name] not in ('', str(observed).lower()):
                raise ValueError('Entered scoring column conflicts with recomputed authored-reference comparison')
        scores['guessed_absent_fields'] = sum(fields[name] is not None and case['typed_entry'][name] is None
                                              for name in fields)
        scores['blank_readable_fields'] = sum(fields[name] is None and case['typed_entry'][name] is not None
                                              for name in fields)
        scores['decision_disagrees_with_final_identifier_rules'] = row['final_decision'] != assess(request)['decision']
        row['scores'] = scores
    elif any(row[name] for name in ('model_matches_reference', 'batch_matches_reference',
                                    'false_eligible_against_reference')):
        raise ValueError('Noncompleted trials cannot supply final-result scores')
    return row


def summarize(rows):
    completed = [row for row in rows if row['outcome'] == 'completed']
    counts = Counter(row['outcome'] for row in rows)
    edits = [int(r['suggested_identifier_fields_edited']) for r in rows
             if r['suggested_identifier_fields_edited'] not in ('', 'na')]
    rounds = [int(r['clarification_rounds']) for r in rows if r['clarification_rounds'] not in ('', 'na')]
    return {'reported_suggested_field_edits': stats(edits), 'reported_clarification_rounds': stats(rounds),
            'recorded_attempts': len(rows), 'outcomes': {name: counts[name] for name in sorted(OUTCOMES)},
            'completed_elapsed_seconds': stats([row['elapsed_seconds'] for row in completed]),
            'reported_extraction_unavailable': sum(row['extraction_unavailable'] == 'true' for row in rows),
            'extraction_availability_unknown': sum(row['extraction_unavailable'] == '' for row in rows),
            'completed_fields_compared': 2 * len(completed),
            'completed_field_errors': sum(not row['scores'][name + '_matches_reference']
                                          for row in completed for name in ('model', 'batch')),
            'guessed_absent_fields': sum(row['scores']['guessed_absent_fields'] for row in completed),
            'blank_readable_fields': sum(row['scores']['blank_readable_fields'] for row in completed),
            'completed_decisions_compared': len(completed),
            'false_eligible_against_authored_reference': sum(row['scores']['false_eligible_against_reference'] for row in completed),
            'observed_decision_rule_disagreements': sum(row['scores']['decision_disagrees_with_final_identifier_rules'] for row in completed),
            'self_reported_clarification_judgments': dict(Counter(row['clarification_appropriate'] or 'unknown' for row in rows))}


def report(sessions_path, trials_path, manifest_path=DEFAULT_MANIFEST):
    dataset = load_dataset(manifest_path)
    cases = {case['case_id']: case for case in dataset['cases']}
    sessions, sessions_hash = read_csv(sessions_path, 'sessions.csv')
    trials, trials_hash = read_csv(trials_path, 'trials.csv')
    indexed = {}
    for session in sessions:
        validate_session(session, dataset['manifest']['dataset_version'])
        if session['session_id'] in indexed:
            raise ValueError('Duplicate session')
        indexed[session['session_id']] = session
    checked, seen, positions, attempts = [], set(), set(), {}
    for trial in trials:
        if trial['session_id'] not in indexed or trial['case_id'] not in cases:
            raise ValueError('Unknown session or synthetic case')
        row = validate_trial(trial, indexed[trial['session_id']], cases[trial['case_id']], dataset['template'])
        task = (row['session_id'], row['case_id'], row['condition'])
        key, position = (*task, row['attempt']), (row['session_id'], row['position'])
        if key in seen or position in positions:
            raise ValueError('Duplicate task attempt or session position')
        seen.add(key)
        positions.add(position)
        attempts.setdefault(task, []).append((row['attempt'], row['position']))
        checked.append(row)
    for values in attempts.values():
        numbers = sorted(attempt for attempt, _ in values)
        if numbers != list(range(1, max(numbers) + 1)):
            raise ValueError('Retain every attempt, starting at attempt 1')
        if [attempt for attempt, _ in sorted(values, key=lambda item: item[1])] != numbers:
            raise ValueError('Retries cannot precede their earlier attempts')
    summaries = []
    for index, session in enumerate(sessions, 1):
        rows = [row for row in checked if row['session_id'] == session['session_id']]
        first = {(row['case_id'], row['condition']): row for row in rows if row['attempt'] == 1}
        pairs, unpaired = [], []
        for case_id in cases:
            typed, assisted = (first.get((case_id, arm)) for arm in ('typed', 'assisted'))
            if typed and assisted and typed['outcome'] == assisted['outcome'] == 'completed':
                pairs.append({'case_id': case_id, 'typed_seconds': typed['elapsed_seconds'],
                              'assisted_seconds': assisted['elapsed_seconds'],
                              'typed_minus_assisted_seconds': round(typed['elapsed_seconds'] - assisted['elapsed_seconds'], 6)})
            else:
                unpaired.append({'case_id': case_id, 'typed': typed['outcome'] if typed else 'not_recorded',
                                 'assisted': assisted['outcome'] if assisted else 'not_recorded'})
        arms = ('typed', 'assisted') if session['condition_order'] == 'typed_first' else ('assisted', 'typed')
        expected = [(case_id, arms[0]) for case_id in cases] + [(case_id, arms[1]) for case_id in reversed(cases)]
        observed = [(r['case_id'], r['condition']) for r in sorted(rows, key=lambda r: r['position']) if r['attempt'] == 1]
        summaries.append({'session_number': index, 'evidence_commit': session['evidence_commit'],
                          'protocol_commit': session['protocol_commit'],
                          'declared_condition_order': session['condition_order'],
                          'first_attempt_order_matches_protocol_prefix': observed == expected[:len(observed)] if observed else None,
                          'extraction_mode': session['extraction_mode'],
                          'provider': session['provider'], 'requested_model': session['requested_model'],
                          'configuration_verified': False, 'planned_first_attempts': 2 * len(cases),
                          'unrecorded_first_attempts': 2 * len(cases) - len(first),
                          'conditions': {arm: {'first_attempts': summarize([r for r in rows if r['condition'] == arm and r['attempt'] == 1]),
                                               'retries': summarize([r for r in rows if r['condition'] == arm and r['attempt'] > 1])}
                                         for arm in ('typed', 'assisted')},
                          'completed_first_attempt_pairs': pairs, 'unpaired_cases': unpaired,
                          'paired_typed_minus_assisted_seconds': stats([p['typed_minus_assisted_seconds'] for p in pairs]),
                          'documented_deviation_rows': sum(bool(r['deviation'].strip()) for r in rows)})
    return {'report_kind': 'self-reported-development-timing-summary', 'report_version': 'study-report-1',
            'reporter_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'reference_dataset_version': dataset['manifest']['dataset_version'],
            'status': 'observations_present' if checked else 'no_observations',
            'holdout': False, 'human_validated': False, 'human_work_verified': False,
            'reference_kind': 'provisional-authored-development-reference',
            'input_sha256': {'sessions': sessions_hash, 'trials': trials_hash, 'manifest': dataset['manifest_sha256']},
            'participants_recorded': len({s['participant_alias'] for s in sessions}),
            'sessions_recorded': len(sessions), 'recorded_attempts': len(checked), 'sessions': summaries,
            'limitations': ['Records, consent, timings and configuration are self-reported and unauthenticated.',
                           'CSV provenance pointers are not opened; no provider or payment calls occur.',
                           'Comparisons use authored development references, not independent labels or a holdout.',
                           'Sessions and extraction modes are summarized separately; retries never replace first attempts.',
                           'Only completed tasks enter time summaries; all outcomes and unrecorded pairs remain visible.',
                           'Repeated cases introduce learning; differences do not establish causal savings or generalization.',
                           'Aliases, free-text notes, paths and raw final identifiers are omitted; review before sharing.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sessions', type=Path, required=True)
    parser.add_argument('--trials', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--output', type=Path, required=True, help='New JSON report; never overwrite')
    args = parser.parse_args()
    try:
        result = report(args.sessions, args.trials, args.manifest)
        with args.output.open('x') as destination:
            destination.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    except (OSError, ValueError, TypeError, KeyError):
        parser.error('Invalid study inputs or output path; use exact templates, complete self-reported records and a new report path')
    print(json.dumps({'status': result['status'], 'sessions': result['sessions_recorded'],
                      'recorded_attempts': result['recorded_attempts'], 'holdout': False, 'human_validated': False}))


if __name__ == '__main__':
    main()
