"""Deterministic configuration/restart regression matrix, not a held-out AI benchmark."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import config_fixture as config
import restart_fixture as restart


def evaluate():
    rows = []
    with tempfile.TemporaryDirectory() as temporary:
        with patch.object(config, 'ROOT', Path(temporary)), patch.object(restart, 'ROOT', Path(temporary)):
            croot, rroot = config.create_fixture(), restart.create_fixture()
        cases = []
        for value in [config.MIB, 2*config.MIB, 4*config.MIB, 8*config.MIB, 0, -1, 9*config.MIB, True, '2097152', None]:
            plan = {'steps': [{'tool': 'SET_CONFIG', 'path': 'app.json', 'key': 'max_upload_bytes', 'value': value}]}
            expected = type(value) is int and config.MIB <= value <= 8*config.MIB
            cases.append(('configuration', repr(value), plan, expected, config.validate_plan, croot))
        for service in ['futureproof-demo', 'sshd', '../futureproof-demo', 'futureproof-demo; reboot', '']:
            plan = {'steps': [{'tool': 'RESTART_SERVICE', 'service': service}]}
            cases.append(('restart', repr(service), plan, service == 'futureproof-demo', restart.validate_plan, rroot))
        for family, name, plan, expected, validator, root in cases:
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            try:
                validator(plan, root)
                allowed = True
            except ValueError:
                allowed = False
            unchanged = before == {p.name: p.read_bytes() for p in root.iterdir()}
            rows.append({'family': family, 'case': name, 'expected_allowed': expected,
                         'allowed': allowed, 'passed': allowed == expected and unchanged})
    return {'evaluation': 'deterministic policy regression, not model quality or held-out testing',
            'cases': rows, 'passed': sum(r['passed'] for r in rows), 'total': len(rows)}


if __name__ == '__main__':
    result = evaluate()
    output = config.ROOT / 'artifacts/evaluations'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'policy-regression.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Policy regression: %s/%s passed. No API calls or container executions.' % (result['passed'], result['total']))
    print('Report:', output / 'policy-regression.json')
    raise SystemExit(0 if result['passed'] == result['total'] else 1)
