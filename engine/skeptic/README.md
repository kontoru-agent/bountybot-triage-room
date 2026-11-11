# Layer 3 — skeptic/

**Responsibility:** Try to *disprove* every candidate. For each one: argue the
strongest "not a bug" case (unreachable path? trusted role by design? impact
already accepted?), re-run the known-issues gate (`../scope/check_known_issues.py`)
with full context, and check previous audits / accepted-risk notes.
Verdict per candidate: `kill` (with reason) or `survive`.

**Input:** `candidates.jsonl` + `known_issues.txt` + prior audit reports.
**Output:** `survivors.jsonl` (candidate + `skeptic_verdict`, `skeptic_notes`,
`known_issue_max_score`) and a kill log.

Status: **implemented and run** — `rank_candidates.py` applies five kill
gates in order (G1 known-issues filter, G2 documented behaviour, G3
Panther impact classes, G4 trusted-role exclusion, G5 awarexone template
completeness), ranks survivors for PoC priority, assigns each candidate a
signing-gate decision (block / warn) for the NEAR wrapper, and renders
`triage_report.md`. On the Plether demo set: 3 survivors, 5 killed.
A candidate with no surviving disproof argument still must pass Layer 4.
