"""Conservative approval labels for display only; executors remain authoritative."""
from datetime import datetime, timedelta, timezone


def state(fixture, approval_path, record, now=None):
    transaction = fixture / ('apply-' + approval_path.stem)
    if transaction.exists() or transaction.is_symlink():
        return 'consumed'
    if record.get('status') != 'approved' or record.get('target_applied') is not False:
        return 'invalid'
    if 'expires_at' not in record:
        return 'expiry_unknown'
    try:
        begin = datetime.fromisoformat(record['approved_at'])
        end = datetime.fromisoformat(record['expires_at'])
        now = now or datetime.now(timezone.utc)
        if begin.tzinfo is None or end.tzinfo is None or end-begin != timedelta(hours=24) or begin > now:
            return 'invalid'
        return 'expired' if now >= end else 'unused_not_revalidated'
    except (ValueError, TypeError, KeyError):
        return 'invalid'
