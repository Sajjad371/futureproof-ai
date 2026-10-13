"""Test a fixed synthetic service restart in a restricted rootless container."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid
from restart_fixture import ROOT, CONTENTS, inspect, validate_plan
from restart_http_worker import check_report
from config_fixture import read_json
from approval_state import digest
FILES = set(CONTENTS)


def load_plan(fixture, filename, before):
    if not re.fullmatch(r'restart-plan-[0-9a-f]{32}\.json', filename):
        raise ValueError('Invalid planning record name')
    path = fixture / filename
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError('Invalid planning record file')
    record = read_json(path)
    if (record.get('version') != 1 or record.get('status') != 'policy_passed'
            or record.get('fixture') != fixture.name
            or record.get('actions_executed') is not False
            or record.get('baseline_hashes') != before
            or record.get('plan_sha256') != digest(record.get('plan'))):
        raise ValueError('Planning record does not match fixture')
    validate_plan(record['plan'], fixture)
    return record


def snapshot(fixture):
    inspect(fixture)
    return {name: hashlib.sha256((fixture / name).read_bytes()).hexdigest()
            for name in FILES | {'manifest.json'}}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture')
    parser.add_argument('--plan', help='Validated restart planning record in this fixture')
    args = parser.parse_args()
    if not re.fullmatch(r'restart-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a generated restart fixture name only')
    fixture = ROOT / 'artifacts/restart-fixtures' / args.fixture
    name = 'futureproof-restart-' + uuid.uuid4().hex[:12]
    tag = 'localhost/' + name
    evidence = {'status': 'failed', 'fixture': args.fixture, 'target_applied': False,
                'candidate_source': 'fixed synthetic restart, not AI-generated'}
    created = False
    valid_fixture = False
    try:
        validate_plan({'steps': [{'tool': 'RESTART_SERVICE', 'service': 'futureproof-demo'}]}, fixture)
        before = snapshot(fixture)
        plan_record = load_plan(fixture, args.plan, before) if args.plan else None
        if plan_record is not None:
            evidence.update(candidate_source='validated planning record', plan_file=args.plan,
                            plan_sha256=plan_record['plan_sha256'], planning_sha256=digest(plan_record))
        valid_fixture = True
        evidence['baseline_hashes'] = before
        result = subprocess.run(['podman', 'info', '--format', '{{.Host.Security.Rootless}}'],
                                check=True, capture_output=True, text=True, timeout=30)
        if result.stdout.strip() != 'true':
            raise ValueError('Rootless Podman required')
        with tempfile.TemporaryDirectory(prefix='futureproof-restart-') as temporary:
            context = Path(temporary)
            (context / 'baseline').mkdir()
            for filename in before:
                shutil.copy2(fixture / filename, context / 'baseline' / filename)
            if snapshot(context / 'baseline') != before:
                raise ValueError('Baseline copy mismatch')
            for filename in ['config_fixture.py', 'restart_fixture.py', 'restart_http_worker.py']:
                shutil.copyfile(ROOT / 'scripts' / filename, context / filename)
            (context / 'Containerfile').write_text('FROM docker.io/library/python:3.12-alpine\n'
                'COPY baseline/ /baseline/\nCOPY config_fixture.py restart_fixture.py restart_http_worker.py /app/\n'
                'USER 1000:1000\nCMD ["python", "-B", "/app/restart_http_worker.py"]\n', encoding='utf-8')
            created = True
            subprocess.run(['podman', 'build', '-t', tag, str(context)], check=True, timeout=600)
        result = subprocess.run(['podman', 'run', '--rm', '--name', name, '--network=none', '--read-only',
            '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user=1000:1000',
            '--memory=256m', '--cpus=1', '--pids-limit=64',
            '--tmpfs=/workspace:rw,noexec,nosuid,nodev,size=16m,mode=1777', tag],
            check=True, capture_output=True, text=True, timeout=90)
        report = json.loads(result.stdout)
        check_report(report)
        if plan_record is not None and load_plan(fixture, args.plan, before) != plan_record:
            raise ValueError('Planning record changed during simulation')
        if snapshot(fixture) != before:
            raise ValueError('Original fixture changed')
        evidence.update(status='passed', original_unchanged=True, checks=report)
        print('PASS: old service process exited; new process loaded revision 2.')
        print('PASS: HTTP health, authentication, and protected document checks passed.')
        print('PASS: configuration, protected files, and original fixture unchanged.')
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        evidence['error_type'] = type(error).__name__
        print('Restart check failed:', type(error).__name__)
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
        print('Restart evidence:', output)
    return 0 if evidence['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
