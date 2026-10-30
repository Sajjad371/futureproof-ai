"""Read-only local evidence dashboard. Start with python3 scripts/dashboard.py."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import stat
import secrets
import base64
import getpass
import re
from datetime import datetime, timezone
from dashboard_jobs import Jobs, CREATORS
from dashboard_approval import Reviews
from evaluation_summary import summaries
from approval_display import state as approval_display_state

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
body{margin:auto;line-height:1.6}h1{font-size:42px;letter-spacing:-1px;margin-bottom:0}h2{font-size:21px}nav{padding:14px 0;color:#83dfcb}a{color:#83dfcb}button,select,input{font:inherit;border:1px solid #51627a;border-radius:8px;background:#263b53;color:#f3f7fc;margin:4px;padding:10px 14px}button:hover:not(:disabled){background:#365777}button:disabled{opacity:.4;cursor:not-allowed}input:focus,button:focus-visible,select:focus{outline:2px solid #83dfcb;outline-offset:3px}section.note{margin:20px 0}pre{background:#121e30;padding:16px;border-radius:8px;font-size:13px}summary{font-weight:600}@media(max-width:640px){body{padding:16px}h1{font-size:32px}button{width:100%;margin:5px 0}input{max-width:85%}}
table{width:100%;border-collapse:collapse;margin-top:24px}td,th{text-align:left;padding:12px;border-bottom:1px solid #344056;overflow-wrap:anywhere}
.note{padding:16px;background:#1e2b40;border-radius:8px}#error{color:#ffb5b5}
details{background:#1e2b40;padding:16px;margin:16px 0;border-radius:8px}summary{cursor:pointer;overflow-wrap:anywhere}select{padding:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{padding:12px;border-top:1px solid #45536a}
:root{color-scheme:light;--ink:#202039;--muted:#626579;--line:#e7e8f0;--accent:#6441d9;--surface:#fff}
*{box-sizing:border-box}body{font:15px/1.65 'Segoe UI',system-ui,sans-serif;background:radial-gradient(ellipse at 85% 0%,#eee8ff 0,transparent 38%),#f7f8fc;color:var(--ink);max-width:1280px;padding:28px 44px 72px;margin:auto}
.brandbar{display:flex;align-items:center;justify-content:space-between;padding:0 0 25px;border-bottom:1px solid var(--line);margin-bottom:38px}.brand{display:flex;align-items:center;gap:12px;font-weight:750;font-size:18px}.brandmark{display:grid;place-items:center;width:38px;height:38px;background:linear-gradient(135deg,#8565ed,#5030bd);border-radius:12px;color:white;box-shadow:0 5px 14px #6943cf26}.workspace-label{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.hero{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:26px}.eyebrow{font-size:11px;font-weight:750;color:var(--accent);letter-spacing:.15em;text-transform:uppercase;margin:0 0 8px}h1{font-size:38px;line-height:1.2;letter-spacing:-1.3px;margin:0 0 12px;font-weight:750}h2{font-size:20px;letter-spacing:-.4px;margin:0 0 10px}p{color:var(--muted);margin:12px 0}.hero p:last-child{margin:0;max-width:640px}a{color:var(--accent)}.export-link{white-space:nowrap;text-decoration:none;font-size:13px;font-weight:650;border:1px solid #dcd8ec;background:#fff;border-radius:10px;padding:12px 18px;box-shadow:0 3px 8px #20203905}
nav{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0;margin:28px 0;color:var(--ink)}nav span{display:flex;align-items:center;gap:10px;padding:14px 16px;background:#ffffffb8;border:1px solid var(--line);border-radius:12px;font-size:13px;font-weight:600}nav b{display:grid;place-items:center;flex-shrink:0;width:27px;height:27px;background:#eee9fc;color:var(--accent);border-radius:8px;font-size:12px}
.note{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:26px;box-shadow:0 5px 22px #24244504}p.note{background:#f0edfb;border-color:#e6e0f5;color:#61567c;font-size:13px;padding:13px 18px;box-shadow:none}section.note{margin:24px 0}.section-kicker{font-size:10px;letter-spacing:.14em;font-weight:750;color:#8a80a6;margin-bottom:6px;text-transform:uppercase}
button,select,input{font:inherit;font-size:13px;border:1px solid #dedfe9;border-radius:9px;background:white;color:var(--ink);margin:5px 5px 5px 0;padding:11px 15px;transition:background .15s,box-shadow .15s}button{font-weight:600;box-shadow:0 2px 3px #26234805}button:hover:not(:disabled){background:#f1edfc;border-color:#c5b6ee}#create,#approve{background:var(--accent);border-color:var(--accent);color:white;box-shadow:0 4px 12px #6441d927}#create:hover,#approve:hover{background:#5232bd}#ai:not(:disabled){background:#f0eafd;border-color:#d7c9f5;color:#5533b5}button:disabled{opacity:1;background:#f5f5f9;color:#9295a5;border-color:#ececf2;cursor:not-allowed;box-shadow:none}input{min-width:230px}input:focus,button:focus-visible,select:focus,a:focus-visible,summary:focus-visible{outline:3px solid #b8a0ef;outline-offset:3px}label{font-size:13px;font-weight:600;margin-right:10px}#created,#job,#approval-status{font-size:13px;color:#57516c}#job:not(:empty){background:#f7f5fd;border:1px solid #ece7f7;border-radius:8px;padding:10px 14px}section.note>p:last-child{font-size:12px;line-height:1.8;max-width:950px}
#evaluations{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}#evaluations p{background:linear-gradient(145deg,#faf9ff,#fff);border:1px solid var(--line);border-top:3px solid #c8b7ee;padding:18px;border-radius:10px;overflow-wrap:anywhere;font-size:13px;margin:4px 0}#summary{font-size:12px;color:#73768b;padding:8px 0}#error{color:#b02b46}#error:empty{display:none}
details{background:#fff;border:1px solid var(--line);padding:0;margin:12px 0;border-radius:12px;box-shadow:0 2px 6px #29244303;overflow:hidden}summary{padding:18px 22px;color:#3b3b53;font-size:13px;font-weight:600;cursor:pointer;overflow-wrap:anywhere}summary::marker{color:#9a88c4}details[open]{border-color:#d4c7ed}details[open]>summary{background:#faf8ff;border-bottom:1px solid var(--line)}article{margin:0 22px;padding:20px 0;border-top:1px solid var(--line)}article:first-of-type{border-top:0}article>p:first-child{font-weight:650;color:#45435d;font-size:13px;overflow-wrap:anywhere}article p{font-size:13px}pre{font:12px/1.8 Consolas,monospace;background:#f7f8fc;color:#525872;border:1px solid #e9eaf2;padding:18px;border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere}#approval-panel{border-color:#c7b6ed;box-shadow:0 8px 30px #6943cf0d}table{width:100%}td,th{border-color:var(--line)}
@media(max-width:800px){body{padding:20px}nav{grid-template-columns:repeat(2,1fr)}.hero{align-items:flex-start;flex-direction:column}#evaluations{grid-template-columns:1fr}.workspace-label{display:none}h1{font-size:31px}}@media(max-width:480px){section.note{padding:18px}nav{gap:8px}nav span{padding:10px;font-size:11px}button{width:100%;margin:6px 0}input{min-width:0;width:100%;max-width:100%}summary{padding:16px}article{margin:0 16px}.brandbar{margin-bottom:26px}}@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
</style><header class="brandbar"><div class="brand"><span class="brandmark" aria-hidden="true">F</span>FutureProof AI</div><span class="workspace-label">Evidence workspace</span></header>
<div class="hero"><div><p class="eyebrow">Test first. Approve with evidence.</p><h1>Your changes. Verified.</h1><p>Review saved evidence across cleanup, configuration, and restart demos.</p></div><a class="export-link" href="/api/export" download="futureproof-evidence.json">Download evidence summary (JSON) &darr;</a></div>
<nav aria-label="Workflow"><span><b>01</b>Create fixture</span><span><b>02</b>Simulate</span><span><b>03</b>Review &amp; approve</span><span><b>04</b>Apply &amp; recover</span></nav>
<p class="note">Saved statuses are historical reports, not a fresh validation or permission to apply changes.</p>
<section class="note"><div class="section-kicker">Run a controlled scenario</div><h2>Demo controls</h2>
<label for="create-family">New fixture</label> <select id="create-family"><option>configuration</option><option>restart</option><option>cleanup</option></select>
<button id="create">Create fixture</button><p id="created" role="status"></p>
<button id="simulate" disabled>Run fixed container check</button>
<button id="ai" disabled>Generate AI candidates and simulate (uses credits)</button><p id="job" role="status"></p>
<p>Configuration tests a fixed 2 MiB candidate; restart tests a fixed demo restart. Fixed checks use no AI credits. The AI button requests configuration candidates from Nebius and simulates permitted plans. Neither button approves or applies changes. Cleanup and restart AI planning remain in the CLI.</p></section>
<section class="note"><h2>Saved evaluations</h2><p>Developer-authored configuration tests. Planning and container results are separate; these scores are not proof of general safety.</p><div id="evaluations"></div></section><button id="refresh">Refresh evidence</button>
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
for(const action of ['apply','recover']){const phrase=action.toUpperCase()+' '+item.fixture;const button=document.createElement('button');button.textContent=action==='apply'?'Apply approved change':'Recover original configuration';button.disabled=action==='apply'?item.approval_state!=='unused_not_revalidated':item.approval_state!=='consumed';button.onclick=async()=>{if(input.value!==phrase){outcome.textContent='Type exactly: '+phrase;return}if(busy){outcome.textContent='Wait for the current job to finish.';return}busy=true;controls();button.disabled=true;try{await post('/api/jobs',{family:'configuration',fixture:item.fixture,action,approval:item.record,confirmation:input.value});input.value='';outcome.textContent='Started '+action+'. Follow progress above; wait until it finishes.';document.getElementById('job').scrollIntoView({behavior:'smooth'});poll()}catch(e){outcome.textContent=e.message;busy=false;controls();button.disabled=false}};section.append(button)}section.append(outcome);article.append(section)}
function render(){const rows=document.getElementById('rows');rows.replaceChildren();const groups=new Map();
for(const item of data.records){if(document.getElementById('family').value && item.family!==document.getElementById('family').value)continue;
const key=item.family+' / '+item.fixture;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(item)}
for(const [key,items] of groups){items.sort((a,b)=>b.modified_ns-a.modified_ns);const box=document.createElement('details');
const heading=document.createElement('summary');heading.textContent=key+' - latest saved record: '+items[0].status;box.append(heading);
for(const item of items){const article=document.createElement('article');const title=document.createElement('p');title.textContent=item.record+' - '+item.status;
article.append(title);if(item.family==='configuration'&&/^config-approval-[0-9a-f]{32}\\.json$/.test(item.record)){executionControls(item,article)}if(item.family==='configuration'&&item.record.startsWith('config-comparison-')&&item.status==='passed'){const button=document.createElement('button');button.textContent='Review recommended candidate';button.onclick=()=>openReview(item);article.append(button)}const note=document.createElement('p');note.textContent=item.stage==='approval'?'Approval: '+({consumed:'consumed - cannot be applied again',expired:'expired - review and approve again',invalid:'invalid record',expiry_unknown:'expiry unknown',unused_not_revalidated:'unused and within its time window - executor will revalidate'}[item.approval_state]||'unknown'):'';article.append(note);
const detail=document.createElement('pre');detail.textContent=JSON.stringify(item.details,null,2);article.append(detail);box.append(article)}rows.append(box)}
document.getElementById('summary').textContent=groups.size+' fixtures shown; '+data.records.length+' records loaded; '+data.skipped+' unreadable or unsupported records skipped. Limit: 500 records.';
if(!groups.size)rows.textContent='No saved evidence for this selection.';}
async function refreshEvaluations(){const r=await fetch('/api/evaluations');if(!r.ok)throw Error('Unable to load evaluations');const d=await r.json();const box=document.getElementById('evaluations');box.replaceChildren();for(const report of d.reports){const p=document.createElement('p');p.textContent=report.kind+': '+report.passed+'/'+report.total+' - '+report.status+' ('+report.record+')';box.append(p)}if(!d.reports.length)box.textContent='No saved evaluation reports.';if(d.skipped){const p=document.createElement('p');p.textContent=d.skipped+' unsupported or inconsistent reports skipped.';box.append(p)}}
async function refresh(){try{await refreshEvaluations();const r=await fetch('/api/runs');if(!r.ok)throw Error('Unable to load evidence');
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
                                    'approval_state': approval_display_state(fixture, path, data) if stage == 'approval' else None,
                                    'details': summary_details(data)})
                    if len(records) >= 500:
                        return {'records': records, 'skipped': skipped}
                except (OSError, ValueError, AttributeError):
                    skipped += 1
    return {'records': records, 'skipped': skipped}


def export_summary(root=ROOT):
    """Export only the same bounded, projected data exposed by the viewer."""
    return {'schema_version': 1, 'exported_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Historical projected summaries; not execution authorization or raw evidence.',
            'runs': inventory(root), 'evaluations': summaries(root)}


class Handler(BaseHTTPRequestHandler):
    def authorize(self):
        origin = getattr(self.server, 'public_origin', None)
        if origin:
            allowed = (origin.removeprefix('https://'),)
        else:
            allowed = ('127.0.0.1:%s' % self.server.server_port, 'localhost:%s' % self.server.server_port)
        if self.headers.get('Host') not in allowed:
            self.send_error(403)
            return False
        if origin:
            expected = self.server.demo_authorization
            supplied = self.headers.get('Authorization', '')
            if not secrets.compare_digest(supplied.encode(), expected.encode()):
                self.send_response(401)
                self.send_header('WWW-Authenticate', 'Basic realm="FutureProof demo", charset="UTF-8"')
                self.send_header('Content-Length', '0')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return False
        return True

    def do_POST(self):
        if not self.authorize():
            return
        host = self.headers.get('Host')
        origin = getattr(self.server, 'public_origin', None)
        allowed_origins = (origin,) if origin else (None, 'http://' + host)
        if (self.headers.get('Origin') not in allowed_origins
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
        if not self.authorize():
            return
        if self.path == '/':
            content, kind = PAGE.replace('__CONTROL_TOKEN__', CONTROL_TOKEN).encode(), 'text/html; charset=utf-8'
        elif self.path == '/api/jobs':
            content, kind = json.dumps(JOBS.status()).encode(), 'application/json'
        elif self.path == '/api/runs':
            content, kind = json.dumps(inventory()).encode(), 'application/json'
        elif self.path == '/api/evaluations':
            content, kind = json.dumps(summaries()).encode(), 'application/json'
        elif self.path == '/api/export':
            content, kind = json.dumps(export_summary(), indent=2).encode(), 'application/json'
        elif self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        if self.path == '/api/export':
            self.send_header('Content-Disposition', 'attachment; filename="futureproof-evidence.json"')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--public-origin', help='Exact HTTPS trycloudflare.com origin; enables mandatory password protection')
    args = parser.parse_args()
    if args.public_origin and not re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com', args.public_origin):
        parser.error('Expected the exact HTTPS Quick Tunnel origin without a trailing slash')
    password = None
    if args.public_origin:
        password = getpass.getpass('Choose a demo-only password (at least 16 characters; input hidden): ')
        if len(password) < 16:
            parser.error('Demo password must have at least 16 characters')
    with HTTPServer(('127.0.0.1', args.port), Handler) as server:
        server.public_origin = args.public_origin
        if password:
            server.demo_authorization = 'Basic ' + base64.b64encode(('demo:' + password).encode()).decode()
        address = args.public_origin or ('http://127.0.0.1:%s' % server.server_port)
        print('Evidence dashboard: %s - Ctrl+C to stop' % address, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
