#!/usr/bin/env python3
"""
server.py — Bountybot Triage Room backend (Python 3 standard library only).

Modes
-----
LIVE  (NEXCONN_APP_KEY + NEXCONN_APP_SECRET set in the server environment):
  tokens are issued through the signed Nexconn Server API, the triage
  group is created/joined server-side, and every pipeline event is
  broadcast into the group as a real Nexconn message from the engine's
  bot user. Human discussion/approvals happen in the same group via the
  Web Chat SDK in the browser.

DEMO  (no credentials configured):
  the full flow runs locally with the same engine and the same Gate;
  events are returned to the browser and rendered in a clearly labelled
  local preview. Nothing in demo mode is, or claims to be, a Nexconn
  message — it exists so the app can be evaluated before an App Key is
  provisioned.

The App Secret is used only inside nexconn_client.py on this server.
It is never sent to a browser and never logged.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from nexconn_client import NexconnClient, NexconnError
from triage_service import TriageService, USERS, GROUP_ID, GROUP_NAME

HERE = Path(__file__).resolve().parent
DIST = HERE.parent / "dist"

CLIENT = NexconnClient.from_env()
MODE = "live" if CLIENT else "demo"
APP_KEY = os.environ.get("NEXCONN_APP_KEY", "")
TRIAGE = TriageService()

MSG_TYPES = {"candidate_card": "BB:CandidateCard",
             "verdict": "BB:Verdict",
             "approval": "BB:Approval"}


def broadcast(event: dict) -> None:
    """Live mode only: send one event into the group as the bot user."""
    if MODE != "live":
        return
    mtype = MSG_TYPES.get(event["type"], "BB:SystemNote")
    push = {
        "candidate_card": f"New candidate {event['candidate']['id']}",
        "verdict": f"Verdict {event.get('candidate_id')}: "
                   f"{event.get('decision')}",
        "approval": f"Approval {event.get('candidate_id')}: "
                    f"{event.get('verdict')}",
    }.get(event["type"], "Bountybot Triage Room event")
    CLIENT.send_group_message("bountybot", GROUP_ID, mtype,
                              json.dumps(event), push_content=push)


class Handler(BaseHTTPRequestHandler):
    # -- helpers ---------------------------------------------------------
    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def log_message(self, *args):  # keep stdout clean
        pass

    # -- API ---------------------------------------------------------------
    def do_GET(self):
        if self.path == "/api/config":
            return self._json(200, {
                "mode": MODE,
                "appKey": APP_KEY if MODE == "live" else None,
                "group": {"id": GROUP_ID, "name": GROUP_NAME},
                "users": USERS,
            })
        if self.path == "/api/status":
            return self._json(200, {"mode": MODE, **TRIAGE.status()})
        if self.path == "/api/log":
            return self._json(200, {"entries": TRIAGE.decision_log()})
        return self._static()

    def do_POST(self):
        try:
            return self._post()
        except NexconnError as exc:
            return self._json(502, {"error": f"nexconn: {exc}"})
        except Exception as exc:  # never leak a stack trace to the client
            return self._json(500, {"error": str(exc)})

    def _post(self):
        body = self._body()
        if self.path == "/api/token":
            user = body.get("user", "")
            if user not in USERS:
                return self._json(400, {"error": f"unknown user '{user}'"})
            if MODE == "demo":
                return self._json(200, {"user": user, "token": None,
                                        "demo": True})
            token = CLIENT.issue_token(user, USERS[user]["name"])
            return self._json(200, {"user": user, "token": token})

        if self.path == "/api/bootstrap":
            if MODE == "demo":
                return self._json(200, {"group": GROUP_ID, "demo": True})
            CLIENT.issue_token("bountybot", USERS["bountybot"]["name"])
            try:
                CLIENT.create_group(GROUP_ID, GROUP_NAME, "bountybot",
                                    [u for u in USERS if u != "bountybot"])
            except NexconnError:
                # Group already exists: make sure everyone is a member.
                CLIENT.join_group(GROUP_ID,
                                  [u for u in USERS if u != "bountybot"])
            return self._json(200, {"group": GROUP_ID})

        if self.path == "/api/run":
            events = TRIAGE.run_pipeline()
            for ev in events:
                broadcast(ev)
            return self._json(200, {"events": events})

        if self.path in ("/api/approve", "/api/reject"):
            actor = body.get("actor", "")
            cid = body.get("candidate_id", "")
            fn = TRIAGE.approve if self.path == "/api/approve" else TRIAGE.reject
            result = fn(actor, cid)
            broadcast({"type": "approval", **result})
            return self._json(200, result)

        if self.path == "/api/inject":
            result = TRIAGE.injection_demo()
            broadcast({"type": "verdict", "candidate_id": "INJ-1",
                       "decision": result["verdict"],
                       "gate": "gated_signer",
                       "reason": result["reason"]})
            return self._json(200, result)

        return self._json(404, {"error": "not found"})

    # -- static (production build) -----------------------------------------
    def _static(self):
        rel = self.path.split("?")[0].lstrip("/") or "index.html"
        target = (DIST / rel).resolve()
        if DIST.exists() and target.is_file() and \
                str(target).startswith(str(DIST.resolve())):
            ctype = {".html": "text/html", ".js": "text/javascript",
                     ".css": "text/css", ".svg": "image/svg+xml",
                     ".png": "image/png"}.get(target.suffix,
                                               "application/octet-stream")
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return self._json(404, {
            "error": "frontend not built — run `npm run build`, "
                     "or use `npm run dev` for development"})


def main() -> None:
    port = int(os.environ.get("PORT", "8787"))
    print(f"Bountybot Triage Room server — mode={MODE} port={port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
