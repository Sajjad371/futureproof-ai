"""Apply/restore the one-file synthetic demo only, using a saved approval.

Trusted single-user workspace. The lock coordinates our own commands, not
uncooperative programs. Records are not authenticated against local tampering.
"""
import argparse
from contextlib import contextmanager
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import stat
import threading
import urllib.request
import uuid

from check_nebius import ROOT
from approval_state import ALLOWED, binding, digest, read_record
from approve_cleanup import review

TARGET = 'uploads/old.tmp'


def save(path, record):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def locked(fixture):
    if fixture.is_symlink() or not fixture.is_dir():
        raise ValueError('Invalid fixture')
    path = fixture / '.apply.lock'
    if path.is_symlink():
        raise ValueError('Invalid lock file')
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def check_file(path, entry):
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or metadata.st_size != entry['size_bytes']
            or int(metadata.st_mtime) != entry['modified_at']
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']):
        raise ValueError('File verification failed: ' + entry['path'])


def verify_target(fixture, manifest, deleted):
    uploads = fixture / 'uploads'
    expected = ALLOWED - ({TARGET} if deleted else set())
    if uploads.is_symlink() or {('uploads/' + p.name) for p in uploads.iterdir()} != expected:
        raise ValueError('Unexpected target layout')
    for entry in manifest['files']:
        if entry['path'] in expected:
            check_file(fixture / entry['path'], entry)
    config = read_record(uploads / 'current.json')
    if config != {'status': 'ready', 'document': 'customer-demo.txt'}:
        raise ValueError('Application configuration failed')
    document = (uploads / 'customer-demo.txt').read_bytes()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                payload = json.dumps(config).encode()
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = 'http://127.0.0.1:' + str(server.server_port)
        with urllib.request.urlopen(base + '/health', timeout=5) as response:
            if json.load(response)['status'] != 'ready':
                raise ValueError('HTTP health failed')
        with urllib.request.urlopen(base + '/document', timeout=5) as response:
            if response.read() != document:
                raise ValueError('HTTP document failed')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def authorized(fixture, approval_path):
    approval = read_record(approval_path)
    name = approval.get('simulation', '')
    if not re.fullmatch(r'futureproof-simulation-[0-9a-f]{12}\.json', name):
        raise ValueError('Invalid simulation reference')
    current, evidence, plan = review(fixture, fixture / name)
    if (approval.get('approval_version') != 1 or approval.get('status') != 'approved'
            or approval.get('target_applied') is not False or approval.get('binding') != current
            or approval.get('simulation_sha256') != digest(evidence)
            or approval.get('confirmation') != 'APPROVE ' + Path(name).stem):
        raise ValueError('Approval is invalid or stale')
    if plan != {'steps': [{'tool': 'DELETE_FILE', 'path': TARGET}]}:
        raise ValueError('Application currently supports only the old.tmp demo')
    return approval


def restore(fixture, transaction, record):
    # Validate the saved manifest before deriving any paths from it.
    manifest = record['manifest']
    if (len(manifest['files']) != 4 or {e['path'] for e in manifest['files']} != ALLOWED
            or digest(manifest) != record['binding']['manifest_sha256']):
        raise ValueError('Invalid recovery manifest')
    if (fixture / 'uploads').is_symlink():
        raise ValueError('Invalid uploads directory')
    entry = next(e for e in manifest['files'] if e['path'] == TARGET)
    backup = transaction / 'old.tmp'
    check_file(backup, entry)
    target = fixture / TARGET
    # Never overwrite a file created/changed after the attempt.
    if target.exists() or target.is_symlink():
        check_file(target, entry)
    else:
        with target.open('xb') as handle:
            handle.write(backup.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.utime(target, ns=(record['atime_ns'], record['mtime_ns']))
        os.chmod(target, record['mode'])
    verify_target(fixture, manifest, deleted=False)
    if binding(fixture) != record['binding']:
        raise ValueError('Restored fixture does not match approved state')
    record['status'] = 'restored'
    save(transaction / 'result.json', record)


def apply(fixture, approval_path):
    with locked(fixture):
        transaction = fixture / ('apply-' + approval_path.stem)
        if transaction.exists() or transaction.is_symlink():
            raise FileExistsError('This approval already has an application attempt. '
                                  'Inspect its result.json; use recover to restore the demo. '
                                  'Do not apply the same approval again.')
        approval = authorized(fixture, approval_path)
        # Exclusive directory is also the durable one-use marker for this approval.
        transaction.mkdir()
        manifest = read_record(fixture / 'manifest.json')
        target = fixture / TARGET
        metadata = target.stat()
        record = {'status': 'preparing', 'approval': approval_path.name,
                  'binding': approval['binding'], 'manifest': manifest,
                  'mtime_ns': metadata.st_mtime_ns, 'atime_ns': metadata.st_atime_ns,
                  'mode': stat.S_IMODE(metadata.st_mode)}
        save(transaction / 'result.json', record)
        try:
            shutil.copy2(target, transaction / 'old.tmp')
            with (transaction / 'old.tmp').open('r+b') as handle:
                os.fsync(handle.fileno())
            check_file(transaction / 'old.tmp', next(e for e in manifest['files'] if e['path'] == TARGET))
            if authorized(fixture, approval_path) != approval:
                raise ValueError('Approval changed during preparation')
            record['status'] = 'prepared'
            save(transaction / 'result.json', record)
        except Exception:
            record['status'] = 'aborted_before_delete'
            save(transaction / 'result.json', record)
            raise
        try:
            target.unlink()
            record['status'] = 'verifying'
            save(transaction / 'result.json', record)
            verify_target(fixture, manifest, deleted=True)
            record['status'] = 'applied'
            save(transaction / 'result.json', record)
        except (Exception, KeyboardInterrupt):
            try:
                restore(fixture, transaction, record)
            except Exception:
                record['status'] = 'recovery_required'
                save(transaction / 'result.json', record)
                raise RuntimeError('Verification/recovery incomplete; retain backup and run recover') from None
            raise RuntimeError('Application failed; original demo state restored') from None
        return transaction


def recover(fixture, approval_path):
    with locked(fixture):
        transaction = fixture / ('apply-' + approval_path.stem)
        if transaction.is_symlink():
            raise ValueError('Invalid transaction directory')
        record = read_record(transaction / 'result.json')
        if record['approval'] != approval_path.name or record['binding']['fixture'] != fixture.name:
            raise ValueError('Transaction does not match fixture/approval')
        restore(fixture, transaction, record)
        return transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['apply', 'recover'])
    parser.add_argument('fixture')
    parser.add_argument('approval')
    args = parser.parse_args()
    if not re.fullmatch(r'cleanup-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a fixture name only')
    if not re.fullmatch(r'approval-[0-9a-f]{32}\.json', args.approval):
        parser.error('Supply an approval filename only')
    fixture = ROOT / 'artifacts' / 'fixtures' / args.fixture
    try:
        transaction = (apply if args.operation == 'apply' else recover)(fixture, fixture / args.approval)
        print('PASS:', 'approved demo cleanup applied' if args.operation == 'apply' else 'original demo state restored')
        print('PASS: file hashes, HTTP health, and document download.')
        print('Transaction and retained backup:', transaction)
        print('Backup remains on the same disk; this demo does not claim net disk-space savings.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print('Operation did not complete:', str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
