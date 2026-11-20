import csv
from contextlib import nullcontext, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark as bench
from framework import runner as run
from framework.transcript import summarize


class BenchmarkTests(unittest.TestCase):
    def test_default_plan_and_published_dataset(self):
        with redirect_stdout(io.StringIO()) as output, patch.object(bench, 'attempt', side_effect=AssertionError):
            self.assertEqual(bench.main([]), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual(len(plan), 208)
        self.assertEqual({c['model'] for c in plan[:104]}, {'claude-opus-5-5'})
        self.assertEqual({c['model'] for c in plan[104:]}, {'gpt-6.1-sol'})
        self.assertEqual(sum(c['split']=='dev' for c in plan), 56)
        self.assertEqual([c['arm'] for c in plan[:5]], ['aside','egolite','playwright','kitsune','egolite'])
        key = lambda c: (c['model'], c['task'], c['arm'], c['split'])
        with (bench.ROOT.parent/'docs/results/2026-11-20-webarena-pro-four-way.csv').open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 208)
        self.assertEqual(set(map(key, rows)), set(map(key, plan)))
        self.assertEqual(sum(r['status']=='error' for r in rows), 4)
        self.assertEqual(sum(bool(r['input']) for r in rows), 204)

    def test_single_task_execution_records_eight_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'out'
            with patch.dict('os.environ', BENCH_WAP_CORE='core', BENCH_KITSUNE_CHECKOUT='checkout'), \
                 patch.object(bench, 'binary', side_effect=str), patch.object(bench, 'settings', return_value=nullcontext({})), \
                 patch.object(bench, 'attempt', return_value={'status':'fail','score':0}), redirect_stdout(io.StringIO()):
                self.assertEqual(bench.main(['--task','wap-199','--execute','--out',str(out)]), 0)
                with self.assertRaises(FileExistsError):
                    bench.main(['--task','wap-199','--execute','--out',str(out)])
            rows = [json.loads(line) for line in (out/'results.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 8)
            self.assertEqual({r['browser_mode'] for r in rows if r['arm']=='kitsune'}, {'isolated'})

    def test_prepare_login_agent_grade(self):
        cell = next(c for c in bench.matrix() if c['arm']=='playwright')
        task = bench.TASKS[0]
        events = []
        def core(cmd, task_id, state, *args):
            events.append(cmd)
            if cmd == 'grade':
                self.assertEqual(args, ('Denver',))
                return {'success':False, 'score':0.5, 'nodes':[]}
            return {'urls':{s:'http://localhost' for s in task['sites']}, 'states':{s:{'cookies':[]} for s in task['sites']}, 'credentials':{}}
        def agent(h, exe, model, surfaced, prompt, folder, timeout):
            events.append('agent')
            self.assertIn('--storage-state', surfaced[0]['browser']['args'])
            self.assertIn(task['intent'], prompt)
            result = {'type':'result','is_error':False,'subtype':'success','result':'FINAL ANSWER: Denver'}
            return json.dumps(result), '', 0, False, 1.0
        with tempfile.TemporaryDirectory() as tmp, patch.object(run, 'wap_core', core), patch.object(run,'agent',agent):
            result = run.attempt(cell, task, {'command':'pw','args':[]}, 'claude', Path(tmp)/'log')
        self.assertEqual(events,['prepare','agent','grade'])
        self.assertEqual((result['status'], result['score']), ('fail', 0.5))

    def test_token_accounting(self):
        c = {'type':'result','usage':{'input_tokens':3,'cache_creation_input_tokens':4,'cache_read_input_tokens':5,'output_tokens':6}}
        x = {'type':'turn.completed','usage':{'input_tokens':40,'cached_input_tokens':10,'output_tokens':5}}
        self.assertEqual(summarize('claude',json.dumps(c))['tokens'],dict(input=12,cached_input=5,output=6))
        self.assertEqual(summarize('codex',json.dumps(x))['tokens'],dict(input=40,cached_input=10,output=5))
