"""WebArena-Pro Core bridge. Runs inside the webarena-pro-core virtualenv (Python 3.12+), not the runner's.

  tasks                      -> JSON list of the deterministic light-site subset
  prepare TASK_ID DIR        -> reset the task's sites, log in, write DIR/{prepare.json,<site>.json}
  grade TASK_ID DIR ANSWER   -> run the task's evaluation DAG; print {score, success, nodes}
  control DIR                -> negative control: every task, reset and graded with no action, must fail

Only tasks whose every rubric node starts with an authoritative backend_state or answer_match check are
selected, so grading never depends on which browser tool produced the trajectory. Later strategies (UI
evidence, LLM judge) get no evidence here and cannot award credit; a node a backend check cannot prove fails.
"""
from datetime import date
import json
from pathlib import Path
import sys
import time

from webarena_pro_core.autologin.sync_api import AutoLogin
from webarena_pro_core.eval.dag import DAGEvaluator, EvalContext, parse_eval_dag
from webarena_pro_core.state_reset import reset_site
from webarena_pro_core.task import load_task_configs
from webarena_pro_core.website_metadata import deployed_website_urls

# Sites whose images are under 150 MB compressed (paper Table 16); together they fit a laptop VM.
LIGHT = {'flight-search', 'minerva-lite', 'password-manager', 'pipedrive', 'travelmap', 'thunderbird', 'x-lite',
         'jobportal'}
AUTHORITATIVE = {'backend_state', 'answer_match'}


def _first(node):
    strategies = (node.get('eval_config') or {}).get('strategies')
    return strategies[0]['type'] if strategies else node.get('type')


def subset():
    out = {}
    for split in ('test', 'dev'):
        for task in load_task_configs(split=split):
            ev = task.raw_task.get('eval') or {}
            nodes = ev.get('nodes') or []
            if (set(task.sites) <= LIGHT and nodes and not ev.get('baseline')
                    and all(_first(n) in AUTHORITATIVE for n in nodes)):
                out[task.task_id] = (split, task)
    return out


def _users(task):
    raw = task.raw_task
    users = dict(raw.get('login_usernames') or {})
    for site in task.sites:
        users.setdefault(site, raw.get('login_username'))
    return users


def tasks():
    return [{'id': f'wap-{tid}', 'task_id': tid, 'split': split, 'sites': list(t.sites), 'intent': t.intent,
             'urls': deployed_website_urls(t.sites), 'users': _users(t)} for tid, (split, t) in subset().items()]


def prepare(task_id, folder):
    _, task = subset()[task_id]
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    login = AutoLogin()
    credentials = {}
    for site in task.sites:
        # Recreate from the seed image: some in-place restores (pipedrive's restore-seed-if-empty) keep mutations.
        reset_site(site, backend='container')
    for site, user in _users(task).items():
        login.save_storage_state(site, folder / f'{site}.json', username=user, browser_name='firefox')
        if site == 'flight-search':
            credentials[site] = {'passkey': login.resolve_passkey(site)}
        else:
            name, password = login.resolve_credentials(site, username=user)
            credentials[site] = {'username': name, 'password': password}
            if site == 'jobportal':
                credentials[site]['user_type'] = login.resolve_jobportal_user_type(name)
    start = {'task_start_time_ms': int(time.time() * 1000), 'task_start_date': date.today().isoformat(),
             'urls': deployed_website_urls(task.sites), 'credentials': credentials}
    (folder / 'prepare.json').write_text(json.dumps(start))
    return {'ok': True, 'sites': list(task.sites)}


def grade(task_id, folder, answer):
    _, task = subset()[task_id]
    start = json.loads((Path(folder) / 'prepare.json').read_text())
    ev = task.raw_task['eval']
    context = EvalContext(task_config=task.raw_task, last_action=f'send_msg_to_user({json.dumps(answer)})',
                          chat_messages=[{'role': 'assistant', 'message': answer}],
                          task_start_date=date.fromisoformat(start['task_start_date']),
                          task_start_time_ms=start['task_start_time_ms'])
    score, details = DAGEvaluator(parse_eval_dag(ev)).evaluate(context)
    nodes = [{'id': k, 'passed': v.get('passed'), 'reason': str(v.get('reason', ''))[:400]} for k, v in details.items()]
    return {'score': score, 'success': score >= 1.0, 'nodes': nodes}


def control(folder):
    out = {}
    for task_id in subset():
        prepare(task_id, Path(folder) / task_id)
        result = grade(task_id, Path(folder) / task_id, 'done')
        out[task_id] = {'score': result['score'], 'success': result['success']}
    return {'ok': not any(r['success'] for r in out.values()), 'tasks': out}


if __name__ == '__main__':
    command, *args = sys.argv[1:]
    result = {'tasks': tasks, 'prepare': prepare, 'grade': grade, 'control': control}[command](*args)
    print(json.dumps(result, default=str))
