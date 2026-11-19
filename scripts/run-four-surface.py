"""Plan, run and report four-surface-v1. Plan/report never launch a model."""
import argparse
import base64
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import io
import json
import os
from pathlib import Path
import plistlib
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kitsune_benchmark import adapter, ego_mcp  # noqa: E402
from kitsune_benchmark.four_surface import VendorWorker, config, file_hash, plan, run_cell, worker_executable  # noqa: E402
from kitsune_benchmark.four_surface_report import chart, measured, records, summarize  # noqa: E402
from kitsune_benchmark.smoke import source_revision  # noqa: E402

VENDOR_APPS = {'aside': Path('/Applications/Aside.app'), 'ego': Path(ego_mcp.APP)}


def read(p):
    return json.loads(p.read_text())


@contextmanager
def exclusive(out):
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def image_directory(value, out=None):
    path = value.resolve() if value and value.is_absolute() else None
    if (path is None or not path.is_dir() or path.is_relative_to(ROOT) or ROOT.is_relative_to(path)
            or out is not None and (path.is_relative_to(out) or out.is_relative_to(path))):
        raise ValueError('Provide a dedicated absolute PNG drop separate from the grader and evidence directories')
    return path


def check_install():
    """Static check of the installed GUI bundles; never repair, launch or re-sign either app."""
    versions = config()['vendor_gui_versions']
    for target, path in VENDOR_APPS.items():
        name, version = ('Aside' if target == 'aside' else 'EgoLite'), versions[target]
        try:
            r = subprocess.run(['/usr/bin/codesign', '--verify', '--strict', path], capture_output=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f'Cannot verify the {name} GUI bundle; no vendor or model start') from exc
        if r.returncode:
            detail = ' (Finder/resource-fork metadata rejected)' if b'detritus not allowed' in r.stderr else ''
            raise ValueError(f'{name} GUI bundle failed strict signature verification{detail}; no vendor or model start')
        try:
            with (path/'Contents/Info.plist').open('rb') as f:
                actual = plistlib.load(f)['CFBundleShortVersionString']
        except (OSError, KeyError, plistlib.InvalidFileException) as exc:
            raise ValueError(f'Cannot verify the {name} GUI version; no vendor or model start') from exc
        if actual != version:
            raise ValueError(f'{name} GUI version {actual} does not match {version}; no vendor or model start')


