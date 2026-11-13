"""Host context for the stress tracks: what the machine was, and whether it slowed down.

None of this changes a workload, schedule or measured metric (`host-diagnostics-v1`).
`host_details()` is read once per run. `cpu_canary()` times a fixed single-threaded loop
in the driver before and after each arm, outside warmup, idle and load: a canary slower
than the run's first one means a slower or busier host (thermal limits on a fanless
laptop, other applications), not a slower target. `HostCPU` reads whole-machine CPU time
across a load window, so CPU that neither the owned processes nor the driver used shows.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

import psutil

HOST_PROBE = "host-diagnostics-v1"
CANARY_ITERATIONS = 3_000_000  # about 0.09 s on an Apple M2 performance core
CANARY_REPEATS = 5
SLOWER_RATIO = 1.15  # a canary this much slower than the run's first one is a measurement warning
BUSY_FIELDS = ("user", "nice", "system", "irq", "softirq", "steal")  # Linux guest time is inside user/nice


def _output(argv: list[str]) -> str | None:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=5, check=True).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip() or None
    except OSError:
        return None


def _integer(text: str | None) -> int | None:
    return int(text) if text and text.isdigit() else None


def host_details() -> dict:
    """Model, CPU, core types, power source and thermal notes; unknown fields are None."""
    if platform.system() == "Darwin":
        cores = [{"name": _output(["sysctl", "-n", f"hw.perflevel{level}.name"]),
                  "logical_cpus": _integer(_output(["sysctl", "-n", f"hw.perflevel{level}.logicalcpu"]))}
                 for level in range(_integer(_output(["sysctl", "-n", "hw.nperflevels"])) or 0)]
        battery = _output(["pmset", "-g", "batt"]) or ""
        thermal = _output(["pmset", "-g", "therm"])
        details = {"model": _output(["sysctl", "-n", "hw.model"]),
                   "cpu_brand": _output(["sysctl", "-n", "machdep.cpu.brand_string"]),
                   "core_types": cores or None,
                   "power_source": battery.split("'")[1] if battery.count("'") >= 2 else None,
                   "thermal_notes": thermal.splitlines()[:6] if thermal else None}
    else:
        cpuinfo = _read(Path("/proc/cpuinfo")) or ""
        brand = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines()
                      if line.startswith("model name")), None)
        supplies = Path("/sys/class/power_supply")
        mains = [_read(p / "online") for p in supplies.glob("*") if _read(p / "type") == "Mains"] if supplies.is_dir() else []
        details = {"model": _read(Path("/sys/devices/virtual/dmi/id/product_name")),
                   "cpu_brand": brand or platform.processor() or None, "core_types": None,
                   "power_source": ("AC Power" if "1" in mains else "Battery Power") if mains else None,
                   "thermal_notes": None}
    return {**details, "load_average_at_start": list(os.getloadavg()) if hasattr(os, "getloadavg") else None}


def _loop(iterations: int) -> int:
    total = 0
    for i in range(iterations):
        total += i * i
    return total


def cpu_canary(iterations: int = CANARY_ITERATIONS, repeats: int = CANARY_REPEATS) -> dict:
    """Best and median wall/CPU seconds of a fixed pure-Python loop in the driver process.

    Wall time well above CPU time means the driver waited for a core (a busy host); more
    CPU seconds for the same loop mean a slower core (lower clock or an efficiency core).
    """
    walls, cpus = [], []
    for _ in range(repeats):
        cpu, wall = time.process_time(), time.perf_counter()
        _loop(iterations)
        walls.append(time.perf_counter() - wall)
        cpus.append(time.process_time() - cpu)
    return {"iterations": iterations, "best_wall_sec": min(walls), "median_wall_sec": statistics.median(walls),
            "best_cpu_sec": min(cpus), "median_cpu_sec": statistics.median(cpus)}


def canary_record(before: dict, after: dict | None, first: dict) -> dict:
    return {"before": before, "after": after,
            "slowdown_vs_first": before["best_wall_sec"] / first["best_wall_sec"]}


def canary_warnings(record: dict) -> list[str]:
    return ["host_cpu_slower"] if record["slowdown_vs_first"] > SLOWER_RATIO else []


def _busy(times) -> float:
    return sum(getattr(times, name, 0.0) for name in BUSY_FIELDS)


class HostCPU:
    """Whole-machine busy CPU over a window, one-core normalized like the owned totals.

    Construct at the start of the window and call stop() at its end.
    """

    def __init__(self):
        self.observer = psutil.Process()
        self.before, self.observer_before = psutil.cpu_times(), self.observer.cpu_times()
        self.after = self.observer_after = None

    def stop(self) -> None:
        self.after, self.observer_after = psutil.cpu_times(), self.observer.cpu_times()

    def record(self, elapsed: float, owned_percent: float | None) -> dict:
        """`unowned` is approximate: the owned phase window differs by milliseconds and sampled
        owned CPU can miss short-lived processes."""
        if self.after is None or elapsed <= 0:
            return {"load_percent_one_core": None, "observer_percent_one_core": None, "unowned_percent_one_core": None}
        busy = 100 * (_busy(self.after) - _busy(self.before)) / elapsed
        driver = 100 * (self.observer_after.user + self.observer_after.system
                        - self.observer_before.user - self.observer_before.system) / elapsed
        return {"load_percent_one_core": busy, "observer_percent_one_core": driver,
                "unowned_percent_one_core": busy - driver - owned_percent if owned_percent is not None else None}


def run_canary_summary(levels: list[dict]) -> dict | None:
    records = [level["host_canary"] for level in levels if level.get("host_canary")]
    if not records:
        return None
    return {"probe": HOST_PROBE, "first_best_wall_sec": records[0]["before"]["best_wall_sec"],
            "max_slowdown_vs_first": max(r["slowdown_vs_first"] for r in records),
            "levels_with_slower_host": sum(bool(canary_warnings(r)) for r in records)}
