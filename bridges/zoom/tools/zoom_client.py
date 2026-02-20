"""
Zoom REST API v2 Client (Server-to-Server OAuth)

Provides authenticated access to the Zoom API for the tenant (configured
via ZOOM_ACCOUNT_ID; e.g., example.zoom.us) with automatic token refresh, pagination, and
rate-limit handling.

Authentication uses Zoom's Server-to-Server OAuth flow:
  - POST https://zoom.us/oauth/token with grant_type=account_credentials
  - Tokens are valid for 1 hour
  - Tokens are cached and auto-refreshed 5 minutes before expiry

Environment variables (set in docker-compose.yml):
  ZOOM_ACCOUNT_ID    - Zoom account ID from S2S app
  ZOOM_CLIENT_ID     - Client ID from S2S app
  ZOOM_CLIENT_SECRET - Client secret from S2S app
"""

import os
import sys
import time
import base64
import json
import requests
from pathlib import Path
from dotenv import load_dotenv


# Load .env for non-secret config. load_dotenv does NOT override existing
# env vars, so Docker-injected values always take precedence.
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID", "")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID", "")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET", "")

TOKEN_URL = "https://zoom.us/oauth/token"
API_BASE = "https://api.zoom.us/v2"

# Refresh tokens 5 minutes before expiry to avoid mid-request failures
TOKEN_REFRESH_BUFFER_SECS = 300


