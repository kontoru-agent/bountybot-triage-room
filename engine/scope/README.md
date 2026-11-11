# Layer 1 — scope/

**Responsibility:** Establish the only legal playing field. Fetch the program's
official scope, freeze the exact commit, list in-scope / out-of-scope paths,
and load the known-issues + previous-audit + accepted-risk lists *before* any
analysis. Provide the duplicate gate used again by `skeptic/`.

**Input:** official program URL (e.g. Immunefi competition page).
**Output:** `scope.json` (contract in `../DESIGN.md` §3) + `known_issues.txt`.

**Implemented:** `load_scope.py` freezes the bundled official data
(`data/plether_scope.json` + `data/plether_known_issues.txt` — the real
Plether list: program page + Cecuro 113 + AI-scan 31 + SC pre-audit +
SECURITY.md limitations, 93 entries) into `demo_output/`. The root
`pipeline.py` runs Layers 1–3 end-to-end from this freeze.

## Functional tool: check_known_issues.py

Deterministic keyword-overlap duplicate flagger (no LLM, no network).
Findings format: entries separated by a line `---`, first line = title.
Known issues: one per line (`#` = comment).

```bash
python3 check_known_issues.py            # bundled examples, threshold 0.30
python3 check_known_issues.py --findings F.txt --known K.txt --threshold 0.30
# exit 0 = all clear · exit 2 = at least one DUPLICATE-CANDIDATE
```

### Actual run (2026-11-09, Python 3.12.3, bundled examples)

```
findings=2 known_issues=7 threshold=0.3
[DUPLICATE-CANDIDATE] score=0.55 finding='Stale cached price used when opening a position'
    closest known issue: 'Opens committed against a stale cached price and keeper bounty sized from stale price (Cecuro MED-16)'
[CLEAR] score=0.26 finding='Missing access control on Junior tranche redemption queue cleanup'
result: 1 duplicate candidate(s), 1 clear
exit=2
```

The flagged finding is a re-wording of known issue MED-16 — exactly the kind
of ineligible duplicate that must die before PoC work. The cleared finding
still goes to `skeptic/`; CLEAR here means only "not a keyword duplicate".

**Limits (honest):** keyword overlap is a cheap first gate, not a semantic
judge — paraphrases with disjoint vocabulary can slip through, which is why
Layer 3 re-checks with full context.
