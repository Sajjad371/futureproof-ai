"""Synthetic stale-process fixture and read-only restart policy.

No system services or processes are started or stopped by this module.
"""
import hashlib
import json
from pathlib import Path
import stat
import tempfile

from config_fixture import read_json

ROOT = Path(__file__).resolve().parents[1]
SERVICE = 'futureproof-demo'
CONFIG = {'revision': 2, 'message': 'Current demo configuration',
          'bind_host': '127.0.0.1', 'auth_required': True,
          'document': 'customer-demo.txt'}
STARTUP = {'revision': 1, 'message': 'Stale demo configuration'}
CONTENTS = {
    'app.json': json.dumps(CONFIG, sort_keys=True).encode('utf-8'),
    'startup.json': json.dumps(STARTUP, sort_keys=True).encode('utf-8'),
    'customer-demo.txt': b'Synthetic protected restart-demo document.\n',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Invalid restart fixture root')
    for name in set(CONTENTS) | {'manifest.json'}:
        metadata = (root / name).lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_size > 1024 * 1024):
            raise ValueError('Unsupported fixture file')
    manifest = read_json(root / 'manifest.json')
    expected = {'fixture_version': 1, 'task_family': 'service_restart',
                'service': SERVICE, 'files': {k: digest(v) for k, v in CONTENTS.items()}}
    if manifest != expected:
        raise ValueError('Unsupported restart manifest')
    for name, content in CONTENTS.items():
        if (root / name).read_bytes() != content:
            raise ValueError('Protected fixture content changed')
    return manifest


def validate_plan(plan, root):
    inspect(root)
    if type(plan) is not dict or set(plan) != {'steps'}:
        raise ValueError('Expected only steps')
    steps = plan['steps']
    if type(steps) is not list or len(steps) != 1:
        raise ValueError('Exactly one restart is required')
    step = steps[0]
    if (type(step) is not dict or set(step) != {'tool', 'service'}
            or step['tool'] != 'RESTART_SERVICE' or step['service'] != SERVICE):
        raise ValueError('Only the synthetic demo service may be restarted')
    return SERVICE


def create_fixture():
    directory = ROOT / 'artifacts' / 'restart-fixtures'
    directory.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='restart-', dir=directory))
    for name, content in CONTENTS.items():
        (root / name).write_bytes(content)
    manifest = {'fixture_version': 1, 'task_family': 'service_restart',
                'service': SERVICE, 'files': {k: digest(v) for k, v in CONTENTS.items()}}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    inspect(root)
    return root


if __name__ == '__main__':
    print('Restart fixture created:', create_fixture())
    print('PASS: configuration, startup seed, and protected document verified.')
    print('Scenario: service starts with revision 1; restart must load revision 2.')
    print('No service started or restarted. Container process checks are the next step.')
