#!/usr/bin/env python3
"""
Bountybot — scan/generate_candidates.py  (Layer 2: candidate generation)

Emits candidates ONLY — never reports. In the full system this layer runs
Slither detectors + a Foundry build and applies a manual-pattern checklist
(access control, oracle/staleness, rounding/accounting, reentrancy,
liquidation math). For the reproducible demo run, the candidate set is the
output of the manual deep-recon of the Plether scope at the frozen commit
(human + agent code reading of the 48 core state-changing contracts,
bundled as scan/plether_candidates.json with file:line locations), so the
whole pipeline re-runs deterministically with no network and no forge.

Output: demo_output/candidates.jsonl  (schema: DESIGN.md section 3)

Usage:  python3 scan/generate_candidates.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def generate(out_dir: Path) -> list[dict]:
    raw = json.loads((HERE / "plether_candidates.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "candidates.jsonl").open("w", encoding="utf-8") as fh:
        for c in raw:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "demo_output"))
    args = ap.parse_args()
    cands = generate(Path(args.out))
    print(f"[scan] candidates emitted={len(cands)} "
          f"(source: manual deep-recon of in-scope contracts at frozen commit; "
          f"Slither/forge pass is a separate tooling step)")
    for c in cands:
        print(f"[scan]   {c['id']:<4} {c['title'][:88]}")
    print(f"[scan] wrote {Path(args.out) / 'candidates.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
