#!/usr/bin/env python3
"""
Bountybot — pipeline.py  (end-to-end local run, Layers 1–3 + NEAR triage)

    scope/load_scope.py            freeze official scope + known issues
    scan/generate_candidates.py    candidates.jsonl (hypotheses only)
    skeptic/rank_candidates.py     known-issues filter + Panther gate +
                                   awarexone template -> survivors.jsonl,
                                   triage_report.md
    near/ai_cloud_client.py        annotate survivors (NEAR AI Cloud TEE
                                   inference when NEARAI_API_KEY is set;
                                   deterministic local fallback otherwise)

Everything runs offline with the Python 3 standard library only.
Outputs land in demo_output/ and are safe to commit: they contain no
secrets and make no bug claims — survivors are hypotheses awaiting a
runnable PoC (Layer 4, separate, Foundry-based).

Usage:  python3 pipeline.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "demo_output"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    print("=== Bountybot pipeline — Plether demo target (frozen scope) ===\n")
    scope_mod = _load("load_scope", "scope/load_scope.py")
    scope = scope_mod.load_scope(OUT)
    print()
    scan_mod = _load("generate_candidates", "scan/generate_candidates.py")
    scan_mod.generate(OUT)
    print(f"[scan] candidates -> {OUT / 'candidates.jsonl'}")
    print()
    rank_mod = _load("rank_candidates", "skeptic/rank_candidates.py")
    survivors, killed = rank_mod.rank(OUT)
    print(f"[skeptic] survivors={len(survivors)} killed={len(killed)} -> "
          f"survivors.jsonl + triage_report.md")
    print()
    ai_mod = _load("ai_cloud_client", "near/ai_cloud_client.py")
    ai_mod.annotate(OUT / "survivors.jsonl")
    print("\n=== done — artefacts in demo_output/ "
          "(survivors are hypotheses; PoC gate is Layer 4) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
