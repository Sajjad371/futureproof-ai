"""Measure repeated automated suite runs; no model calls or container benchmark claims."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    output = ROOT / 'artifacts/release-checks' / ('release-' + uuid.uuid4().hex)
    output.mkdir(parents=True)
    rows = []
    for index in range(args.runs):
        started = time.perf_counter()
        log = output / ('tests-%s.log' % (index + 1))
        with log.open('w', encoding='utf-8') as handle:
            try:
                result = subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                    '-s', 'scripts', '-p', 'test_*.py'], cwd=ROOT, stdout=handle,
                    stderr=subprocess.STDOUT, timeout=600)
                status = 'passed' if result.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                status = 'timeout'
        elapsed = time.perf_counter() - started
        rows.append({'run': index + 1, 'status': status, 'elapsed_seconds': round(elapsed, 3), 'log': log.name})
        print('Run %s: %s in %.2f seconds' % (index + 1, status, elapsed), flush=True)
    report = {'created_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Repeated automated tests on this machine; not AI latency, live container throughput, or independent-machine verification.',
        'python': platform.python_version(), 'platform': platform.system(),
        'runs': rows, 'median_seconds': statistics.median(r['elapsed_seconds'] for r in rows),
        'max_seconds': max(r['elapsed_seconds'] for r in rows),
        'passed': all(r['status'] == 'passed' for r in rows)}
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Report:', output / 'report.json')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
