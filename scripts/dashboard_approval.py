"""Short-lived, single-use review tickets for local configuration approval."""
import re
import secrets
import time
from config_fixture import ROOT, MIB
from approve_config import review, approve


class Reviews:
    def __init__(self):
        self.pending = {}

    def prepare(self, body):
        if type(body) is not dict or set(body) != {'fixture', 'comparison'}:
            raise ValueError('Invalid review request')
        if (not isinstance(body['fixture'], str) or not isinstance(body['comparison'], str)
                or not re.fullmatch(r'config-[A-Za-z0-9_-]+', body['fixture'])
                or not re.fullmatch(r'config-comparison-[0-9a-f]{32}\.json', body['comparison'])):
            raise ValueError('Invalid review references')
        baseline = ROOT / 'artifacts/config-fixtures' / body['fixture']
        comparison = baseline / body['comparison']
        fixture, binding, value = review(baseline, comparison)
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if v[0] > now}
        if len(self.pending) >= 100:
            raise ValueError('Too many open reviews')
        ticket = secrets.token_urlsafe(32)
        self.pending[ticket] = (now + 600, baseline, comparison, binding)
        return {'ticket': ticket, 'fixture': fixture.name, 'candidate': binding['candidate'],
                'old_limit_bytes': MIB, 'new_limit_bytes': value,
                'confirmation': 'APPROVE ' + fixture.name, 'plan_sha256': binding['plan_sha256']}

    def confirm(self, body):
        if (type(body) is not dict or set(body) != {'ticket', 'confirmation'}
                or not isinstance(body['ticket'], str) or not isinstance(body['confirmation'], str)):
            raise ValueError('Invalid approval request')
        item = self.pending.pop(body['ticket'], None)
        if item is None or item[0] <= time.monotonic():
            raise ValueError('Review expired or used; review again')
        _, baseline, comparison, binding = item
        def confirmation(_):
            # Called between the CLI approver's own before/after state checks.
            if review(baseline, comparison)[1] != binding:
                raise ValueError('Evidence changed since browser review')
            return body['confirmation']
        path = approve(baseline, comparison, confirm=confirmation)
        return {'status': 'approved', 'fixture': path.parent.name,
                'approval': path.name, 'target_applied': False}
