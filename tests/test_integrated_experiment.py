import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kitsune_benchmark import integrated_experiment as experiment


class IntegratedTests(unittest.TestCase):
    def test_schedule_is_complete_and_paired(self):
        rows=experiment.schedule()
        self.assertEqual(len(rows),158)
        self.assertEqual(len({r['unit'] for r in rows}),79)
        for i in range(0,len(rows),2):
            self.assertEqual(rows[i]['unit'],rows[i+1]['unit'])
            self.assertEqual({rows[i]['target'],rows[i+1]['target']},{'kitsune','playwright'})
        self.assertEqual(sum(r['pilot'] for r in rows),8)

    def test_tool_scope_matches_inventory(self):
        self.assertEqual(len(set(experiment.KITSUNE_TOOLS)),27)
        self.assertFalse(set(experiment.KITSUNE_TOOLS)&{'browser_js','browser_workflows','browser_workflow'})
        self.assertNotIn('browser_run_code',experiment.TOOLS['playwright'])

    def test_dry_run_creates_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'not-created'
            with patch.object(experiment,'run_pair',side_effect=AssertionError('inference')):
                plan=experiment.run(output,Path('/unused'))
            self.assertFalse(output.exists())
            self.assertEqual(plan['budget_usd'],20)
            self.assertEqual(plan['reserved_other_phases_usd'],10)

    def test_budget_bounds(self):
        for value in (float('nan'),float('inf'),0,21,30):
            with self.assertRaises(ValueError):experiment.run(Path('/unused'),Path('/unused'),budget=value)

    def test_prior_spend_is_reserved(self):
        with self.assertRaises(ValueError):
            experiment.run(Path('/unused'),Path('/unused'),budget=20,prior_cost=.01058)
        plan=experiment.run(Path('/unused'),Path('/unused'),budget=19.98942,prior_cost=.01058)
        self.assertAlmostEqual(plan['budget_usd']+plan['prior_charges_usd']+plan['reserved_other_phases_usd'],30)

    def test_blank_setup_never_navigates(self):
        from kitsune_benchmark.integrated_session import BlankSession
        session=BlankSession({'target':'kitsune','evidence_path':'/unused'})
        tabs=[{'id':1,'url':'about:blank','active':True}]
        with patch.object(session,'wait_inventory',return_value=tabs),patch.object(session,'save'),patch.object(session,'diagnostic'),patch.object(session,'tool',side_effect=AssertionError('must not navigate')):
            session.prepare()
            self.assertTrue(session.evidence['setup_complete'])

    def test_model_pinned_without_modifying_original_config(self):
        original=experiment.personal.config()
        item=next(r for r in experiment.schedule() if r['track']=='personal')
        spec=experiment.spec_for(item)
        self.assertEqual(spec['claude_code']['model'],'claude-opus-5-5')
        self.assertEqual(experiment.personal.config(),original)

if __name__=='__main__':unittest.main()
