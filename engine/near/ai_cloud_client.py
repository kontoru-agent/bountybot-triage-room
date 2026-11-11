#!/usr/bin/env python3
"""
Bountybot — near/ai_cloud_client.py  (NEAR AI Cloud triage client)

The private-triage step of the pipeline. Pre-disclosure target code must not
be pasted into a public model endpoint: NEAR AI Cloud serves OpenAI-compatible
inference inside TEEs (private and verifiable), which is exactly the surface a
bounty hunter needs for classifying candidate findings.

Router pattern (same shape as a multi-model router):
    base_url / model / api_key are configuration, not code.
      NEARAI_BASE_URL  (default https://cloud-api.near.ai/v1)
      NEARAI_MODEL     (default from near/config.json: zai-org/GLM-5.1-FP8)
      NEARAI_API_KEY   (env ONLY — never a file, never printed, never logged)

Fallback: with no key (or on any request error), triage degrades to a
deterministic LOCAL classifier (keyword rules over the candidate text) and
says so in its output. The pipeline therefore runs end-to-end offline, and
the day a key is provided the same call sites upgrade to private cloud
inference with zero code changes.

Honesty boundary: the model only *annotates* (category + rationale). It can
never promote or kill a candidate — the deterministic gates in skeptic/ own
every verdict. An LLM agreeing with itself is not evidence.

CLI:  python3 near/ai_cloud_client.py [survivors.jsonl]
      (annotates the file in place with an `ai_triage` object per record)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

CATEGORIES = [
    ("liquidation-accounting", ("liquidat", "reserve", "write-off", "writeoff",
                                "bad debt", "bounty")),
    ("tranche-accounting", ("tranche", "senior", "junior", "high-water",
                            "high water", "hwm", "unassigned")),
    ("queue-liveness", ("fifo", "queue", "head order", "prune", "stuck",
                        "freeze", "frozen", "permanent")),
    ("oracle-staleness", ("oracle", "stale", "cached", "signed price", "mark")),
    ("access-control", ("access control", "role", "onlyowner", "anyone can",
                        "permissionless")),
    ("rounding-accounting", ("rounding", "dust", "round", "atom", "precision")),
]

SYSTEM_PROMPT = (
    "You are the triage classifier inside Bountybot, an evidence-gated bug "
    "bounty agent. Classify the candidate finding into exactly one category "
    "from: liquidation-accounting, tranche-accounting, queue-liveness, "
    "oracle-staleness, access-control, rounding-accounting, other. Reply "
    "with ONLY a JSON object: {\"category\": \"...\", \"rationale\": \"one "
    "sentence\"}. You are annotating, not judging: never claim the candidate "
    "is or is not a real bug."
)


def local_classify(text: str) -> tuple[str, str]:
    t = text.lower()
    hits = [(cat, sum(1 for kw in kws if kw in t)) for cat, kws in CATEGORIES]
    hits.sort(key=lambda h: -h[1])
    if hits and hits[0][1] > 0:
        return hits[0][0], (f"local keyword classifier: {hits[0][1]} keyword "
                            f"hit(s) for {hits[0][0]}")
    return "other", "local keyword classifier: no category keywords matched"


class NearAiTriage:
    def __init__(self) -> None:
        self.base_url = os.environ.get("NEARAI_BASE_URL",
                                       CONFIG["base_url"]).rstrip("/")
        self.model = os.environ.get("NEARAI_MODEL", CONFIG["model"])
        self.api_key = os.environ.get("NEARAI_API_KEY", "")

    @property
    def mode(self) -> str:
        return "cloud" if self.api_key else "local-fallback"

    def triage(self, candidate: dict) -> dict:
        text = (f"{candidate.get('title', '')}\n"
                f"{candidate.get('description', '')}")
        if not self.api_key:
            cat, why = local_classify(text)
            return {"mode": "local-fallback", "model": None,
                    "category": cat, "rationale": why,
                    "note": "no NEARAI_API_KEY in env — deterministic local "
                            "classifier used; no model was called"}
        try:
            body = json.dumps({
                "model": self.model,
                "temperature": CONFIG["triage"]["temperature"],
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text[:6000]},
                ],
            }).encode()
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions", data=body, headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {"mode": "cloud", "model": self.model,
                    "category": parsed["category"],
                    "rationale": parsed["rationale"],
                    "note": "NEAR AI Cloud (TEE inference); annotation only"}
        except Exception as exc:  # network, auth, shape — degrade, never crash
            cat, why = local_classify(text)
            return {"mode": "local-fallback", "model": self.model,
                    "category": cat, "rationale": why,
                    "note": f"cloud call failed ({type(exc).__name__}); "
                            "local classifier used instead"}


def annotate(path: Path) -> int:
    client = NearAiTriage()
    records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
               if l.strip()]
    for r in records:
        r["ai_triage"] = client.triage(r)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                            for r in records), encoding="utf-8")
    print(f"[near-ai] mode={client.mode} model={client.model} "
          f"annotated={len(records)} record(s) in {path.name}")
    for r in records:
        print(f"[near-ai]   {r['id']:<4} category={r['ai_triage']['category']}")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        HERE.parent / "demo_output" / "survivors.jsonl")
    raise SystemExit(annotate(target))
