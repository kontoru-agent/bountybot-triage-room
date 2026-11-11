#!/usr/bin/env python3
"""
nexconn_client.py — minimal signed client for the Nexconn Platform Chat API
(Server API). Python 3 standard library only.

Implements exactly the documented surface this app needs:
  * POST /v4/auth/access-token/issue        -> register user / get token
  * POST /v4/group-channel/create           -> create the triage group
  * POST /v4/group-channel/join             -> add members
  * POST /v4/group-channel/message/send     -> bot broadcasts into the group

Signature: SHA1(AppSecret + Nonce + Timestamp), sent as headers
App-Key / Nonce / Timestamp / Signature.
Docs: https://docs.nexconn.ai/platform-chat-api/prepare-to-use-api/auth
      https://docs.nexconn.ai/platform-chat-api/user/register
      https://docs.nexconn.ai/platform-chat-api/message/send-group

The App Secret is read from the server environment ONLY. It never leaves
this module and is never returned to a client.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import urllib.request
import urllib.error

# Data-center base URLs (docs: prepare-to-use-api/base-url).
# Singapore is the default: closest data center to this app's users.
BASE_URLS = {
    "sg": ("api.sg-light-api.com", "api-b.sg-light-api.com"),
    "us": ("api.us-light-api.com", "api-b.us-light-api.com"),
    "sau": ("api.sau-light-api.com", "api-b.sau-light-api.com"),
}


class NexconnError(RuntimeError):
    pass


class NexconnClient:
    def __init__(self, app_key: str, app_secret: str, dc: str = "sg"):
        if dc not in BASE_URLS:
            raise NexconnError(f"unknown data center '{dc}'")
        self.app_key = app_key
        self.app_secret = app_secret
        self.hosts = BASE_URLS[dc]
        self._host_idx = 0

    @classmethod
    def from_env(cls) -> "NexconnClient | None":
        key = os.environ.get("NEXCONN_APP_KEY", "").strip()
        secret = os.environ.get("NEXCONN_APP_SECRET", "").strip()
        if not key or not secret:
            return None
        return cls(key, secret, os.environ.get("NEXCONN_DC", "sg").strip() or "sg")

    # -- transport ------------------------------------------------------
    def _headers(self) -> dict:
        nonce = str(secrets.randbelow(10**12))
        timestamp = str(int(time.time() * 1000))
        signature = hashlib.sha1(
            f"{self.app_secret}{nonce}{timestamp}".encode()).hexdigest()
        return {
            "App-Key": self.app_key,
            "Nonce": nonce,
            "Timestamp": timestamp,
            "Signature": signature,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        last_err: Exception | None = None
        # Primary host, then one failover to the backup host (docs guidance).
        for attempt in range(2):
            host = self.hosts[self._host_idx]
            req = urllib.request.Request(
                f"https://{host}{path}", data=data,
                headers=self._headers(), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    payload = json.loads(resp.read().decode())
                if payload.get("code") != 0:
                    raise NexconnError(
                        f"{path} -> code {payload.get('code')}: {payload}")
                return payload
            except (urllib.error.URLError, TimeoutError, NexconnError) as exc:
                last_err = exc
                self._host_idx = 1 - self._host_idx  # switch primary/backup
        raise NexconnError(f"{path} failed on both hosts: {last_err}")

    # -- API surface ----------------------------------------------------
    def issue_token(self, user_id: str, name: str) -> str:
        payload = self._post("/v4/auth/access-token/issue",
                             {"userId": user_id, "name": name})
        return payload["result"]["accessToken"]

    def create_group(self, channel_id: str, name: str, owner: str,
                     user_ids: list[str]) -> dict:
        return self._post("/v4/group-channel/create", {
            "channelId": channel_id,
            "name": name,
            "owner": owner,
            "userIds": user_ids,
            "permissions": {"joinPerm": 1, "memInvitePerm": 2},
        })

    def join_group(self, channel_id: str, user_ids: list[str]) -> dict:
        return self._post("/v4/group-channel/join",
                          {"channelId": channel_id, "userIds": user_ids})

    def send_group_message(self, from_user: str, channel_id: str,
                           message_type: str, content: str,
                           push_content: str = "") -> dict:
        body = {
            "fromUserId": from_user,
            "toChannelIds": [channel_id],
            "messageType": message_type,
            "content": content,
        }
        if push_content:
            body["pushContent"] = push_content
        return self._post("/v4/group-channel/message/send", body)
