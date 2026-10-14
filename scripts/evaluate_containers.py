"""Replay accepted frozen AI evaluation plans in fresh disposable containers."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid
from approval_state import digest
from config_fixture import ROOT, create_fixture, read_json, validate_plan
from check_config_container import snapshot, check_report
from evaluate_ai import suite, grade


def select_cases(frozen, evaluation):
    if frozen.get('suite') != suite() or frozen.get('suite_sha256') != digest(suite()):
        raise ValueError('Frozen suite differs from evaluator')
    if (evaluation.get('suite_sha256') != frozen['suite_sha256']
            or evaluation.get('model') != suite()['model']
            or evaluation.get('status') != 'completed'
            or evaluation.get('fixture_unchanged') is not True
            or evaluation.get('actions_executed') is not False):
        raise ValueError('Evaluation is incomplete or does not match the suite')
    rows = evaluation['rows']
    expected = {case['id']: case for case in frozen['suite']['cases']}
    if (type(rows) is not list or len(rows) != len(expected)
            or any(type(row) is not dict for row in rows)
            or len({row['id'] for row in rows}) != len(expected)
            or {row['id'] for row in rows} != set(expected)):
        raise ValueError('Missing, duplicated, or unknown evaluation cases')
    selected = []
    for row in rows:
        case = expected[row['id']]
        if row.get('expected_bytes') != case['expected_bytes']:
            raise ValueError('Case expectation mismatch')
        if case['expected_bytes'] is None:
            continue  # Forbidden requests are never sent to a container.
        if (row.get('passed') is not True or row.get('policy_allowed') is not True
                or row.get('response_sha256') != digest(row.get('validated_plan'))):
            raise ValueError('Supported case lacks an accepted, fingerprinted plan')
        selected.append((case, row['validated_plan']))
    return selected


def run(frozen_path, evaluation_path):
    frozen, evaluation = read_json(frozen_path), read_json(evaluation_path)
    selected = select_cases(frozen, evaluation)
    output = ROOT / 'artifacts/evaluations' / ('container-evaluation-' + uuid.uuid4().hex + '.json')
    report = {'status': 'running', 'suite_sha256': frozen['suite_sha256'],
              'planning_report_sha256': digest(evaluation), 'rows': [],
              'scope': 'accepted configuration plans only; no target application', 'api_calls': 0}
    for case, plan in selected:
        row = {'id': case['id'], 'plan_sha256': digest(plan), 'passed': False}
        report['rows'].append(row)
        try:
            fixture = create_fixture()
            row['fixture'] = fixture.name
            before = snapshot(fixture)
            value = validate_plan(plan, fixture)
            if not grade(case, plan, fixture)['passed']:
                raise ValueError('Plan no longer meets exact requested goal')
            print('Testing', case['id'], 'at', value, 'bytes in', fixture.name, flush=True)
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_config_container.py'),
                fixture.name, '--limit-bytes', str(value)], timeout=900)
            reports = list(fixture.glob('futureproof-config-*.json'))
            if result.returncode or len(reports) != 1:
                raise ValueError('Container runner failed or evidence is ambiguous')
            evidence = read_json(reports[0])
            if (evidence.get('status') != 'passed' or evidence.get('fixture') != fixture.name
                    or evidence.get('limit_bytes') != value or evidence.get('baseline_hashes') != before
                    or evidence.get('original_unchanged') is not True
                    or evidence.get('target_applied') is not False or snapshot(fixture) != before):
                raise ValueError('Container evidence mismatch')
            check_report(evidence['checks'], value)
            if evidence['checks'].get('exact_limit_roundtrip') is not True:
                raise ValueError('Exact limit was not tested')
            row.update(passed=True, evidence=reports[0].name, evidence_sha256=digest(evidence),
                       configured_upload_bytes=value, exact_limit_roundtrip=True)
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
            row['error_type'] = type(error).__name__
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(case['id'], ':', 'PASS' if row['passed'] else 'FAIL', flush=True)
    report.update(status='completed', passed=sum(row['passed'] for row in report['rows']), total=len(selected))
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Container evaluation: %s/%s passed.' % (report['passed'], report['total']))
    print('Report:', output)
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('evaluation', type=Path)
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.suite, args.evaluation))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('Evaluation stopped:', type(error).__name__)
        raise SystemExit(1)
