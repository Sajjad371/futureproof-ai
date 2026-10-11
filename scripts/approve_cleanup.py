"""Record explicit approval of a tested demo plan. Does not apply changes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid
from check_nebius import ROOT
from approval_state import binding, digest, read_record


def review(fixture, evidence_path):
    evidence = read_record(evidence_path)
    current = binding(fixture)
    if (evidence.get('evidence_version') != 2 or evidence.get('binding') != current
            or evidence.get('status') != 'passed' or evidence.get('original_unchanged') is not True
            or evidence.get('target_applied') is not False
            or evidence.get('http_health') is not True or evidence.get('document_download') is not True
            or evidence.get('container') != evidence_path.stem):
        raise ValueError('Missing, failed, or stale simulation; rerun simulation')
    plan = read_record(fixture / 'planning-result.json')['plan']
    if evidence.get('deleted') != [s['path'] for s in plan['steps']]:
        raise ValueError('Simulation does not match plan')
    return current, evidence, plan


def approve(fixture, evidence_path, confirm=input):
    current, evidence, plan = review(fixture, evidence_path)
    evidence_hash = digest(evidence)
    print('Fixture:', fixture.name)
    print('Successful simulation:', evidence_path.name)
    print('Plan fingerprint:', current['plan_sha256'])
    for step in plan['steps']:
        print('Proposed deletion:', step['path'])
    print('This records approval only. No target files will be deleted.')
    phrase = 'APPROVE ' + evidence_path.stem
    if confirm('Type exactly: ' + phrase + '\n> ') != phrase:
        raise ValueError('Approval cancelled; confirmation did not match')
    latest, new_evidence, _ = review(fixture, evidence_path)
    if latest != current or digest(new_evidence) != evidence_hash:
        raise ValueError('State changed during review; rerun simulation')
    record = {'approval_version': 1, 'status': 'approved', 'binding': current,
              'simulation': evidence_path.name, 'simulation_sha256': evidence_hash,
              'approved_at': datetime.now(timezone.utc).isoformat(),
              'confirmation': phrase, 'target_applied': False}
    output = fixture / ('approval-' + uuid.uuid4().hex + '.json')
    with output.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture')
    parser.add_argument('simulation', help='Exact simulation JSON filename printed by the simulator')
    args = parser.parse_args()
    if not re.fullmatch(r'cleanup-[A-Za-z0-9_-]+', args.fixture):
        parser.error('Supply a fixture directory name only')
    if not re.fullmatch(r'futureproof-simulation-[0-9a-f]{12}\.json', args.simulation):
        parser.error('Supply a simulation JSON filename only')
    fixture = ROOT / 'artifacts' / 'fixtures' / args.fixture
    try:
        output = approve(fixture, fixture / args.simulation)
        print('PASS: approval recorded; no target changes applied.')
        print('Approval record:', output)
        return 0
    except (OSError, ValueError, KeyError, TypeError, EOFError, KeyboardInterrupt) as error:
        print('Approval not recorded:', str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
