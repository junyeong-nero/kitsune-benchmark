"""Plan, run and report four-surface-v1. Plan/report never launch a model."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kitsune_benchmark import adapter, ego_mcp  # noqa: E402
from kitsune_benchmark.four_surface import config, file_hash, plan, run_cell  # noqa: E402
from kitsune_benchmark.four_surface_report import chart, measured, records, summarize  # noqa: E402
from kitsune_benchmark.smoke import source_revision  # noqa: E402


def read(p):
    return json.loads(p.read_text())


@contextmanager
def exclusive(out):
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def check_worker():
    """Model/browser-free negative control. Never read a real credential or another profile."""
    private = ROOT / 'artifacts'
    private.mkdir(mode=0o700, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.four-surface-control-', dir=private) as directory:
        with tempfile.NamedTemporaryFile(dir=directory) as canary:
            path = json.dumps(canary.name)
            code = ("const fs = await import('node:fs/promises'); let access = 'visible'; "
                    f"try {{ await fs.access({path}); }} catch (e) {{ access = e.code; }} "
                    "console.log(JSON.stringify({privateFileAccess:access}));")
            reply = ego_mcp.run_script(ego_mcp.find_binary(), code)
    observed = []
    for block in reply.get('content', []):
        for line in block.get('text', '').splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and 'privateFileAccess' in record:
                observed.append(record['privateFileAccess'])
    if observed == ['visible']:
        raise ValueError('EgoLite can see the private grader canary on this worker; no model starts')
    if reply.get('isError') or len(observed) != 1 or observed[0] not in {'EACCES', 'EPERM', 'ENOENT'}:
        raise ValueError('Private grader isolation could not be measured; no model starts')


def pins(project, base, release, profiles):
    spec=config()
    for path,sha in [(project,spec['kitsune'])]+([(base,spec['release_base'])] if release else []):
        if source_revision(path) != {'revision':sha,'dirty':False}:
            raise ValueError(f'Expected a clean product checkout at {sha}: {path}')
    rev=source_revision(ROOT)
    if not rev['revision'] or rev['dirty']:
        raise ValueError('Commit the benchmark protocol before executing')
    files={'package-lock':ROOT/'package-lock.json','uv-lock':ROOT/'uv.lock'}
    for h,(model,version) in spec['models'].items():
        exe=adapter.resolve(h,h)
        adapter.harness_preflight(h,exe,adapter.harness_environment(h,exe),model,cli_version=version)
        files[h]=Path(exe)
    env={**os.environ,'PLAYWRIGHT_BROWSERS_PATH':str(ROOT/'artifacts/browsers')}
    firefox=subprocess.check_output(['node','-e',"process.stdout.write(require('playwright').firefox.executablePath())"],
                                    cwd=ROOT,env=env,text=True,timeout=10)
    files.update(firefox=Path(firefox),playwright=ROOT/'node_modules/@playwright/mcp/package.json')
    if not release:
        if not all(profiles.values()):
            raise ValueError('Supply the two designated benchmark-only vendor profile IDs; refusing default personal profiles')
        files.update(aside=Path.home()/'.local/bin/aside', ego=Path(ego_mcp.find_binary()),
                     aside_app=Path('/Applications/Aside.app/Contents/Info.plist'),
                     ego_app=Path('/Applications/ego lite.app/Contents/Info.plist'))
    return {'benchmark_commit':rev['revision'], 'files':{k:file_hash(p) for k,p in files.items()},
            'profiles':profiles if not release else {}, 'models':spec['models']}


def catalog_pins(rows):
    seen = {}
    for row in rows:
        key = row['harness'], row['surface']
        digest = row.get('catalog_sha256')
        if not digest or seen.setdefault(key, digest) != digest:
            raise ValueError('Missing or drifting native catalog; no publication')
    return seen


def run(args, matrix):
    profiles={'aside':args.aside_profile,'ego':args.ego_profile}
    release=args.scope=='release'
    if not args.dedicated_worker:
        raise ValueError('Model-driven native runtimes require a dedicated benchmark worker, not a personal workstation')
    out=args.out.resolve()
    image_drop = None
    if not release:
        check_worker()
        image_drop = args.image_drop.resolve() if args.image_drop else None
        if (image_drop is None or not image_drop.is_dir() or image_drop.is_relative_to(ROOT)
                or image_drop.is_relative_to(out) or out.is_relative_to(image_drop) or ROOT.is_relative_to(image_drop)):
            raise ValueError('Provide a dedicated shared PNG drop separate from the grader and evidence directories')
    provenance=pins(args.kitsune_project,args.release_base,release,profiles)
    reference_catalogs = {}
    if args.scope in {'main','replication'}:
        if args.pilot is None:
            raise ValueError('Supply a measured pilot from these same pins')
        pilot=read(args.pilot/'manifest.json')
        pm=plan('pilot')
        pilot_rows=records(args.pilot,pm)
        if (pilot!={'provenance':provenance,'plan':pm} or len(pilot_rows)!=32 or
                not all(measured(r) and r['safety'] for r in pilot_rows)):
            raise ValueError('Pilot evidence, custody or pins do not qualify; no start')
        reference_catalogs = catalog_pins(pilot_rows)
    with exclusive(out):
        frozen={'provenance':provenance,'plan':matrix}
        manifest=out/'manifest.json'
        if manifest.exists():
            if read(manifest)!=frozen:
                raise ValueError('Refusing to mix plans, runtimes or profiles')
        else:
            adapter.write_json(manifest,frozen)
        old=records(out,matrix)
        if any(not measured(r) or not r['safety'] for r in old):
            raise ValueError('Stopped cohort, no replacement of started cells')
        if old and not release:
            for key, digest in catalog_pins(old).items():
                if reference_catalogs.setdefault(key, digest) != digest:
                    raise ValueError('Catalog differs from pilot')
        done={r['seq'] for r in old}
        for cell in matrix['cells']:
            if cell['seq'] in done:
                continue
            if shutil.disk_usage(out).free<2*1024**3 or shutil.disk_usage(ROOT/'artifacts').free<2*1024**3:
                raise ValueError('Less than 2 GiB free; preserving all artifacts')
            folder=out/f"cell-{cell['seq']:03d}"
            folder.mkdir(mode=0o700)
            adapter.write_json(folder/'started.json',cell)
            project=args.release_base if cell['arm']=='base' else args.kitsune_project
            print(f"{cell['seq']}/{len(matrix['cells'])}: {cell['harness']} · {cell['arm']} · {cell['task']}",flush=True)
            try:
                result=run_cell(cell, project, profiles, image_drop)
            except Exception as exc:
                adapter.write_json(folder/'result.json',{**cell,'status':'runner_error','error':str(exc)[:600]})
                raise
            if not release:
                key = cell['harness'], cell['surface']
                digest = result.get('catalog_sha256')
                if not digest or reference_catalogs.setdefault(key, digest) != digest:
                    result.update(valid_evidence=False, measurement_error='missing_or_changed_catalog')
            adapter.write_json(folder/'result.json',result)
            print(f"  {result['status']} success={result['success']} safety={result['safety']}",flush=True)
            if not measured(result) or result['safety'] is not True:
                raise ValueError('Operational, custody or safety stop; inspect the retained evidence')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('plan','check-worker','run','report','chart'))
    p.add_argument('--scope',choices=('pilot','main','replication','release'),default='pilot')
    p.add_argument('--out',type=Path)
    p.add_argument('--pilot',type=Path)
    p.add_argument('--kitsune-project',type=Path,default=ROOT.parent/'kitsune')
    p.add_argument('--release-base',type=Path,default=ROOT.parent/'kitsune-v0.8.0')
    p.add_argument('--dedicated-worker',action='store_true',help='Confirm isolated native-code worker with no personal data and fixture-only browser access')
    p.add_argument('--aside-profile',help='Dedicated LOCAL Aside benchmark profile ID')
    p.add_argument('--ego-profile',help='Dedicated EgoLite benchmark profile ID')
    p.add_argument('--image-drop',type=Path,help='Existing screenshot-only directory shared with the isolated EgoLite worker')
    args=p.parse_args()
    matrix=plan(args.scope)
    if args.action=='plan':
        print(json.dumps(matrix, indent=2))
        return
    if args.action == 'check-worker':
        check_worker()
        print('Synthetic private file is not visible. This alone does not certify the worker or profiles.')
        return
    if args.out is None:
        p.error('--out is required; use one new private directory per scope')
    if args.action=='run':
        run(args, matrix)
        return
    if read(args.out/'manifest.json')['plan']!=matrix:
        p.error('Scope/plan mismatch')
    report=summarize(matrix,records(args.out,matrix))
    print(chart(report) if args.action=='chart' else json.dumps(report,indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, BlockingIOError) as exc:
        raise SystemExit(str(exc)) from exc
