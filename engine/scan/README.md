# Layer 2 — scan/

**Responsibility:** Generate *candidates only* — never reports. Run Slither
detectors and Foundry build on the in-scope paths at the frozen commit, then
apply a short manual-pattern checklist: access control, oracle/staleness,
rounding/accounting, reentrancy, liquidation/price math.

**Input:** `scope.json` + target checkout at the frozen commit.
**Output:** `candidates.jsonl` (schema in `../DESIGN.md` §3).

Status: **run on the real target** — `generate_candidates.py` emits the
candidate set from the manual deep-recon of Plether's 48 core contracts at
the frozen commit (bundled as `plether_candidates.json`, with file:line
locations and the awarexone validation fields). Wiring Slither as an
additional automated source is future work. Every candidate carries its
evidence so `skeptic/` can audit it.
