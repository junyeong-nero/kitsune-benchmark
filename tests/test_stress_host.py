"""Host diagnostics for the stress tracks (host-diagnostics-v1); no browser or model."""
from collections import namedtuple
import subprocess
import unittest
from unittest.mock import patch

from kitsune_benchmark import stress_host
from kitsune_benchmark.stress_host import (HostCPU, canary_record, canary_warnings, cpu_canary, host_details,
                                           run_canary_summary)


class HostDiagnosticsTests(unittest.TestCase):
    def test_details_never_fail_and_leave_unknowns_none(self):
        with patch.object(stress_host.subprocess, "run", side_effect=OSError("no such tool")):
            details = host_details()
        self.assertLessEqual({"model", "cpu_brand", "core_types", "power_source", "thermal_notes",
                              "load_average_at_start"}, details.keys())
        if stress_host.platform.system() == "Darwin":
            self.assertEqual((details["model"], details["core_types"], details["power_source"]), (None, None, None))

    def test_macos_core_types_power_source_and_thermal_notes(self):
        answers = {"hw.nperflevels": "2", "hw.perflevel0.name": "Performance", "hw.perflevel0.logicalcpu": "4",
                   "hw.perflevel1.name": "Efficiency", "hw.perflevel1.logicalcpu": "4", "hw.model": "Mac14,2",
                   "machdep.cpu.brand_string": "Apple M2"}

        def run(argv, **kwargs):
            if argv[0] == "sysctl":
                return subprocess.CompletedProcess(argv, 0, answers[argv[2]] + "\n", "")
            if argv[:3] == ["pmset", "-g", "batt"]:
                return subprocess.CompletedProcess(argv, 0, "Now drawing from 'AC Power'\n -InternalBattery-0\n", "")
            return subprocess.CompletedProcess(argv, 0, "Note: No thermal warning level has been recorded\n", "")
        with patch.object(stress_host.platform, "system", return_value="Darwin"), \
             patch.object(stress_host.subprocess, "run", side_effect=run):
            details = host_details()
        self.assertEqual((details["model"], details["cpu_brand"]), ("Mac14,2", "Apple M2"))
        self.assertEqual(details["core_types"], [{"name": "Performance", "logical_cpus": 4},
                                                 {"name": "Efficiency", "logical_cpus": 4}])
        self.assertEqual(details["power_source"], "AC Power")
        self.assertEqual(details["thermal_notes"], ["Note: No thermal warning level has been recorded"])

    def test_canary_times_a_fixed_loop(self):
        canary = cpu_canary(iterations=10_000, repeats=3)
        self.assertEqual(canary["iterations"], 10_000)
        self.assertGreater(canary["best_wall_sec"], 0)
        self.assertLessEqual(canary["best_wall_sec"], canary["median_wall_sec"])
        self.assertLessEqual(canary["best_cpu_sec"], canary["median_cpu_sec"])

    def test_slower_canary_is_a_warning_not_an_error(self):
        first = {"best_wall_sec": 0.10}
        self.assertEqual(canary_warnings(canary_record({"best_wall_sec": 0.11}, None, first)), [])
        slow = canary_record({"best_wall_sec": 0.12}, None, first)
        self.assertAlmostEqual(slow["slowdown_vs_first"], 1.2)
        self.assertEqual(canary_warnings(slow), ["host_cpu_slower"])
        summary = run_canary_summary([{"host_canary": canary_record(first, None, first)}, {"host_canary": slow}, {}])
        self.assertAlmostEqual(summary["max_slowdown_vs_first"], 1.2)
        self.assertEqual((summary["probe"], summary["levels_with_slower_host"]), ("host-diagnostics-v1", 1))
        self.assertIsNone(run_canary_summary([{}]))

    def test_host_cpu_is_one_core_normalized_net_of_owned_and_driver(self):
        Times = namedtuple("Times", "user nice system idle")
        Own = namedtuple("Own", "user system")
        host = iter([Times(10, 0, 5, 100), Times(40, 0, 15, 120)])  # 40 busy CPU-seconds in the window
        driver = iter([Own(1, 0), Own(3, 0)])  # 2 CPU-seconds
        with patch.object(stress_host.psutil, "cpu_times", side_effect=lambda: next(host)), \
             patch.object(stress_host.psutil.Process, "cpu_times", side_effect=lambda: next(driver)):
            window = HostCPU()
            window.stop()
        self.assertEqual(window.record(10.0, owned_percent=300.0),
                         {"load_percent_one_core": 400.0, "observer_percent_one_core": 20.0,
                          "unowned_percent_one_core": 80.0})
        self.assertIsNone(HostCPU().record(10.0, 1.0)["load_percent_one_core"])  # stop() was not called


if __name__ == "__main__":
    unittest.main()
