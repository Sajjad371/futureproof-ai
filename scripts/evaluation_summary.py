"""Project saved evaluation reports into bounded, non-sensitive summaries."""
import json
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summaries(root=ROOT):
    directory = root / 'artifacts/evaluations'
    if (root / 'artifacts').is_symlink() or directory.is_symlink() or not directory.is_dir():
        return {'reports': [], 'skipped': 0}
    results, skipped = [], 0
    for path in sorted(directory.glob('*.json'))[:200]:
        if path.name.startswith('ai-suite-'):
            continue
        try:
            meta = path.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_size > 1000000:
                raise ValueError('Unsupported report')
            report = json.loads(path.read_text(encoding='utf-8'))
            kind = ('AI planning' if path.name.startswith('ai-evaluation-') else
                    'Container verification' if path.name.startswith('container-evaluation-') else
                    'Policy regression' if path.name == 'policy-regression.json' else None)
            if kind is None:
                continue
            rows = report.get('cases') if kind == 'Policy regression' else report.get('rows')
            if type(rows) is not list or not rows or any(type(r) is not dict or type(r.get('passed')) is not bool for r in rows):
                raise ValueError('Invalid cases')
            completed = kind == 'Policy regression' or report.get('status') == 'completed'
            passed = sum(r['passed'] for r in rows)
            if completed and (type(report.get('total')) is not int or report['total'] != len(rows)
                              or type(report.get('passed')) is not int or report['passed'] != passed):
                raise ValueError('Inconsistent totals')
            results.append({'record': path.name, 'kind': kind, 'passed': passed,
                            'total': len(rows), 'status': 'completed' if completed else 'incomplete'})
        except (OSError, ValueError, AttributeError):
            skipped += 1
    return {'reports': results, 'skipped': skipped}
