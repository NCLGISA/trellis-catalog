"""
Sierra Wireless AirVantage REST API Client

Provides authenticated access to the AirVantage API for managing AirLink
cellular gateways via OAuth2 Client Credentials flow. Handles automatic
token acquisition/refresh, pagination, and rate limiting.

API endpoints:
  - Systems:    /api/v1/systems         (inventory, status, data)
  - Gateways:   /api/v1/gateways        (hardware, IMEI, serial)
  - Alert Rules: /api/v2/alertrules     (rule definitions)
  - Alerts:     /api/v3/alerts/current  (active alert states)
  - Alerts:     /api/v3/alerts/history  (alert event log)

Environment variables (set in docker-compose.yml or .env):
  AIRLINK_CLIENT_ID      - OAuth2 client ID
  AIRLINK_CLIENT_SECRET  - OAuth2 client secret
  AIRLINK_REGION         - Datacenter region: na (default) or eu
"""

import os
import sys
import json
import time
import base64
import requests
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

CLIENT_ID = os.getenv("AIRLINK_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AIRLINK_CLIENT_SECRET", "")
REGION = os.getenv("AIRLINK_REGION", "na")

REGIONS = {
    "na": "https://na.airvantage.net",
    "eu": "https://eu.airvantage.net",
}


class AirLinkClient:
    """AirVantage REST API client with OAuth2 Client Credentials token lifecycle."""

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        region: str = None,
    ):
        self.client_id = client_id or CLIENT_ID
        self.client_secret = client_secret or CLIENT_SECRET
        self.region = region or REGION

        if not self.client_id or not self.client_secret:
            print(
                "ERROR: Missing AirVantage credentials.\n"
                "\n"
                "Required environment variables:\n"
                "  AIRLINK_CLIENT_ID\n"
                "  AIRLINK_CLIENT_SECRET\n"
                "\n"
                "Create an API Client in AirVantage:\n"
                "  Develop > API Clients > New\n"
                "  Flow type: Client Credentials\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self.base_url = REGIONS.get(self.region, REGIONS["na"])
        self.session = requests.Session()
        self._access_token = None
        self._token_expires_at = 0

    # ── OAuth2 Token Management ──────────────────────────────────────────

    def _acquire_token(self):
        """Acquire access token via OAuth2 Client Credentials grant."""
        url = f"{self.base_url}/api/oauth/token"
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        resp = self.session.post(
            url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials",
            timeout=30,
        )

        if resp.status_code != 200:
            print(
                f"ERROR: Token acquisition failed: {resp.status_code} {resp.text[:300]}",
                file=sys.stderr,
            )
            sys.exit(1)

        data = resp.json()
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 86400)
        self._token_expires_at = time.time() + expires_in - 300

    def _ensure_token(self):
        """Ensure a valid access token is available."""
        if not self._access_token or time.time() >= self._token_expires_at:
            self._acquire_token()

    def get_token(self) -> str:
        """Return current access token, acquiring if necessary."""
        self._ensure_token()
        return self._access_token

    # ── Core HTTP Methods ────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
        }

    def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """Make an API request with auth and rate-limit retry."""
        url = (
            endpoint
            if endpoint.startswith("http")
            else f"{self.base_url}/{endpoint.lstrip('/')}"
        )
        max_retries = 3

        for attempt in range(max_retries):
            kwargs["headers"] = self._auth_headers()
            resp = self.session.request(method, url, timeout=60, **kwargs)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                print(f"  Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue

            if resp.status_code == 401 and attempt == 0:
                self._access_token = None
                continue

            return resp

        return resp

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("POST", endpoint, json=json_data)

    def put(self, endpoint: str, json_data: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json_data)

    def delete(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("DELETE", endpoint, params=params)

    # ── Pagination ───────────────────────────────────────────────────────

    def get_all(
        self,
        endpoint: str,
        params: dict = None,
        page_size: int = 100,
        max_items: int = 10000,
    ) -> list:
        """
        Paginate through all results using AirVantage offset/size pattern.

        Response format: { "items": [...], "count": N, "size": M, "offset": O }
        """
        params = dict(params or {})
        params["size"] = page_size
        results = []
        offset = 0

        while len(results) < max_items:
            params["offset"] = offset
            resp = self.get(endpoint, params=params)

            if resp.status_code != 200:
                print(
                    f"  Error fetching {endpoint}: {resp.status_code} {resp.text[:200]}",
                    file=sys.stderr,
                )
                break

            data = resp.json()
            items = data.get("items", [])
            results.extend(items)

            total = data.get("count", 0)
            if not items or len(results) >= total:
                break

            offset += len(items)

        return results

    # ── Systems ──────────────────────────────────────────────────────────

    def list_systems(self, fields: str = None, **filters) -> list:
        """List all systems. Pass AirVantage filter params as kwargs."""
        params = dict(filters)
        if fields:
            params["fields"] = fields
        return self.get_all("api/v1/systems", params=params)

    def get_system(self, uid: str) -> dict:
        """Get a single system by UID."""
        resp = self.get(f"api/v1/systems/{uid}")
        resp.raise_for_status()
        return resp.json()

    def get_system_data(self, uid: str, ids: str = None) -> dict:
        """Get last datapoints for a system. Pass comma-separated data IDs or omit for all."""
        params = {}
        if ids:
            params["ids"] = ids
        resp = self.get(f"api/v1/systems/{uid}/data", params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Gateways ─────────────────────────────────────────────────────────

    def list_gateways(self, fields: str = None, **filters) -> list:
        """List all gateways. Pass AirVantage filter params as kwargs."""
        params = dict(filters)
        if fields:
            params["fields"] = fields
        return self.get_all("api/v1/gateways", params=params)

    def get_gateway(self, uid: str) -> dict:
        """Get a single gateway by UID."""
        resp = self.get(f"api/v1/gateways/{uid}")
        resp.raise_for_status()
        return resp.json()

    # ── Alert Rules ──────────────────────────────────────────────────────

    def list_alert_rules(self) -> list:
        """List all alert rules."""
        resp = self.get("api/v2/alertrules")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("items", data) if isinstance(data, dict) else data
        return []

    def get_alert_rule(self, uid: str) -> dict:
        """Get a single alert rule by UID."""
        resp = self.get(f"api/v2/alertrules/{uid}")
        resp.raise_for_status()
        return resp.json()

    # ── Alerts ───────────────────────────────────────────────────────────

    def list_current_alerts(self, state: bool = True, **filters) -> list:
        """Get current alert states. Must filter by state, targetId, or targetType."""
        filters["state"] = str(state).lower()
        resp = self.get("api/v3/alerts/current", params=filters)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("items", []) if isinstance(data, dict) else []
        return []

    def get_company_id(self) -> str:
        """Discover the caller's company ID via token introspection."""
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        self._ensure_token()
        resp = self.session.post(
            f"{self.base_url}/api/oauth/introspect",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=f"token={self._access_token}",
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json().get("companyId", "")
        return ""

    def list_alert_history(self, **filters) -> list:
        """Get alert event history. Auto-discovers company ID if not provided."""
        if "company" not in filters:
            company = self.get_company_id()
            if company:
                filters["company"] = company
        resp = self.get("api/v3/alerts/history", params=filters)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("items", []) if isinstance(data, dict) else []
        return []

    # ── Utility ──────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Health check: validate token and basic API access."""
        try:
            self._acquire_token()
            result = {"ok": True, "region": self.region, "base_url": self.base_url}

            systems = self.list_systems(
                fields="uid,name,commStatus,lastCommDate"
            )
            result["system_count"] = len(systems)

            gateways = self.list_gateways(
                fields="uid,imei,serialNumber,type"
            )
            result["gateway_count"] = len(gateways)

            return result
        except requests.HTTPError as e:
            return {
                "ok": False,
                "error": str(e),
                "status": getattr(e.response, "status_code", None),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── CLI Entrypoint ──────────────────────────────────────────────────────

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "test"
    client = AirLinkClient()

    if action == "test":
        result = client.test_connection()
        print(json.dumps(result, indent=2, default=str))

    elif action == "systems":
        systems = client.list_systems(
            fields="uid,name,commStatus,lastCommDate,lifeCycleState"
        )
        print(f"Total systems: {len(systems)}")
        for s in systems:
            name = s.get("name", "?")
            comm = s.get("commStatus", "?")
            state = s.get("lifeCycleState", "?")
            print(f"  {name:40s}  comm={comm:10s}  state={state}")

    elif action == "gateways":
        gateways = client.list_gateways(
            fields="uid,imei,serialNumber,macAddress,type,state"
        )
        print(f"Total gateways: {len(gateways)}")
        for g in gateways:
            imei = g.get("imei", "?") or "?"
            serial = g.get("serialNumber", "?") or "?"
            gtype = g.get("type", "?") or "?"
            print(f"  IMEI={imei:20s}  SN={serial:20s}  type={gtype}")

    elif action == "token":
        token = client.get_token()
        print(f"Access token acquired (expires in ~24h)")

    else:
        print(f"Unknown action: {action}")
        print("Usage: python3 airlink_client.py [test|systems|gateways|token]")
        sys.exit(1)
