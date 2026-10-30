"""Real fixed-container release checks and end-to-end wall times; no API credits."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid
import config_fixture
import restart_fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, choices=range(1, 4), default=2)
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / 'scripts/check_environment.py')], check=True)
    output = ROOT / 'artifacts/container-smoke' / uuid.uuid4().hex
    output.mkdir(parents=True)
    rows = []
    for iteration in range(args.runs):
        for family in ('cleanup', 'configuration', 'restart'):
            fixture = None
            command = [sys.executable]
            if family == 'configuration':
                fixture = config_fixture.create_fixture()
                command += [str(ROOT / 'scripts/check_config_container.py'), fixture.name]
            elif family == 'restart':
                fixture = restart_fixture.create_fixture()
                command += [str(ROOT / 'scripts/check_restart_container.py'), fixture.name]
            else:
                command += [str(ROOT / 'scripts/check_demo_container.py')]
            started = time.perf_counter()
            log = output / ('%s-%s.log' % (family, iteration + 1))
            with log.open('w', encoding='utf-8') as handle:
                try:
                    result = subprocess.run(command, cwd=ROOT, stdout=handle,
                        stderr=subprocess.STDOUT, timeout=900)
                    status = 'passed' if result.returncode == 0 else 'failed'
                except subprocess.TimeoutExpired:
                    status = 'timeout'
            elapsed = round(time.perf_counter() - started, 3)
            rows.append({'family': family, 'iteration': iteration + 1, 'status': status,
                'elapsed_seconds': elapsed, 'fixture': fixture.name if fixture else None, 'log': log.name})
            print('%s run %s: %s, %.3fs' % (family, iteration + 1, status, elapsed), flush=True)
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'platform': platform.system(),
        'python': platform.python_version(), 'runs': rows,
        'scope': 'Fixed real-container smoke checks. Cleanup checks baseline only; configuration and restart simulate changes. Timings include image build/pull and cleanup; caches may be reused. No AI latency or peak-memory measurement.',
        'passed': all(row['status'] == 'passed' for row in rows)}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Report:', output / 'report.json')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
