"""Loopback-only synthetic demo plus the internal frozen v1 assessment API."""
import argparse
import copy
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from evidence.ai.mock_extractor import propose
from evidence.ai.extraction import ExtractionService, ExtractionUnavailable
from evidence.ai.fixture_extractor import FixtureExtractor
from evidence.ai.omniroute import OmniRouteExtractor, read_key
from evidence.backend.images import decode_image
from evidence.backend.assessment import assess
from evidence.backend.json_input import strict_json
from evidence.backend.resolution_client import ResolutionClient, ResolutionNotFound, ResolutionUnavailable
from evidence.backend.store import AssessmentStore, Conflict
from evidence.backend.validation import InvalidInput, MAX_BODY_BYTES, ROOT

WEB = ROOT / 'evidence' / 'web'


def make_server(port=8101, db_path=None, resolution_url=None, extraction_adapter=None):
    store = AssessmentStore(db_path or ROOT / 'evidence' / '.local' / 'assessments.sqlite3')
    client = ResolutionClient(resolution_url or os.environ.get('RESOLUTION_BASE_URL', 'http://127.0.0.1:8102'))
    extraction = ExtractionService(extraction_adapter if extraction_adapter is not None else FixtureExtractor())
    fixture = json.loads((ROOT / 'contracts' / 'fixtures' / 'assessment-request.json').read_text())

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *args):
            pass  # No bodies, images, identifiers, or secrets in access logs.

        def reply(self, code, body, content_type='application/json'):
            raw = json.dumps(body).encode() if content_type == 'application/json' else body
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def allowed_host(self):
            return len(self.headers.get_all('Host', [])) == 1 and self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host():
                self.reply(403, {'error': 'Loopback Host required'})
                return
            assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path in assets:
                name, content_type = assets[self.path]
                self.reply(200, (WEB / name).read_bytes(), content_type)
            elif self.path == '/health':
                self.reply(200, {'service': 'evidence', 'mode': 'manual', 'extraction_mode': extraction.adapter.mode, 'extraction_provider': extraction.adapter.provider_name, 'synthetic_only': True})
            elif self.path.startswith('/v1/assessments/'):
                try:
                    data = store.latest(unquote(self.path[len('/v1/assessments/'):]))
                    self.reply(200 if data else 404, data or {'error': 'Unknown case'})
                except sqlite3.Error:
                    self.reply(503, {'error': 'Evidence storage is unavailable'})
            elif self.path == '/demo/resolution-status':
                try:
                    self.reply(200, client.get_status(fixture['order']['case_id']))
                except ResolutionNotFound as error:
                    self.reply(404, {'error': str(error)})
                except ResolutionUnavailable as error:
                    self.reply(503, {'error': str(error)})
            else:
                self.reply(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.allowed_host():
                self.reply(403, {'error': 'Loopback Host required'})
                return
            # Browser writes must be same-origin. Internal callers may omit Origin.
            origins = self.headers.get_all('Origin', [])
            if (len(origins) > 1
                    or (origins and origins[0] != f'http://{self.headers.get("Host")}')):
                self.reply(403, {'error': 'Cross-origin writes are disabled'})
                return
            if self.path not in ('/v1/assessments', '/demo/assessments', '/demo/extraction', '/demo/image-extraction'):
                self.reply(404, {'error': 'Not found'})
                return
            try:
                if self.headers.get_all('Transfer-Encoding', []):
                    raise InvalidInput('Transfer encoding is not supported')
                if (len(self.headers.get_all('Content-Type', [])) != 1
                        or self.headers.get_content_type() != 'application/json'):
                    raise InvalidInput('Content-Type must be application/json')
                lengths = self.headers.get_all('Content-Length', [])
                if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                    raise InvalidInput('Expected one valid Content-Length')
                size = int(lengths[0])
                if not 0 < size <= MAX_BODY_BYTES:
                    self.reply(413, {'error': 'Request exceeds the 3 MiB limit or is empty'})
                    return
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise InvalidInput('Incomplete request body')
                body = strict_json(raw)
                if self.path == '/demo/image-extraction':
                    if not isinstance(body, dict) or set(body) != {'image_base64', 'mime_type'}:
                        raise InvalidInput('Provide an image and its MIME type only')
                    image = decode_image(body['image_base64'], body['mime_type'])
                    self.reply(200, extraction.propose(image))
                    return
                if self.path == '/demo/extraction':
                    if not isinstance(body, dict) or set(body) != {'sample_id'} or not isinstance(body['sample_id'], str):
                        raise InvalidInput('Provide one synthetic sample ID')
                    self.reply(200, propose(body['sample_id']))
                    return
                request = body
                if self.path == '/demo/assessments':
                    if not isinstance(body, dict) or set(body) != {'label'}:
                        raise InvalidInput('Demo accepts only a label; campaign/order are server-held')
                    request = copy.deepcopy(fixture)
                    request['label'] = body['label']
                response = assess(request)
                self.reply(200, store.save(request, response))
            except ExtractionUnavailable as error:
                self.reply(503, {'error': str(error)})
            except Conflict as error:
                self.reply(409, {'error': str(error)})
            except (InvalidInput, ValueError, TypeError, KeyError, UnicodeError):
                self.reply(400, {'error': 'Invalid input; use the v1 schema, bounded PNG/JPEG and confirmed identifiers'})
            except (OSError, sqlite3.Error):
                self.reply(503, {'error': 'Evidence storage is unavailable'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8101)
    parser.add_argument('--db', type=Path)
    parser.add_argument('--extractor', choices=('mock', 'omniroute'), default='mock')
    parser.add_argument('--omniroute-env', type=Path, help='Read only OMNIROUTE_API_KEY from an existing env file')
    parser.add_argument('--model', default='auto/smart', help='OmniRoute model; served model is recorded per proposal')
    args = parser.parse_args()
    try:
        adapter = OmniRouteExtractor(read_key(args.omniroute_env), model=args.model) if args.extractor == 'omniroute' else FixtureExtractor()
    except (OSError, ValueError):
        parser.error('Could not load the OmniRoute configuration; check the key source and model identifier')
    server = make_server(args.port, args.db, extraction_adapter=adapter)
    print(f'Evidence synthetic demo: http://127.0.0.1:{server.server_port} (manual rules; {adapter.mode} extraction)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
