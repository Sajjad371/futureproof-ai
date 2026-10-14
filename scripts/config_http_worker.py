"""Synthetic HTTP upload app and independent configuration checks."""
import hashlib
import http.client
import http.server
import json
from pathlib import Path
import shutil
import threading
import tempfile

from config_fixture import BASE_CONFIG, MIB, inspect, read_json, validate_plan, verify_configuration

# Public synthetic test credential, not a service/API secret.
DEMO_AUTH = 'Bearer synthetic-demo-only'


def run_checks(root, value, deployed=False):
    manifest = read_json(root / "manifest.json") if deployed else inspect(root)
    before = read_json(root / "app.json")
    if deployed:
        expected = dict(BASE_CONFIG, max_upload_bytes=value)
        if before != expected or type(before.get("max_upload_bytes")) is not int:
            raise ValueError("Unexpected deployed configuration")
        if value != MIB:
            verify_configuration(BASE_CONFIG, before)
    else:
        validate_plan({'steps': [{'tool': 'SET_CONFIG', 'path': 'app.json',
                             'key': 'max_upload_bytes', 'value': value}]}, root)
    upload_temp = tempfile.TemporaryDirectory(prefix='http-check-', dir=root)
    uploaded = Path(upload_temp.name) / 'uploaded.bin'

    class Handler(http.server.BaseHTTPRequestHandler):
        def reply(self, status, body=b''):
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/health':
                self.reply(200, b'{"status":"ready"}')
            elif self.headers.get('Authorization') != DEMO_AUTH:
                self.reply(401)
            elif self.path == '/document':
                self.reply(200, (root / 'customer-demo.txt').read_bytes())
            elif self.path == '/uploaded' and uploaded.exists():
                self.reply(200, uploaded.read_bytes())
            else:
                self.reply(404)

        def do_POST(self):
            self.connection.settimeout(5)
            try:
                length = int(self.headers.get('Content-Length', '-1'))
            except ValueError:
                self.reply(400)
                return
            if length < 0 or length > 8*MIB+1:
                self.reply(413)
                return
            body = self.rfile.read(length)
            if len(body) != length:
                self.reply(400)
                return
            config = read_json(root / 'app.json')
            if self.path != '/upload':
                self.reply(404)
            elif config['auth_required'] and self.headers.get('Authorization') != DEMO_AUTH:
                self.reply(401)
            elif length > config['max_upload_bytes']:
                self.reply(413)
            else:
                uploaded.write_bytes(body)
                self.reply(201, json.dumps({'bytes': length, 'sha256': hashlib.sha256(body).hexdigest()}).encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(method, path, body=None, auth=True):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=10)
        try:
            connection.request(method, path, body=body,
                               headers={'Authorization': DEMO_AUTH} if auth else {})
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    payload = b'u' * (2*MIB)
    try:
        if not deployed:
            require(request('POST', '/upload', payload)[0] == 413, 'Baseline must reject 2 MiB')
            require(not uploaded.exists(), 'Rejected baseline upload wrote data')
            after = dict(before, max_upload_bytes=value)
            (root / 'app.json').write_text(json.dumps(after), encoding='utf-8')
            measurements = verify_configuration(before, read_json(root / 'app.json'))
        else:
            measurements = {'configured_upload_bytes': value}
            if value == MIB:
                require(request('POST', '/upload', payload)[0] == 413, 'Restored limit must reject 2 MiB')
                payload = b'u' * MIB
        # Verify the exact configured boundary, including limits above 2 MiB.
        payload = b'u' * value
        require(request('POST', '/upload', payload, auth=False)[0] == 401, 'Authentication check failed')
        require(not uploaded.exists(), 'Unauthorized upload wrote data')
        status, receipt = request('POST', '/upload', payload)
        require(status == 201, 'Required upload failed')
        require(json.loads(receipt) == {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()},
                'Upload receipt mismatch')
        require(request('GET', '/uploaded') == (200, payload), 'Upload roundtrip mismatch')
        require(request('POST', '/upload', b'x' * (value+1))[0] == 413, 'Oversized upload accepted')
        require(request('GET', '/uploaded') == (200, payload), 'Rejected upload changed accepted data')
        require(request('GET', '/health') == (200, b'{"status":"ready"}'), 'Health check failed')
        status, document = request('GET', '/document')
        require(status == 200 and hashlib.sha256(document).hexdigest() == manifest['files']['customer-demo.txt'],
                'Protected document changed')
        require(hashlib.sha256((root / 'customer-demo.txt').read_bytes()).hexdigest() == manifest['files']['customer-demo.txt'],
                'Protected file changed')
        return dict(status='passed', baseline_rejected=not deployed or value == MIB, upload_roundtrip=True,
                    exact_limit_roundtrip=True, oversized_rejected=True, unauthorized_rejected=True, health=True,
                    document_preserved=True, protected_settings=True, **measurements)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        upload_temp.cleanup()


if __name__ == '__main__':
    root = Path('/workspace/demo')
    shutil.copytree('/baseline', root)
    value = read_json(Path('/candidate.json'))['max_upload_bytes']
    print(json.dumps(run_checks(root, value)))
