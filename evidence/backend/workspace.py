"""Single-origin local workspace over the two services' existing HTTP APIs."""
import http.client
import io
import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

from evidence.backend.http_server import BoundedHTTPServer, DeadlineReader, IntakeDeadline
from evidence.backend.validation import MAX_BODY_BYTES, ROOT
from evidence.demo import local_origin

WEB = ROOT / 'evidence' / 'workspace'
ROUTES = {
    'customer': {
        'GET': (r'/health', r'/demo/resolution-status', r'/v1/assessments/[A-Za-z0-9_-]{1,128}'),
        'POST': (r'/demo/(?:extraction|image-extraction|assessments|handoff)',),
    },
    'merchant': {
        'GET': (r'/health', r'/v1/cases/[A-Za-z0-9_-]{1,128}'),
        'POST': (r'/v1/cases/[A-Za-z0-9_-]{1,128}/(?:brief|remedy-conditions|approve|reconcile)',),
    },
}


def make_workspace(port, customer_url, merchant_url):
    upstreams = {name: urlsplit(local_origin(url)) for name, url in
                 (('customer', customer_url), ('merchant', merchant_url))}

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def setup(self):
            super().setup()
            self.intake = IntakeDeadline(self.connection, self.server.request_timeout)
            self.rfile.close()
            self.rfile = io.BufferedReader(DeadlineReader(self.connection, self.intake))

        def finish(self):
            try:
                self.intake.close()
            finally:
                super().finish()

        def handle(self):
            try:
                super().handle()
            except (ConnectionError, TimeoutError):
                pass

        def log_message(self, *args):
            pass

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

        def parse_request(self):
            if not super().parse_request():
                return False
            if self.intake.expired():
                self.reply(408, {'error': 'Request receive deadline exceeded'})
                return False
            hosts = self.headers.get_all('Host', [])
            if len(hosts) != 1 or hosts[0] not in {
                    f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
                self.reply(403, {'error': 'Loopback Host required'})
                return False
            origins = self.headers.get_all('Origin', [])
            if origins and origins != [f'http://{hosts[0]}']:
                self.reply(403, {'error': 'Cross-origin requests are disabled'})
                return False
            return True

        def do_GET(self):
            if not self.intake.complete():
                return self.reply(408, {'error': 'Request receive deadline exceeded'})
            assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/workspace.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/workspace.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path in assets:
                file, mime = assets[self.path]
                return self.reply(200, (WEB / file).read_bytes(), mime)
            return self.forward()

        def do_POST(self):
            return self.forward()

        def forward(self):
            parts = self.path.split('/', 3)
            if (len(parts) != 4 or parts[1] != 'api' or parts[2] not in upstreams
                    or not any(re.fullmatch(pattern, '/' + parts[3])
                               for pattern in ROUTES[parts[2]].get(self.command, ()))):
                return self.reply(404, {'error': 'Not found'})
            body = None
            if self.command == 'POST':
                lengths = self.headers.get_all('Content-Length', [])
                if (self.headers.get_all('Transfer-Encoding', []) or len(lengths) != 1
                        or not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0]) > 8
                        or len(self.headers.get_all('Content-Type', [])) != 1
                        or self.headers.get_content_type() != 'application/json'):
                    return self.reply(400, {'error': 'Expected bounded JSON with one Content-Length'})
                size = int(lengths[0])
                if not 0 < size <= MAX_BODY_BYTES:
                    return self.reply(413, {'error': 'Request exceeds the 3 MiB limit or is empty'})
                try:
                    body = self.rfile.read(size)
                except TimeoutError:
                    return self.reply(408, {'error': 'Request receive deadline exceeded'})
                if not self.intake.complete():
                    return self.reply(408, {'error': 'Request receive deadline exceeded'})
                if len(body) != size:
                    return self.reply(400, {'error': 'Incomplete request body'})
            upstream = upstreams[parts[2]]
            # Never forward browser Host, Origin, authorization, cookies or arbitrary
            # destinations. Both upstreams are owned loopback services, fixed at launch.
            connection = http.client.HTTPConnection(upstream.hostname, upstream.port, timeout=12)
            try:
                connection.request(self.command, '/' + parts[3], body=body,
                                   headers={'Content-Type': 'application/json'} if body is not None else {})
                response = connection.getresponse()
                raw = response.read(MAX_BODY_BYTES + 1)
                if len(raw) > MAX_BODY_BYTES or response.getheader('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Invalid service response')
                data = json.loads(raw)
                self.reply(response.status, data)
            except (OSError, ValueError, http.client.HTTPException):
                self.reply(503, {'error': 'The service response could not be confirmed. Refresh status before retrying an action.'})
            finally:
                connection.close()

    return BoundedHTTPServer(('127.0.0.1', port), Handler, max_handlers=8, request_timeout=10)
