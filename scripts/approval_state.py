"""State binding for the local, single-user demo; not a tamper-proof audit store."""
import hashlib
import json
import stat
from cleanup_policy import validate_plan

ALLOWED = {'uploads/current.json', 'uploads/customer-demo.txt',
           'uploads/old.tmp', 'uploads/recent.tmp'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def read_record(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1000000:
        raise ValueError('Invalid record file')
    return json.loads(path.read_text(encoding='utf-8'))


def binding(fixture):
    manifest = read_record(fixture / 'manifest.json')
    record = read_record(fixture / 'planning-result.json')
    if record.get('status') != 'policy_passed':
        raise ValueError('Planning did not pass')
    plan = record['plan']
    paths = validate_plan(plan, manifest, fixture)
    entries = manifest['files']
    if len(entries) != 4 or {e['path'] for e in entries} != ALLOWED:
        raise ValueError('Unsupported fixture layout')
    uploads = fixture / 'uploads'
    if uploads.is_symlink() or {p.name for p in uploads.iterdir()} != {p.split('/')[1] for p in ALLOWED}:
        raise ValueError('Fixture layout changed')
    expected = {e['path'] for e in entries if e['protected'] is False
                and e['path'].endswith('.tmp') and manifest['created_at'] - e['modified_at'] > 30*86400}
    if set(paths) != expected:
        raise ValueError('Incomplete cleanup goal')
    state = []
    for entry in sorted(entries, key=lambda e: e['path']):
        path = fixture / entry['path']
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 1048576:
            raise ValueError('Unsupported fixture file')
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        after = path.lstat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('File changed during inspection')
        if (content_hash != entry['sha256'] or before.st_size != entry['size_bytes']
                or int(before.st_mtime) != entry['modified_at']):
            raise ValueError('Fixture changed; run a new simulation')
        state.append([entry['path'], content_hash, before.st_size, before.st_mtime_ns, before.st_mode])
    return {'fixture': fixture.name, 'plan_sha256': digest(plan),
            'manifest_sha256': digest(manifest), 'state_sha256': digest(state)}
