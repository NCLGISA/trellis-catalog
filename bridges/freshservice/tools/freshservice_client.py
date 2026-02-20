"""
Freshservice REST API v2 Client

Thin wrapper around the Freshservice API with auth, rate limiting, and
methods for tickets, assets, changes, asset types, relationships, and agents.

Authentication is per-operator via the Tendril credential vault.
The FRESHSERVICE_API_KEY environment variable is injected automatically
when commands are executed through Tendril. Each operator stores their
personal Freshservice API key using:

    bridge_credentials(action='set', bridge='freshservice-api',
                       key='api_key', value='<your-API-key>')
"""

import os
import sys
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv


# Load .env for FRESHSERVICE_DOMAIN (non-secret config).
# load_dotenv does NOT override existing env vars, so vault-injected
# FRESHSERVICE_API_KEY always takes precedence.
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)

FRESHSERVICE_API_KEY = os.getenv("FRESHSERVICE_API_KEY", "")
FRESHSERVICE_DOMAIN = os.getenv("FRESHSERVICE_DOMAIN", "")
BASE_URL = f"https://{FRESHSERVICE_DOMAIN}/api/v2"


class FreshserviceClient:
    """Freshservice REST API v2 client with automatic rate-limit handling."""

    def __init__(self, api_key: str = None, domain: str = None):
        self.api_key = api_key or FRESHSERVICE_API_KEY
        self.domain = domain or FRESHSERVICE_DOMAIN

        if not self.api_key:
            operator = os.getenv("TENDRIL_OPERATOR", "unknown")
            print(
                "ERROR: No Freshservice API key available.\n"
                "\n"
                f"Operator '{operator}' does not have a Freshservice API key\n"
                "stored in the Tendril credential vault.\n"
                "\n"
                "Store your Freshservice API key (found in Freshservice under\n"
                "Profile > Profile Settings > API Key):\n"
                "\n"
                "  bridge_credentials(action='set', bridge='freshservice-api',\n"
                "                     key='api_key', value='<your-API-key>')\n",
                file=sys.stderr,
            )
            sys.exit(1)

        self.base_url = f"https://{self.domain}/api/v2"
        # Freshservice uses Basic auth with api_key as username and "X" as password
        self.auth = (self.api_key, "X")
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    # ── Core HTTP Methods ──────────────────────────────────────────────

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an API request with automatic rate-limit retry."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        max_retries = 3
        for attempt in range(max_retries):
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 30))
                print(f"  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            return resp
        return resp  # Return last response even if still rate-limited

    def get(self, endpoint: str, params: dict = None) -> requests.Response:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json: dict = None) -> requests.Response:
        return self._request("POST", endpoint, json=json)

    def put(self, endpoint: str, json: dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json)

    def delete(self, endpoint: str) -> requests.Response:
        return self._request("DELETE", endpoint)

    # ── Pagination Helper ──────────────────────────────────────────────

    def get_all(self, endpoint: str, key: str, params: dict = None) -> list:
        """
        Paginate through all results for a list endpoint.
        `key` is the JSON key containing the array (e.g. 'assets', 'changes').
        """
        params = dict(params or {})
        params.setdefault("per_page", 100)
        page = 1
        results = []
        while True:
            params["page"] = page
            resp = self.get(endpoint, params=params)
            if resp.status_code != 200:
                print(f"  Error fetching {endpoint} page {page}: {resp.status_code}")
                break
            data = resp.json()
            items = data.get(key, [])
            if not items:
                break
            results.extend(items)
            page += 1
        return results

    # ── Tickets ────────────────────────────────────────────────────────

    def create_ticket(self, data: dict) -> dict:
        resp = self.post("tickets", json=data)
        if resp.status_code not in (200, 201):
            print(f"  Error creating ticket: {resp.status_code} {resp.text}")
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    def update_ticket(self, ticket_id: int, data: dict) -> dict:
        resp = self.put(f"tickets/{ticket_id}", json=data)
        if resp.status_code != 200:
            print(f"  Error updating ticket {ticket_id}: {resp.status_code} {resp.text}")
        return resp.json() if resp.status_code == 200 else {"error": resp.text}

    def get_ticket(self, ticket_id: int) -> dict:
        resp = self.get(f"tickets/{ticket_id}")
        resp.raise_for_status()
        return resp.json().get("ticket", {})

    def list_tickets(self, params: dict = None) -> list:
        return self.get_all("tickets", "tickets", params=params)

    # ── Assets / CMDB ──────────────────────────────────────────────────

    def list_assets(self, params: dict = None) -> list:
        return self.get_all("assets", "assets", params=params)

    def get_asset(self, asset_id: int) -> dict:
        resp = self.get(f"assets/{asset_id}")
        resp.raise_for_status()
        return resp.json().get("asset", {})

    def search_assets(self, query: str) -> list:
        """Search assets using Freshservice query language.
        Example: query='name:"IS01S064"'
        """
        return self.get_all("assets", "assets", params={"query": query})

    def find_asset_by_name(self, name: str) -> dict | None:
        """Find asset by exact name. Tries the filter API first, then falls
        back to a case-insensitive paginated scan if the filter misses it."""
        resp = self.get("assets", params={"filter": f"\"name:'{name}'\""})
        assets = resp.json().get("assets", []) if resp.status_code == 200 else []
        if assets:
            return assets[0]
        target = name.lower()
        for asset in self.get_all("assets", "assets"):
            if (asset.get("name") or "").lower() == target:
                return asset
        return None

    def create_asset(self, data: dict) -> dict:
        resp = self.post("assets", json=data)
        if resp.status_code not in (200, 201):
            print(f"  Error creating asset: {resp.status_code} {resp.text}")
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    def update_asset(self, asset_id: int, data: dict) -> dict:
        resp = self.put(f"assets/{asset_id}", json=data)
        if resp.status_code != 200:
            print(f"  Error updating asset {asset_id}: {resp.status_code} {resp.text}")
        return resp.json() if resp.status_code == 200 else {"error": resp.text}

    def filter_assets(self, query: str) -> list:
        """Filter assets. Example: query=\"asset_type_id:27000XXXXX\" """
        return self.get_all("assets/filter", "assets", params={"query": f'"{query}"'})

    # ── Asset Types ────────────────────────────────────────────────────

    def list_asset_types(self) -> list:
        return self.get_all("asset_types", "asset_types")

    def get_asset_type(self, type_id: int) -> dict:
        resp = self.get(f"asset_types/{type_id}")
        resp.raise_for_status()
        return resp.json().get("asset_type", {})

    def list_asset_type_fields(self, asset_type_id: int) -> list:
        """Returns flat list of fields across all sections."""
        resp = self.get(f"asset_types/{asset_type_id}/fields")
        if resp.status_code != 200:
            return []
        sections = resp.json().get("asset_type_fields", [])
        # API returns sections with nested fields
        flat = []
        for section in sections:
            if isinstance(section, dict) and "fields" in section:
                for f in section["fields"]:
                    f["_section"] = section.get("field_header", "")
                    flat.append(f)
            elif isinstance(section, dict):
                flat.append(section)
        return flat

    def list_asset_type_fields_raw(self, asset_type_id: int) -> list:
        """Returns raw sectioned response from the API."""
        resp = self.get(f"asset_types/{asset_type_id}/fields")
        if resp.status_code != 200:
            return []
        return resp.json().get("asset_type_fields", [])

    # ── Asset Relationships ────────────────────────────────────────────

    def list_asset_relationships(self, asset_id: int) -> list:
        resp = self.get(f"assets/{asset_id}/relationships")
        if resp.status_code != 200:
            return []
        return resp.json().get("relationships", [])

    def create_asset_relationship(self, asset_id: int, data: dict) -> dict:
        resp = self.post(f"assets/{asset_id}/relationships", json=data)
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    def create_relationships_bulk(self, relationships: list) -> dict:
        """Create relationships via async bulk-create endpoint.

        Returns the job result after polling for completion.
        ``relationships`` is a list of dicts, each with:
            relationship_type_id, primary_id, primary_type,
            secondary_id, secondary_type.
        """
        import time as _time
        resp = self.post("relationships/bulk-create",
                         json={"relationships": relationships})
        if resp.status_code not in (200, 201, 202):
            return {"error": resp.text, "results": []}

        body = resp.json()
        job_id = body.get("job_id")
        if not job_id:
            # Synchronous response (unlikely but handle)
            return body

        # Poll for job completion (max ~30s)
        for wait in (1, 2, 3, 5, 5, 5, 5, 5):
            _time.sleep(wait)
            job_resp = self.get(f"jobs/{job_id}")
            if job_resp.status_code != 200:
                continue
            job_data = job_resp.json()
            if job_data.get("status") in ("success", "completed", "failed"):
                return job_data
        # Timeout -- return last known state
        return job_data if job_data else {"error": "Job poll timeout", "results": []}

    # ── Changes ────────────────────────────────────────────────────────

    def list_changes(self, params: dict = None) -> list:
        return self.get_all("changes", "changes", params=params)

    def get_change(self, change_id: int) -> dict:
        resp = self.get(f"changes/{change_id}")
        resp.raise_for_status()
        return resp.json().get("change", {})

    def create_change(self, data: dict) -> dict:
        resp = self.post("changes", json=data)
        if resp.status_code not in (200, 201):
            print(f"  Error creating change: {resp.status_code} {resp.text}")
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    def update_change(self, change_id: int, data: dict) -> dict:
        resp = self.put(f"changes/{change_id}", json=data)
        if resp.status_code != 200:
            print(f"  Error updating change {change_id}: {resp.status_code} {resp.text}")
        return resp.json() if resp.status_code == 200 else {"error": resp.text}

    def delete_change(self, change_id: int) -> bool:
        """Delete a change request. Returns True on success."""
        resp = self.delete(f"changes/{change_id}")
        if resp.status_code not in (200, 204):
            print(f"  Error deleting change {change_id}: {resp.status_code} {resp.text}")
            return False
        return True

    def list_change_fields(self) -> list:
        resp = self.get("change_form_fields")
        if resp.status_code != 200:
            return []
        return resp.json().get("change_form_fields", [])

    # ── Change Notes ───────────────────────────────────────────────────

    def create_change_note(self, change_id: int, body: str) -> dict:
        resp = self.post(f"changes/{change_id}/notes", json={"body": body})
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    def list_change_notes(self, change_id: int) -> list:
        return self.get_all(f"changes/{change_id}/notes", "notes")

    # ── Change Tasks ───────────────────────────────────────────────────

    def create_change_task(self, change_id: int, data: dict) -> dict:
        resp = self.post(f"changes/{change_id}/tasks", json=data)
        return resp.json() if resp.status_code in (200, 201) else {"error": resp.text}

    def list_change_tasks(self, change_id: int) -> list:
        return self.get_all(f"changes/{change_id}/tasks", "tasks")

    # ── Agents / Requesters ────────────────────────────────────────────

    def list_agents(self, params: dict = None) -> list:
        return self.get_all("agents", "agents", params=params)

    def get_agent(self, agent_id: int) -> dict:
        resp = self.get(f"agents/{agent_id}")
        resp.raise_for_status()
        return resp.json().get("agent", {})

    def find_agent_by_email(self, email: str) -> dict | None:
        """Find an agent by email address. Returns None if not found."""
        resp = self.get("agents", params={"query": f"email:'{email}'"})
        agents = resp.json().get("agents", []) if resp.status_code == 200 else []
        return agents[0] if agents else None

    def list_requesters(self, params: dict = None) -> list:
        return self.get_all("requesters", "requesters", params=params)

    def find_requester_by_email(self, email: str) -> dict | None:
        """Find a requester by email address. Returns None if not found.
        Note: if creating a ticket, passing the email directly will
        auto-create the requester if they do not exist."""
        resp = self.get("requesters", params={"query": f"email:'{email}'"})
        reqs = resp.json().get("requesters", []) if resp.status_code == 200 else []
        return reqs[0] if reqs else None

    # ── Departments ────────────────────────────────────────────────────

    def list_departments(self) -> list:
        return self.get_all("departments", "departments")

    # ── Relationship Types ─────────────────────────────────────────────

    def list_relationship_types(self) -> list:
        resp = self.get("relationship_types")
        if resp.status_code != 200:
            return []
        return resp.json().get("relationship_types", [])

    # ── Utility ────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Quick health check: fetch current user's agent profile."""
        resp = self.get("agents/me")
        if resp.status_code == 200:
            agent = resp.json().get("agent", {})
            return {
                "ok": True,
                "agent_id": agent.get("id"),
                "name": f"{agent.get('first_name', '')} {agent.get('last_name', '')}".strip(),
                "email": agent.get("email"),
                "role_ids": agent.get("role_ids"),
            }
        return {"ok": False, "status": resp.status_code, "body": resp.text}
