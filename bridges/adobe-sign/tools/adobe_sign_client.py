#!/usr/bin/env python3
"""
Adobe Acrobat Sign REST API v6 Client

Provides authenticated access to Adobe Sign via Integration Key with
automatic base URI discovery, cursor pagination, and rate-limit handling.

Authentication uses a permanent Integration Key (Bearer token):
  - Authorization: Bearer <ADOBE_SIGN_INTEGRATION_KEY>
  - No token refresh required (keys do not expire unless revoked)

Environment variables (set in docker-compose.yml):
  ADOBE_SIGN_INTEGRATION_KEY  - Integration Key with required scopes
  ADOBE_SIGN_API_BASE         - Override API base URL (optional; auto-discovered)
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

import requests

# ── Configuration ──────────────────────────────────────────────────────

INTEGRATION_KEY = os.getenv("ADOBE_SIGN_INTEGRATION_KEY", "")
API_BASE_OVERRIDE = os.getenv("ADOBE_SIGN_API_BASE", "")
DISCOVERY_URL = "https://api.adobesign.com/api/rest/v6/baseUris"

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 100


class AdobeSignClient:
    """Adobe Sign REST API v6 client with pagination and rate limiting."""

    def __init__(self, integration_key: str = None):
        self.integration_key = integration_key or INTEGRATION_KEY

        if not self.integration_key:
            print(
                "ERROR: Missing Adobe Sign Integration Key.\n"
                "\n"
                "Required environment variable:\n"
                "  ADOBE_SIGN_INTEGRATION_KEY\n"
                "\n"
                "Generate from Adobe Sign:\n"
                "  Account > Personal Preferences > Access Tokens\n"
                "  Create an Integration Key with required scopes.\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self.session = requests.Session()
        self._api_base = API_BASE_OVERRIDE.rstrip("/") if API_BASE_OVERRIDE else None
        self._web_base = None

    # ── Auth ────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.integration_key}",
            "Content-Type": "application/json",
        }

    # ── Base URI Discovery ──────────────────────────────────────────────

    def _discover_base_uri(self) -> str:
        """Auto-discover the API base URI for this account's shard."""
        resp = self.session.get(
            DISCOVERY_URL,
            headers=self._auth_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        self._web_base = data.get("webAccessPoint", "").rstrip("/")
        api_access = data.get("apiAccessPoint", "").rstrip("/")
        if not api_access:
            raise RuntimeError("baseUris response missing apiAccessPoint")
        return f"{api_access}/api/rest/v6"

    @property
    def api_base(self) -> str:
        if not self._api_base:
            self._api_base = self._discover_base_uri()
        return self._api_base

    @property
    def web_base(self) -> str:
        if not self._web_base:
            self._discover_base_uri()
        return self._web_base or ""

    # ── Core HTTP Methods ──────────────────────────────────────────────

    def _request(self, method: str, path: str, params=None, json_body=None,
                 raw=False, **kwargs) -> requests.Response | dict:
        """
        Make an API request with auth, rate-limit retry, and retries.
        Returns parsed JSON by default, or raw Response if raw=True.
        """
        url = path if path.startswith("http") else f"{self.api_base}/{path.lstrip('/')}"
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.request(
                    method, url,
                    headers=self._auth_headers(),
                    params=params,
                    json=json_body,
                    timeout=REQUEST_TIMEOUT,
                    **kwargs,
                )

                if resp.status_code == 429:
                    retry_body = {}
                    try:
                        retry_body = resp.json()
                    except Exception:
                        pass
                    wait = retry_body.get("retryAfter",
                           int(resp.headers.get("Retry-After", 2)))
                    print(f"  Rate limited. Waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue

                if raw:
                    resp.raise_for_status()
                    return resp

                resp.raise_for_status()
                if resp.status_code == 204 or not resp.text:
                    return {}
                return resp.json()

            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)

        raise last_error

    def get(self, path: str, params: dict = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, data: dict = None) -> dict:
        return self._request("POST", path, json_body=data)

    def put(self, path: str, data: dict = None) -> dict:
        return self._request("PUT", path, json_body=data)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def get_raw(self, path: str, params: dict = None) -> requests.Response:
        return self._request("GET", path, params=params, raw=True)

    # ── Pagination ─────────────────────────────────────────────────────

    def get_all(self, path: str, list_key: str, params: dict = None,
                page_size: int = DEFAULT_PAGE_SIZE, max_pages: int = 100) -> list:
        """
        Paginate through all results for a list endpoint.

        Adobe Sign uses pageSize + cursor params. The response contains
        a list under `list_key` and pagination info under `page.nextCursor`.
        """
        params = dict(params or {})
        params["pageSize"] = page_size
        all_items = []

        for _ in range(max_pages):
            resp = self.get(path, params=params)
            items = resp.get(list_key, [])
            all_items.extend(items)

            next_cursor = resp.get("page", {}).get("nextCursor")
            if not next_cursor:
                break
            params["cursor"] = next_cursor

        return all_items

    # ── Agreements ─────────────────────────────────────────────────────

    def list_agreements(self, page_size: int = DEFAULT_PAGE_SIZE,
                        max_pages: int = 100) -> list:
        return self.get_all("/agreements", "userAgreementList",
                            page_size=page_size, max_pages=max_pages)

    def get_agreement(self, agreement_id: str) -> dict:
        return self.get(f"/agreements/{agreement_id}")

    def get_agreement_members(self, agreement_id: str) -> dict:
        return self.get(f"/agreements/{agreement_id}/members")

    def get_agreement_documents(self, agreement_id: str) -> list:
        resp = self.get(f"/agreements/{agreement_id}/documents")
        return resp.get("documents", [])

    def get_agreement_combined_document(self, agreement_id: str) -> bytes:
        """Download the combined signed PDF for an agreement."""
        resp = self.get_raw(f"/agreements/{agreement_id}/combinedDocument")
        return resp.content

    def get_agreement_audit_trail(self, agreement_id: str) -> bytes:
        """Download the audit trail PDF for an agreement."""
        resp = self.get_raw(f"/agreements/{agreement_id}/auditTrail")
        return resp.content

    def get_agreement_form_data(self, agreement_id: str) -> str:
        """Get form field data (CSV) from a completed agreement."""
        resp = self.get_raw(f"/agreements/{agreement_id}/formData")
        return resp.text

    def get_agreement_signing_urls(self, agreement_id: str) -> dict:
        return self.get(f"/agreements/{agreement_id}/signingUrls")

    def get_agreement_events(self, agreement_id: str) -> list:
        resp = self.get(f"/agreements/{agreement_id}/events")
        return resp.get("events", [])

    def get_agreement_reminders(self, agreement_id: str) -> list:
        resp = self.get(f"/agreements/{agreement_id}/reminders")
        return resp.get("reminderInfoList", resp.get("participantEmailSetInfos", []))

    def create_agreement(self, agreement_info: dict) -> dict:
        """
        Create and send an agreement.

        agreement_info should include fileInfos, name, participantSetsInfo,
        signatureType, and state.
        """
        return self.post("/agreements", data=agreement_info)

    def cancel_agreement(self, agreement_id: str) -> dict:
        return self.put(f"/agreements/{agreement_id}/state", data={
            "state": "CANCELLED",
        })

    def send_agreement_reminder(self, agreement_id: str, message: str = "") -> dict:
        body = {}
        if message:
            body["note"] = message
        return self.post(f"/agreements/{agreement_id}/reminders", data=body)

    # ── Transient Documents ────────────────────────────────────────────

    def upload_transient_document(self, file_path: str,
                                  mime_type: str = "application/pdf") -> str:
        """
        Upload a file as a transient document (valid ~7 days).
        Returns the transientDocumentId.
        """
        url = f"{self.api_base}/transientDocuments"
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            resp = self.session.post(
                url,
                headers={"Authorization": f"Bearer {self.integration_key}"},
                files={"File": (filename, f, mime_type)},
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json().get("transientDocumentId", "")

    # ── Library Documents (Templates) ──────────────────────────────────

    def list_library_documents(self, page_size: int = DEFAULT_PAGE_SIZE,
                                max_pages: int = 100) -> list:
        return self.get_all("/libraryDocuments", "libraryDocumentList",
                            page_size=page_size, max_pages=max_pages)

    def get_library_document(self, library_document_id: str) -> dict:
        return self.get(f"/libraryDocuments/{library_document_id}")

    # ── Widgets (Web Forms) ────────────────────────────────────────────

    def list_widgets(self, page_size: int = DEFAULT_PAGE_SIZE,
                     max_pages: int = 100) -> list:
        return self.get_all("/widgets", "userWidgetList",
                            page_size=page_size, max_pages=max_pages)

    def get_widget(self, widget_id: str) -> dict:
        return self.get(f"/widgets/{widget_id}")

    def get_widget_form_data(self, widget_id: str) -> str:
        """Get form submission data (CSV) from a web form."""
        resp = self.get_raw(f"/widgets/{widget_id}/formData")
        return resp.text

    def get_widget_agreements(self, widget_id: str) -> list:
        resp = self.get(f"/widgets/{widget_id}/agreements")
        return resp.get("userAgreementList", [])

    # ── Users ──────────────────────────────────────────────────────────

    def list_users(self, page_size: int = DEFAULT_PAGE_SIZE,
                   max_pages: int = 100) -> list:
        return self.get_all("/users", "userInfoList",
                            page_size=page_size, max_pages=max_pages)

    def get_user(self, user_id: str) -> dict:
        return self.get(f"/users/{user_id}")

    def get_user_groups(self, user_id: str) -> list:
        resp = self.get(f"/users/{user_id}/groups")
        return resp.get("groupInfoList", [])

    # ── Webhooks ───────────────────────────────────────────────────────

    def list_webhooks(self, page_size: int = DEFAULT_PAGE_SIZE,
                      max_pages: int = 100) -> list:
        return self.get_all("/webhooks", "userWebhookList",
                            page_size=page_size, max_pages=max_pages)

    def get_webhook(self, webhook_id: str) -> dict:
        return self.get(f"/webhooks/{webhook_id}")

    def create_webhook(self, name: str, url: str, scope: str = "ACCOUNT",
                       events: list = None) -> dict:
        events = events or ["AGREEMENT_ALL"]
        return self.post("/webhooks", data={
            "name": name,
            "scope": scope,
            "webhookSubscriptionEvents": events,
            "webhookUrlInfo": {"url": url},
            "state": "ACTIVE",
        })

    def delete_webhook(self, webhook_id: str) -> dict:
        return self.delete(f"/webhooks/{webhook_id}")

    # ── Workflows ──────────────────────────────────────────────────────

    def list_workflows(self) -> list:
        resp = self.get("/workflows")
        return resp.get("userWorkflowList", [])

    # ── Connection Test ────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Validate Integration Key and report account summary."""
        try:
            _ = self.api_base
            users = self.list_users(page_size=1, max_pages=1)
            agreements_resp = self.get("/agreements", params={"pageSize": 1})
            templates_resp = self.get("/libraryDocuments", params={"pageSize": 1})

            return {
                "ok": True,
                "api_base": self._api_base,
                "web_base": self._web_base,
                "users_accessible": len(users) > 0,
                "agreements_accessible": "userAgreementList" in agreements_resp,
                "templates_accessible": "libraryDocumentList" in templates_resp,
            }
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Utility ────────────────────────────────────────────────────────

    def find_user_by_email(self, email: str) -> dict | None:
        users = self.list_users()
        email_lower = email.lower()
        for u in users:
            if u.get("email", "").lower() == email_lower:
                return u
        return None

    def find_template_by_name(self, name: str) -> dict | None:
        templates = self.list_library_documents()
        name_lower = name.lower()
        for t in templates:
            if name_lower in t.get("name", "").lower():
                return t
        return None


# ── CLI Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = AdobeSignClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)

    elif action == "agreements":
        agreements = client.list_agreements(page_size=10, max_pages=1)
        print(f"Recent agreements ({len(agreements)} shown):")
        for a in agreements:
            status = a.get("status", "?")
            name = a.get("name", "Untitled")
            print(f"  [{status:20s}] {name}")

    elif action == "templates":
        templates = client.list_library_documents(page_size=50, max_pages=1)
        print(f"Library documents ({len(templates)} shown):")
        for t in templates:
            print(f"  {t.get('name', 'Untitled')}")

    elif action == "users":
        users = client.list_users(page_size=50, max_pages=1)
        print(f"Users ({len(users)} shown):")
        for u in users:
            email = u.get("email", "?")
            name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip()
            print(f"  {name:30s}  {email}")

    elif action == "widgets":
        widgets = client.list_widgets(page_size=50, max_pages=1)
        print(f"Web forms ({len(widgets)} shown):")
        for w in widgets:
            status = w.get("status", "?")
            name = w.get("name", "Untitled")
            print(f"  [{status:10s}] {name}")

    elif action == "webhooks":
        webhooks = client.list_webhooks(page_size=50, max_pages=1)
        print(f"Webhooks ({len(webhooks)} shown):")
        for w in webhooks:
            name = w.get("name", "Untitled")
            scope = w.get("scope", "?")
            print(f"  [{scope:10s}] {name}")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 adobe_sign_client.py [test|agreements|templates|users|widgets|webhooks]")
        sys.exit(1)
