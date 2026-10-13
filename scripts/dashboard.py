"""Read-only local evidence dashboard. Start with python3 scripts/dashboard.py."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {'cleanup': 'fixtures', 'configuration': 'config-fixtures', 'restart': 'restart-fixtures'}
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FutureProof AI — Evidence</title><style>
body{font:16px system-ui;background:#101827;color:#e8eef8;margin:0;padding:36px;max-width:1100px}
h1{font-size:32px}p{color:#b8c7da}button{padding:10px 18px;cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:24px}td,th{text-align:left;padding:12px;border-bottom:1px solid #344056;overflow-wrap:anywhere}
.note{padding:16px;background:#1e2b40;border-radius:8px}#error{color:#ffb5b5}
</style><h1>FutureProof AI</h1><p>Review saved evidence across cleanup, configuration, and restart demos.</p>
<p class="note">Read-only evidence viewer. Saved statuses are historical reports, not a fresh validation or permission to apply changes.</p>
<button id="refresh">Refresh evidence</button><p id="summary"></p><p id="error" role="alert"></p>
<table><thead><tr><th>Scenario</th><th>Fixture</th><th>Record</th><th>Recorded status</th></tr></thead><tbody id="rows"></tbody></table>
<script>
async function refresh(){try{const r=await fetch('/api/runs');if(!r.ok)throw Error('Unable to load evidence');
const d=await r.json();const rows=document.getElementById('rows');rows.replaceChildren();
for(const item of d.records){const tr=document.createElement('tr');for(const key of ['family','fixture','record','status']){
const td=document.createElement('td');td.textContent=item[key];tr.append(td)}rows.append(tr)}
document.getElementById('summary').textContent=d.records.length+' records; '+d.skipped+' unreadable or unsupported records skipped. Showing up to 500 records.';
document.getElementById('error').textContent='';}catch(e){document.getElementById('error').textContent=e.message}}
document.getElementById('refresh').onclick=refresh;refresh();</script></html>'''


def inventory(root=ROOT):
    records, skipped = [], 0
    artifacts = root / 'artifacts'
    if artifacts.is_symlink():
        return {'records': [], 'skipped': 1}
    for family, directory in FAMILIES.items():
        base = artifacts / directory
        if base.is_symlink() or not base.is_dir():
            continue
        for fixture in sorted(base.iterdir()):
            if fixture.is_symlink() or not fixture.is_dir():
                continue
            paths = list(fixture.glob('*.json'))
            for transaction in fixture.glob('apply-*'):
                if transaction.is_dir() and not transaction.is_symlink():
                    paths.append(transaction / 'result.json')
            for path in sorted(paths):
                if path.name in ('manifest.json', 'app.json', 'startup.json'):
                    continue
                try:
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1000000:
                        raise ValueError('Unsupported record')
                    data = json.loads(path.read_text(encoding='utf-8'))
                    status = data.get('status')
                    if not isinstance(status, str) or len(status) > 80:
                        raise ValueError('Missing status')
                    records.append({'family': family, 'fixture': fixture.name,
                                    'record': str(path.relative_to(fixture)), 'status': status})
                    if len(records) >= 500:
                        return {'records': records, 'skipped': skipped}
                except (OSError, ValueError, AttributeError):
                    skipped += 1
    return {'records': records, 'skipped': skipped}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Reject cross-origin use and DNS rebinding hostnames.
        if self.headers.get('Host') not in ('127.0.0.1:%s' % self.server.server_port,
                                            'localhost:%s' % self.server.server_port):
            self.send_error(403)
            return
        if self.path == '/':
            content, kind = PAGE.encode(), 'text/html; charset=utf-8'
        elif self.path == '/api/runs':
            content, kind = json.dumps(inventory()).encode(), 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with HTTPServer(('127.0.0.1', args.port), Handler) as server:
        print('Evidence dashboard: http://127.0.0.1:%s — Ctrl+C to stop' % server.server_port, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
