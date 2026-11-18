"""Local fixture setup and custody sampling. Vendor contexts are not OS sandboxes.

On dedicated workers only. Never enumerate or attach to the operator's existing pages.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.full_native_session import FullNativeSession
from kitsune_benchmark.personal_session import error_detail

VENDOR = {"aside": "repl", "ego": "run_script"}
KITSUNE_TOOLS = {"browser_ask_user", "browser_resume", "browser_run_python", "browser_tabs",
                 "browser_take_screenshot", "browser_tools_call"}


def receipt(reply, field):
    for item in reply.get("content", []):
        for line in item.get("text", "").splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and field in obj:
                return obj[field]
    raise ValueError("Missing fixture receipt: " + field)


class Session(FullNativeSession):
    def tool(self, name, arguments, refusal_codes=()):
        if self.config['target'] == 'kitsune' and name not in KITSUNE_TOOLS:
            name, arguments = 'browser_tools_call', {'name': name, 'arguments': arguments}
        return super().tool(name, arguments, refusal_codes)

    def code(self, script):
        target = self.config['target']
        args = {'code': script}
        if target == 'aside':
            args['title'] = 'Local benchmark fixture'
        return self.tool(VENDOR[target], args)

    def inventory(self):
        target = self.config['target']
        if target == 'aside':
            # tabs belongs to this fresh MCP connection. Do not use listBrowserTabs().
            code = '''console.log(JSON.stringify({bm:await Promise.all(tabs.map(async t=>({
              id:t.targetId,url:await t.url(),title:await t.title(),active:t.targetId===page.targetId}))) }));'''
        elif target == 'ego':
            space = json.dumps(self.config['context'])
            code = f'''const s=await taskSpace({space}); console.log(JSON.stringify({{bm:(await s.tabs()).map(t=>({{
                id:t.targetId,url:t.url,title:t.title,active:!!t.active,openedBy:t.openedBy}}))}}));'''
        else:
            tabs = super().inventory()
        if target in VENDOR:
            tabs = receipt(self.code(code), 'bm')
            if (not isinstance(tabs, list) or not tabs or any(not isinstance(t.get('id'), str)
                    or not isinstance(t.get('url'), str) or type(t.get('active')) is not bool for t in tabs)
                    or len({t['id'] for t in tabs}) != len(tabs)):
                raise ValueError('Invalid vendor inventory')
        if self.evidence['setup_complete']:
            self.evidence['outside_navigation'] += sum(t['url'] != 'about:blank' and
                    not t['url'].startswith(self.config['origin'] + '/') for t in tabs)
        return tabs

    def prepare(self):
        if self.evidence['setup_complete']:
            return
        target = self.config['target']
        if target not in VENDOR:
            super().prepare()  # explicit MCP selection, same usable starting cursor on all four surfaces
            self.evidence['cursor_setup'] = 'browser_tabs select'
            self.save()
            return
        started = time.monotonic()
        self.diagnostic('setup_started')
        urls = json.dumps(self.config['urls'])
        first = json.dumps(self.config['bootstrap_url'])
        idx = self.config['active_index']
        if target == 'aside':
            self.code(f'''if(tabs.length) throw new Error('Expected empty benchmark REPL');
                await openTab({first}); await page.goto({urls}[0]); for(const u of {urls}.slice(1)) await openTab(u);
                for(const t of tabs) await t.setViewportSize({{width:1280,height:720}}); page=tabs[{idx}];''')
        else:
            space = json.dumps(self.config['context'])
            profile = json.dumps(self.config['vendor_profile'])
            created = self.code(f'''const s=await taskSpace({space},{{profileId:{profile}}});
                const ts=await s.tabs(); if(ts.length!==1 || ts[0].openedBy!=='agent' || ts[0].url!=='about:blank')
                    throw new Error('Expected a new, empty agent-owned space');
                console.log(JSON.stringify({{bm:s.spaceId}}));''')
            self.evidence['space_id'] = receipt(created, 'bm')
            self.save()
            self.code(f'''const s=await taskSpace({space}); const p=s.page('p1'); await p.goto({first});
                await p.goto({urls}[0]); for(const u of {urls}.slice(1)) await (await s.newPage()).goto(u);
                const ts=await s.tabs(); for(const t of ts) await t.page.cdp('Emulation.setDeviceMetricsOverride',
                    {{width:1280,height:720,deviceScaleFactor:1,mobile:false}});
                await ts[{idx}].page.cdp('Page.bringToFront');''')
        tabs = self.inventory()
        if (sorted(t['url'] for t in tabs) != sorted(self.config['urls']) or
                [t['url'] for t in tabs if t['active']] != [self.config['urls'][idx]] or
                (target == 'ego' and any(t['openedBy'] != 'agent' for t in tabs))):
            raise ValueError('Incorrect vendor starting inventory or cursor')
        self.evidence.update(setup_complete=True, initial_tabs=tabs, snapshots=[tabs], tab_ids='stable',
                             seeding='harness_created', cursor_setup='REPL page' if target == 'aside' else 'TaskSpace active page')
        self.save()
        self.diagnostic('setup_completed', duration_sec=time.monotonic() - started)

    def request(self, method, params=None, *, notify=None, role='harness'):
        # The transport only returns the current attempt's single designated PNG, never a model-supplied path.
        image = (Path(self.config['screenshot']) if role == 'agent' and method == 'tools/call'
                 and self.config['target'] == 'ego' else None)
        if image is not None:
            image.unlink(missing_ok=True)
        reply = super().request(method, params, notify=notify, role=role)
        if role == 'agent' and method == 'tools/list':
            catalog = reply.get('result', {})
            target = self.config['target']
            tools = catalog.get('tools', [])
            if target in VENDOR:
                tools = [t for t in tools if t.get('name') == VENDOR[target]]
            names = {t['name'] for t in tools}
            if (catalog.get('nextCursor') or not names or len(names) != len(tools)
                    or (target == 'kitsune' and names != KITSUNE_TOOLS)
                    or (target == 'playwright' and not {'browser_tabs','browser_snapshot'} <= names)):
                raise ValueError('Unexpected model-facing catalog')
            self.evidence['catalog_sha256'] = hashlib.sha256(json.dumps(tools,sort_keys=True).encode()).hexdigest()
            self.evidence['catalog_tools'] = sorted(names)
            self.save()
        if image is not None and image.exists() and isinstance(reply.get('result'), dict):
            with os.fdopen(os.open(image, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as f:
                info = os.fstat(f.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 8 <= info.st_size <= 8_000_000:
                    raise ValueError('Invalid screenshot file')
                data = f.read(8_000_001)
            if len(data) != info.st_size or not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid screenshot data')
            reply['result']['content'].append({'type':'image','mimeType':'image/png','data':base64.b64encode(data).decode()})
        return reply

    def forward(self, message, emit):
        args = (message.get('params') or {}).get('arguments') or {}
        if (self.config['target'] == 'aside' and message.get('method') == 'tools/call'
                and any(k not in {'title','code'} for k in args)):
            emit({'jsonrpc':'2.0','id':message['id'],'result':{'isError':True,'content':[
                {'type':'text','text':'Only code and title on the prepared benchmark profile are allowed.'}]}})
            return
        return super().forward(message, emit)

    def close(self):
        try:
            if self.process and self.process.poll() is None:
                if self.config['target'] == 'aside':
                    prefix = json.dumps(self.config['bootstrap_url'].rsplit('/', 1)[0] + '/')
                    self.code(f'for(const t of [...tabs]) if((await t.url()).startsWith({prefix})) await closeTab(t);')
                elif self.config['target'] == 'ego' and self.evidence.get('space_id') is not None:
                    self.code(f"const s=await taskSpace({json.dumps(self.evidence['space_id'])}); await s.finish({{keep:[]}});")
        except (OSError, ValueError, KeyError) as exc:
            self.evidence['teardown_error'] = error_detail(exc)
        finally:
            super().close()
            self.evidence['session_closed'] = True
            self.save()


def main():
    if '--worker' not in sys.argv:
        # Same EOF/cleanup lifecycle as coexistence_session; the client kills its immediate process group.
        return subprocess.run([sys.executable, *sys.argv, '--worker'], start_new_session=True).returncode
    s = Session(json.loads(Path(sys.argv[1]).read_text()))
    try:
        s.start()
        for line in sys.stdin:
            if line.strip():
                s.forward(json.loads(line), lambda reply: print(json.dumps(reply), flush=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        s.evidence.update(error='four_surface_session_error', error_detail=error_detail(exc))
        s.save()
        s.hold_failed_setup()
        return 2
    finally:
        s.close()


if __name__ == '__main__':
    raise SystemExit(main())
