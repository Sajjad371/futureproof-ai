"""Execute a saved plan only in a disposable, restricted Podman workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from check_nebius import ROOT
from cleanup_policy import validate_plan

WORKER = r'''
import hashlib, json, pathlib, shutil, http.server, threading, urllib.request
from cleanup_policy import validate_plan
root = pathlib.Path('/workspace/demo')
shutil.copytree('/baseline', root)
manifest = json.loads((root / 'manifest.json').read_text())
plan = json.loads(pathlib.Path('/plan.json').read_text())
for entry in manifest['files']:
    assert hashlib.sha256((root / entry['path']).read_bytes()).hexdigest() == entry['sha256'], 'Baseline mismatch'
paths = validate_plan(plan, manifest, root)
expected = {e['path'] for e in manifest['files'] if e['protected'] is False
            and e['path'].endswith('.tmp') and manifest['created_at']-e['modified_at'] > 30*86400}
assert set(paths) == expected, 'Plan does not complete the fixed cleanup goal'
for path in paths:
    (root / path).unlink()
preserved = []
for entry in manifest['files']:
    target = root / entry['path']
    if entry['path'] in expected:
        assert not target.exists(), 'Eligible file still exists'
    else:
        assert hashlib.sha256(target.read_bytes()).hexdigest() == entry['sha256'], 'Preserved file changed'
        preserved.append(entry['path'])
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
    with urllib.request.urlopen(base+'/health', timeout=5) as response:
        assert json.load(response)['status'] == 'ready', 'Health check failed'
    with urllib.request.urlopen(base+'/document', timeout=5) as response:
        digest = hashlib.sha256(response.read()).hexdigest()
    assert digest == next(e['sha256'] for e in manifest['files'] if e['path']=='uploads/customer-demo.txt')
finally:
    server.shutdown()
print(json.dumps({'status':'passed', 'deleted':paths, 'preserved':preserved,
                  'http_health':True, 'document_download':True,
                  'removed_file_bytes':sum(e['size_bytes'] for e in manifest['files'] if e['path'] in expected)}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', help='Generated fixture directory name, e.g. cleanup-kwip223n')
    args = parser.parse_args()
    if not args.fixture.startswith('cleanup-') or Path(args.fixture).name != args.fixture or '/' in args.fixture or '\\' in args.fixture:
        parser.error('Supply only a generated cleanup directory name')
    fixture = ROOT / 'artifacts' / 'fixtures' / args.fixture
    name = 'futureproof-simulation-' + uuid.uuid4().hex[:12]
    tag = 'localhost/' + name
    evidence = {'status':'failed', 'container':name, 'target_applied':False}
    created = False
    try:
        manifest = json.loads((fixture / 'manifest.json').read_text())
        record = json.loads((fixture / 'planning-result.json').read_text())
        if record.get('status') != 'policy_passed':
            raise ValueError('Planning did not pass')
        plan = record['plan']
        paths = validate_plan(plan, manifest, fixture)
        expected = {e['path'] for e in manifest['files'] if e['protected'] is False
                    and e['path'].endswith('.tmp')
                    and manifest['created_at'] - e['modified_at'] > 30 * 86400}
        if set(paths) != expected:
            raise ValueError('Plan does not complete the fixed cleanup goal')
        # Only our fixed synthetic fixture is supported at this stage.
        allowed = {'uploads/current.json','uploads/customer-demo.txt','uploads/old.tmp','uploads/recent.tmp'}
        if {e['path'] for e in manifest['files']} != allowed or len(manifest['files']) != 4:
            raise ValueError('Unsupported fixture layout')
        for entry in manifest['files']:
            p = fixture / entry['path']
            if p.is_symlink() or p.stat().st_nlink != 1 or p.stat().st_size > 1048576:
                raise ValueError('Unsupported fixture file')
            if hashlib.sha256(p.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('Fixture changed')
        info = subprocess.run(['podman','info','--format','{{.Host.Security.Rootless}}'], check=True,
                              capture_output=True, text=True, timeout=30)
        if info.stdout.strip() != 'true':
            raise ValueError('Rootless Podman required')
        with tempfile.TemporaryDirectory(prefix='futureproof-simulation-') as temporary:
            context = Path(temporary)
            (context/'baseline/uploads').mkdir(parents=True)
            (context/'baseline/manifest.json').write_text(json.dumps(manifest))
            for entry in manifest['files']:
                shutil.copy2(fixture/entry['path'], context/'baseline'/entry['path'])
            (context/'plan.json').write_text(json.dumps(plan))
            (context/'worker.py').write_text(WORKER)
            shutil.copyfile(ROOT/'scripts/cleanup_policy.py', context/'cleanup_policy.py')
            (context/'Containerfile').write_text('FROM docker.io/library/python:3.12-alpine\n'
                'COPY baseline/ /baseline/\nCOPY plan.json worker.py cleanup_policy.py /\n'
                'USER 1000:1000\nCMD ["python", "-B", "/worker.py"]\n')
            created = True
            subprocess.run(['podman','build','-t',tag,str(context)], check=True, timeout=600)
        result = subprocess.run(['podman','run','--rm','--name',name,'--network=none','--read-only',
            '--cap-drop=ALL','--security-opt=no-new-privileges','--user=1000:1000',
            '--memory=256m','--cpus=1','--pids-limit=64',
            '--tmpfs=/workspace:rw,noexec,nosuid,nodev,size=16m,mode=1777',tag],
            check=True, capture_output=True, text=True, timeout=60)
        report = json.loads(result.stdout)
        preserved = {e['path'] for e in manifest['files']} - expected
        removed_bytes = sum(e['size_bytes'] for e in manifest['files'] if e['path'] in expected)
        if (type(report) is not dict or report.get('status') != 'passed'
                or report.get('http_health') is not True
                or report.get('document_download') is not True
                or report.get('deleted') != paths
                or type(report.get('preserved')) is not list
                or sorted(report['preserved']) != sorted(preserved)
                or type(report.get('removed_file_bytes')) is not int
                or report['removed_file_bytes'] != removed_bytes):
            raise ValueError('Incomplete or inconsistent simulation report')
        # Only copy checked fields; worker output cannot override host evidence.
        for key in ('status', 'deleted', 'preserved', 'http_health',
                    'document_download', 'removed_file_bytes'):
            evidence[key] = report[key]
        unchanged = all(hashlib.sha256((fixture/e['path']).read_bytes()).hexdigest()==e['sha256'] for e in manifest['files'])
        evidence['original_unchanged'] = unchanged
        if not unchanged:
            raise ValueError('Original fixture changed')
        print('PASS: cleanup completed inside the disposable container.')
        print('PASS: protected and recent files unchanged; HTTP health and download passed.')
        print('PASS: original fixture unchanged.')
        print('Deleted inside container only:', ', '.join(evidence['deleted']))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        evidence['status'] = 'failed'
        evidence['error_type'] = type(error).__name__
        print('Simulation failed:', type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr[-3000:])
    finally:
        if created:
            for command in (['podman','rm','--force','--ignore',name], ['podman','rmi','--ignore',tag]):
                try:
                    result = subprocess.run(command, capture_output=True, timeout=30)
                    if result.returncode:
                        print('WARNING: temporary resource cleanup failed:',name)
                except (OSError, subprocess.SubprocessError):
                    print('WARNING: temporary resource cleanup failed:',name)
    if fixture.is_dir():
        output = fixture / (name + '.json')
        output.write_text(json.dumps(evidence, indent=2))
        print('Simulation evidence:',output)
    return 0 if evidence['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
