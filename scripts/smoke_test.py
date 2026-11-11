#!/usr/bin/env python3
"""
smoke_test.py — offline checks for the Triage Room backend (no Nexconn
credentials, no network beyond localhost).

Run:  python3 scripts/smoke_test.py
Expects the server to be started separately in demo mode:
      python3 server/server.py &   (PORT default 8787)
or set BASE=http://localhost:PORT.
"""
import json
import os
import sys
import urllib.request

BASE = os.environ.get("BASE", "http://localhost:8787")
FAILS = []


def call(path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


cfg = call("/api/config")
check("config is demo mode", cfg["mode"] == "demo")
check("config hides appKey in demo", cfg["appKey"] is None)

events = call("/api/run", {})["events"]
cards = [e for e in events if e["type"] == "candidate_card"]
verdicts = [e for e in events if e["type"] == "verdict"]
check("8 candidate cards", len(cards) == 8, str(len(cards)))
check("8 verdicts", len(verdicts) == 8, str(len(verdicts)))
blocks = [v for v in verdicts if v["decision"] == "block"]
warns = [v for v in verdicts if v["decision"] == "warn"]
check("5 blocks / 3 warns (real engine output)", len(blocks) == 5 and len(warns) == 3,
      f"{len(blocks)}/{len(warns)}")
check("blocks carry a named gate", all(v.get("gate") for v in blocks))
check("K-1 survives at warn", any(v["candidate_id"] == "K-1" for v in warns))

r = call("/api/approve", {"actor": "reviewer", "candidate_id": "K-1"})
check("reviewer approval does NOT release (warn)", r["verdict"] == "warn", str(r))
r = call("/api/approve", {"actor": "lead", "candidate_id": "K-1"})
check("lead approval releases warn -> allow", r["verdict"] == "allow", str(r))
killed = blocks[0]["candidate_id"]
r = call("/api/approve", {"actor": "lead", "candidate_id": killed})
check("approving a killed candidate stays block", r["verdict"] == "block", str(r))

r = call("/api/inject", {})
check("injection demo is blocked by the Gate", r["verdict"] == "block", str(r))

log = call("/api/log")["entries"]
check("decision log recorded entries", len(log) >= 4, str(len(log)))

print("\n%d failure(s)" % len(FAILS))
sys.exit(1 if FAILS else 0)
