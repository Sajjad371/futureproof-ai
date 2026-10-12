"""Test a fixed configuration candidate in a restricted rootless container."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid
from config_fixture import ROOT, MIB, FILES, inspect


def snapshot(fixture):
    inspect(fixture)
    return {name: hashlib.sha256((fixture / name).read_bytes()).hexdigest()
            for name in FILES | {'manifest.json'}}


def check_report(report, value):
    required = ('baseline_rejected', 'upload_roundtrip', 'oversized_rejected',
                'unauthorized_rejected', 'health', 'document_preserved', 'protected_settings')
    if (type(report) is not dict or report.get('status') != 'passed'
            or any(report.get(key) is not True for key in required)
            or any(type(report.get(key)) is not int for key in
                   ('required_upload_bytes', 'configured_upload_bytes', 'excess_capacity_bytes'))
            or report['configured_upload_bytes'] != value
            or report['required_upload_bytes'] != 2*MIB
            or report['excess_capacity_bytes'] != value-2*MIB):
        raise ValueError('Incomplete or inconsistent HTTP evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture')
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument('--limit-mib', type=int, choices=[2, 4], default=2)
    limits.add_argument('--limit-bytes', type=int)
    args = parser.parse_args()
    if not re.fullmatch(r'config-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a generated configuration fixture name only')
    fixture = ROOT / 'artifacts/config-fixtures' / args.fixture
    value = args.limit_bytes if args.limit_bytes is not None else args.limit_mib*MIB
    if not MIB <= value <= 8*MIB:
        parser.error('Limit must be between 1 and 8 MiB')
    name = 'futureproof-config-' + uuid.uuid4().hex[:12]
    tag = 'localhost/' + name
    evidence = {'status': 'failed', 'fixture': args.fixture, 'target_applied': False,
                'candidate_source': 'command-line value; provenance recorded by caller', 'limit_bytes': value}
    created = False
    valid_fixture = False
    try:
        before = snapshot(fixture)
        valid_fixture = True
        evidence['baseline_hashes'] = before
        result = subprocess.run(['podman', 'info', '--format', '{{.Host.Security.Rootless}}'],
                                check=True, capture_output=True, text=True, timeout=30)
        if result.stdout.strip() != 'true':
            raise ValueError('Rootless Podman required')
        with tempfile.TemporaryDirectory(prefix='futureproof-config-') as temporary:
            context = Path(temporary)
            (context / 'baseline').mkdir()
            for filename in before:
                shutil.copy2(fixture / filename, context / 'baseline' / filename)
            if snapshot(context / 'baseline') != before:
                raise ValueError('Baseline copy mismatch')
            for filename in ['config_fixture.py', 'config_http_worker.py']:
                shutil.copyfile(ROOT / 'scripts' / filename, context / filename)
            (context / 'candidate.json').write_text(json.dumps({'max_upload_bytes': value}), encoding='utf-8')
            (context / 'Containerfile').write_text('FROM docker.io/library/python:3.12-alpine\n'
                'COPY baseline/ /baseline/\nCOPY config_fixture.py config_http_worker.py /app/\n'
                'COPY candidate.json /candidate.json\n'
                'USER 1000:1000\nCMD ["python", "-B", "/app/config_http_worker.py"]\n', encoding='utf-8')
            created = True
            subprocess.run(['podman', 'build', '-t', tag, str(context)], check=True, timeout=600)
        result = subprocess.run(['podman', 'run', '--rm', '--name', name, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user=1000:1000',
            '--memory=256m', '--cpus=1', '--pids-limit=64',
            '--tmpfs=/workspace:rw,noexec,nosuid,nodev,size=16m,mode=1777', tag],
            check=True, capture_output=True, text=True, timeout=90)
        report = json.loads(result.stdout)
        check_report(report, value)
        if snapshot(fixture) != before:
            raise ValueError('Original fixture changed')
        evidence.update(status='passed', original_unchanged=True, checks=report)
        print('PASS: baseline rejected the 2 MiB upload; updated limit accepted and returned identical data.')
        print('PASS: oversized and unauthorized uploads rejected; health and protected document passed.')
        print('PASS: protected settings and original fixture unchanged. Changed container copy only.')
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        evidence['error_type'] = type(error).__name__
        print('Configuration check failed:', type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr[-3000:])
    finally:
        if created:
            for command in (['podman', 'rm', '--force', '--ignore', name], ['podman', 'rmi', '--ignore', tag]):
                try:
                    result = subprocess.run(command, capture_output=True, timeout=30)
                    if result.returncode:
                        print('WARNING: temporary resource cleanup failed:', name)
                except (OSError, subprocess.SubprocessError):
                    print('WARNING: temporary resource cleanup failed:', name)
    if valid_fixture:
        output = fixture / (name + '.json')
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        print('Configuration evidence:', output)
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
