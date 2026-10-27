"""Counter-ordered, model-free comparison of supported shared-Firefox deployments.

Separate from stress-v1: transport, response-volume accounting, topology proofs,
observer metrics and order are part of this comparison protocol.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import psutil

from .adapter import terminate_group, write_json
from .personal_session import tabs_from_result
from .resources import ResourceRoot
from .smoke import ROOT, await_bridge, benchmark_source, bridge_status, copy_extension, private_ports, source_revision
from .stress import Client, SafetyStop, StressCollector, aggregate_levels, failed, percentiles, stress_plan
from .stress_http import HTTPClient
from .stress_resources import StressProcessProbe

CONFIG = ROOT / 'configs/benchmarks/stress-compare-v1.json'
BASE_URL = 'about:blank#stress-shared-base'
PROBE_URL = 'about:blank#stress-shared-probe'
BASELINE = ['about:blank', BASE_URL]


def comparison_plan(profile=None, **overrides):
    if profile not in (None, 'shared-browser-v1'):
        raise ValueError('Unknown comparison profile')
    explicit = {k: v for k, v in overrides.items() if v is not None}
    if profile and explicit:
        raise ValueError('Fixed comparison profile cannot have workload overrides')
    config = json.loads(CONFIG.read_text()) if profile else {'clients': [1, 2], 'repeats': 1, 'duration': 5.0}
    config.update(explicit)
    settings = {k: v for k, v in config.items() if k not in ('protocol', 'profile')}
    validated = stress_plan(**settings)
    schedule = []
    for r in range(validated['repeats']):
        counts = validated['clients'] if r % 2 == 0 else list(reversed(validated['clients']))
        for count in counts:
            position = validated['clients'].index(count)
            targets = ['kitsune', 'playwright'] if (position + r) % 2 == 0 else ['playwright', 'kitsune']
            for target in targets:
                schedule.append({'repeat': r + 1, 'clients': count, 'target': target,
                                 'pair_order': 'kp' if targets[0] == 'kitsune' else 'pk'})
    if len(set(validated['clients'])) != len(validated['clients']):
        raise ValueError('Use repeats rather than duplicate comparison client levels')
    return {**validated, 'protocol': 'stress-compare-v1', 'profile': profile or 'custom',
            'resource_probe': 'single-table-v1', 'schedule': schedule,
            'order': 'alternating targets by level; reversed level and target order next repeat',
            'topology': {'kitsune': 'N stdio MCP processes -> shared bridge -> one Firefox context',
                         'playwright': 'N HTTP MCP sessions -> one MCP server -> one Firefox context'},
            'initial_tabs': BASELINE, 'startup_request_timeout_sec': 60}


def tool(client, name, arguments):
    response = client.request('tools/call', {'name': name, 'arguments': arguments})
    if failed(response):
        raise ValueError('Topology/setup tool call failed: ' + name)
    return response


def inventory(client, target):
    response = client.call()
    if failed(response):
        raise ValueError('Tab inventory failed')
    return tabs_from_result(target, response['result'])


def shared_context_proof(clients, target, stage=None):
    """Mutate from one session, verify in ALL sessions (including an extra at N=1)."""
    if [t['url'] for t in inventory(clients[0], target)] != ['about:blank']:
        raise ValueError('Expected exactly one fresh about:blank starting tab')
    tool(clients[0], 'browser_tabs', {'action': 'new', 'url': BASE_URL})
    tool(clients[0], 'browser_tabs', {'action': 'new', 'url': PROBE_URL})
    # A new tab can be returned before its final URL appears in the browser tab
    # inventory. Readiness polling is setup-only, never a retry of measured load.
    ready_end = time.monotonic() + 10
    polls = 0
    while True:
        observations = [inventory(c, target) for c in clients]
        polls += 1
        if all(sorted(t['url'] for t in tabs) == sorted([*BASELINE, PROBE_URL]) for tabs in observations):
            break
        if time.monotonic() >= ready_end:
            if stage:
                write_json(stage / 'probe-observations.json', observations)
            raise ValueError('Clients do not share the same three-tab browser context')
        time.sleep(.1)
    probe = next(t for t in observations[0] if t['url'] == PROBE_URL)
    tool(clients[0], 'browser_tabs', {'action': 'close', 'index': probe['id']})
    for c in clients:
        tool(c, 'browser_tabs', {'action': 'select', 'index': 1})
    final = [inventory(c, target) for c in clients]
    if any([t['url'] for t in tabs] != BASELINE for tabs in final):
        raise ValueError('Shared-tab cleanup/baseline mismatch')
    return {'verified': True, 'readiness_polls': polls, 'sessions_checked': len(clients), 'during_probe': observations,
            'after_probe': final, 'method': 'one session opens/closes marker; every session observes both changes'}


class Runtime:
    def __init__(self, stack, directory, env, resources, target):
        self.stack, self.directory, self.env = stack, directory, env
        self.resources, self.target = resources, target

    def spawn(self, argv, name, component, stdio=False):
        log = self.stack.enter_context((self.directory / (name + '.log')).open('xb'))
        os.chmod(log.name, 0o600)
        process = subprocess.Popen(argv, cwd=self.directory, env=self.env, start_new_session=True,
            stdin=subprocess.PIPE if stdio else subprocess.DEVNULL,
            stdout=subprocess.PIPE if stdio else log, stderr=log)
        closed = False
        def close():
            nonlocal closed
            if closed:
                return
            terminate_group(process)
            closed = True
            for pipe in (process.stdin, process.stdout):
                if pipe:
                    pipe.close()
        self.stack.callback(close)
        self.resources.register(ResourceRoot(process.pid, component, self.target))
        self.resources.check()
        return process, close


def await_stable_extension(port, token, process, resources):
    """web-ext can briefly connect generation 1 before restarting the extension.

    A socket alone is not readiness: require hello/version and one unchanged,
    connected generation for a full second. This is startup-only, not load retry.
    """
    end, since, generation = time.monotonic() + 40, None, None
    while time.monotonic() < end:
        resources.check()
        if process.poll() is not None:
            raise ValueError('Firefox exited during extension readiness')
        status = bridge_status(port, token)
        now = time.monotonic()
        if status and status.get('extension_connected') and status.get('extension_version'):
            current = status.get('extension_generation')
            if since is None or current != generation:
                since, generation = now, current
            if now - since >= 1:
                return {k: status.get(k) for k in ('extension_version', 'extension_build', 'extension_generation')}
        else:
            since, generation = None, None
        time.sleep(.25)
    raise TimeoutError('No stable extension handshake within 40 seconds')


def await_port(port, process, resources):
    end = time.monotonic() + 40
    while time.monotonic() < end:
        resources.check()
        if process.poll() is not None:
            raise ValueError('Playwright HTTP server exited; inspect stage log')
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2):
                return
        except OSError:
            time.sleep(.1)
    raise TimeoutError('Playwright HTTP listener did not start')


def worker(client, target, index, start, deadline, stage):
    latencies, errors, payload_bytes, text_bytes = [], {}, 0, 0
    path = stage / f'requests-{index}.jsonl'
    with path.open('x') as stream:
        path.chmod(0o600)
        start.wait()
        while time.monotonic() < deadline[0]:
            before = time.monotonic()
            error, response, fatal = None, None, False
            try:
                response = client.call()
                elapsed = time.monotonic() - before  # Excludes benchmark validation/serialization below.
                if failed(response):
                    error = 'tool_error'
                elif [t['url'] for t in tabs_from_result(target, response['result'])] != BASELINE:
                    error = 'tab_inventory_changed'
            except (OSError, EOFError, ValueError, http.client.HTTPException) as exc:
                elapsed = time.monotonic() - before
                error, fatal = type(exc).__name__, True
            size = len(json.dumps(response, ensure_ascii=False, separators=(',', ':')).encode()) if response else 0
            texts = sum(len(i.get('text', '').encode()) for i in (response or {}).get('result', {}).get('content', [])
                        if i.get('type') == 'text')
            latencies.append((elapsed, error))
            payload_bytes += size
            text_bytes += texts
            if error:
                errors[error] = errors.get(error, 0) + 1
            stream.write(json.dumps({'client': index, 'started_mono': before, 'latency_sec': elapsed,
                                     'error': error, 'response_json_bytes': size, 'response_text_bytes': texts}) + '\n')
            if fatal:
                break
    return {'samples': latencies, 'errors': errors, 'json_bytes': payload_bytes, 'text_bytes': text_bytes}


def stage_run(stage, spec, plan, project, firefox, env):
    stage.mkdir(mode=0o700)
    target, count = spec['target'], spec['clients']
    with ExitStack() as stack:
        resources = stack.enter_context(StressCollector(stage, interval_sec=plan['interval'],
            probe=StressProcessProbe(), min_available_mib=plan['min_available_mib'], max_rss_mib=plan['max_rss_mib']))
        resources.check()
        resources.set_phase('setup')
        sockets = stack.enter_context(tempfile.TemporaryDirectory(prefix='sc-', dir='/tmp'))
        stage_env = {**env, 'PWTEST_SOCKETS_DIR': sockets}
        runtime = Runtime(stack, stage, stage_env, resources, target)
        connected = []
        if target == 'kitsune':
            http, ws = private_ports()
            patch = copy_extension(project / 'extension', stage / 'extension', ws)
            write_json(stage / 'extension-patch.json', patch)
            stage_env.update(KITSUNE_HOME=str(stage / 'bridge-home'), KITSUNE_HTTP_PORT=str(http),
                             KITSUNE_WS_PORT=str(ws), KITSUNE_TOKEN=secrets.token_urlsafe(32))
            base = ['uv', 'run', '--locked', '--project', str(project)]
            bridge, _ = runtime.spawn(base + ['python', '-m', 'kitsune.bridge'], 'bridge', 'bridge')
            await_bridge(http, stage_env['KITSUNE_TOKEN'], bridge)
            browser, _ = runtime.spawn([str(ROOT / 'node_modules/.bin/web-ext'), 'run', '--no-config-discovery',
                '--no-input', '--source-dir', str(stage / 'extension'), '--artifacts-dir', str(stage / 'web-ext'),
                '--firefox', str(firefox), '--no-reload', '--start-url', 'about:blank', '--args=-headless'],
                'firefox', 'browser_launcher')
            ready = await_stable_extension(http, stage_env['KITSUNE_TOKEN'], browser, resources)
            write_json(stage / 'extension-ready.json', ready)
            resources.set_phase('connect')
            for i in range(max(2, count)):
                process, close = runtime.spawn(base + ['kitsune'], f'client-{i}', 'mcp', stdio=True)
                client = Client(process, 60)
                client.close = close
                connected.append(client)
        else:
            port, _ = private_ports()
            argv = ['node', str(ROOT / 'node_modules/@playwright/mcp/cli.js'), '--browser', 'firefox',
                    '--executable-path', str(firefox), '--headless', '--shared-browser-context',
                    '--user-data-dir', str(stage / 'profile'), '--port', str(port), '--host', '127.0.0.1']
            write_json(stage / 'launch.json', {'argv': argv, 'isolated': False})
            process, _ = runtime.spawn(argv, 'playwright', 'mcp_server')
            await_port(port, process, resources)
            resources.set_phase('connect')
            for _ in range(max(2, count)):
                client = HTTPClient(port, 60)
                stack.callback(client.close)
                connected.append(client)
        with ThreadPoolExecutor(max_workers=len(connected)) as pool:
            responses = list(pool.map(lambda c: c.initialize(), connected))
        write_json(stage / 'initialize-probes.json', responses)
        if any(failed(r) for r in responses):
            raise ValueError('Client initialization/probe failed; inspect initialize-probes.json')
        resources.check()
        proof = shared_context_proof(connected, target, stage)
        if target == 'playwright':
            hashes = [c.session_hash for c in connected]
            if len(set(hashes)) != len(connected):
                raise ValueError('HTTP clients reused an MCP session')
            proof['session_hashes'] = hashes
        if count == 1:
            extra = connected.pop()
            extra.close()  # Extra proof observer removed before measured phases.
            if getattr(extra, 'close_error', None):
                raise ValueError('Extra proof session did not close cleanly')
        for c in connected:
            c.timeout = plan['timeout']
        with resources._lock:
            resources.sample()
            rows = resources._previous['processes']
            browser_pids = {p['pid'] for p in rows if p['component'] == 'browser'}
            roots = [p['pid'] for p in rows if p['pid'] in browser_pids and p['ppid'] not in browser_pids]
        if len(roots) != 1:
            raise ValueError(f'Expected exactly one owned Firefox tree; found {len(roots)}')
        proof['browser_root_count'] = len(roots)
        proof['measured_clients'] = count
        write_json(stage / 'topology.json', proof)
        write_json(stage / 'clients.json', [c.metadata for c in connected])
        resources.set_phase('warmup')
        def warm(client):
            end = time.monotonic() + plan['warmup']
            while time.monotonic() < end:
                resources.check()
                if failed(client.call()):
                    raise ValueError('Warmup failed')
        with ThreadPoolExecutor(max_workers=count) as pool:
            list(pool.map(warm, connected))
        resources.check()
        resources.set_phase('idle')
        time.sleep(plan['idle'])
        resources.check()
        start, deadline = threading.Event(), [0.0]
        observer = psutil.Process()
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(worker, c, target, i, start, deadline, stage) for i, c in enumerate(connected)]
            try:
                resources.set_phase('load')
                cpu_before = observer.cpu_times()
                rss_before = observer.memory_info().rss
                before = time.monotonic()
                deadline[0] = before + plan['duration']
                start.set()
                while not all(f.done() for f in futures):
                    if resources.stop_reason:
                        deadline[0] = 0
                    time.sleep(.05)
                outcomes = [f.result() for f in futures]
                elapsed = time.monotonic() - before
                cpu_after = observer.cpu_times()
                rss_after = observer.memory_info().rss
            finally:
                deadline[0] = 0
                start.set()
        resources.set_phase('verify')  # Post-load evidence must not inflate load CPU/RSS.
        # Do not reuse a timed-out/failed stream just to collect more evidence.
        if not any(row['errors'] for row in outcomes):
            after = [inventory(c, target) for c in connected]
            if any([t['url'] for t in tabs] != BASELINE for tabs in after):
                raise ValueError('Post-load tab baseline changed')
        resources.set_phase('cleanup')
    samples = [s for row in outcomes for s in row['samples']]
    successful = [s[0] for s in samples if s[1] is None]
    errors = {}
    for row in outcomes:
        for name, n in row['errors'].items():
            errors[name] = errors.get(name, 0) + n
    reasons = ['request_errors'] if errors else []
    for key in ('sampling_errors', 'unexpected_alive_at_stop'):
        if resources.summary[key]:
            reasons.append(key)
    if resources.stop_reason:
        reasons.append(resources.stop_reason)
    if any(not row['samples'] for row in outcomes):
        reasons.append('client_without_requests')
    if any(getattr(c, 'close_error', None) for c in connected):
        reasons.append('http_session_cleanup_error')
    metrics = {}
    for key, bucket in resources.summary['metrics'].items():
        if key.startswith(('phase/load/', 'phase/idle/')):
            metrics[key] = {**bucket, 'mean_cpu_percent_one_core':
                100 * (bucket['observed_cpu_user_sec'] + bucket['observed_cpu_system_sec']) / bucket['duration_sec']
                if bucket['duration_sec'] else None}
    max_gap = max(resources.load_gaps, default=None)
    warnings = ['sampling_cadence_degraded'] if max_gap is None or max_gap > max(1, 4 * plan['interval']) else []
    result = {**spec, 'valid': not reasons, 'invalid_reasons': reasons, 'elapsed_sec': elapsed,
        'attempts': len(samples), 'successes': len(successful), 'errors': errors,
        'successful_requests_per_sec': len(successful) / elapsed,
        'latency_sec_all': percentiles([s[0] for s in samples]), 'latency_sec_success': percentiles(successful),
        'mean_response_json_bytes': sum(r['json_bytes'] for r in outcomes) / len(samples) if samples else None,
        'mean_response_text_bytes': sum(r['text_bytes'] for r in outcomes) / len(samples) if samples else None,
        'per_client_attempts': [len(r['samples']) for r in outcomes], 'resources': metrics,
        'observer': {'cpu_percent_one_core': 100 * (cpu_after.user + cpu_after.system - cpu_before.user - cpu_before.system) / elapsed,
                     'rss_before_bytes': rss_before, 'rss_after_bytes': rss_after, 'scope': 'load generator + resource sampler; excluded from owned totals'},
        'measurement_warnings': warnings, 'load_sample_cadence': {'median_sec': statistics.median(resources.load_gaps) if resources.load_gaps else None,
                                                               'max_sec': max_gap, 'intervals': len(resources.load_gaps)},
        'topology_path': str(stage / 'topology.json'), 'resource_summary_path': str(stage / 'resource-summary.json')}
    write_json(stage / 'summary.json', result)
    return result


def paired_ratios(levels):
    pairs = {}
    for row in levels:
        pairs.setdefault((row['repeat'], row['clients']), {})[row['target']] = row
    output = []
    for (repeat, count), pair in pairs.items():
        if set(pair) != {'kitsune', 'playwright'} or not all(r['valid'] for r in pair.values()):
            continue
        k, p = pair['kitsune'], pair['playwright']
        output.append({'repeat': repeat, 'clients': count, 'pair_order': k['pair_order'],
            'ratios_kitsune_over_playwright': {
                'throughput': k['successful_requests_per_sec'] / p['successful_requests_per_sec'],
                'p95_latency': k['latency_sec_success']['p95'] / p['latency_sec_success']['p95'],
                'mean_rss': k['resources']['phase/load/all']['time_weighted_mean_rss_bytes'] / p['resources']['phase/load/all']['time_weighted_mean_rss_bytes']}})
    return output


def run_comparison(*, execute=False, profile=None, kitsune_project=None, **overrides):
    plan = comparison_plan(profile, **overrides)
    if not execute:
        return {'mode': 'stress_comparison_plan_only', **plan}
    project = Path(kitsune_project).expanduser().resolve() if kitsune_project else ROOT.parent / 'kitsune'
    identity = source_revision(project)
    if os.name != 'posix' or not (project / 'extension/manifest.json').is_file():
        raise ValueError('Requires POSIX and a Kitsune source checkout')
    if profile and (not identity['revision'] or identity['dirty']):
        raise ValueError('Fixed profile requires a clean committed Kitsune checkout')
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT'}}
    env.update(PLAYWRIGHT_BROWSERS_PATH=str(ROOT / 'artifacts/browsers'), PLAYWRIGHT_SKIP_BROWSER_GC='1')
    def output(argv):
        return subprocess.run(argv, env=env, cwd=ROOT, capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    firefox = Path(output(['node', '-e', "console.log(require('playwright').firefox.executablePath())"]))
    if not firefox.is_file() or not (ROOT / 'node_modules/.bin/web-ext').exists():
        raise ValueError('Install pinned npm tools and private Firefox first')
    root = ROOT / 'artifacts/stress-compare' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    root.mkdir(parents=True, mode=0o700)
    files = ['kitsune_benchmark/stress_compare.py', 'kitsune_benchmark/stress_http.py', 'kitsune_benchmark/stress.py',
             'kitsune_benchmark/stress_resources.py', 'kitsune_benchmark/resources.py', 'kitsune_benchmark/personal_session.py',
             'kitsune_benchmark/smoke.py', 'kitsune_benchmark/adapter.py', 'configs/benchmarks/stress-compare-v1.json',
             'uv.lock', 'package-lock.json', 'node_modules/playwright-core/lib/coreBundle.js']
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
    manifest = {**plan, 'kitsune_source': {**identity, 'describe': output(['git', '-C', str(project), 'describe', '--tags', '--always', '--dirty'])},
        'benchmark_source': benchmark_source(), 'file_sha256': hashes, 'browser_binary': str(firefox),
        'versions': {'firefox': output([str(firefox), '--version']), 'node': output(['node', '--version']),
                     'uv': output(['uv', '--version']), 'python': sys.version, 'psutil': psutil.__version__,
                     **{name: json.loads((ROOT / f'node_modules/{name}/package.json').read_text())['version']
                        for name in ('@playwright/mcp', 'playwright', 'web-ext')}},
        'host': {'os': platform.platform(), 'arch': platform.machine(), 'logical_cpus': psutil.cpu_count(),
                 'total_ram_bytes': psutil.virtual_memory().total, 'available_ram_bytes_at_start': psutil.virtual_memory().available,
                 'swap_used_bytes_at_start': psutil.swap_memory().used}}
    write_json(root / 'manifest.json', manifest)
    summary = {**plan, 'run_dir': str(root), 'levels': [], 'status': 'running'}
    try:
        for i, spec in enumerate(plan['schedule']):
            if source_revision(project) != identity:
                raise ValueError('Kitsune checkout changed during comparison')
            print(f"compare repeat {spec['repeat']}, {spec['clients']} clients, {spec['target']} ({spec['pair_order']})", file=sys.stderr, flush=True)
            stage = root / f"{i:02d}-r{spec['repeat']}-n{spec['clients']}-{spec['target']}"
            result = stage_run(stage, spec, plan, project, firefox, env)
            summary['levels'].append(result)
            if not result['valid']:
                summary.update(status='failed', stopped_reason=result['invalid_reasons'])
                break
            time.sleep(plan['cooldown'])
        else:
            summary['status'] = 'completed'
        if source_revision(project) != identity or any(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h for p, h in hashes.items()):
            summary.update(status='failed', stopped_reason='source_or_instrumentation_changed')
    except SafetyStop as exc:
        summary.update(status='stopped', stopped_reason=str(exc), incomplete_stage=str(stage))
    except BaseException as exc:
        summary.update(status='failed', failure_type=type(exc).__name__, incomplete_stage=str(stage))
        raise
    finally:
        summary['completed_levels'] = len(summary['levels'])
        summary['requested_levels'] = len(plan['schedule'])
        summary['aggregates'] = {target: aggregate_levels([r for r in summary['levels'] if r['target'] == target])
                                 for target in ('kitsune', 'playwright')}
        summary['paired_ratios'] = paired_ratios(summary['levels'])
        write_json(root / 'summary.json', summary)
    return summary
