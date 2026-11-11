#!/usr/bin/env python3
"""
Bountybot — skeptic/rank_candidates.py  (Layer 3: skeptic + ranker)

Tries to DISPROVE every candidate, then ranks what survives. Gates, in order:

  G1 Known-issues filter — token-overlap score (same engine as
     scope/check_known_issues.py) against the program's real known-issues
     list. score >= threshold -> KILLED as duplicate-candidate. In audit
     competitions, known issues pay exactly 0; letting one through is the
     canonical AI-slop failure.
  G2 Documented behaviour — behaviour the protocol documents and explicitly
     tests as intended -> KILLED (would be rejected as known/design).
  G3 Panther impact gate — only four payable impact classes survive:
     direct user fund loss, permanent fund freeze, protocol insolvency,
     core-function breakage. Anything else -> KILLED as non-payable.
  G4 Panther trust model — a path only a trusted role (owner/admin) can
     trigger -> KILLED as non-payable on its own.
  G5 awarexone validation template — SETUP / CALL / RESULT / COST / DETECT /
     NET ROI must be filled with specifics. Empty RESULT (attacker goes home
     with nothing) -> KILLED: not a bug. RESULT marked conditional
     (reachability unproven) -> survives but flagged UNVALIDATED and ranked
     down; its PoC is the reachability proof itself.

Survivors are scored for PoC priority:
    impact base (fund loss 40 / insolvency 35 / freeze 30 / core break 25)
    + 15 no-test-coverage gap   + 10 partly-fixed surface
    + 10 full template          - known-overlap * 20
and each gets a signing-gate decision for the NEAR policy wrapper:
    killed -> block · unvalidated -> warn · validated survivor -> warn
    (allow is only possible after a passing PoC AND a human order; Layer 4/5)

Outputs: demo_output/survivors.jsonl, demo_output/triage_report.md
Usage:   python3 skeptic/rank_candidates.py [--out DIR] [--threshold 0.30]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

IMPACT_BASE = {
    "direct_user_fund_loss": 40,
    "protocol_insolvency": 35,
    "permanent_fund_freeze": 30,
    "core_function_breakage": 25,
}
PAYABLE_IMPACTS = set(IMPACT_BASE)


def _load_dup_engine():
    spec = importlib.util.spec_from_file_location(
        "check_known_issues", REPO_ROOT / "scope" / "check_known_issues.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def evaluate(cand: dict, known_tokens: list, engine, threshold: float) -> dict:
    """Return a verdict record for one candidate."""
    text = f"{cand['title']} {cand.get('description', '')}"
    ft = engine.tokenise(text)
    best_text, best_score = "", 0.0
    for k_text, kt in known_tokens:
        s = engine.score(ft, kt)
        if s > best_score:
            best_text, best_score = k_text, s

    v = cand.get("validation", {})
    rec = {"id": cand["id"], "known_issue_max_score": best_score,
           "closest_known_issue": best_text, "killed_by": None, "reason": ""}

    if best_score >= threshold:
        rec["killed_by"] = "G1 known-issues filter"
        rec["reason"] = (f"keyword overlap {best_score:.3f} >= {threshold} with a "
                         f"published known issue — duplicate-candidate, ineligible")
        return rec
    if cand.get("documented_behavior"):
        rec["killed_by"] = "G2 documented behaviour"
        rec["reason"] = ("behaviour is documented and explicitly tested as "
                         "intended — would be rejected as known/design")
        return rec
    if cand.get("impact_class") not in PAYABLE_IMPACTS:
        rec["killed_by"] = "G3 Panther impact gate"
        rec["reason"] = (f"impact class '{cand.get('impact_class')}' is not one of "
                         "the four payable classes (fund loss / freeze / "
                         "insolvency / core-function breakage)")
        return rec
    if cand.get("actor") in ("owner", "admin"):
        rec["killed_by"] = "G4 Panther trust model"
        rec["reason"] = ("only a trusted role can trigger this path — "
                         "non-payable under the program's trust model")
        return rec
    if v.get("result_status") == "empty" or not v.get("result"):
        rec["killed_by"] = "G5 awarexone template"
        rec["reason"] = ("RESULT is empty: the attacker goes home with nothing "
                         "and no quantified harm is shown — not a bug")
        return rec

    unvalidated = v.get("result_status") == "conditional"
    score = IMPACT_BASE[cand["impact_class"]]
    if cand.get("test_gap"):
        score += 15
    if cand.get("partly_fixed_surface"):
        score += 10
    if v.get("result_status") == "filled":
        score += 10
    score -= round(best_score * 20)
    if unvalidated:
        score -= 15
    rec.update({
        "verdict": "UNVALIDATED" if unvalidated else "SURVIVE",
        "rank_score": score,
        "gate_decision": "warn",
        "reason": ("survives all kill gates; RESULT is conditional on an "
                   "unproven reachability premise, so it is flagged "
                   "UNVALIDATED and its PoC must prove reachability first"
                   if unvalidated else
                   "survives all kill gates with a complete validation "
                   "template; next gate is a runnable PoC (Layer 4)"),
    })
    return rec


def rank(out_dir: Path, threshold: float = 0.30) -> tuple[list, list]:
    engine = _load_dup_engine()
    known = engine.load_known(out_dir / "known_issues.txt")
    known_tokens = [(k, engine.tokenise(k)) for k in known]
    cands = [json.loads(line) for line in
             (out_dir / "candidates.jsonl").read_text(encoding="utf-8").splitlines()
             if line.strip()]

    survivors, killed = [], []
    for c in cands:
        rec = evaluate(c, known_tokens, engine, threshold)
        if rec.get("killed_by"):
            killed.append({**c, **rec, "gate_decision": "block"})
        else:
            survivors.append({**c, **rec})
    survivors.sort(key=lambda s: -s["rank_score"])
    for i, s in enumerate(survivors, 1):
        s["rank"] = i

    with (out_dir / "survivors.jsonl").open("w", encoding="utf-8") as fh:
        for s in survivors:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    (out_dir / "triage_report.md").write_text(
        render_report(survivors, killed, threshold), encoding="utf-8")
    return survivors, killed


def _template_block(c: dict) -> str:
    v = c.get("validation", {})
    rows = [("SETUP", v.get("setup", "")), ("CALL", v.get("call", "")),
            ("RESULT", v.get("result", "")), ("COST", v.get("cost", "")),
            ("DETECT", v.get("detect", "")), ("NET ROI", v.get("net_roi", ""))]
    return "\n".join(f"  - **{k}:** {val}" for k, val in rows)


def render_report(survivors: list, killed: list, threshold: float) -> str:
    lines = [
        "# Bountybot triage report — Plether (Immunefi audit competition)",
        "",
        "Frozen commit `a82d4fefb02768e5b3bddcc97dee371eee24fea8` · scope "
        "`packages/perps/src` · generated by `pipeline.py` (Layers 1–3).",
        "",
        "**Every entry below is a hypothesis, not a bug claim.** A candidate "
        "becomes a finding only after a runnable PoC passes at the frozen "
        "commit (Layer 4) — that step is separate and still in testing.",
        "",
        f"## Survivors — {len(survivors)} (PoC priority order)",
        "",
    ]
    for s in survivors:
        lines += [
            f"### #{s['rank']} {s['id']} — {s['title']}",
            f"- **Verdict:** {s['verdict']} · rank score {s['rank_score']} · "
            f"signing gate: `{s['gate_decision']}`",
            f"- **Impact class (Panther):** {s['impact_class']} · "
            f"actor: {s['actor']} · known-issue overlap: "
            f"{s["known_issue_max_score"]:.3f} (< {threshold})",
            f"- **Locations:** {'; '.join(s['locations'])}",
            f"- **Why it survived:** {s['reason']}",
            f"- **Test coverage:** {s.get('test_note', '')}",
            "- **Validation template (awarexone):**",
            _template_block(s),
            "",
        ]
    lines += [f"## Killed — {len(killed)} (the gates doing their job)", ""]
    for k in killed:
        lines += [
            f"### {k['id']} — {k['title']}",
            f"- **Killed by:** {k['killed_by']} · signing gate: `block`",
            f"- **Reason:** {k['reason']}",
            f"- Known-issue overlap: {k["known_issue_max_score"]:.3f}"
            + (f" — closest: “{k['closest_known_issue']}”"
               if k["known_issue_max_score"] > 0 else ""),
            "",
        ]
    lines += [
        "## Signing-gate summary (input to the NEAR policy wrapper)",
        "",
        "| Candidate | Gate | Meaning |",
        "|---|---|---|",
    ]
    for s in survivors:
        lines.append(f"| {s['id']} | warn | No signature without human review; "
                     "PoC still required |")
    for k in killed:
        lines.append(f"| {k['id']} | block | Wrapper must refuse to sign "
                     "anything based on this candidate |")
    lines += ["", "_No candidate is `allow`: allow requires a passing PoC "
              "AND an explicit human order (Layers 4–5)._", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "demo_output"))
    ap.add_argument("--threshold", type=float, default=0.30)
    args = ap.parse_args()
    survivors, killed = rank(Path(args.out), args.threshold)
    print(f"[skeptic] survivors={len(survivors)} killed={len(killed)}")
    for s in survivors:
        print(f"[skeptic]   #{s['rank']} {s['id']:<4} {s['verdict']:<11} "
              f"score={s['rank_score']:<3} gate=warn :: {s['title'][:72]}")
    for k in killed:
        print(f"[skeptic]   KILL {k['id']:<4} {k['killed_by']:<26} "
              f"gate=block :: {k['title'][:60]}")
    print(f"[skeptic] wrote survivors.jsonl + triage_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
