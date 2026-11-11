"""Resolution-only SQLite case state. Money-related states are never overwritten by a review."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path

LOCKED_STATUSES = {'pending', 'refunded', 'failed'}


class AlreadyInProgress(ValueError):
    pass


class ApprovalConflict(ValueError):
    pass


class CaseStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, status TEXT NOT NULL, response TEXT NOT NULL, request TEXT)')
            db.execute('''CREATE TABLE IF NOT EXISTS operations (
                operation_id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE, amount_minor INTEGER NOT NULL,
                approved_by TEXT NOT NULL, assessment_id TEXT NOT NULL, campaign_version INTEGER NOT NULL,
                capture_id TEXT NOT NULL, currency TEXT NOT NULL)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def latest(self, case_id):
        with self.connect() as db:
            row = db.execute('SELECT response FROM cases WHERE case_id=?', (case_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def request(self, case_id):
        with self.connect() as db:
            row = db.execute('SELECT request FROM cases WHERE case_id=?', (case_id,)).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def list_cases(self):
        with self.connect() as db:
            rows = db.execute('SELECT response FROM cases ORDER BY case_id').fetchall()
        return [json.loads(row[0]) for row in rows]

    def operation(self, case_id):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute('SELECT * FROM operations WHERE case_id=?', (case_id,)).fetchone()
        return dict(row) if row else None

    def save_review(self, request, response):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status, request, response FROM cases WHERE case_id=?', (response['case_id'],)).fetchone()
            if row and row[0] in LOCKED_STATUSES:
                raise AlreadyInProgress('Case already has a refund in progress or finished')
            if row and row[1]:
                previous = json.loads(row[1])
                same_snapshot = all(previous.get(key) == request.get(key)
                                    for key in ('schema_version', 'order', 'assessment'))
                if (same_snapshot and previous.get('remedy_conditions_met') is True
                        and request.get('remedy_conditions_met') is False):
                    # A delayed customer handoff must not retract merchant confirmation
                    # or replace a provider hold. Compare and return under the write lock.
                    return json.loads(row[2])
            db.execute('INSERT INTO cases(case_id,status,response,request) VALUES(?,?,?,?) '
                       'ON CONFLICT(case_id) DO UPDATE SET status=excluded.status, response=excluded.response, request=excluded.request',
                       (response['case_id'], response['status'], json.dumps(response, sort_keys=True),
                        json.dumps(request, sort_keys=True)))
        return response

    def claim_refund(self, case_id, operation_id, approval, pending_response):
        """Atomically bind an approval and persist the operation ID before any PayPal call.

        Returns (response, claimed). Only the caller that gets claimed=True may start the refund.
        """
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status, response, request FROM cases WHERE case_id=?', (case_id,)).fetchone()
            if not row:
                raise ApprovalConflict('No reviewed case exists')
            status, response, request = row[0], json.loads(row[1]), row[2]
            existing = db.execute('SELECT operation_id FROM operations WHERE case_id=?', (case_id,)).fetchone()
            if existing:
                if existing[0] != operation_id:
                    raise ApprovalConflict('Case was approved with different details')
                return response, False  # Repeated approval: report state, never start a second refund.
            if status != 'awaiting_approval' or not request:
                raise ApprovalConflict('Case is not awaiting approval')
            snapshot = json.loads(request)
            order, assessment = snapshot['order'], snapshot['assessment']
            bound = (assessment['assessment_id'], assessment['campaign_version'], order['capture_id'], response['proposed_amount_minor'])
            if bound != (approval['assessment_id'], approval['campaign_version'], approval['capture_id'], approval['amount_minor']):
                raise ApprovalConflict('Approval does not match the reviewed assessment, campaign, capture and amount')
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,?,?)',
                       (operation_id, case_id, approval['amount_minor'], approval['approved_by'],
                        approval['assessment_id'], approval['campaign_version'], approval['capture_id'], order['currency']))
            db.execute('UPDATE cases SET status=?, response=? WHERE case_id=?',
                       ('pending', json.dumps(pending_response, sort_keys=True), case_id))
        return pending_response, True

    def hold(self, case_id, response):
        """Move a case that is still awaiting approval to manual handling. Never touches money states."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status FROM cases WHERE case_id=?', (case_id,)).fetchone()
            if not row or row[0] != 'awaiting_approval':
                return False
            db.execute('UPDATE cases SET status=?, response=? WHERE case_id=?',
                       (response['status'], json.dumps(response, sort_keys=True), case_id))
        return True

    def unsettled_case_for_capture(self, capture_id):
        """The case id of a refund on this payment that is still pending, or failed (a failure can be wrong
        when concurrent requests got different answers), if exactly one such case exists."""
        with self.connect() as db:
            rows = db.execute('SELECT o.case_id FROM operations o JOIN cases c ON c.case_id=o.case_id '
                              'WHERE o.capture_id=? AND c.status IN (?, ?)', (capture_id, 'pending', 'failed')).fetchall()
        return rows[0][0] if len(rows) == 1 else None

    def finish(self, case_id, response):
        """Settle a pending case. A case that already left 'pending' is never overwritten, with one exception.

        Two overlapping reconciles can both start from 'pending'; the first to finish wins and the
        later one gets the stored state back, so a completed refund can never revert to pending.
        The exception: a case stored as 'failed' may still become 'refunded'. Concurrent requests with
        the same ID can get different answers from PayPal, and callers only report 'refunded' after the
        refund has been read back from PayPal as COMPLETED, so money that really moved must not stay
        hidden behind an earlier failure. Nothing else ever overwrites 'failed' or 'refunded'.
        """
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT status, response FROM cases WHERE case_id=?', (case_id,)).fetchone()
            if row and row[0] != 'pending' and not (row[0] == 'failed' and response['status'] == 'refunded'):
                return json.loads(row[1])
            db.execute('UPDATE cases SET status=?, response=? WHERE case_id=?',
                       (response['status'], json.dumps(response, sort_keys=True), case_id))
        return response
