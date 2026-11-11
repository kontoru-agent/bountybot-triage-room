#!/usr/bin/env python3
"""
Bountybot — scope/check_known_issues.py

Purpose (Layer 1 -> Layer 3 gate):
    Flag a candidate finding as a likely DUPLICATE of a program's known-issues
    list *before* any PoC work or report drafting. In audit competitions
    (e.g. Plether on Immunefi) findings that match public known issues are
    ineligible and pay nothing — submitting them is pure AI slop.

Method (deliberately simple, deterministic, no LLM, no network):
    - Tokenise title+description of each finding and each known issue.
    - Lower-case, strip punctuation, drop a small English stopword list and
      tokens shorter than 3 chars.
    - Score = Jaccard(token sets) blended with containment
      (intersection / min(set sizes)), which catches a short known-issue
      title fully contained in a longer finding description.
    - score >= threshold  -> DUPLICATE-CANDIDATE (needs human / skeptic review)
      score <  threshold  -> CLEAR (on this check only; skeptic layer still runs)

Input formats:
    findings file : entries separated by a line containing only '---'
                    first line of an entry = title, rest = description
    known file    : one known issue per line (blank lines and '#' comments ignored)

Usage:
    python3 check_known_issues.py [--findings F] [--known K] [--threshold 0.30]

Defaults point at the bundled examples/ so it runs out of the box.
Exit code: 0 = no duplicate candidates, 2 = at least one duplicate candidate.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STOPWORDS = {
    "the", "and", "for", "with", "can", "may", "when", "from", "that", "this",
    "are", "was", "were", "will", "would", "could", "should", "into", "onto",
    "per", "via", "not", "but", "all", "any", "its", "it", "in", "on", "of",
    "to", "a", "an", "is", "be", "by", "or", "at", "as", "if", "no",
}

HERE = Path(__file__).resolve().parent


def tokenise(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return {t for t in tokens if len(t) >= 3 and t not in STOPWORDS}


def score(finding_tokens: set[str], known_tokens: set[str]) -> float:
    if not finding_tokens or not known_tokens:
        return 0.0
    inter = len(finding_tokens & known_tokens)
    union = len(finding_tokens | known_tokens)
    jaccard = inter / union if union else 0.0
    containment = inter / min(len(finding_tokens), len(known_tokens))
    return round(0.5 * jaccard + 0.5 * containment, 4)


def load_findings(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    entries = [e.strip() for e in raw.split("\n---\n") if e.strip()]
    findings = []
    for e in entries:
        lines = e.splitlines()
        findings.append({"title": lines[0].strip(),
                         "text": " ".join(lines).strip()})
    return findings


def load_known(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", default=str(HERE / "examples" / "findings.txt"))
    ap.add_argument("--known", default=str(HERE / "examples" / "known_issues.txt"))
    ap.add_argument("--threshold", type=float, default=0.30)
    args = ap.parse_args()

    findings = load_findings(Path(args.findings))
    known = load_known(Path(args.known))
    known_tokens = [(k, tokenise(k)) for k in known]

    print(f"findings={len(findings)} known_issues={len(known)} threshold={args.threshold}")
    flagged = 0
    for f in findings:
        ft = tokenise(f["text"])
        best_text, best_score = "", 0.0
        for k_text, kt in known_tokens:
            s = score(ft, kt)
            if s > best_score:
                best_text, best_score = k_text, s
        verdict = "DUPLICATE-CANDIDATE" if best_score >= args.threshold else "CLEAR"
        if verdict == "DUPLICATE-CANDIDATE":
            flagged += 1
        print(f"[{verdict}] score={best_score:.2f} finding={f['title']!r}")
        if verdict == "DUPLICATE-CANDIDATE":
            print(f"    closest known issue: {best_text!r}")
    print(f"result: {flagged} duplicate candidate(s), {len(findings) - flagged} clear")
    return 2 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
