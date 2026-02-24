"""
Microsoft Defender Unified Security Client

Provides authenticated access to three API surfaces from a single client:
  1. Defender XDR / MDE unified API  (api.security.microsoft.com)
  2. Sentinel ARM API                (management.azure.com)
  3. Log Analytics query API         (api.loganalytics.io)

Authentication uses MSAL client_credentials for Security, ARM, and Log
Analytics token endpoints.  Tokens are cached independently and auto-refreshed.

Environment variables (set in docker-compose.yml / .env):
  AZURE_TENANT_ID          - Entra ID tenant ID
  DEFENDER_CLIENT_ID       - App registration client ID
  DEFENDER_CLIENT_SECRET   - App registration client secret
  SENTINEL_SUBSCRIPTION_ID - Azure subscription containing the workspace
  SENTINEL_RESOURCE_GROUP  - Resource group containing the workspace
  SENTINEL_WORKSPACE_NAME  - Log Analytics workspace name
  SENTINEL_WORKSPACE_ID    - Log Analytics workspace GUID (for queries)
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("DEFENDER_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DEFENDER_CLIENT_SECRET", "")

SENTINEL_SUBSCRIPTION_ID = os.getenv("SENTINEL_SUBSCRIPTION_ID", "")
SENTINEL_RESOURCE_GROUP = os.getenv("SENTINEL_RESOURCE_GROUP", "")
SENTINEL_WORKSPACE_NAME = os.getenv("SENTINEL_WORKSPACE_NAME", "")
SENTINEL_WORKSPACE_ID = os.getenv("SENTINEL_WORKSPACE_ID", "")

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

XDR_SCOPE = "https://api.security.microsoft.com/.default"
XDR_BASE = "https://api.security.microsoft.com"

MDE_SCOPE = "https://api.securitycenter.microsoft.com/.default"
MDE_BASE = "https://api.securitycenter.microsoft.com"

ARM_SCOPE = "https://management.azure.com/.default"
ARM_BASE = "https://management.azure.com"

SENTINEL_API_VERSION = "2024-09-01"

LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io/.default"
LOG_ANALYTICS_BASE = "https://api.loganalytics.io/v1"

TOKEN_REFRESH_BUFFER = 300


class DefenderClient:
    """Unified client for Defender XDR, MDE, Sentinel, and Log Analytics."""

    def __init__(self):
        self.tenant_id = TENANT_ID
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET

        if not all([self.tenant_id, self.client_id, self.client_secret]):
            print(
                "ERROR: Missing Defender credentials.\n\n"
                "Required environment variables:\n"
                "  AZURE_TENANT_ID\n"
                "  DEFENDER_CLIENT_ID\n"
                "  DEFENDER_CLIENT_SECRET\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self._tokens: dict[str, dict] = {}
        self.session = requests.Session()

    # ── Token Management ───────────────────────────────────────────────

    def _get_token(self, scope: str) -> str:
        """Obtain or refresh an MSAL client_credentials token for the given scope."""
        now = time.time()
        cached = self._tokens.get(scope)
        if cached and now < cached["expires_at"]:
            return cached["token"]

        resp = requests.post(
            TOKEN_URL.format(tenant=self.tenant_id),
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": scope,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(
                f"ERROR: Token request failed for {scope} "
                f"({resp.status_code}): {resp.text}",
                file=sys.stderr,
            )
            sys.exit(1)

        data = resp.json()
        self._tokens[scope] = {
            "token": data["access_token"],
            "expires_at": now + data.get("expires_in", 3600) - TOKEN_REFRESH_BUFFER,
        }
        return data["access_token"]

    def _xdr_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token(XDR_SCOPE)}",
            "Content-Type": "application/json",
        }

    def _mde_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token(MDE_SCOPE)}",
            "Content-Type": "application/json",
        }

    def _arm_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token(ARM_SCOPE)}",
            "Content-Type": "application/json",
        }

    def _la_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token(LOG_ANALYTICS_SCOPE)}",
            "Content-Type": "application/json",
        }

    # ── Core HTTP ──────────────────────────────────────────────────────

    def _request(
        self, method: str, url: str, headers_fn, **kwargs
    ) -> requests.Response:
        max_retries = 3
        resp = None
        for attempt in range(max_retries):
            kwargs["headers"] = headers_fn()
            resp = self.session.request(method, url, timeout=120, **kwargs)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                print(f"  Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue

            if resp.status_code == 401:
                for scope_key in list(self._tokens):
                    del self._tokens[scope_key]
                continue

            return resp

        return resp

    # ── Defender XDR API (incidents, advanced hunting) ────────────────

    def security_get(self, path: str, params: dict = None) -> requests.Response:
        url = f"{XDR_BASE}{path}" if path.startswith("/") else f"{XDR_BASE}/{path}"
        return self._request("GET", url, self._xdr_headers, params=params)

    def security_post(self, path: str, json_data: dict = None) -> requests.Response:
        url = f"{XDR_BASE}{path}" if path.startswith("/") else f"{XDR_BASE}/{path}"
        return self._request("POST", url, self._xdr_headers, json=json_data)

    def security_patch(self, path: str, json_data: dict = None) -> requests.Response:
        url = f"{XDR_BASE}{path}" if path.startswith("/") else f"{XDR_BASE}/{path}"
        return self._request("PATCH", url, self._xdr_headers, json=json_data)

    def security_delete(self, path: str) -> requests.Response:
        url = f"{XDR_BASE}{path}" if path.startswith("/") else f"{XDR_BASE}/{path}"
        return self._request("DELETE", url, self._xdr_headers)

    # ── MDE API (machines, vulnerabilities, indicators) ────────────

    def mde_get(self, path: str, params: dict = None) -> requests.Response:
        url = f"{MDE_BASE}{path}" if path.startswith("/") else f"{MDE_BASE}/{path}"
        return self._request("GET", url, self._mde_headers, params=params)

    def mde_post(self, path: str, json_data: dict = None) -> requests.Response:
        url = f"{MDE_BASE}{path}" if path.startswith("/") else f"{MDE_BASE}/{path}"
        return self._request("POST", url, self._mde_headers, json=json_data)

    def mde_patch(self, path: str, json_data: dict = None) -> requests.Response:
        url = f"{MDE_BASE}{path}" if path.startswith("/") else f"{MDE_BASE}/{path}"
        return self._request("PATCH", url, self._mde_headers, json=json_data)

    def mde_delete(self, path: str) -> requests.Response:
        url = f"{MDE_BASE}{path}" if path.startswith("/") else f"{MDE_BASE}/{path}"
        return self._request("DELETE", url, self._mde_headers)

    # ── Sentinel ARM API ───────────────────────────────────────────────

    def _sentinel_base(self) -> str:
        return (
            f"{ARM_BASE}/subscriptions/{SENTINEL_SUBSCRIPTION_ID}"
            f"/resourceGroups/{SENTINEL_RESOURCE_GROUP}"
            f"/providers/Microsoft.OperationalInsights/workspaces/{SENTINEL_WORKSPACE_NAME}"
            f"/providers/Microsoft.SecurityInsights"
        )

    def sentinel_get(self, resource: str, params: dict = None) -> requests.Response:
        url = f"{self._sentinel_base()}/{resource}"
        params = params or {}
        params["api-version"] = SENTINEL_API_VERSION
        return self._request("GET", url, self._arm_headers, params=params)

    def sentinel_put(self, resource: str, json_data: dict) -> requests.Response:
        url = f"{self._sentinel_base()}/{resource}"
        params = {"api-version": SENTINEL_API_VERSION}
        return self._request("PUT", url, self._arm_headers, params=params, json=json_data)

    def sentinel_delete(self, resource: str) -> requests.Response:
        url = f"{self._sentinel_base()}/{resource}"
        params = {"api-version": SENTINEL_API_VERSION}
        return self._request("DELETE", url, self._arm_headers, params=params)

    def sentinel_post(self, resource: str, json_data: dict = None) -> requests.Response:
        url = f"{self._sentinel_base()}/{resource}"
        params = {"api-version": SENTINEL_API_VERSION}
        return self._request("POST", url, self._arm_headers, params=params, json=json_data)

    # ── Log Analytics Query ────────────────────────────────────────────

    def query_logs(self, kql: str, timespan: str = "P1D") -> dict:
        """Execute a KQL query against the Log Analytics workspace."""
        url = f"{LOG_ANALYTICS_BASE}/workspaces/{SENTINEL_WORKSPACE_ID}/query"
        body = {"query": kql, "timespan": timespan}
        resp = self._request("POST", url, self._la_headers, json=body)
        if resp.status_code != 200:
            return {"error": resp.status_code, "message": resp.text}
        return resp.json()

    # ── Pagination Helpers ─────────────────────────────────────────────

    def security_get_all(
        self, path: str, params: dict = None, top: int = 100, max_pages: int = 50
    ) -> list:
        """Paginate through XDR API results using @odata.nextLink."""
        results = []
        params = params or {}
        params.setdefault("$top", top)
        url = f"{XDR_BASE}{path}" if path.startswith("/") else f"{XDR_BASE}/{path}"

        for _ in range(max_pages):
            resp = self._request("GET", url, self._xdr_headers, params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            results.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            url = next_link
            params = {}

        return results

    def mde_get_all(
        self, path: str, params: dict = None, top: int = 100, max_pages: int = 50
    ) -> list:
        """Paginate through MDE API results using @odata.nextLink."""
        results = []
        params = params or {}
        params.setdefault("$top", top)
        url = f"{MDE_BASE}{path}" if path.startswith("/") else f"{MDE_BASE}/{path}"

        for _ in range(max_pages):
            resp = self._request("GET", url, self._mde_headers, params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            results.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            if not next_link:
                break
            url = next_link
            params = {}

        return results

    def sentinel_get_all(
        self, resource: str, params: dict = None, max_pages: int = 50
    ) -> list:
        """Paginate through Sentinel ARM API results."""
        results = []
        params = params or {}
        params["api-version"] = SENTINEL_API_VERSION
        url = f"{self._sentinel_base()}/{resource}"

        for _ in range(max_pages):
            resp = self._request("GET", url, self._arm_headers, params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            results.extend(data.get("value", []))
            next_link = data.get("nextLink")
            if not next_link:
                break
            url = next_link
            params = {}

        return results

    # ── Convenience: Advanced Hunting ──────────────────────────────────

    def advanced_hunt(self, query: str) -> dict:
        """Execute an advanced hunting KQL query via the unified XDR API."""
        resp = self.security_post("/api/advancedhunting/run", {"Query": query})
        if resp.status_code != 200:
            return {"error": resp.status_code, "message": resp.text}
        return resp.json()

    # ── Connection Tests ───────────────────────────────────────────────

    def test_security_api(self) -> dict:
        """Test connectivity to the Defender XDR API."""
        resp = self.security_get("/api/incidents", params={"$top": 1})
        return {"ok": resp.status_code == 200, "status": resp.status_code}

    def test_mde_api(self) -> dict:
        """Test connectivity to the MDE API."""
        resp = self.mde_get("/api/machines", params={"$top": 1})
        return {"ok": resp.status_code == 200, "status": resp.status_code}

    def test_sentinel_api(self) -> dict:
        """Test connectivity to the Sentinel ARM API."""
        resp = self.sentinel_get("incidents", params={"$top": 1})
        return {"ok": resp.status_code == 200, "status": resp.status_code}

    def test_log_analytics(self) -> dict:
        """Test KQL query against the workspace."""
        result = self.query_logs("print test='hello'", timespan="PT5M")
        return {"ok": "error" not in result, "result": result}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 defender_client.py test")
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    if cmd == "test":
        print("Testing Defender XDR / MDE API...")
        r = client.test_security_api()
        print(f"  Security API: {'OK' if r['ok'] else 'FAIL'} ({r['status']})")

        if SENTINEL_SUBSCRIPTION_ID:
            print("Testing Sentinel ARM API...")
            r = client.test_sentinel_api()
            print(f"  Sentinel API: {'OK' if r['ok'] else 'FAIL'} ({r['status']})")

            print("Testing Log Analytics query...")
            r = client.test_log_analytics()
            print(f"  Log Analytics: {'OK' if r['ok'] else 'FAIL'}")
        else:
            print("  Sentinel: SKIPPED (SENTINEL_SUBSCRIPTION_ID not set)")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