def check_worker(binary, service, image_drop):
    """No model or page actions. Require a denied synthetic marker AND an actual PNG round trip."""
    service = ego_mcp.validate_service(service)
    check_install()
    png = io.BytesIO()
    Image.frombytes('RGB', (4, 1), secrets.token_bytes(12)).save(png, format='PNG')
    payload = png.getvalue()
    dest = image_drop / ('four-control-' + secrets.token_hex(16) + '.png')
    if os.path.lexists(dest):
        raise ValueError('PNG control path collision; no start')
    private = ROOT / 'artifacts'
    private.mkdir(mode=0o700, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(prefix='.four-surface-control-', dir=private) as canary:
            code = ("const fs = await import('node:fs/promises'); let access = 'visible'; "
                    f"try {{ await fs.access({json.dumps(canary.name)}); }} catch (e) {{ access = e.code; }} "
                    "if (['EACCES','EPERM','ENOENT'].includes(access)) "
                    f"await fs.writeFile({json.dumps(str(dest))}, Buffer.from('{base64.b64encode(payload).decode()}', "
                    "'base64'), {flag:'wx', mode:0o640}); console.log(JSON.stringify({privateFileAccess:access}));")
            reply = ego_mcp.run_script(binary, code, server_name=service)
        observed = []
        for block in reply.get('content', []):
            for line in block.get('text', '').splitlines():
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and 'privateFileAccess' in record:
                    observed.append(record['privateFileAccess'])
        if 'visible' in observed:
            raise ValueError('EgoLite can see the private grader canary on this worker; no model starts')
        if reply.get('isError') or len(observed) != 1 or observed[0] not in ('EACCES', 'EPERM', 'ENOENT'):
            raise ValueError('Named EgoLite runtime did not prove grader isolation; no model starts')
        try:
            with os.fdopen(os.open(dest, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
                info = os.fstat(f.fileno())
                if not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == len(payload)
                        and f.read(len(payload) + 1) == payload):
                    raise ValueError('PNG handoff mismatch; no model starts')
        except OSError as exc:
            raise ValueError('PNG handoff unavailable; no model starts') from exc
    finally:
        try:
            dest.unlink(missing_ok=True)
        except OSError as exc:
            raise ValueError('Could not clean up the disposable PNG control; no model starts') from exc


def pins(project, base, release, worker):
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
        files.update(aside=Path(worker.aside_cli), ego=Path(worker.ego_cli))
        files.update({key+'_app':path/'Contents/Info.plist' for key,path in VENDOR_APPS.items()})
    return {'benchmark_commit':rev['revision'], 'files':{k:file_hash(p) for k,p in files.items()},
            **({'worker':asdict(worker), 'vendor_gui_versions':spec['vendor_gui_versions']} if not release else {'profiles':{}}), 'models':spec['models']}


def catalog_pins(rows):
    seen = {}
    for row in rows:
        key = row['harness'], row['surface']
        digest = row.get('catalog_sha256')
        if not digest or seen.setdefault(key, digest) != digest:
            raise ValueError('Missing or drifting native catalog; no publication')
    return seen


def run(args, matrix):
    release=args.scope=='release'
    if not args.dedicated_worker:
        raise ValueError('Model-driven native runtimes require a dedicated benchmark worker, not a personal workstation')
    out=args.out.resolve()
    worker = image_drop = None
    if not release:
        worker = VendorWorker.from_args(args)
        image_drop = image_directory(args.image_drop, out)
        check_worker(worker.ego_cli, worker.ego_service, image_drop)
    provenance=pins(args.kitsune_project,args.release_base,release,worker)
    if not release:
        provenance = {**provenance, 'image_drop':str(image_drop)}
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
                result=run_cell(cell, project, worker, image_drop)
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
    p.add_argument('action',choices=('plan','check-install','check-worker','run','report','chart'))
    p.add_argument('--scope',choices=('pilot','main','replication','release'),default='pilot')
    p.add_argument('--out',type=Path)
    p.add_argument('--pilot',type=Path)
    p.add_argument('--kitsune-project',type=Path,default=ROOT.parent/'kitsune')
    p.add_argument('--release-base',type=Path,default=ROOT.parent/'kitsune-v0.8.0')
    p.add_argument('--dedicated-worker',action='store_true',help='Confirm isolated native-code worker with no personal data and fixture-only browser access')
    p.add_argument('--aside-cli',type=Path,help='Absolute path to the verified LOCAL Aside CLI or restricted launcher')
    p.add_argument('--ego-cli',type=Path,help='Absolute path to the verified EgoLite CLI or restricted launcher')
    p.add_argument('--ego-server-name',help='Verified named EgoLite test service (never the default)')
    p.add_argument('--aside-profile',help='Dedicated LOCAL Aside benchmark profile ID')
    p.add_argument('--ego-profile',help='Dedicated EgoLite benchmark profile ID')
    p.add_argument('--image-drop',type=Path,help='Existing screenshot-only directory shared with the isolated EgoLite worker')
    args=p.parse_args()
    matrix=plan(args.scope)
    if args.action=='plan':
        print(json.dumps(matrix, indent=2))
        return
    if args.action == 'check-install':
        check_install()
        print('Both installed GUI bundles match the version pins and pass codesign --verify --strict. This does not certify a worker.')
        return
    if args.action == 'check-worker':
        service = ego_mcp.validate_service(args.ego_server_name)
        drop = image_directory(args.image_drop, args.out.resolve() if args.out else None)
        check_worker(worker_executable(args.ego_cli, 'EgoLite'), service, drop)
        print('Named EgoLite runtime denied the grader marker and wrote the control PNG. Browser routing, network and Aside remain separate gates.')
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
