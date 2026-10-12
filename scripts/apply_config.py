"""Apply and restore an approved upload-limit change in its synthetic fixture."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from config_fixture import ROOT, MIB, BASE_CONFIG, FILES
from approval_state import read_record
from approve_config import review
from apply_cleanup import locked, save
from config_http_worker import run_checks


def file_hash(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MIB:
        raise ValueError('Unsupported file: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authorize(fixture, approval_path):
    record = read_record(approval_path)
    bound = record['binding']
    if (record.get('approval_version') != 1 or record.get('task_family') != 'upload_limit'
            or record.get('status') != 'approved' or record.get('target_applied') is not False
            or not record.get('approved_by') or record.get('confirmation') != 'APPROVE ' + fixture.name
            or bound.get('fixture') != fixture.name):
        raise ValueError('Invalid approval')
    start = datetime.fromisoformat(record['approved_at'])
    end = datetime.fromisoformat(record['expires_at'])
    now = datetime.now(timezone.utc)
    if start.tzinfo is None or end.tzinfo is None or not start <= now < end or end-start != timedelta(hours=24):
        raise ValueError('Approval expired or invalid; review and approve again')
    if (not re.fullmatch(r'config-[A-Za-z0-9_-]+', bound['baseline'])
            or not re.fullmatch(r'config-comparison-[0-9a-f]{32}\.json', bound['comparison'])):
        raise ValueError('Invalid approval references')
    baseline = fixture.parent / bound['baseline']
    candidate, current, value = review(baseline, baseline / bound['comparison'], bound['candidate'])
    if candidate != fixture or current != bound or record['scope'] != {
            'fixture': fixture.name, 'path': 'app.json', 'key': 'max_upload_bytes', 'value': value}:
        raise ValueError('Approval scope or state changed')
    return record, value


def verify(fixture, record, restored=False):
    bound = record['binding']
    for name in ('manifest.json', 'customer-demo.txt'):
        if file_hash(fixture / name) != bound['baseline_hashes'][name]:
            raise ValueError('Protected file changed')
    expected = bound['baseline_hashes']['app.json'] if restored else record['applied_sha256']
    if file_hash(fixture / 'app.json') != expected:
        raise ValueError('Configuration content mismatch')
    checks = run_checks(fixture, MIB if restored else record['value'], deployed=True)
    # Check again after HTTP tests; the verifier must not mutate the configuration.
    if file_hash(fixture / 'app.json') != expected:
        raise ValueError('Configuration changed during verification')
    return checks


def replace_config(fixture, content, mode, mtime_ns=None):
    temporary = fixture / ('config-write-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if mtime_ns is not None:
            os.utime(temporary, ns=(mtime_ns, mtime_ns))
        os.replace(temporary, fixture / 'app.json')
    finally:
        if temporary.exists():
            temporary.unlink()


def restore(fixture, transaction, record):
    backup = transaction / 'app.backup.json'
    expected = record['binding']['baseline_hashes']['app.json']
    if file_hash(backup) != expected:
        raise ValueError('Backup verification failed')
    current = file_hash(fixture / 'app.json')
    if current not in (expected, record['applied_sha256']):
        raise ValueError('Configuration changed after application; refusing to overwrite')
    for name in ('manifest.json', 'customer-demo.txt'):
        if file_hash(fixture / name) != record['binding']['baseline_hashes'][name]:
            raise ValueError('Protected file changed; manual inspection required')
    metadata = record['binding']['metadata']['app.json']
    replace_config(fixture, backup.read_bytes(), metadata[2], metadata[1])
    record['recovery_checks'] = verify(fixture, record, restored=True)
    for name in FILES | {'manifest.json'}:
        info = (fixture / name).stat()
        if [info.st_size, info.st_mtime_ns, stat.S_IMODE(info.st_mode)] != record['binding']['metadata'][name]:
            raise ValueError('Restored metadata mismatch')
    record.update(status='restored', restored_at=datetime.now(timezone.utc).isoformat())
    save(transaction / 'result.json', record)


def apply(fixture, approval_path):
    with locked(fixture):
        transaction = fixture / ('apply-' + approval_path.stem)
        if transaction.exists() or transaction.is_symlink():
            raise ValueError('Approval already used; inspect transaction or run recover')
        approval, value = authorize(fixture, approval_path)
        content = json.dumps(dict(BASE_CONFIG, max_upload_bytes=value), indent=2).encode()
        record = {'status': 'preparing', 'approval': approval_path.name,
                  'binding': approval['binding'], 'value': value,
                  'applied_sha256': hashlib.sha256(content).hexdigest(),
                  'started_at': datetime.now(timezone.utc).isoformat()}
        transaction.mkdir()
        save(transaction / 'result.json', record)
        try:
            backup = transaction / 'app.backup.json'
            shutil.copy2(fixture / 'app.json', backup)
            with backup.open('r+b') as handle:
                os.fsync(handle.fileno())
            if file_hash(backup) != approval['binding']['baseline_hashes']['app.json']:
                raise ValueError('Backup mismatch')
            if authorize(fixture, approval_path)[0] != approval:
                raise ValueError('Approval changed during preparation')
            record['status'] = 'prepared'
            save(transaction / 'result.json', record)
        except Exception:
            record['status'] = 'aborted_before_change'
            save(transaction / 'result.json', record)
            raise
        try:
            replace_config(fixture, content, approval['binding']['metadata']['app.json'][2])
            record['status'] = 'verifying'
            save(transaction / 'result.json', record)
            record['postflight_checks'] = verify(fixture, record)
            record.update(status='applied', applied_at=datetime.now(timezone.utc).isoformat())
            save(transaction / 'result.json', record)
        except (Exception, KeyboardInterrupt):
            try:
                restore(fixture, transaction, record)
            except Exception:
                record['status'] = 'recovery_required'
                save(transaction / 'result.json', record)
                raise RuntimeError('Recovery incomplete; retain transaction and backup') from None
            raise RuntimeError('Application failed; original configuration restored') from None
        return transaction


def recover(fixture, approval_path):
    with locked(fixture):
        transaction = fixture / ('apply-' + approval_path.stem)
        if transaction.is_symlink():
            raise ValueError('Invalid transaction directory')
        record = read_record(transaction / 'result.json')
        if record['approval'] != approval_path.name or record['binding']['fixture'] != fixture.name:
            raise ValueError('Transaction identity mismatch')
        restore(fixture, transaction, record)
        return transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['apply', 'recover'])
    parser.add_argument('fixture')
    parser.add_argument('approval')
    args = parser.parse_args()
    if not re.fullmatch(r'config-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a fixture name only')
    if not re.fullmatch(r'config-approval-[0-9a-f]{32}\.json', args.approval):
        parser.error('Supply a configuration approval filename only')
    fixture = ROOT / 'artifacts/config-fixtures' / args.fixture
    try:
        transaction = (apply if args.operation == 'apply' else recover)(fixture, fixture / args.approval)
        print('PASS:', 'approved configuration applied' if args.operation == 'apply' else 'original 1 MiB configuration restored')
        print('PASS: upload behavior, authentication, health, protected document, and configuration checks.')
        print('Transaction and retained backup:', transaction)
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print('Operation did not complete:', str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
