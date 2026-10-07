"""Build a synthetic fixture image and verify it in a restricted Podman container."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

import create_demo_fixture

ROOT = Path(__file__).resolve().parents[1]

CHECK = r'''
import hashlib, http.server, json, pathlib, threading, urllib.request
root = pathlib.Path('/demo')
manifest = json.loads((root / 'manifest.json').read_text())
for entry in manifest['files']:
    assert hashlib.sha256((root / entry['path']).read_bytes()).hexdigest() == entry['sha256'], 'Baseline mismatch'
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        config = json.loads((root / 'uploads/current.json').read_text())
        document = (root / 'uploads' / config['document']).read_bytes()
        if self.path == '/health':
            payload = json.dumps({'status': config['status']}).encode()
        elif self.path == '/document':
            payload = document
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args):
        pass
server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = 'http://127.0.0.1:' + str(server.server_port)
try:
    with urllib.request.urlopen(base + '/health', timeout=5) as response:
        assert json.load(response)['status'] == 'ready', 'Health failed'
    with urllib.request.urlopen(base + '/document', timeout=5) as response:
        actual = hashlib.sha256(response.read()).hexdigest()
    expected = next(x['sha256'] for x in manifest['files'] if x['path'] == 'uploads/customer-demo.txt')
    assert actual == expected, 'Document download mismatch'
    print('PASS: baseline hashes, HTTP health, and protected document download.')
finally:
    server.shutdown()
'''


def main():
    if shutil.which('podman') is None:
        print('Run this command inside Ubuntu, where Podman is installed.')
        return 1
    try:
        info = subprocess.run(['podman', 'info', '--format', '{{.Host.Security.Rootless}}'],
                              check=True, capture_output=True, text=True, timeout=30)
        if info.stdout.strip() != 'true':
            print('Rootless Podman is required. Run without sudo.')
            return 1
        fixture = create_demo_fixture.main()
        # Use an isolated copy of only the generated fixture, never the project/.env.
        manifest = json.loads((fixture / 'manifest.json').read_text())
        name = 'futureproof-baseline-' + uuid.uuid4().hex[:12]
        tag = 'localhost/' + name
        try:
            with tempfile.TemporaryDirectory(prefix='futureproof-build-') as context:
                context = Path(context)
                shutil.copytree(fixture, context / 'fixture')
                (context / 'check.py').write_text(CHECK, encoding='utf-8')
                (context / 'Containerfile').write_text(
                    'FROM docker.io/library/python:3.12-alpine\n'
                    'COPY fixture/ /demo/\nCOPY check.py /check.py\n'
                    'USER 1000:1000\nCMD ["python", "-B", "/check.py"]\n', encoding='utf-8')
                subprocess.run(['podman', 'build', '-t', tag, str(context)], check=True, timeout=600)
            subprocess.run(['podman', 'run', '--rm', '--name', name,
                            '--network=none', '--read-only', '--cap-drop=ALL',
                            '--security-opt=no-new-privileges', '--user=1000:1000',
                            '--memory=256m', '--cpus=1', '--pids-limit=64', tag],
                           check=True, timeout=60)
            for entry in manifest['files']:
                if hashlib.sha256((fixture / entry['path']).read_bytes()).hexdigest() != entry['sha256']:
                    raise RuntimeError('Original fixture changed')
            print('PASS: original fixture unchanged. No cleanup actions executed.')
        finally:
            for command in (['podman', 'rm', '--force', '--ignore', name],
                            ['podman', 'rmi', '--ignore', tag]):
                try:
                    result = subprocess.run(command, capture_output=True, timeout=30)
                    if result.returncode:
                        print('WARNING: temporary resource cleanup failed:', name)
                except (OSError, subprocess.TimeoutExpired):
                    print('WARNING: temporary resource cleanup could not complete:', name)
        return 0
    except (subprocess.SubprocessError, OSError, ValueError, RuntimeError) as error:
        print('Container check failed:', type(error).__name__)
        print('Share the preceding container error output for diagnosis.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
