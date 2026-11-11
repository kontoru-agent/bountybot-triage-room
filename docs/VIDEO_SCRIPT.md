# Video script — Bountybot Triage Room demo (±2–3 min)

Record from the LIVE app (live URL, two browser windows side by side:
left = lead, right = reviewer). Voiceover or captions; keep it honest —
no sped-up fake typing, no staged data beyond the real engine output.

| Time | Screen | Narration |
|---|---|---|
| 0:00 | Title + one line | "AI bug hunting produces verdicts nobody can audit. This is the room where those verdicts happen — in chat, on Nexconn." |
| 0:15 | Both windows join `#triage-plether` as lead / reviewer | "Two researchers, one channel. Tokens are issued by our backend — the App Secret never touches a browser." |
| 0:35 | Click **Run pipeline** (left window) | "The engine runs against a real frozen scope — Plether on Immunefi. Eight candidates enter the room as structured Nexconn messages…" |
| 0:50 | Cards + verdicts stream into BOTH windows | "…and the skeptic gates announce themselves: five blocked — two are re-worded duplicates of published known issues, the classic AI slop — and three held at warn. Hypotheses, not bug claims." |
| 1:25 | Reviewer types a real question about K-1 in chat | "Humans discuss in the same channel. The discussion is part of the audit trail." |
| 1:45 | Reviewer clicks Approve on K-1 → stays WARN | "A reviewer can't release a candidate. The policy gate holds it." |
| 2:00 | Lead clicks Approve on K-1 → ALLOW; decision log updates | "The lead can. Allow means: released for a human submission order. Bountybot never submits on its own — and every decision lands in the log." |
| 2:20 | Click **Injection demo** → BLOCK | "A chat note ordering the agent to sign a transfer and hide it? Treated as data. Blocked by construction — and logged anyway." |
| 2:40 | Show repo + live URL | "Real SDK usage end to end: tokens, group channel, custom message types, server-side broadcasts. Links below." |

Checklist before upload: watchable via public link (YouTube unlisted /
Loom / Drive share), captions legible on mobile, no App Secret or
console credentials visible in any frame.
