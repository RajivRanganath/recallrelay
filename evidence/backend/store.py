"""Evidence-only SQLite history. Image bodies are never persisted."""
from contextlib import contextmanager
import hashlib
import json
import sqlite3
from pathlib import Path


class Conflict(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class AssessmentStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS assessments (
                sequence INTEGER PRIMARY KEY, case_id TEXT NOT NULL,
                request_key TEXT NOT NULL, snapshot TEXT NOT NULL, response TEXT NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS case_history ON assessments(case_id, sequence)')

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
            row = db.execute('SELECT response FROM assessments WHERE case_id=? ORDER BY sequence DESC LIMIT 1', (case_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, request, response):
        # Persist only trusted context and confirmed text. Uploaded images are transient.
        snapshot = {key: request[key] for key in ('campaign', 'order')}
        request_key = hashlib.sha256(canonical(request).encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT snapshot, request_key, response FROM assessments WHERE case_id=? ORDER BY sequence DESC LIMIT 1', (response['case_id'],)).fetchone()
            if row:
                previous = json.loads(row[0])
                old, new = previous['campaign'], snapshot['campaign']
                if (old['campaign_id'] != new['campaign_id'] or previous['order'] != snapshot['order']
                    or new['version'] < old['version']
                    or (old['version'] == new['version'] and old != new)):
                    raise Conflict('Stale or conflicting campaign/order snapshot')
                if row[1] == request_key:
                    return json.loads(row[2])
            db.execute('INSERT INTO assessments(case_id,request_key,snapshot,response) VALUES(?,?,?,?)',
                       (response['case_id'], request_key, canonical(snapshot), canonical(response)))
        return response
