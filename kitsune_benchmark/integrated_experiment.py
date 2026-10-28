"""Bounded Opus local phase: local task units, native UI surface, both MCPs.

Online and revision-control phases are NOT implemented by this module. $20 of
an approved $30 total is reserved here, leaving at least $10 for later phases.
"""
from __future__ import annotations
import argparse
import copy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

from . import gallery, miniwob, personal
from .adapter import write_json
from .personal_session import NativeSession
from .smoke import ROOT, run_pair, source_revision
from .target_view_experiment import PIN

MODEL = 'claude-opus-5-5'
CAP = .5
KITSUNE_TOOLS = ('browser_status','browser_tabs','browser_page_info','browser_page_text',
 'browser_forms','browser_dom','browser_snapshot','browser_screenshot','browser_navigate',
 'browser_click','browser_type','browser_scroll','browser_hover','browser_find',
 'browser_handle_dialog','browser_wait_for','browser_markdown','browser_select_option',
 'browser_check','browser_keypress','browser_submit_form','browser_form_fill',
 'browser_upload_file','browser_back','browser_forward','browser_watch_console','browser_console_logs')
TOOLS = {'kitsune': KITSUNE_TOOLS, 'playwright': tuple(dict.fromkeys(
 personal.UI_TOOLS['playwright'] + ('browser_console_messages','browser_file_upload','browser_handle_dialog','browser_wait_for')))}
FILES = ('integrated_experiment.py','integrated_session.py','personal.py','personal_session.py','gallery.py','miniwob.py',
 'smoke.py','adapter.py','claude_harness.py')


def hashes():
    return {n: hashlib.sha256((ROOT/'kitsune_benchmark'/n).read_bytes()).hexdigest() for n in FILES}


# This experiment predates external-v1 and keeps its single MiniWoB task.
MINIWOB_TASK = {'id':'mw-click-test-2','kind':'miniwob','task_id':'click-test-2','seed':42}


def units():
    rows = [{'track':'miniwob','task':MINIWOB_TASK['task_id'],'layout':None}]
    rows += [{'track':'personal','task':t,'layout':None} for t in personal.runnable_ids()]
    rows += [{'track':'gallery','task':t.id,'layout':layout} for t in gallery.select() for layout in ('crowded','isolated')]
    priorities = [('miniwob','click-test-2',None),('personal','pb-current-01',None),
                  ('gallery','ui-rowmenu','crowded'),('gallery','mm-video','isolated')]
    rows.sort(key=lambda r: priorities.index((r['track'],r['task'],r['layout'])) if (r['track'],r['task'],r['layout']) in priorities else 99)
    return [{**r,'unit': '/'.join(str(x) for x in (r['track'],r['task'],r['layout']) if x is not None)} for r in rows]


def schedule():
    return [{**u,'repeat':0,'target':target,'pilot':i<4,'position':j}
            for i,u in enumerate(units()) for j,target in enumerate(
                ('kitsune','playwright') if i%2==0 else ('playwright','kitsune'))]


class MiniFixture(miniwob.BenchmarkServer):
    def prepare_server(self,target,server,task,pair_dir):
        url = re.search(r'https?://\S+', task.prompt).group(0)
        parsed = urlsplit(url)
        path = pair_dir/(target+'-session.json')
        write_json(path, {'target':target,'upstream':[server.command,*server.args],
            'bootstrap_url':'about:blank','urls':['about:blank'],'active_index':0,
            'evidence_path':str(pair_dir/(target+'-session-evidence.json')),
            'origin':f'{parsed.scheme}://{parsed.netloc}','enabled_tools':list(server.enabled_tools),
            'diagnostics_path':str(pair_dir/(target+'-native-rpc.jsonl')),
            'metadata_path':str(pair_dir/(target+'-native-metadata.json'))})
        return replace(server,command=sys.executable,args=(str(ROOT/'kitsune_benchmark/integrated_session.py'),str(path)))


def fixture_for(item):
    if item['track']=='personal':return personal.PersonalServer(personal.selected_tasks([item['task']])[0],0)
    if item['track']=='gallery':return gallery.GalleryServer(gallery.select([item['task']])[0],0,item['layout'])
    spec=miniwob.config();source=ROOT/spec['source_directory']
    miniwob.verify_source(source,spec['source_revision'])
    return MiniFixture(source,spec,MINIWOB_TASK)


def spec_for(item):
    module={'personal':personal,'gallery':gallery,'miniwob':miniwob}[item['track']]
    spec=copy.deepcopy(module.config())
    spec['claude_code'].update(model=MODEL,effort='medium',max_budget_usd_per_run=CAP)
    spec.update(timeout_sec=240 if item['track']=='gallery' else 180,variant=0,
                layout=item['layout'],integrated_experiment=item)
    return spec


def audit_run(pair,item):
    run=pair['results'].get(item['target'],{})
    if not personal.pair_complete(pair,(item['target'],)):return 'unscorable_or_execution_error'
    md=json.loads((Path(pair['pair_dir'])/(item['target']+'-native-metadata.json')).read_text())
    names={t['name'] for p in md['tools_pages'] for t in p['tools']} & set(md['enabled_tools'])
    if item['target']=='kitsune' and names!=set(KITSUNE_TOOLS):return 'unexpected_tool_surface'
    if names & {'browser_js','browser_workflow','browser_workflows','browser_evaluate','browser_run_code'}:return 'unsafe_tool_surface'
    models=set()
    for line in (Path(run['run_dir'])/'events.jsonl').read_text().splitlines():
        e=json.loads(line)
        if e.get('type')=='assistant' and e.get('message',{}).get('model'):models.add(e['message']['model'])
    if models!={MODEL}:return 'unexpected_actual_model'
    return None


