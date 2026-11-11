#!/usr/bin/env python3
"""
Bountybot — scope/load_scope.py  (Layer 1: scope loader)

Freezes one official program scope into the pipeline's working artefacts:

    demo_output/scope.json          (data contract: DESIGN.md section 3)
    demo_output/known_issues.txt    (verbatim list consumed by the dup gate)

The bundled source data under scope/data/ is the Plether Immunefi audit
competition scope as read from the official program page on 2026-11-09,
frozen at commit a82d4fefb02768e5b3bddcc97dee371eee24fea8. Freezing means:
every later layer works against these exact bytes, and any scope change
upstream produces a visible diff here instead of a silent behaviour change.

Usage:  python3 scope/load_scope.py [--out DIR]
Exit:   0 on success.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DATA = HERE / "data"


def load_scope(out_dir: Path) -> dict:
    src = json.loads((DATA / "plether_scope.json").read_text(encoding="utf-8"))
    scope = {
        "program": src["program"],
        "platform": src["platform"],
        "program_url": src["program_url"],
        "repo": src["repo"],
        "commit": src["commit"],
        "in_scope": src["in_scope"],
        "exclusions": src["exclusions"],
        "known_issues_source": src["known_issues_source"],
        "poc_requirement": src["poc_requirement"],
        "trust_model": src["trust_model"],
        "in_scope_stats": src["in_scope_stats"],
        "competition": src["competition"],
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scope.json").write_text(
        json.dumps(scope, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "known_issues.txt").write_text(
        (DATA / "plether_known_issues.txt").read_text(encoding="utf-8"),
        encoding="utf-8")
    return scope


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "demo_output"))
    args = ap.parse_args()
    scope = load_scope(Path(args.out))
    n_known = sum(1 for line in (Path(args.out) / "known_issues.txt")
                  .read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.startswith("#"))
    print(f"[scope] program={scope['program']} platform={scope['platform']}")
    print(f"[scope] repo={scope['repo']}")
    print(f"[scope] frozen commit={scope['commit']}")
    print(f"[scope] in_scope={scope['in_scope']} "
          f"({scope['in_scope_stats']['sol_files']} .sol files, "
          f"{scope['in_scope_stats']['total_lines']} lines)")
    print(f"[scope] known_issues loaded={n_known} "
          f"exclusions={len(scope['exclusions'])}")
    print(f"[scope] wrote {Path(args.out) / 'scope.json'} + known_issues.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
