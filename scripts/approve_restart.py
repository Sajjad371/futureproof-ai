"""Record local approval for a tested synthetic restart; never control processes."""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import re
import stat
import uuid

from restart_fixture import ROOT, SERVICE, CONTENTS, read_json
from check_restart_container import snapshot, load_plan
from restart_http_worker import check_report
from approval_state import digest


def review(fixture, simulation):
    if not re.fullmatch(r'futureproof-restart-[0-9a-f]{12}\.json', simulation):
        raise ValueError('Invalid simulation filename')
    before = snapshot(fixture)
    path = fixture / simulation
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
            or metadata.st_size > 1000000):
        raise ValueError('Invalid simulation record')
    evidence = read_json(path)
    if (evidence.get('status') != 'passed' or evidence.get('fixture') != fixture.name
            or evidence.get('original_unchanged') is not True
            or evidence.get('target_applied') is not False
            or evidence.get('baseline_hashes') != before
            or evidence.get('candidate_source') != 'validated planning record'):
        raise ValueError('A passing plan-linked simulation of this fixture is required')
    check_report(evidence['checks'])
    plan_file = evidence['plan_file']
    plan = load_plan(fixture, plan_file, before)
    if (evidence.get('plan_sha256') != plan['plan_sha256']
            or evidence.get('planning_sha256') != digest(plan)):
        raise ValueError('Plan differs from tested plan; simulate again')
    metadata = {}
    for name in set(CONTENTS) | {'manifest.json'}:
        item = (fixture / name).stat()
        metadata[name] = [item.st_size, item.st_mtime_ns, stat.S_IMODE(item.st_mode)]
    return {'fixture': fixture.name, 'baseline_hashes': before, 'metadata': metadata,
            'plan_file': plan_file, 'plan_sha256': plan['plan_sha256'],
            'planning_sha256': digest(plan), 'simulation': simulation,
            'simulation_sha256': digest(evidence)}


def approve(fixture, simulation, confirm=input):
    binding = review(fixture, simulation)
    print('Fixture:', fixture.name)
    print('Tested action: restart', SERVICE, 'to load revision 2.')
    print('Simulation:', simulation)
    print('Plan fingerprint:', binding['plan_sha256'])
    print('Scope: synthetic fixture only. Approval expires after 24 hours.')
    print('This records approval only. No service will be restarted.')
    phrase = 'APPROVE ' + fixture.name
    if confirm('Type exactly: ' + phrase + '\n> ') != phrase:
        raise ValueError('Confirmation did not match')
    if review(fixture, simulation) != binding:
        raise ValueError('State changed during confirmation; simulate again')
    now = datetime.now(timezone.utc)
    record = {'approval_version': 1, 'task_family': 'service_restart', 'status': 'approved',
              'binding': binding, 'approved_by': getpass.getuser(),
              'approved_at': now.isoformat(), 'expires_at': (now + timedelta(hours=24)).isoformat(),
              'scope': {'fixture': fixture.name, 'service': SERVICE, 'revision': 2},
              'confirmation': phrase, 'target_applied': False}
    output = fixture / ('restart-approval-' + uuid.uuid4().hex + '.json')
    with output.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture')
    parser.add_argument('simulation')
    args = parser.parse_args()
    if not re.fullmatch(r'restart-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a generated fixture name only')
    fixture = ROOT / 'artifacts/restart-fixtures' / args.fixture
    try:
        output = approve(fixture, args.simulation)
        print('PASS: restart approval recorded; no service restarted.')
        print('Approval record:', output)
        return 0
    except (OSError, ValueError, KeyError, TypeError, EOFError, KeyboardInterrupt) as error:
        print('Approval not recorded:', type(error).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
