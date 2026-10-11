"""Read-only preflight for the fixed Version 1 cleanup task.

The manifest is trusted application inventory, never model-supplied policy.
Passing preflight is not execution authorization. The eventual isolated executor
must repeat checks under exclusive control of its workspace to avoid races.
"""
import hashlib
from pathlib import Path
import re
import stat


class PolicyDenied(ValueError):
    pass


def validate_plan(plan, manifest, fixture):
    if type(plan) is not dict or set(plan) != {'steps'}:
        raise PolicyDenied('Plan must contain only steps')
    steps = plan['steps']
    if type(steps) is not list or not 1 <= len(steps) <= 10:
        raise PolicyDenied('Expected 1 to 10 steps')
    if manifest.get('fixture_version') != 1 or manifest.get('retention_days') != 30:
        raise PolicyDenied('Unsupported fixture policy')
    inventory = {entry['path']: entry for entry in manifest['files']}
    if len(inventory) != len(manifest['files']):
        raise PolicyDenied('Duplicate inventory paths')
    root = Path(fixture)
    if root.is_symlink() or not root.is_dir():
        raise PolicyDenied('Invalid fixture root')
    approved = []
    for step in steps:
        if type(step) is not dict or set(step) != {'tool', 'path'}:
            raise PolicyDenied('Each step must contain only tool and path')
        if step['tool'] != 'DELETE_FILE':
            raise PolicyDenied('Unsupported tool')
        path = step['path']
        # Deliberately narrow ASCII filenames: no traversal, nested paths,
        # absolute paths, Unicode aliases, Windows separators or shell syntax.
        if type(path) is not str or not re.fullmatch(r'uploads/[A-Za-z0-9_-]+\.[A-Za-z0-9]+', path):
            raise PolicyDenied('Path outside supported filename format')
        if path in approved:
            raise PolicyDenied('Duplicate action')
        entry = inventory.get(path)
        if entry is None:
            raise PolicyDenied('Path not in trusted inventory')
        if entry.get('protected') is not False:
            raise PolicyDenied('Protected file')
        if not path.endswith('.tmp'):
            raise PolicyDenied('Only temporary files are eligible')
        if manifest['created_at'] - entry['modified_at'] <= 30 * 86400:
            raise PolicyDenied('File is not older than 30 days')
        try:
            parent = root / 'uploads'
            if parent.is_symlink() or not parent.is_dir():
                raise PolicyDenied('Invalid uploads directory')
            target = root / path
            metadata = target.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise PolicyDenied('Links and nonregular files are unsupported')
            if metadata.st_size != entry['size_bytes'] or int(metadata.st_mtime) != entry['modified_at']:
                raise PolicyDenied('File metadata changed since inventory')
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
                raise PolicyDenied('File content changed since inventory')
        except OSError:
            raise PolicyDenied('Cannot inspect inventoried file') from None
        approved.append(path)
    return approved