class ZoomClient:
    """Zoom REST API v2 client with S2S OAuth token management."""

    def __init__(
        self,
        account_id: str = None,
        client_id: str = None,
        client_secret: str = None,
    ):
        self.account_id = account_id or ZOOM_ACCOUNT_ID
        self.client_id = client_id or ZOOM_CLIENT_ID
        self.client_secret = client_secret or ZOOM_CLIENT_SECRET

        if not all([self.account_id, self.client_id, self.client_secret]):
            print(
                "ERROR: Missing Zoom S2S OAuth credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  ZOOM_ACCOUNT_ID\n"
                "  ZOOM_CLIENT_ID\n"
                "  ZOOM_CLIENT_SECRET\n"
                "\n"
                "Create a Server-to-Server OAuth app at:\n"
                "  https://marketplace.zoom.us/develop/create\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self._access_token = None
        self._token_expires_at = 0
        self.session = requests.Session()

    # ── OAuth Token Management ─────────────────────────────────────────

    def _get_token(self) -> str:
        """Obtain or refresh the S2S OAuth access token."""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        auth_str = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "account_credentials",
                "account_id": self.account_id,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(
                f"ERROR: Token request failed ({resp.status_code}): {resp.text}",
                file=sys.stderr,
            )
            sys.exit(1)

        token_data = resp.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = now + expires_in - TOKEN_REFRESH_BUFFER_SECS

        return self._access_token

    def _auth_headers(self) -> dict:
        """Return headers with a valid Bearer token."""
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── Core HTTP Methods ──────────────────────────────────────────────

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make an API request with auth, rate-limit retry, and token refresh."""
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        max_retries = 3

        for attempt in range(max_retries):
            kwargs["headers"] = self._auth_headers()
            resp = self.session.request(method, url, timeout=60, **kwargs)

            # Rate limited -- respect Retry-After header
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue

            # Token expired mid-flight (shouldn't happen with buffer, but handle it)
            if resp.status_code == 401:
                self._access_token = None
                self._token_expires_at = 0
                continue

            return resp

        return resp

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("POST", endpoint, json=json_data)

    def patch(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PATCH", endpoint, json=json_data)

    def put(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("DELETE", endpoint, params=params)

    # ── Pagination Helper ──────────────────────────────────────────────

    def get_all(
        self,
        endpoint: str,
        key: str,
        params: dict = None,
        page_size: int = 300,
        max_pages: int = 100,
    ) -> list:
        """
        Paginate through all results for a list endpoint.

        Zoom uses `next_page_token` for cursor-based pagination.
        `key` is the JSON key containing the array (e.g., 'users', 'meetings').
        """
        params = dict(params or {})
        params["page_size"] = min(page_size, 300)
        results = []
        next_page_token = ""

        for _ in range(max_pages):
            if next_page_token:
                params["next_page_token"] = next_page_token

            resp = self.get(endpoint, params=params)
            if resp.status_code != 200:
                print(f"  Error fetching {endpoint}: {resp.status_code} {resp.text}")
                break

            data = resp.json()
            items = data.get(key, [])
            results.extend(items)

            next_page_token = data.get("next_page_token", "")
            if not next_page_token:
                break

        return results

    # ── Users ──────────────────────────────────────────────────────────

    def list_users(self, status: str = "active", params: dict = None) -> list:
        """List all users in the account. status: active, inactive, pending."""
        p = dict(params or {})
        p["status"] = status
        return self.get_all("users", "users", params=p)

    def get_user(self, user_id: str = "me") -> dict:
        """Get a single user's profile. user_id can be email or Zoom user ID."""
        resp = self.get(f"users/{user_id}")
        resp.raise_for_status()
        return resp.json()

    def create_user(self, data: dict) -> dict:
        """Create a new user. data must include action and user_info."""
        resp = self.post("users", json_data=data)
        if resp.status_code not in (200, 201):
            print(f"  Error creating user: {resp.status_code} {resp.text}")
        return resp.json()

    def update_user(self, user_id: str, data: dict) -> dict:
        """Update a user's profile."""
        resp = self.patch(f"users/{user_id}", json_data=data)
        if resp.status_code != 204:
            return {"error": resp.status_code, "body": resp.text}
        return {"ok": True}

    def delete_user(self, user_id: str, action: str = "disassociate") -> dict:
        """Remove a user. action: disassociate (remove) or delete (permanent)."""
        resp = self.delete(f"users/{user_id}", params={"action": action})
        if resp.status_code != 204:
            return {"error": resp.status_code, "body": resp.text}
        return {"ok": True}

    def get_user_settings(self, user_id: str) -> dict:
        resp = self.get(f"users/{user_id}/settings")
        resp.raise_for_status()
        return resp.json()

    # ── Meetings ───────────────────────────────────────────────────────

    def list_meetings(self, user_id: str = "me", meeting_type: str = "scheduled") -> list:
        """List meetings for a user. type: scheduled, live, upcoming, previous_meetings."""
        return self.get_all(
            f"users/{user_id}/meetings",
            "meetings",
            params={"type": meeting_type},
        )

    def get_meeting(self, meeting_id: int) -> dict:
        resp = self.get(f"meetings/{meeting_id}")
        resp.raise_for_status()
        return resp.json()

    def create_meeting(self, user_id: str, data: dict) -> dict:
        """Create a meeting for a user."""
        resp = self.post(f"users/{user_id}/meetings", json_data=data)
        if resp.status_code not in (200, 201):
            print(f"  Error creating meeting: {resp.status_code} {resp.text}")
        return resp.json()

    def update_meeting(self, meeting_id: int, data: dict) -> dict:
        resp = self.patch(f"meetings/{meeting_id}", json_data=data)
        if resp.status_code != 204:
            return {"error": resp.status_code, "body": resp.text}
        return {"ok": True}

    def delete_meeting(self, meeting_id: int) -> dict:
        resp = self.delete(f"meetings/{meeting_id}")
        if resp.status_code != 204:
            return {"error": resp.status_code, "body": resp.text}
        return {"ok": True}

    def list_meeting_participants(self, meeting_id: int) -> list:
        """List participants from a past meeting instance."""
        return self.get_all(
            f"past_meetings/{meeting_id}/participants",
            "participants",
        )

    # ── Recordings ─────────────────────────────────────────────────────

    def list_recordings(self, user_id: str, from_date: str = None, to_date: str = None) -> list:
        """
        List cloud recordings for a user.
        Dates in YYYY-MM-DD format. Defaults to last 30 days if not specified.
        """
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self.get_all(
            f"users/{user_id}/recordings",
            "meetings",
            params=params,
        )

    def get_meeting_recordings(self, meeting_id: int) -> dict:
        resp = self.get(f"meetings/{meeting_id}/recordings")
        resp.raise_for_status()
        return resp.json()

    def delete_meeting_recordings(self, meeting_id: int, action: str = "trash") -> dict:
        """Delete recordings. action: trash (recoverable) or delete (permanent)."""
        resp = self.delete(
            f"meetings/{meeting_id}/recordings",
            params={"action": action},
        )
        if resp.status_code != 204:
            return {"error": resp.status_code, "body": resp.text}
        return {"ok": True}

    # ── Dashboard ──────────────────────────────────────────────────────

    def dashboard_meetings(self, from_date: str, to_date: str, meeting_type: str = "past") -> list:
        """Dashboard meeting data. Requires dashboard_meetings:read:admin scope."""
        return self.get_all(
            "metrics/meetings",
            "meetings",
            params={"type": meeting_type, "from": from_date, "to": to_date},
        )

    def dashboard_meeting_detail(self, meeting_id: int) -> dict:
        resp = self.get(f"metrics/meetings/{meeting_id}")
        resp.raise_for_status()
        return resp.json()

    def dashboard_meeting_participants(self, meeting_id: int) -> list:
        return self.get_all(
            f"metrics/meetings/{meeting_id}/participants",
            "participants",
        )

    # ── Reports ────────────────────────────────────────────────────────

    def report_daily(self, year: int = None, month: int = None) -> dict:
        """Daily usage report for the account."""
        params = {}
        if year:
            params["year"] = year
        if month:
            params["month"] = month
        resp = self.get("report/daily", params=params)
        resp.raise_for_status()
        return resp.json()

    def report_users(self, from_date: str, to_date: str) -> list:
        """Active/inactive hosts report."""
        return self.get_all(
            "report/users",
            "users",
            params={"from": from_date, "to": to_date},
        )

    def report_meetings(self, user_id: str, from_date: str, to_date: str) -> list:
        """Meeting report for a specific user."""
        return self.get_all(
            f"report/users/{user_id}/meetings",
            "meetings",
            params={"from": from_date, "to": to_date},
        )

    def report_operation_logs(self, from_date: str, to_date: str) -> list:
        """Operation logs (admin audit trail)."""
        return self.get_all(
            "report/operationlogs",
            "operation_logs",
            params={"from": from_date, "to": to_date},
        )

    # ── Groups ─────────────────────────────────────────────────────────

    def list_groups(self) -> list:
        resp = self.get("groups")
        resp.raise_for_status()
        return resp.json().get("groups", [])

    def get_group(self, group_id: str) -> dict:
        resp = self.get(f"groups/{group_id}")
        resp.raise_for_status()
        return resp.json()

    def list_group_members(self, group_id: str) -> list:
        return self.get_all(f"groups/{group_id}/members", "members")

    # ── Zoom Phone ─────────────────────────────────────────────────────

    def phone_list_users(self) -> list:
        """List Zoom Phone users. Requires phone:read:admin scope."""
        return self.get_all("phone/users", "users")

    def phone_list_call_queues(self) -> list:
        return self.get_all("phone/call_queues", "call_queues")

    def phone_user_call_logs(
        self, user_id: str, from_date: str, to_date: str
    ) -> list:
        """Call logs for a specific phone user."""
        return self.get_all(
            f"phone/users/{user_id}/call_logs",
            "call_logs",
            params={"from": from_date, "to": to_date},
        )

    def phone_account_call_logs(self, from_date: str, to_date: str) -> list:
        """Account-wide call logs."""
        return self.get_all(
            "phone/call_logs",
            "call_logs",
            params={"from": from_date, "to": to_date},
        )

    # ── Zoom Phone: Department Workflows ─────────────────────────────

    def phone_department(self, department_name: str) -> dict:
        """
        Get the complete phone infrastructure for a department in one call:
        auto attendant(s), call queue(s) with members, and individual user extensions.

        Returns a clean dict with 'users', 'auto_attendants', and 'call_queues'.
        """
        name_lower = department_name.lower()

        all_users = self.get_all("/phone/users", key="users", page_size=100)
        users = [u for u in all_users if name_lower in (u.get("department") or "").lower()]

        aa_resp = self.get("/phone/auto_receptionists", params={"page_size": 100})
        aas = [
            a for a in aa_resp.json().get("auto_receptionists", [])
            if name_lower in (a.get("name") or "").lower()
        ]

        cq_resp = self.get("/phone/call_queues", params={"page_size": 100})
        queues = []
        for q in cq_resp.json().get("call_queues", []):
            if name_lower in (q.get("name") or "").lower():
                detail = self.get(f"/phone/call_queues/{q['id']}").json()
                q["members"] = detail.get("members", {}).get("users", [])
                queues.append(q)

        return {
            "department": department_name,
            "users": [
                {
                    "name": u["name"],
                    "ext": u.get("extension_number"),
                    "did": next((n["number"] for n in u.get("phone_numbers", [])), None),
                    "email": u.get("email"),
                }
                for u in users
            ],
            "auto_attendants": [
                {
                    "name": a["name"],
                    "ext": a.get("extension_number"),
                    "did": next((n["number"] for n in a.get("phone_numbers", [])), None),
                }
                for a in aas
            ],
            "call_queues": [
                {
                    "name": q["name"],
                    "ext": q.get("extension_number"),
                    "id": q["id"],
                    "members": [m.get("name") for m in q.get("members", [])],
                }
                for q in queues
            ],
        }

    def phone_recordings(
        self,
        from_date: str,
        to_date: str = None,
        department: str = None,
        owner: str = None,
    ) -> list:
        """
        Get phone call recordings from the account-level endpoint.

        IMPORTANT: Call queue recordings are owned by the queue, not individual
        users. This method uses /phone/recordings (account-level) which captures
        both user and call queue recordings. Never use /phone/users/{id}/recordings
        if you want call queue recordings.

        Optionally filter by department name or owner name (matched against
        the recording's owner.name field).

        Returns a list of clean dicts with only the fields needed for analysis.
        """
        to_date = to_date or from_date
        all_recs = self.get_all(
            "/phone/recordings",
            key="recordings",
            params={"from": from_date, "to": to_date},
            page_size=300,
        )

        if department or owner:
            filtered = []
            dept_lower = (department or "").lower()
            owner_lower = (owner or "").lower()
            for r in all_recs:
                rec_owner = (
                    r.get("owner", {}).get("name", "")
                    if isinstance(r.get("owner"), dict)
                    else ""
                )
                accepted_name = (
                    r.get("accepted_by", {}).get("name", "")
                    if isinstance(r.get("accepted_by"), dict)
                    else ""
                )
                if dept_lower and (
                    dept_lower in rec_owner.lower() or dept_lower in accepted_name.lower()
                ):
                    filtered.append(r)
                elif owner_lower and (
                    owner_lower in rec_owner.lower() or owner_lower in accepted_name.lower()
                ):
                    filtered.append(r)
            all_recs = filtered

        return [
            {
                "id": r.get("id"),
                "time": r.get("date_time"),
                "direction": r.get("direction"),
                "caller": r.get("caller_name", r.get("caller_number")),
                "caller_number": r.get("caller_number"),
                "callee": r.get("callee_name", r.get("callee_number")),
                "duration": r.get("duration", 0),
                "answered_by": (
                    r.get("accepted_by", {}).get("name")
                    if isinstance(r.get("accepted_by"), dict)
                    else None
                ),
                "owner": (
                    r.get("owner", {}).get("name")
                    if isinstance(r.get("owner"), dict)
                    else None
                ),
                "has_transcript": bool(r.get("transcript_download_url")),
                "transcript_url": r.get("transcript_download_url"),
            }
            for r in all_recs
        ]

    def phone_transcript(self, transcript_url: str) -> list:
        """
        Download and parse a call transcript into clean speaker:text pairs.

        Strips the QA disclaimer lines and all metadata noise (avatar_url,
        client_type, channel_mark, word_items, etc.). Returns only what
        matters: who said what.

        Returns a list of {'speaker': str, 'text': str} dicts.
        """
        token = self._get_token()
        resp = requests.get(
            transcript_url,
            headers={"Authorization": f"Bearer {token}"},
            allow_redirects=True,
            timeout=30,
        )
        if resp.status_code != 200:
            return [{"speaker": "ERROR", "text": f"HTTP {resp.status_code}"}]

        DISCLAIMER_PHRASES = {
            "this call may be monitored or recorded for quality assurance and training purposes.",
            "this call may be monitored or recorded for quality assurance or training purposes.",
            "this call may be monitored.",
            "monitored.",
            "are recorded for quality.",
            "quality assurance and training purposes.",
            "or recorded for quality assurance and training purposes.",
            "the call may.",
        }

        data = resp.json()
        lines = []
        for entry in data.get("timeline", []):
            text = entry.get("text", "").strip()
            if text.lower() in DISCLAIMER_PHRASES:
                continue
            speaker = (
                entry.get("users", [{}])[0].get("username", "?")
                if entry.get("users")
                else "?"
            )
            lines.append({"speaker": speaker, "text": text})
        return lines

    # ── Account ────────────────────────────────────────────────────────

    def get_account_settings(self) -> dict:
        resp = self.get("accounts/me/settings")
        resp.raise_for_status()
        return resp.json()

    def get_account_info(self) -> dict:
        resp = self.get("accounts/me")
        resp.raise_for_status()
        return resp.json()

    # ── Zoom Rooms ─────────────────────────────────────────────────────

    def list_rooms(self) -> list:
        return self.get_all("rooms", "rooms")

    def get_room(self, room_id: str) -> dict:
        resp = self.get(f"rooms/{room_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Webinars ───────────────────────────────────────────────────────

    def list_webinars(self, user_id: str) -> list:
        return self.get_all(f"users/{user_id}/webinars", "webinars")

    def get_webinar(self, webinar_id: int) -> dict:
        resp = self.get(f"webinars/{webinar_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Utility ────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """
        Health check: fetch current account info to validate credentials
        and confirm API access.
        """
        try:
            user = self.get_user("me")
            account = self.get_account_info()
            return {
                "ok": True,
                "account_id": account.get("id"),
                "account_name": account.get("account_name"),
                "owner_email": account.get("owner_email"),
                "vanity_url": account.get("vanity_url"),
                "plan": account.get("plan_base", {}).get("type", "unknown"),
                "authenticated_as": user.get("email", "unknown"),
            }
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ─────────────────────────────────────────────────────
# Allows quick testing: python3 zoom_client.py test

if __name__ == "__main__":
    import json as _json

    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = ZoomClient()

    if action == "test":
        result = client.test_connection()
        print(_json.dumps(result, indent=2))

    elif action == "users":
        users = client.list_users()
        print(f"Total users: {len(users)}")
        for u in users:
            license_type = {1: "Basic", 2: "Licensed", 3: "On-Prem"}.get(
                u.get("type"), str(u.get("type"))
            )
            print(f"  {u['email']:40s}  {license_type:10s}  {u.get('status', '')}")

    elif action == "account":
        info = client.get_account_info()
        print(_json.dumps(info, indent=2))

    elif action == "groups":
        groups = client.list_groups()
        print(f"Total groups: {len(groups)}")
        for g in groups:
            print(f"  {g['name']:30s}  members={g.get('total_members', '?')}")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 zoom_client.py [test|users|account|groups]")
        sys.exit(1)
