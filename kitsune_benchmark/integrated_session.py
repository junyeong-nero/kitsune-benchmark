"""MiniWoB relay: verify the initial blank tab without navigating about:blank."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kitsune_benchmark.personal_session import NativeSession


class BlankSession(NativeSession):
    def prepare(self):
        if self.evidence['setup_complete']:
            return
        started=time.monotonic()
        self.diagnostic('setup_started')
        tabs=self.wait_inventory(lambda rows:len(rows)>=1)
        if len(tabs)!=1 or tabs[0]['url']!='about:blank' or not tabs[0]['active']:
            raise ValueError('Expected one active blank tab in a fresh profile')
        self.evidence.update(setup_complete=True,initial_tabs=tabs,snapshots=[tabs])
        self.save()
        self.diagnostic('setup_completed',duration_sec=time.monotonic()-started)


def main():
    session=BlankSession(json.loads(Path(sys.argv[1]).read_text()))
    try:
        session.start()
        for line in sys.stdin:
            if line.strip():session.forward(json.loads(line),lambda message:print(json.dumps(message,ensure_ascii=False),flush=True))
        return 0
    except (OSError,ValueError,KeyError,TypeError):
        session.evidence['error']='blank_session_setup_or_inventory_failed';session.save()
        print('Blank-session setup/inventory failed; inspect private artifacts.',file=sys.stderr)
        session.hold_failed_setup()
        return 2
    finally:
        session.close()

if __name__=='__main__':raise SystemExit(main())
