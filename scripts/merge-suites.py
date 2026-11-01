"""Combine a stopped suite directory and its retry (run-full-suite.py --from) into one directory. No model or browser
calls; the track outputs stay where they are, since suite-log.jsonl entries point at them.

The merged suite-manifest.json is the first suite's, plus `sources` (both directories and their manifests) and
`replaced` (the first suite's entries the retry ran again). The merged suite-log.jsonl is the first suite's log
without those entries, followed by the retry's log. Suites that differ in model, harness, plan, policy, Kitsune
revision, taskset tag or attempt layout are refused: their entries are not one cohort.

usage: uv run --locked python scripts/merge-suites.py artifacts/opus-full artifacts/opus-full-retry \\
           --out artifacts/opus-full-merged
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SAME_SETTINGS = ("model", "harness", "plan", "elicitation", "targets_in_parallel", "attempts", "order_policy")


def read_suite(suite_dir: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((suite_dir / "suite-manifest.json").read_text())
    log = suite_dir / "suite-log.jsonl"
    entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()] if log.is_file() else []
    return manifest, entries


def mismatches(first: dict, retry: dict) -> list[str]:
    """Settings that differ between the two manifests."""
    different = [key for key in SAME_SETTINGS if first.get(key) != retry.get(key)]
    if (first.get("kitsune") or {}).get("revision") != (retry.get("kitsune") or {}).get("revision"):
        different.append("kitsune.revision")
    if (first.get("taskset") or {}).get("tag") != (retry.get("taskset") or {}).get("tag"):
        different.append("taskset.tag")
    return different


def merge(first_dir: Path, retry_dir: Path) -> tuple[dict, list[dict]]:
    """(manifest, log entries) of the merged suite; ValueError if the two suites are not one cohort."""
    first, first_entries = read_suite(first_dir)
    retry, retry_entries = read_suite(retry_dir)
    different = mismatches(first, retry)
    if different:
        raise ValueError(f"{first_dir} and {retry_dir} differ in {', '.join(different)}")
    rerun = {(entry["name"], entry.get("attempt")) for entry in retry_entries}
    kept = [entry for entry in first_entries if (entry["name"], entry.get("attempt")) not in rerun]
    replaced = list(dict.fromkeys(entry["name"] for entry in first_entries
                                  if (entry["name"], entry.get("attempt")) in rerun))
    manifest = {**first, "sources": [{"suite": str(first_dir.resolve()), "manifest": first},
                                     {"suite": str(retry_dir.resolve()), "manifest": retry}],
                "replaced": replaced}
    return manifest, kept + retry_entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", help="The stopped suite directory")
    parser.add_argument("retry", help="The run-full-suite.py --from retry of it")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        parser.error("--out must be empty; refusing to overwrite suite evidence.")
    try:
        manifest, entries = merge(Path(args.first), Path(args.retry))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    out.mkdir(parents=True, exist_ok=True)
    (out / "suite-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "suite-log.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in entries))
    print(f"merged {len(entries)} entries into {out}; replaced: {', '.join(manifest['replaced']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