def run(output,project,execute=False,budget=20.,pilot_only=False,prior_cost=0.):
    if not math.isfinite(budget) or not CAP<=budget<=20:raise ValueError('Local allocation must be $0.50–$20; total authorization is $30.')
    if not math.isfinite(prior_cost) or prior_cost<0 or budget+prior_cost>20+1e-9:
        raise ValueError('New local budget plus prior charges must not exceed $20.')
    plan={'phase':'local','model':MODEL,'effort':'medium','harness':'claude-api','kitsune_pin':PIN,
          'budget_usd':budget,'prior_charges_usd':prior_cost,'total_authorized_usd':30,'reserved_other_phases_usd':10,
          'unallocated_usd':max(0.,20-budget-prior_cost),
          'per_run_cap_usd':CAP,'admission_window_sec':10800,'tools':TOOLS,'source_hashes':hashes(),
          'schedule':schedule()[:8] if pilot_only else schedule(),
          'online_status':'not_implemented_not_started','revision_control_status':'not_started',
          'error_contract_source':'https://github.com/junyeong-nero/kitsune/issues/69'}
    if not execute:return plan
    source={'revision':PIN,'dirty':False}
    if source_revision(project)!=source:raise ValueError('Requires clean pinned Kitsune v0.3.0')
    miniwob.verify_source(ROOT/miniwob.config()['source_directory'],miniwob.config()['source_revision'])
    output.mkdir(parents=True,exist_ok=False);write_json(output/'plan.json',plan)
    state={'state':'running','phase':'local','model':MODEL,'runs':[],'estimated_cost_usd':0.,
           'started':datetime.now(timezone.utc).isoformat(),'stopped_reason':None,'pilot_passed':False}
    started=time.monotonic()
    def save():NativeSession.write_private_json(output/'summary.json',state)
    save()
    for item in plan['schedule']:
        if state['estimated_cost_usd']+CAP>budget:state['stopped_reason']='budget_reserve';break
        if time.monotonic()-started+360>plan['admission_window_sec']:state['stopped_reason']='time_reserve';break
        if source_revision(project)!=source or hashes()!=plan['source_hashes']:state['stopped_reason']='source_changed';break
        state['active']=item;save()
        try:
            with fixture_for(item) as fixture:
                pair=run_pair(execute=True,kitsune_project=str(project),executable='claude',
                    experiment_spec=spec_for(item),artifact_scope='integrated-opus-local',
                    task_for_target=fixture.begin,prepare_server=fixture.prepare_server,
                    evaluate=fixture.evaluate,enabled_tools=TOOLS,harness='claude-api',
                    kitsune_preset='full',targets=(item['target'],))
            result=pair['results'].get(item['target'],{})
            cost=result.get('list_price_cost_usd')
            valid_cost=isinstance(cost,(int,float)) and math.isfinite(cost) and cost>=0
            state['estimated_cost_usd']+=cost if valid_cost else CAP
            state['runs'].append({**item,'pair':pair,'kitsune_source_after':source_revision(project)})
            reason=audit_run(pair,item)
            if not valid_cost:reason=reason or 'missing_cost'
            if valid_cost and cost>CAP:reason=reason or 'per_run_budget_overshoot'
            if source_revision(project)!=source or hashes()!=plan['source_hashes']:reason=reason or 'source_changed'
            if reason:state['stopped_reason']=reason;save();break
            if len(state['runs'])==8:state['pilot_passed']=True
            save()
        except Exception as exc:
            state['state']='stopped';state['stopped_reason']='execution_exception'
            state['exception_type']=type(exc).__name__
            # A partly billed failed attempt without a result is conservatively reserved.
            if state['runs'] and state['runs'][-1].get('unit')==item['unit'] and state['runs'][-1].get('target')==item['target']:pass
            else:state['estimated_cost_usd']+=CAP
            save();raise
    state.pop('active',None)
    state['state']='completed' if state['stopped_reason'] is None else 'stopped'
    state['ended']=datetime.now(timezone.utc).isoformat();state['elapsed_sec']=time.monotonic()-started;save()
    return {k:state[k] for k in ('state','estimated_cost_usd','stopped_reason','pilot_passed')}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--pilot-only',action='store_true');p.add_argument('--budget-usd',type=float,default=20)
    p.add_argument('--prior-cost-usd',type=float,default=0)
    p.add_argument('--output',type=Path,default=ROOT/'artifacts/integrated-opus-20261022-local')
    p.add_argument('--kitsune-project',type=Path,default=ROOT/'artifacts/vendor/kitsune-v0.3.0')
    a=p.parse_args();result=run(a.output.resolve(),a.kitsune_project.resolve(),a.execute,a.budget_usd,a.pilot_only,a.prior_cost_usd)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result.get('state','completed')=='completed' else 3

if __name__=='__main__':raise SystemExit(main())
