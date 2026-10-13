"""Read-only local evidence dashboard. Start with python3 scripts/dashboard.py."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import stat
import secrets
from dashboard_jobs import Jobs, CREATORS
from dashboard_approval import Reviews

JOBS = Jobs()
REVIEWS = Reviews()
CONTROL_TOKEN = secrets.token_urlsafe(32)

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {'cleanup': 'fixtures', 'configuration': 'config-fixtures', 'restart': 'restart-fixtures'}
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FutureProof AI - Evidence</title><style>
body{font:16px system-ui;background:#101827;color:#e8eef8;margin:0;padding:36px;max-width:1100px}
h1{font-size:32px}p{color:#b8c7da}button{padding:10px 18px;cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:24px}td,th{text-align:left;padding:12px;border-bottom:1px solid #344056;overflow-wrap:anywhere}
.note{padding:16px;background:#1e2b40;border-radius:8px}#error{color:#ffb5b5}
details{background:#1e2b40;padding:16px;margin:16px 0;border-radius:8px}summary{cursor:pointer;overflow-wrap:anywhere}select{padding:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{padding:12px;border-top:1px solid #45536a}
</style><h1>FutureProof AI</h1><p>Review saved evidence across cleanup, configuration, and restart demos.</p>
<p class="note">Saved statuses are historical reports, not a fresh validation or permission to apply changes.</p>
<section class="note"><h2>Demo controls</h2>
<label for="create-family">New fixture</label> <select id="create-family"><option>configuration</option><option>restart</option><option>cleanup</option></select>
<button id="create">Create fixture</button><p id="created" role="status"></p>
<button id="simulate" disabled>Run fixed container check</button>
<button id="ai" disabled>Generate AI candidates and simulate (uses credits)</button><p id="job" role="status"></p>
<p>Configuration tests a fixed 2 MiB candidate; restart tests a fixed demo restart. Fixed checks use no AI credits. The AI button requests configuration candidates from Nebius and simulates permitted plans. Neither button approves or applies changes. Cleanup and restart AI planning remain in the CLI.</p></section>
<button id="refresh">Refresh evidence</button>
<label for="family">Scenario</label> <select id="family"><option value="">All scenarios</option><option>cleanup</option><option>configuration</option><option>restart</option></select>
<section id="approval-panel" class="note" hidden><h2>Review configuration approval</h2><pre id="approval-details"></pre><p>Scope: selected synthetic candidate only. Approval expires after 24 hours. No change is applied here.</p><label for="approval-phrase">Type the exact displayed approval phrase</label><input id="approval-phrase" autocomplete="off"><button id="approve">Record approval only</button><p id="approval-status" role="status"></p></section><p id="summary"></p><p id="error" role="alert"></p><main id="rows"></main>
<script>
let data={records:[],skipped:0};
let selected=null;const token='__CONTROL_TOKEN__';
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d}
let busy=false;
function controls(){document.getElementById('create').disabled=busy;document.getElementById('simulate').disabled=busy||!selected||selected.family==='cleanup';document.getElementById('ai').disabled=busy||!selected||selected.family!=='configuration'}
document.getElementById('create').onclick=async()=>{busy=true;controls();try{selected=await post('/api/fixtures',{family:document.getElementById('create-family').value});document.getElementById('created').textContent='Selected fixture: '+selected.fixture;document.getElementById('job').textContent='';}catch(e){document.getElementById('error').textContent=e.message}finally{busy=false;controls()}};
async function launch(action){busy=true;controls();document.getElementById('error').textContent='';try{await post('/api/jobs',{...selected,action});poll()}catch(e){document.getElementById('error').textContent=e.message;busy=false;controls()}}
document.getElementById('simulate').onclick=()=>launch('check');
document.getElementById('ai').onclick=()=>launch('ai_compare');
async function poll(){try{const r=await fetch('/api/jobs');if(!r.ok)throw Error('Unable to read job status');const job=await r.json();busy=job.status==='running';document.getElementById('job').textContent=({ai_compare:'AI candidate comparison',apply:'Configuration application',recover:'Configuration recovery'}[job.action]||'Container check')+' / '+(job.fixture||'')+': '+job.status+(job.message?' - '+job.message:'');controls();if(busy)setTimeout(poll,1500);else refresh()}catch(e){document.getElementById('error').textContent=e.message+'; refresh the page to reconnect.'}}
poll();
let reviewTicket=null;
async function openReview(item){try{const r=await post('/api/config-review',{fixture:item.fixture,comparison:item.record});reviewTicket=r.ticket;document.getElementById('approval-panel').hidden=false;document.getElementById('approval-details').textContent='Candidate '+r.candidate+' / '+r.fixture+'\\nUpload limit: '+r.old_limit_bytes+' -> '+r.new_limit_bytes+' bytes\\nPlan: '+r.plan_sha256+'\\nType: '+r.confirmation;document.getElementById('approval-phrase').value='';document.getElementById('approval-status').textContent='';document.getElementById('approve').disabled=false;document.getElementById('approval-panel').scrollIntoView({behavior:'smooth'})}catch(e){document.getElementById('error').textContent=e.message}}
document.getElementById('approve').onclick=async()=>{const button=document.getElementById('approve');button.disabled=true;try{const r=await post('/api/config-approve',{ticket:reviewTicket,confirmation:document.getElementById('approval-phrase').value});document.getElementById('approval-status').textContent='Approval recorded for '+r.fixture+': '+r.approval+'. No changes applied.';refresh()}catch(e){document.getElementById('approval-status').textContent=e.message}finally{reviewTicket=null}};
function executionControls(item,article){
const section=document.createElement('section');const explanation=document.createElement('p');explanation.textContent='Apply changes this synthetic fixture using the saved approval. Recover restores its backup. Server checks may reject expired, consumed, or changed approvals.';section.append(explanation);
const label=document.createElement('label');label.textContent='Confirmation: ';const input=document.createElement('input');input.autocomplete='off';label.append(input);section.append(label);
const outcome=document.createElement('p');outcome.setAttribute('role','status');
for(const action of ['apply','recover']){const phrase=action.toUpperCase()+' '+item.fixture;const button=document.createElement('button');button.textContent=action==='apply'?'Apply approved change':'Recover original configuration';button.onclick=async()=>{if(input.value!==phrase){outcome.textContent='Type exactly: '+phrase;return}if(busy){outcome.textContent='Wait for the current job to finish.';return}busy=true;controls();button.disabled=true;try{await post('/api/jobs',{family:'configuration',fixture:item.fixture,action,approval:item.record,confirmation:input.value});input.value='';outcome.textContent='Started '+action+'. Follow progress above; wait until it finishes.';document.getElementById('job').scrollIntoView({behavior:'smooth'});poll()}catch(e){outcome.textContent=e.message;busy=false;controls();button.disabled=false}};section.append(button)}section.append(outcome);article.append(section)}
function render(){const rows=document.getElementById('rows');rows.replaceChildren();const groups=new Map();
for(const item of data.records){if(document.getElementById('family').value && item.family!==document.getElementById('family').value)continue;
const key=item.family+' / '+item.fixture;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(item)}
for(const [key,items] of groups){items.sort((a,b)=>b.modified_ns-a.modified_ns);const box=document.createElement('details');
const heading=document.createElement('summary');heading.textContent=key+' - latest saved record: '+items[0].status;box.append(heading);
for(const item of items){const article=document.createElement('article');const title=document.createElement('p');title.textContent=item.record+' - '+item.status;
article.append(title);if(item.family==='configuration'&&/^config-approval-[0-9a-f]{32}\\.json$/.test(item.record)){executionControls(item,article)}if(item.family==='configuration'&&item.record.startsWith('config-comparison-')&&item.status==='passed'){const button=document.createElement('button');button.textContent='Review recommended candidate';button.onclick=()=>openReview(item);article.append(button)}const note=document.createElement('p');note.textContent=item.stage==='approval'?'Historical approval; may be expired or consumed.':'';article.append(note);
const detail=document.createElement('pre');detail.textContent=JSON.stringify(item.details,null,2);article.append(detail);box.append(article)}rows.append(box)}
document.getElementById('summary').textContent=groups.size+' fixtures shown; '+data.records.length+' records loaded; '+data.skipped+' unreadable or unsupported records skipped. Limit: 500 records.';
if(!groups.size)rows.textContent='No saved evidence for this selection.';}
async function refresh(){try{const r=await fetch('/api/runs');if(!r.ok)throw Error('Unable to load evidence');
data=await r.json();render();
document.getElementById('error').textContent='';}catch(e){document.getElementById('error').textContent=e.message}}
document.getElementById('refresh').onclick=refresh;document.getElementById('family').onchange=render;refresh();</script></html>'''


def summary_details(data):
    """Explicit projections only: never return arbitrary record content."""
    details = {}
    if type(data.get('recommended_candidate')) is int:
        details['recommended_candidate'] = data['recommended_candidate']
    if type(data.get('candidates')) is list:
        details['candidates'] = []
        for row in data['candidates'][:3]:
            if type(row) is dict:
                projected = {k: row[k] for k in ('candidate', 'limit_bytes', 'excess_capacity_bytes')
                             if type(row.get(k)) is int}
                if row.get('status') in ('passed', 'rejected', 'duplicate'):
                    projected['status'] = row['status']
                details['candidates'].append(projected)
    for key in ('target_applied', 'actions_executed', 'original_unchanged',
                'fixture_unchanged', 'session_only', 'owned_processes_stopped'):
        if type(data.get(key)) is bool:
            details[key] = data[key]
    for key in ('checks', 'application_checks', 'recovery_checks', 'postflight_checks'):
        value = data.get(key)
        if type(value) is dict:
            details[key] = {k: v for k, v in value.items() if k in (
                'health', 'http_health', 'authentication', 'document_preserved',
                'files_preserved', 'state_unchanged', 'baseline_stale',
                'old_process_exited', 'new_instance', 'current_revision',
                'unauthorized_rejected', 'upload_roundtrip', 'protected_settings')
                and type(v) is bool}
    return details


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
                    # Configuration plans are provenance records, not failed reports.
                    if path.name == 'config-plan.json' and type(data.get('plan')) is dict:
                        status = 'plan_recorded'
                    if not isinstance(status, str) or len(status) > 80:
                        raise ValueError('Missing status')
                    stage = 'approval' if 'approval' in path.name else 'evidence'
                    records.append({'family': family, 'fixture': fixture.name,
                                    'record': path.relative_to(fixture).as_posix(), 'status': status,
                                    'stage': stage, 'modified_ns': info.st_mtime_ns,
                                    'details': summary_details(data)})
                    if len(records) >= 500:
                        return {'records': records, 'skipped': skipped}
                except (OSError, ValueError, AttributeError):
                    skipped += 1
    return {'records': records, 'skipped': skipped}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        host = self.headers.get('Host')
        allowed = ('127.0.0.1:%s' % self.server.server_port, 'localhost:%s' % self.server.server_port)
        if (host not in allowed or self.headers.get('Origin') not in (None, 'http://' + host)
                or self.headers.get('X-Control-Token') != CONTROL_TOKEN):
            self.send_error(403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096 or self.headers.get('Content-Type') != 'application/json':
                raise ValueError('Expected a small JSON request')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/fixtures':
                if type(body) is not dict or set(body) != {'family'} or body['family'] not in CREATORS:
                    raise ValueError('Unknown fixture family')
                result = {'family': body['family'], 'fixture': CREATORS[body['family']]().name}
            elif self.path == '/api/jobs':
                result = JOBS.submit(body)
            elif self.path == '/api/config-review':
                result = REVIEWS.prepare(body)
            elif self.path == '/api/config-approve':
                result = REVIEWS.confirm(body)
            else:
                self.send_error(404)
                return
            code = 200
        except (ValueError, TypeError, OSError, KeyError):
            result, code = {'error': 'Request rejected. Evidence may have changed, the review expired, or confirmation did not match. Review again.'}, 400
        content = json.dumps(result).encode()
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def do_GET(self):
        try:
            self.respond_get()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A browser may cancel a request when navigating or refreshing.
            self.close_connection = True

    def respond_get(self):
        # Reject cross-origin use and DNS rebinding hostnames.
        if self.headers.get('Host') not in ('127.0.0.1:%s' % self.server.server_port,
                                            'localhost:%s' % self.server.server_port):
            self.send_error(403)
            return
        if self.path == '/':
            content, kind = PAGE.replace('__CONTROL_TOKEN__', CONTROL_TOKEN).encode(), 'text/html; charset=utf-8'
        elif self.path == '/api/jobs':
            content, kind = json.dumps(JOBS.status()).encode(), 'application/json'
        elif self.path == '/api/runs':
            content, kind = json.dumps(inventory()).encode(), 'application/json'
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
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
        print('Evidence dashboard: http://127.0.0.1:%s - Ctrl+C to stop' % server.server_port, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
