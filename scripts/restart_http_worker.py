"""Exercise a real child-process restart against a synthetic loopback service."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

from restart_fixture import CONFIG, STARTUP, inspect

TOKEN = 'Bearer synthetic-restart-demo-only'
CHECKS = ('baseline_stale', 'old_process_exited', 'new_instance', 'current_revision',
          'health', 'unauthorized_rejected', 'document_preserved', 'files_preserved')


def serve(root, source, instance):
    loaded = json.loads((root / source).read_text(encoding='utf-8'))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == '/health':
                data, status = b'ready', 200
            elif self.headers.get('Authorization') != TOKEN:
                data, status = b'unauthorized', 401
            elif self.path == '/state':
                data = json.dumps({'revision': loaded['revision'], 'message': loaded['message'],
                                   'instance': instance}).encode()
                status = 200
            elif self.path == '/document':
                data, status = (root / 'customer-demo.txt').read_bytes(), 200
            else:
                data, status = b'not found', 404
            self.send_response(status)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    with HTTPServer(('127.0.0.1', 0), Handler) as server:
        print(server.server_port, flush=True)
        server.serve_forever()


def request(port, path, authorized=True):
    headers = {'Authorization': TOKEN} if authorized else {}
    # Ignore host proxy settings for this loopback-only test.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request('http://127.0.0.1:%s%s' % (port, path), headers=headers)
    try:
        with opener.open(req, timeout=2) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read()


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def start(root, source):
    # A reader thread keeps startup bounded even if the child never reports a port.
    import queue
    import threading
    instance = uuid.uuid4().hex
    process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
        '--serve', str(root), '--source', source, '--instance', instance],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    lines = queue.Queue()
    thread = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
    thread.start()
    try:
        port = int(lines.get(timeout=5).strip())
        if not 1 <= port <= 65535 or request(port, '/health') != (200, b'ready'):
            raise ValueError('Service did not become healthy')
        return process, port, instance
    except BaseException:
        stop(process)
        raise
    finally:
        if not thread.is_alive():
            process.stdout.close()


def run_checks(root):
    before = inspect(root)
    first = second = None
    try:
        first, port, old_instance = start(root, 'startup.json')
        code, body = request(port, '/state')
        baseline = json.loads(body)
        if code != 200 or baseline != dict(STARTUP, instance=old_instance):
            raise ValueError('Expected stale baseline service')
        stop(first)
        if first.poll() is None:
            raise ValueError('Original process still running')
        second, port, new_instance = start(root, 'app.json')
        code, body = request(port, '/state')
        state = json.loads(body)
        if (code != 200 or state != {'revision': CONFIG['revision'],
                'message': CONFIG['message'], 'instance': new_instance}
                or new_instance == old_instance):
            raise ValueError('Restart did not load current configuration')
        if request(port, '/state', False)[0] != 401 or request(port, '/document', False)[0] != 401:
            raise ValueError('Unauthorized access accepted')
        if request(port, '/document') != (200, (root / 'customer-demo.txt').read_bytes()):
            raise ValueError('Protected download mismatch')
        if request(port, '/health') != (200, b'ready') or inspect(root) != before:
            raise ValueError('Post-restart checks failed')
        return dict(status='passed', before_revision=1, after_revision=2,
                    **{key: True for key in CHECKS})
    finally:
        for process in (first, second):
            if process is not None:
                stop(process)


def check_report(report):
    if (type(report) is not dict or report.get('status') != 'passed'
            or any(report.get(key) is not True for key in CHECKS)
            or type(report.get('before_revision')) is not int
            or type(report.get('after_revision')) is not int
            or report['before_revision'] != 1 or report['after_revision'] != 2):
        raise ValueError('Incomplete or inconsistent restart evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', type=Path)
    parser.add_argument('--source', choices=['startup.json', 'app.json'])
    parser.add_argument('--instance')
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.source, args.instance)
    else:
        root = Path('/workspace/demo')
        shutil.copytree('/baseline', root)
        print(json.dumps(run_checks(root)))
