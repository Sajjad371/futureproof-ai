"""Allowlisted dashboard jobs; AI comparison requires an explicit action."""
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from config_fixture import create_fixture as create_config
from restart_fixture import create_fixture as create_restart
from create_demo_fixture import main as create_cleanup

ROOT = Path(__file__).resolve().parents[1]
CREATORS = {'cleanup': create_cleanup, 'configuration': create_config, 'restart': create_restart}


def command(family, fixture, action='check'):
    options = {'configuration': ('config', 'check_config_container.py'),
               'restart': ('restart', 'check_restart_container.py')}
    if family not in options:
        raise ValueError('Use the CLI for cleanup planning and simulation for now')
    prefix, script = options[family]
    if not isinstance(fixture, str) or not re.fullmatch(prefix + r'-[A-Za-z0-9_-]+', fixture):
        raise ValueError('Invalid fixture name')
    if action == 'ai_compare' and family == 'configuration':
        script = 'compare_config.py'
    elif action != 'check':
        raise ValueError('Unsupported action for this family')
    return [sys.executable, str(ROOT / 'scripts' / script), fixture]


class Jobs:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = {'status': 'idle'}

    def status(self):
        with self.lock:
            return dict(self.current)

    def submit(self, body):
        if type(body) is not dict:
            raise ValueError('Expected a job object')
        if body.get('action') in ('apply', 'recover'):
            args = execution_command(body)
        elif set(body) not in ({'family', 'fixture'}, {'family', 'fixture', 'action'}):
            raise ValueError('Expected family, fixture and optional action only')
        else:
            args = command(body['family'], body['fixture'], body.get('action', 'check'))
        with self.lock:
            if self.current['status'] == 'running':
                raise ValueError('A container check is already running')
            self.current = dict(body, id=uuid.uuid4().hex, status='running')
        threading.Thread(target=self.run, args=(args,), daemon=True).start()
        return self.status()

    def run(self, args):
        details = {}
        try:
            # Child runners enforce container limits/timeouts and resource cleanup.
            result = subprocess.run(args, cwd=ROOT, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=3600)
            status = 'passed' if result.returncode == 0 else 'failed'
            if status == 'failed':
                details = {'failure_kind': 'runner_failed', 'exit_code': result.returncode,
                           'message': 'The workflow did not pass. Inspect this fixture\'s saved evidence. Application may have rolled back; check its transaction before retrying.'}
        except subprocess.TimeoutExpired:
            status = 'failed'
            details = {'failure_kind': 'timeout', 'message': 'The workflow exceeded its time limit. Inspect saved evidence and remaining container resources before retrying.'}
        except (OSError, subprocess.SubprocessError):
            status = 'failed'
            details = {'failure_kind': 'launch_failed', 'message': 'The workflow could not run. Check Python, Podman, and the project installation in this Ubuntu session.'}
        with self.lock:
            self.current['status'] = status
            self.current.update(details)


def execution_command(body):
    if set(body) != {'family', 'fixture', 'action', 'approval', 'confirmation'}:
        raise ValueError('Invalid execution request')
    if (body['family'] != 'configuration' or body['action'] not in ('apply', 'recover')
            or not isinstance(body['fixture'], str)
            or not re.fullmatch(r'config-[A-Za-z0-9_-]+', body['fixture'])
            or not isinstance(body['approval'], str)
            or not re.fullmatch(r'config-approval-[0-9a-f]{32}\.json', body['approval'])
            or body['confirmation'] != body['action'].upper() + ' ' + body['fixture']):
        raise ValueError('Invalid scope or confirmation')
    # The executor owns expiry, state binding, locks, backups and replay checks.
    return [sys.executable, str(ROOT / 'scripts/apply_config.py'), body['action'],
            body['fixture'], body['approval']]
