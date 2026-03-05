# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Teams Client -- Graph API client for tenant-wide message reads and
localhost bot server API wrapper for proactive messaging.

Graph API permissions (application):
  - ChatMessage.Read.All
  - ChannelMessage.Read.All
  - Team.ReadBasic.All
  - Channel.ReadBasic.All
"""

import json
import os
import sys
import time
from typing import Any

import msal
import requests

try:
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"


class TeamsClient:
    """Unified client for Graph API reads and bot server proactive sends."""

    def __init__(self):
        self.tenant_id = os.environ.get("TEAMS_BOT_TENANT_ID", "")
        self.app_id = os.environ.get("TEAMS_BOT_APP_ID", "")
        self.app_secret = os.environ.get("TEAMS_BOT_APP_SECRET", "")
        self.bot_name = os.environ.get("TEAMS_BOT_NAME", "Tendril Bot")
        self.bot_mode = os.environ.get("TEAMS_BOT_MODE", "webhook")
        self.bot_port = int(os.environ.get("TEAMS_BOT_PORT", 3978))

        if not all([self.tenant_id, self.app_id, self.app_secret]):
            raise ValueError(
                "TEAMS_BOT_TENANT_ID, TEAMS_BOT_APP_ID, and "
                "TEAMS_BOT_APP_SECRET must all be set"
            )

        self._msal_app = msal.ConfidentialClientApplication(
            self.app_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.app_secret,
        )
        self._token_cache: dict = {}
        self._session = requests.Session()

    # ── Token Management ──────────────────────────────────────────

    def _get_token(self) -> str:
        now = time.time()
        if self._token_cache.get("expires_at", 0) > now + 60:
            return self._token_cache["access_token"]

        result = self._msal_app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Token acquisition failed: {result.get('error_description', result)}"
            )

        self._token_cache = {
            "access_token": result["access_token"],
            "expires_at": now + result.get("expires_in", 3600),
        }
        return result["access_token"]

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    # ── Graph API Helpers ─────────────────────────────────────────

    def get(self, endpoint: str, params: dict | None = None, beta: bool = False) -> requests.Response:
        base = GRAPH_BETA if beta else GRAPH_BASE
        url = f"{base}/{endpoint}" if not endpoint.startswith("http") else endpoint
        return self._session.get(url, headers=self._headers(), params=params)

    def get_all(self, endpoint: str, top: int = 100, beta: bool = False) -> list:
        """Paginated GET returning all items."""
        items = []
        params = {"$top": top}
        base = GRAPH_BETA if beta else GRAPH_BASE
        url = f"{base}/{endpoint}"

        while url:
            resp = self._session.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None
        return items

    # ── Teams / Channels ──────────────────────────────────────────

    def list_teams(self, top: int = 999) -> list:
        return self.get_all("teams", top=top)

    def get_team(self, team_id: str) -> dict:
        resp = self.get(f"teams/{team_id}")
        resp.raise_for_status()
        return resp.json()

    def list_channels(self, team_id: str) -> list:
        resp = self.get(f"teams/{team_id}/channels")
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_channel(self, team_id: str, channel_id: str) -> dict:
        resp = self.get(f"teams/{team_id}/channels/{channel_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Channel Messages (Graph API) ─────────────────────────────

    def list_channel_messages(
        self, team_id: str, channel_id: str, top: int = 50
    ) -> list:
        return self.get_all(
            f"teams/{team_id}/channels/{channel_id}/messages", top=top
        )

    def get_channel_message(
        self, team_id: str, channel_id: str, message_id: str
    ) -> dict:
        resp = self.get(
            f"teams/{team_id}/channels/{channel_id}/messages/{message_id}"
        )
        resp.raise_for_status()
        return resp.json()

    def list_message_replies(
        self, team_id: str, channel_id: str, message_id: str, top: int = 50
    ) -> list:
        return self.get_all(
            f"teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
            top=top,
        )

    # ── Chat Messages (Graph API) ────────────────────────────────
    # App-only access requires user-scoped endpoints:
    #   /users/{user-id}/chats  (Chat.Read.All + User.Read.All)
    #   /chats/{chat-id}/messages  (ChatMessage.Read.All)

    def list_users(self, top: int = 100) -> list:
        return self.get_all("users", top=top)

    def list_user_chats(self, user_id: str, top: int = 50) -> list:
        """List chats for a specific user (app-only: Chat.Read.All + User.Read.All)."""
        return self.get_all(f"users/{user_id}/chats", top=top)

    def get_chat(self, chat_id: str) -> dict:
        resp = self.get(f"chats/{chat_id}")
        resp.raise_for_status()
        return resp.json()

    def list_chat_messages(self, chat_id: str, top: int = 50) -> list:
        return self.get_all(f"chats/{chat_id}/messages", top=top)

    def get_chat_message(self, chat_id: str, message_id: str) -> dict:
        resp = self.get(f"chats/{chat_id}/messages/{message_id}")
        resp.raise_for_status()
        return resp.json()

    def list_chat_members(self, chat_id: str) -> list:
        resp = self.get(f"chats/{chat_id}/members")
        resp.raise_for_status()
        return resp.json().get("value", [])

    # ── Bot Server API (localhost) ────────────────────────────────

    def bot_health(self) -> dict:
        """Check bot server health (webhook mode only)."""
        try:
            resp = requests.get(
                f"http://localhost:{self.bot_port}/api/health", timeout=5
            )
            return resp.json()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def bot_conversations(self) -> dict:
        """List conversation references from bot server."""
        try:
            resp = requests.get(
                f"http://localhost:{self.bot_port}/api/conversations", timeout=5
            )
            return resp.json()
        except Exception as exc:
            return {"error": str(exc)}

    def bot_send(self, conversation_id: str, message: str) -> dict:
        """Send proactive message via bot server."""
        try:
            resp = requests.post(
                f"http://localhost:{self.bot_port}/api/send",
                json={"conversation_id": conversation_id, "message": message},
                timeout=15,
            )
            return resp.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ── Connection Test ───────────────────────────────────────────

    def test_connection(self) -> dict:
        """Validate Graph API access and optionally bot server health."""
        result: dict[str, Any] = {"graph_api": False, "bot_server": None}

        try:
            resp = self.get("teams", params={"$top": 1})
            if resp.status_code == 200:
                result["graph_api"] = True
                result["teams_accessible"] = True
            elif resp.status_code == 403:
                result["graph_api"] = True
                result["teams_accessible"] = False
                result["note"] = "Token valid but Team.ReadBasic.All may be missing"
            else:
                result["error"] = f"Graph API returned {resp.status_code}"
        except Exception as exc:
            result["error"] = str(exc)

        if self.bot_mode == "webhook":
            result["bot_server"] = self.bot_health()

        return result


if __name__ == "__main__":
    client = TeamsClient()
    result = client.test_connection()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("graph_api") else 1)
