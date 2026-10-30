"""Simulate fixed cleanup plans across four fixture variations; no AI calls."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
from create_demo_fixture import main as create_fixture
from cleanup_policy import validate_plan

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = []
    for variant in ('standard', 'retention-edge', 'empty-expired', 'large-expired'):
        fixture = create_fixture(variant)
        manifest = json.loads((fixture / 'manifest.json').read_text())
        plan = {'steps': [{'tool': 'DELETE_FILE', 'path': 'uploads/old.tmp'}]}
        validate_plan(plan, manifest, fixture)
        (fixture / 'planning-result.json').write_text(json.dumps({
            'status': 'policy_passed', 'plan': plan, 'actions_executed': False,
            'source': 'fixed regression plan, not AI output'}), encoding='utf-8')
        started = time.perf_counter()
        try:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/simulate_cleanup.py'), fixture.name],
                                    cwd=ROOT, timeout=900)
            passed = result.returncode == 0
        except subprocess.TimeoutExpired:
            passed = False
        rows.append({'variant': variant, 'fixture': fixture.name, 'passed': passed,
                     'elapsed_seconds': round(time.perf_counter()-started, 3)})
    output = ROOT / 'artifacts/evaluations' / ('cleanup-variations-' + uuid.uuid4().hex + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'scope': 'Fixed plans with real containers; not AI evaluation',
        'cases': rows, 'passed': sum(row['passed'] for row in rows), 'total': len(rows)}, indent=2), encoding='utf-8')
    print('Report:', output)
    return 0 if all(row['passed'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
