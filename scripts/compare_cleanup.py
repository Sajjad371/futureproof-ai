"""Compare up to three proposed plans on independent copies of one demo baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from check_nebius import ROOT, BASE_URL, MODEL
from plan_cleanup import load_key, parse_plan, PROMPT
from create_demo_fixture import main as create_fixture
from cleanup_policy import validate_plan
from approval_state import ALLOWED, binding, digest, read_record
from approve_cleanup import review


def parse_candidates(content):
    value = parse_plan(content)
    if (type(value) is not dict or set(value) != {'candidates'}
            or type(value['candidates']) is not list or not 1 <= len(value['candidates']) <= 3):
        raise ValueError('Expected candidates containing one to three plans')
    return value['candidates']


def request_candidates(manifest):
    prompt = PROMPT + '''
For this request return {"candidates":[PLAN,...]} instead of a single PLAN.
Return one to three candidates, each using the exact steps schema above.
Do not invent unsafe alternatives for variety. If only one valid plan exists,
return one candidate. Never return shell commands or approval fields.'''
    body = json.dumps({'model': MODEL, 'messages': [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': json.dumps(manifest)}], 'max_tokens': 2048}).encode()
    request = urllib.request.Request(BASE_URL + 'chat/completions', data=body,
        headers={'Authorization': 'Bearer ' + load_key(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=90) as response:
        value = json.loads(response.read(1000000))
    choice = value['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError('Incomplete model response')
    return parse_candidates(choice['message']['content'])


def baseline_state(fixture):
    manifest = read_record(fixture / 'manifest.json')
    if fixture.is_symlink() or (fixture / 'uploads').is_symlink():
        raise ValueError('Invalid baseline directory')
    if len(manifest['files']) != 4 or {e['path'] for e in manifest['files']} != ALLOWED:
        raise ValueError('Unsupported baseline')
    if {'uploads/' + p.name for p in (fixture / 'uploads').iterdir()} != ALLOWED:
        raise ValueError('Unexpected baseline file')
    state = []
    for entry in sorted(manifest['files'], key=lambda e: e['path']):
        path = fixture / entry['path']
        meta = path.lstat()
        if path.is_symlink() or not path.is_file() or meta.st_nlink != 1 or meta.st_size > 1048576:
            raise ValueError('Unsupported baseline file')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry['sha256'] or meta.st_size != entry['size_bytes'] or int(meta.st_mtime) != entry['modified_at']:
            raise ValueError('Baseline drift')
        state.append([entry['path'], actual, meta.st_size, meta.st_mtime_ns, meta.st_mode])
    return digest({'manifest': manifest, 'files': state})


def run_simulation(fixture):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/simulate_cleanup.py'), fixture.name],
                            timeout=900)
    reports = list(fixture.glob('futureproof-simulation-*.json'))
    if result.returncode != 0 or len(reports) != 1:
        raise ValueError('Simulation did not produce one successful report')
    return reports[0]


def compare(baseline, candidates, runner=run_simulation):
    if type(candidates) is not list or not 1 <= len(candidates) <= 3:
        raise ValueError('Expected one to three candidates')
    before = baseline_state(baseline)
    manifest = read_record(baseline / 'manifest.json')
    rows, seen = [], {}
    for index, plan in enumerate(candidates, 1):
        row = {'candidate': index, 'status': 'rejected'}
        rows.append(row)
        try:
            paths = validate_plan(plan, manifest, baseline)
            key = digest(sorted(paths))
            if key in seen:
                row.update(status='duplicate', duplicate_of=seen[key])
                continue
            seen[key] = index
            if baseline_state(baseline) != before:
                raise ValueError('Baseline changed')
            fixture = Path(tempfile.mkdtemp(prefix='cleanup-', dir=baseline.parent))
            (fixture / 'uploads').mkdir()
            shutil.copy2(baseline / 'manifest.json', fixture / 'manifest.json')
            for entry in manifest['files']:
                shutil.copy2(baseline / entry['path'], fixture / entry['path'])
            if baseline_state(fixture) != before:
                raise ValueError('Candidate copy differs from baseline')
            row['fixture'] = fixture.name
            (fixture / 'planning-result.json').write_text(json.dumps({
                'status': 'policy_passed', 'plan': plan, 'actions_executed': False,
                'fixture_unchanged': True, 'model': MODEL}), encoding='utf-8')
            binding(fixture)  # Includes completeness check before any container execution.
            print('Simulating candidate', index, 'in', fixture.name, flush=True)
            evidence_path = runner(fixture)
            if evidence_path.parent != fixture:
                raise ValueError('Unexpected evidence location')
            _, evidence, _ = review(fixture, evidence_path)
            expected_bytes = sum(e['size_bytes'] for e in manifest['files'] if e['path'] in paths)
            expected_preserved = sorted(ALLOWED - set(paths))
            if (type(evidence.get('removed_file_bytes')) is not int
                    or evidence['removed_file_bytes'] != expected_bytes
                    or evidence.get('preserved') is None
                    or sorted(evidence['preserved']) != expected_preserved):
                raise ValueError('Inconsistent comparison evidence')
            row.update(status='passed', simulation=evidence_path.name,
                       removed_file_bytes=expected_bytes, actions=len(paths))
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            row['status'] = 'rejected'
            row['reason'] = type(error).__name__
            # Never persist raw model content, credentials, or subprocess output.
    unchanged = baseline_state(baseline) == before
    passed = sorted((r for r in rows if r['status'] == 'passed'),
                    key=lambda r: (-r['removed_file_bytes'], r['actions'], r['candidate'])) if unchanged else []
    result = {'status': 'passed' if passed else 'no_candidate_passed',
              'baseline': baseline.name, 'baseline_sha256': before, 'baseline_unchanged': unchanged,
              'candidates': rows, 'recommended_candidate': passed[0]['candidate'] if passed else None,
              'ranking_rule': 'Passing checks first; removed file bytes descending; action count ascending; input order for ties.',
              'target_applied': False, 'approval_recorded': False}
    (baseline / 'comparison-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    baseline = create_fixture()
    try:
        print('Requesting up to three plans from Nebius. This uses API credits.', flush=True)
        candidates = request_candidates(read_record(baseline / 'manifest.json'))
        result = compare(baseline, candidates)
        for row in result['candidates']:
            print('Candidate', row['candidate'], ':', row['status'])
        print('Comparison record:', baseline / 'comparison-result.json')
        if result['recommended_candidate'] is None:
            print('No candidate passed. No approval or target application performed.')
            return 1
        chosen = next(r for r in result['candidates'] if r['candidate'] == result['recommended_candidate'])
        print('Recommended candidate:', chosen['candidate'])
        print('Review command: python3 scripts/approve_cleanup.py', chosen['fixture'], chosen['simulation'])
        print('Recommendation is not approval. Target files have not been changed.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as error:
        print('Comparison stopped:', type(error).__name__, '; no fallback plan used.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
