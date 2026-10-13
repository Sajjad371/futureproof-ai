"""Approved synthetic restart session with verified recovery and child cleanup.

The service lives only for this command's session. No host service is managed.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import re

from restart_fixture import ROOT, SERVICE, CONFIG, STARTUP
from approve_restart import review
from approval_state import read_record
from apply_cleanup import locked, save
from restart_http_worker import start, stop, request


def authorize(fixture, path):
    record = read_record(path)
    if (record.get('approval_version') != 1 or record.get('task_family') != 'service_restart'
            or record.get('status') != 'approved' or record.get('target_applied') is not False
            or not record.get('approved_by') or record.get('confirmation') != 'APPROVE ' + fixture.name
            or record.get('scope') != {'fixture': fixture.name, 'service': SERVICE, 'revision': 2}):
        raise ValueError('Invalid approval scope')
    begin = datetime.fromisoformat(record['approved_at'])
    end = datetime.fromisoformat(record['expires_at'])
    if (begin.tzinfo is None or end.tzinfo is None or end-begin != timedelta(hours=24)
            or not begin <= datetime.now(timezone.utc) < end):
        raise ValueError('Approval expired or invalid; approve again')
    if review(fixture, record['binding']['simulation']) != record['binding']:
        raise ValueError('Approved state changed; simulate and approve again')
    return record


def verify(fixture, process, port, instance, revision, binding):
    expected = STARTUP if revision == 1 else CONFIG
    status, body = request(port, '/state')
    if (process.poll() is not None or status != 200 or json.loads(body) != {
            'revision': revision, 'message': expected['message'], 'instance': instance}):
        raise ValueError('Service revision or identity mismatch')
    if request(port, '/health') != (200, b'ready'):
        raise ValueError('Health check failed')
    if any(request(port, route, False)[0] != 401 for route in ['/state', '/document']):
        raise ValueError('Authentication check failed')
    if request(port, '/document') != (200, (fixture / 'customer-demo.txt').read_bytes()):
        raise ValueError('Document download mismatch')
    if review(fixture, binding['simulation']) != binding:
        raise ValueError('Protected fixture or evidence changed')
    return {'revision': revision, 'http_health': True, 'authentication': True,
            'document_preserved': True, 'state_unchanged': True}


def run_session(fixture, approval_path, confirm=input):
    with locked(fixture):
        transaction = fixture / ('apply-' + approval_path.stem)
        if transaction.exists() or transaction.is_symlink():
            raise ValueError('Approval already used; inspect its session record')
        approval = authorize(fixture, approval_path)
        transaction.mkdir()
        record = {'status': 'preparing', 'approval': approval_path.name,
                  'binding': approval['binding'], 'session_only': True,
                  'started_at': datetime.now(timezone.utc).isoformat()}
        process = None
        def checkpoint(status):
            record['status'] = status
            save(transaction / 'result.json', record)
        def recover():
            nonlocal process
            if process is not None:
                stop(process)
                process = None
            # Never rewrite unexpected file edits to force recovery to pass.
            if review(fixture, approval['binding']['simulation']) != approval['binding']:
                raise ValueError('Fixture changed; recovery requires inspection')
            process, port, instance = start(fixture, 'startup.json')
            record['recovery_checks'] = verify(fixture, process, port, instance, 1, approval['binding'])
            checkpoint('restored')
        try:
            checkpoint('preparing')
            process, port, instance = start(fixture, 'startup.json')
            record['baseline_checks'] = verify(fixture, process, port, instance, 1, approval['binding'])
            if authorize(fixture, approval_path) != approval:
                raise ValueError('Approval changed during preparation')
            checkpoint('restarting')
            stop(process)
            process = None
            process, port, instance = start(fixture, 'app.json')
            record['application_checks'] = verify(fixture, process, port, instance, 2, approval['binding'])
            checkpoint('applied')
            print('PASS: approved synthetic restart applied; revision 2 and HTTP checks passed.', flush=True)
            while confirm('Type RECOVER to restore revision 1 and finish the demo session:\n> ') != 'RECOVER':
                print('Enter RECOVER, or press Ctrl+C for automatic recovery.')
            recover()
            print('PASS: revision 1 restored and HTTP checks passed.')
        except (Exception, KeyboardInterrupt) as error:
            record['failure_type'] = type(error).__name__
            try:
                recover()
            except (Exception, KeyboardInterrupt):
                checkpoint('recovery_failed')
                raise RuntimeError('Session failed; recovery verification failed. Inspect the record.') from None
            raise RuntimeError('Session interrupted or failed; revision 1 recovery verified.') from None
        finally:
            if process is not None:
                stop(process)
            record['session_finished_at'] = datetime.now(timezone.utc).isoformat()
            record['owned_processes_stopped'] = True
            save(transaction / 'result.json', record)
        return transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture')
    parser.add_argument('approval')
    args = parser.parse_args()
    if not re.fullmatch(r'restart-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a fixture name only')
    if not re.fullmatch(r'restart-approval-[0-9a-f]{32}\.json', args.approval):
        parser.error('Supply a restart approval filename only')
    fixture = ROOT / 'artifacts/restart-fixtures' / args.fixture
    try:
        path = run_session(fixture, fixture / args.approval)
        print('Session record:', path)
        print('Demo service stopped after recovery verification. Approval cannot be reused.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print('Session did not complete:', str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
