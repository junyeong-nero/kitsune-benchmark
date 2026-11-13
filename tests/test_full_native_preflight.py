"""Legacy full-native compatibility checks: no model, browser, or fixture actions."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark import full_native as native
from kitsune_benchmark.__main__ import main


SOURCE = {"revision": "legacy-test-pin", "dirty": False}
CORE = [{"name": "browser_snapshot"}, {"name": "browser_click"}]


def observation(arm, project=Path("/unused")):
    return {"server_file": str((project / "src/kitsune/server.py").resolve()), "enabled_caps": ["core" if arm == "core" else "all"], "published_caps": ["core"],
            "scripting": False, "tools": CORE + ([{"name": n} for n in native.GATEWAY_TOOLS] if arm == "gateway" else [])}


class FullNativePreflightTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.project = self.root / "project"
        self.project.mkdir()
        root_patch = patch.object(native, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        revision_patch = patch.object(native, "source_revision", return_value=SOURCE)
        revision_patch.start()
        self.addCleanup(revision_patch.stop)
        self.calls = []

    def respond(self, command, **kwargs):
        env = kwargs["env"]
        arm = "gateway" if "KITSUNE_PUBLISH" in env else "core"
        self.calls.append((arm, command, kwargs))
        return subprocess.CompletedProcess(command, 0, json.dumps(observation(arm, self.project)), "")

    def evidence(self):
        path, = self.root.glob("artifacts/full-native-preflight/*/preflight.json")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        return path, json.loads(path.read_text())

    def test_checks_both_unmodified_arms_in_private_restricted_environments(self):
        inherited = {"KITSUNE_CAPS": "history", "KITSUNE_PUBLISH": "all", "KITSUNE_SCRIPTING": "1",
                     "KITSUNE_MODE": "read", "ANTHROPIC_API_KEY": "private-key", "PYTHONPATH": "/injected"}
        with patch.dict(os.environ, inherited), patch.object(native.subprocess, "run", side_effect=self.respond):
            path = native.compatibility_preflight(self.project, SOURCE)
        evidence_path, report = self.evidence()
        self.assertEqual(path, str(evidence_path))
        self.assertTrue(report["compatible"])
        self.assertFalse(report["model_invoked"])
        self.assertEqual(report["kitsune_source"], SOURCE)
        self.assertEqual([c[0] for c in self.calls], ["core", "gateway"])
        for arm, command, kwargs in self.calls:
            env = kwargs["env"]
            self.assertEqual(command[:5], ["uv", "run", "--locked", "--project", str(self.project)])
            self.assertEqual(kwargs["timeout"], 60)
            self.assertEqual({k: env[k] for k in native.ARMS[arm]}, native.ARMS[arm])
            self.assertEqual(env["KITSUNE_NO_BRIDGE_RESTART"], "1")
            self.assertTrue(Path(env["KITSUNE_HOME"]).is_relative_to(evidence_path.parent))
            for forbidden in ("KITSUNE_SCRIPTING", "KITSUNE_MODE", "ANTHROPIC_API_KEY", "PYTHONPATH", "VIRTUAL_ENV"):
                self.assertNotIn(forbidden, env)
        self.assertNotEqual(self.calls[0][2]["env"]["KITSUNE_HOME"], self.calls[1][2]["env"]["KITSUNE_HOME"])

    def test_plan_does_not_probe_or_start_processes(self):
        with patch.object(native, "compatibility_preflight", side_effect=AssertionError("probe")), \
                patch.object(native.subprocess, "Popen", side_effect=AssertionError("process")):
            result = native.run_full_native(kitsune_project="/nonexistent")
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["compatibility_check"], "legacy-caps-publish-v1")

    def test_insufficient_budget_is_rejected_before_probing(self):
        with patch.object(native, "compatibility_preflight", side_effect=AssertionError("probe")), \
                self.assertRaisesRegex(ValueError, "Suite budget is smaller"):
            native.run_full_native(execute=True, harness="claude-api", budget_usd=0.001)

    def test_cli_stops_before_fixtures_and_does_not_print_private_errors(self):
        out = io.StringIO()
        failed = subprocess.CompletedProcess([], 1, "", "Remove KITSUNE_CAPS; private-key")
        with patch.object(native.subprocess, "run", return_value=failed), \
                patch.object(native, "run_unit", side_effect=AssertionError("fixture/model")) as run, redirect_stdout(out):
            code = main(["full-native", "--execute", "--kitsune-project", str(self.project)])
        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertIn("KITSUNE_CAPS/KITSUNE_PUBLISH", out.getvalue())
        self.assertIn("No fixture or model", out.getvalue())
        self.assertNotIn("private-key", out.getvalue())
        _, report = self.evidence()
        self.assertFalse(report["compatible"])
        self.assertFalse(report["model_invoked"])
        self.assertEqual(report["arms"]["core"]["stderr"], failed.stderr)
        self.assertNotIn("gateway", report["arms"], "stop on the first failure; do not retry")

    def test_both_checks_finish_before_first_unit(self):
        def boundary(*args, **kwargs):
            self.assertEqual([c[0] for c in self.calls], ["core", "gateway"])
            self.assertTrue(Path(kwargs["compatibility_path"]).is_file())
            raise RuntimeError("before fixture/model")
        with patch.object(native.subprocess, "run", side_effect=self.respond), \
                patch.object(native, "run_unit", side_effect=boundary), \
                self.assertRaisesRegex(RuntimeError, "before fixture/model"):
            native.run_full_native(execute=True, kitsune_project=str(self.project))

    def test_rejects_ignored_settings_minimal_surface_and_invalid_catalogs(self):
        changes = ({"server_file": "/wrong/checkout/server.py"}, {"enabled_caps": ["all"]},
                   {"published_caps": ["all"]}, {"scripting": True},
                   {"tools": []}, {"tools": CORE + CORE}, {"tools": CORE + [{"name": "browser_tools_call"}]})
        for i, change in enumerate(changes):
            with self.subTest(change=change), patch.object(native, "ROOT", self.root / str(i)), \
                    patch.object(native.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], 0, json.dumps({**observation("core", self.project), **change}), "")), \
                    self.assertRaises(native.FullNativeCompatibilityError):
                native.compatibility_preflight(self.project, SOURCE)

    def test_missing_gateway_and_source_drift_fail_closed(self):
        def missing_gateway(command, **kwargs):
            result = self.respond(command, **kwargs)
            if self.calls[-1][0] == "gateway":
                result.stdout = json.dumps({**observation("gateway", self.project), "tools": CORE})
            return result
        with patch.object(native.subprocess, "run", side_effect=missing_gateway), \
                self.assertRaises(native.FullNativeCompatibilityError):
            native.compatibility_preflight(self.project, SOURCE)
        _, report = self.evidence()
        self.assertFalse(report["compatible"])
        with patch.object(native, "ROOT", self.root / "drift"), \
                patch.object(native, "source_revision", return_value={"revision": "changed", "dirty": False}), \
                patch.object(native.subprocess, "run", side_effect=self.respond), \
                self.assertRaises(native.FullNativeCompatibilityError):
            native.compatibility_preflight(self.project, SOURCE)

    def test_startup_timeout_and_malformed_output_preserve_failure_evidence(self):
        errors = (OSError("missing uv"), subprocess.TimeoutExpired("probe", 60, output=b"partial", stderr=b"diagnostic"),
                  subprocess.CompletedProcess([], 0, "not json", ""))
        for i, error in enumerate(errors):
            with self.subTest(error=error), patch.object(native, "ROOT", self.root / str(i)):
                options = {"side_effect": error} if isinstance(error, Exception) else {"return_value": error}
                with patch.object(native.subprocess, "run", **options), self.assertRaises(native.FullNativeCompatibilityError):
                    native.compatibility_preflight(self.project, SOURCE)
                path, = (self.root / str(i)).glob("artifacts/full-native-preflight/*/preflight.json")
                report = json.loads(path.read_text())
                self.assertFalse(report["compatible"])
                self.assertFalse(report["model_invoked"])
                if isinstance(error, subprocess.TimeoutExpired):
                    self.assertEqual(report["arms"]["core"]["stdout"], "partial")
                    self.assertEqual(report["arms"]["core"]["stderr"], "diagnostic")


class FullNativeProbeWorkerTests(unittest.TestCase):
    def test_worker_only_imports_configuration_and_lists_registered_tools(self):
        worker = Path(native.__file__).with_name("full_native_probe.py")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / "kitsune"
            package.mkdir()
            (package / "__init__.py").touch()
            (package / "server.py").write_text('''import os
ENABLED_CAPS = frozenset({os.environ['KITSUNE_CAPS']})
PUBLISHED_CAPS = frozenset({os.environ.get('KITSUNE_PUBLISH', os.environ['KITSUNE_CAPS'])})
SCRIPTING = False
class Tool:
    def model_dump(self, **kwargs):
        return {'name': 'browser_snapshot', 'inputSchema': {'type': 'object'}}
class MCP:
    async def list_tools(self): return [Tool()]
    def run(self, *args, **kwargs): raise AssertionError('no MCP server/bridge')
    async def call_tool(self, *args, **kwargs): raise AssertionError('no tool calls')
mcp = MCP()
def main(): raise AssertionError('no bridge startup')
''')
            for arm, settings in native.ARMS.items():
                command = [sys.executable, "-c", "import runpy,sys; sys.path.insert(0,sys.argv[1]); runpy.run_path(sys.argv[2],run_name='__main__')",
                           str(root), str(worker)]
                env = {k: v for k, v in os.environ.items() if k in native.BASE_ENV}
                result = subprocess.run(command, env={**env, **settings}, capture_output=True, text=True, timeout=10, check=True)
                data = json.loads(result.stdout)
                self.assertEqual(data["enabled_caps"], observation(arm)["enabled_caps"])
                self.assertEqual(data["published_caps"], ["core"])
                self.assertEqual(data["tools"][0]["name"], "browser_snapshot")
