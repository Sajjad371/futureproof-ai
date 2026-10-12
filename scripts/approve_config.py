"""Approve a configuration candidate from a verified comparison; no mutation."""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
import re
import stat
import uuid
from config_fixture import ROOT, MIB, FILES, validate_plan
from check_config_container import snapshot, check_report
from approval_state import digest, read_record


def review(baseline, comparison_path, candidate=None):
    report = read_record(comparison_path)
    before = snapshot(baseline)
    if (report.get('status') != 'passed' or report.get('baseline') != baseline.name
            or report.get('baseline_unchanged') is not True or report.get('baseline_hashes') != before
            or report.get('target_applied') is not False):
        raise ValueError('Comparison failed or baseline changed; compare again')
    selected = report.get('recommended_candidate') if candidate is None else candidate
    rows = [r for r in report['candidates'] if r.get('candidate') == selected]
    if len(rows) != 1 or rows[0].get('status') != 'passed':
        raise ValueError('Candidate is not a unique passing result')
    row = rows[0]
    name = row['fixture']
    if not re.fullmatch(r'config-[A-Za-z0-9_-]+', name):
        raise ValueError('Invalid candidate fixture')
    fixture = baseline.parent / name
    if snapshot(fixture) != before:
        raise ValueError('Candidate fixture changed')
    plan_record = read_record(fixture / 'config-plan.json')
    plan = plan_record['plan']
    value = validate_plan(plan, fixture)
    if (value < 2*MIB or row.get('limit_bytes') != value
            or row.get('plan_sha256') != digest(plan)
            or plan_record.get('plan_sha256') != digest(plan)
            or plan_record.get('baseline_hashes') != before):
        raise ValueError('Plan does not match tested candidate')
    simulation = row['simulation']
    if not re.fullmatch(r'futureproof-config-[0-9a-f]{12}\.json', simulation):
        raise ValueError('Invalid simulation reference')
    evidence = read_record(fixture / simulation)
    if (digest(evidence) != row.get('evidence_sha256') or evidence.get('status') != 'passed'
            or evidence.get('fixture') != name or evidence.get('limit_bytes') != value
            or evidence.get('original_unchanged') is not True or evidence.get('target_applied') is not False
            or evidence.get('baseline_hashes') != before):
        raise ValueError('Simulation evidence changed or failed')
    check_report(evidence['checks'], value)
    metadata = {}
    for filename in FILES | {'manifest.json'}:
        item = (fixture / filename).stat()
        metadata[filename] = [item.st_size, item.st_mtime_ns, stat.S_IMODE(item.st_mode)]
    binding = {'baseline': baseline.name, 'fixture': name, 'candidate': selected,
               'baseline_hashes': before, 'plan_sha256': digest(plan),
               'plan_record_sha256': digest(plan_record), 'simulation': simulation,
               'simulation_sha256': digest(evidence), 'comparison': comparison_path.name,
               'comparison_sha256': digest(report), 'metadata': metadata}
    return fixture, binding, value


def approve(baseline, comparison_path, candidate=None, confirm=input):
    fixture, binding, value = review(baseline, comparison_path, candidate)
    print('Candidate:', binding['candidate'], 'Fixture:', fixture.name)
    print('Change: app.json / max_upload_bytes:', MIB, '->', value, 'bytes')
    print('Protected settings and document must remain unchanged.')
    print('Approval scope: this candidate fixture only; expires after 24 hours.')
    print('This command records approval only. It does not apply the change.')
    phrase = 'APPROVE ' + fixture.name
    if confirm('Type exactly: ' + phrase + '\n> ') != phrase:
        raise ValueError('Confirmation did not match; no approval recorded')
    _, latest, _ = review(baseline, comparison_path, candidate)
    if latest != binding:
        raise ValueError('State changed during confirmation; compare again')
    now = datetime.now(timezone.utc)
    record = {'approval_version': 1, 'task_family': 'upload_limit', 'status': 'approved',
              'binding': binding, 'approved_by': getpass.getuser(),
              'approved_at': now.isoformat(), 'expires_at': (now+timedelta(hours=24)).isoformat(),
              'scope': {'fixture': fixture.name, 'path': 'app.json', 'key': 'max_upload_bytes', 'value': value},
              'confirmation': phrase, 'target_applied': False}
    path = fixture / ('config-approval-' + uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as handle:
        json.dump(record, handle, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline')
    parser.add_argument('comparison')
    parser.add_argument('--candidate', type=int, choices=[1, 2, 3])
    args = parser.parse_args()
    if not re.fullmatch(r'config-[A-Za-z0-9_-]+', args.baseline):
        parser.error('Supply a baseline fixture name only')
    if not re.fullmatch(r'config-comparison-[0-9a-f]{32}\.json', args.comparison):
        parser.error('Supply a comparison report filename only')
    baseline = ROOT / 'artifacts/config-fixtures' / args.baseline
    try:
        path = approve(baseline, baseline / args.comparison, args.candidate)
        print('PASS: configuration approval recorded; no changes applied.')
        print('Approval record:', path)
        return 0
    except (OSError, ValueError, KeyError, TypeError, EOFError, KeyboardInterrupt) as error:
        print('Approval not recorded:', str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
