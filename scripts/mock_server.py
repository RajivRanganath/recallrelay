"""Dependency-free local contract mock. No AI, persistence or external requests."""
import argparse
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def result(lane, scenario='default', body=None):
    name = 'assessment' if lane == 'evidence' else 'resolution'
    data = json.loads((ROOT / f'contracts/fixtures/{name}-response.json').read_text())
    if body:
        data['case_id'] = body['order']['case_id']
    if lane == 'evidence':
        if body:
            data['campaign_id'] = body['campaign']['campaign_id']
            data['campaign_version'] = body['campaign']['version']
        if scenario == 'missing':
            data.update(decision='needs_information', batch=None, missing_fields=['batch'], clarification='Please provide a clearer batch number.', evidence=[], reason='Mock: batch is unreadable.')
        elif scenario == 'excluded':
            data.update(decision='excluded', batch='B103', evidence=[{'source_id':'confirmed-label','field':'batch','value':'B103'}], reason='Mock: batch excluded from this campaign, not a safety finding.')
        elif scenario != 'default':
            raise ValueError('Unknown mock scenario')
    else:
        if scenario == 'manual':
            data.update(status='manual_required', brief='Mock: payment route requires manual handling.', proposed_amount_minor=0)
        elif scenario in ('pending', 'failed'):
            data.update(status=scenario, brief=f'Mock: refund {scenario}; no money moved.', operation_id='operation-mock-1')
        elif scenario != 'default':
            raise ValueError('Unknown mock scenario')
    return data

def make_server(lane, port):
    resource = 'assessments' if lane == 'evidence' else 'resolutions'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, code, body):
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('X-RecallRelay-Mode', 'mock')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            if self.path == '/health':
                self.reply(200, {'service':lane, 'mode':'mock'})
            elif self.path == f'/v1/{resource}/case-demo-1':
                self.reply(200, result(lane))
            else:
                self.reply(404, {'error':'Not found', 'mode':'mock'})
        def do_POST(self):
            if self.path != f'/v1/{resource}':
                self.reply(404, {'error':'Not found', 'mode':'mock'}); return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1_000_000:
                    raise ValueError('Body must be 1..1000000 bytes')
                body = json.loads(self.rfile.read(size))
                name = 'assessment-request' if lane == 'evidence' else 'resolution-request'
                schema = json.loads((ROOT / f'contracts/schemas/{name}.schema.json').read_text())
                if not isinstance(body, dict) or not all(k in body for k in schema['required']):
                    raise ValueError('Missing required fields')
                if body['schema_version'] != '1.0':
                    raise ValueError('Expected schema_version 1.0')
                self.reply(200, result(lane, self.headers.get('X-Mock-Scenario', 'default'), body))
            except (ValueError, KeyError, TypeError):
                self.reply(400, {'error':'Invalid mock input or scenario', 'mode':'mock'})
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('lane', choices=['evidence', 'resolution'])
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    port = args.port or (8101 if args.lane == 'evidence' else 8102)
    print(f'{args.lane} MOCK on http://127.0.0.1:{port}; no AI or money movement', flush=True)
    make_server(args.lane, port).serve_forever()
