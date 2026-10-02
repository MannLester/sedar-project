#!/usr/bin/env python3
"""Run SEDAR's static architecture and hygiene checks.

Violations listed in architecture/baseline.json are tolerated legacy debt; any other
violation fails the run. Entries in the baseline that no longer occur are reported so the
baseline only ever shrinks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from checks import boundaries, docs_sync, hygiene
from checks.core import BASELINE_FILE, Violation

CHECKS = {
    "boundaries": boundaries.run,
    "comments": hygiene.check_comments,
    "pragmas": hygiene.check_pragmas,
    "file-size": hygiene.check_sizes,
    "xml": hygiene.check_xml,
    "manifest": hygiene.check_manifests,
    "access": hygiene.check_access,
    "docs-sync": docs_sync.run,
}


def load_baseline(path: Path = BASELINE_FILE) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_baseline(found: dict[str, list[Violation]], path: Path = BASELINE_FILE) -> None:
    data = {name: sorted({v.key for v in violations}) for name, violations in found.items() if violations}
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def partition(violations: list[Violation], baseline_keys: set[str]) -> tuple[list[Violation], set[str]]:
    new = [v for v in violations if v.key not in baseline_keys]
    stale = baseline_keys - {v.key for v in violations}
    return new, stale


def run_checks(selected: list[str], baseline: dict[str, list[str]]) -> tuple[dict[str, list[Violation]], int]:
    found: dict[str, list[Violation]] = {}
    failures = 0
    for name in selected:
        violations = CHECKS[name]()
        found[name] = violations
        new, stale = partition(violations, set(baseline.get(name, [])))
        status = "FAIL" if new else "ok"
        print(f"{status:4} {name}: {len(new)} new, {len(violations) - len(new)} baselined")
        for violation in new:
            print(f"     {violation.render()}")
        for key in sorted(stale):
            print(f"     stale baseline entry (fixed, remove with --update-baseline): {key}")
        failures += len(new)
    return found, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checks", nargs="*", help=f"checks to run (default: all): {', '.join(CHECKS)}")
    parser.add_argument("--update-baseline", action="store_true", help="rewrite the baseline from current violations")
    args = parser.parse_args(argv)
    unknown = [name for name in args.checks if name not in CHECKS]
    if unknown:
        parser.error(f"unknown check: {', '.join(unknown)}")
    selected = args.checks or list(CHECKS)
    baseline = load_baseline()
    found, failures = run_checks(selected, baseline)
    if args.update_baseline:
        merged = {name: [Violation("", key, "") for key in keys] for name, keys in baseline.items() if name not in selected}
        merged.update(found)
        write_baseline(merged)
        print(f"baseline written to {BASELINE_FILE}")
        return 0
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
