#!/usr/bin/env python3
"""Endpoint Central REST API client.

Handles authentication, pagination, and search for the on-premise
Endpoint Central API v1.4.

Environment:
    EC_INSTANCE_URL    Server URL (e.g. https://ec.yourdomain.local:8443)
    EC_AUTH_TOKEN      Pre-generated API auth token
    EC_USERNAME        (fallback) Username for token generation
    EC_PASSWORD        (fallback) Base64-encoded password
    EC_VERIFY_SSL      Set to "false" to disable TLS verification (default: false for on-prem)
"""

import base64
import json
import os
import sys

import requests
import urllib3

INSTANCE = os.environ.get("EC_INSTANCE_URL", "").rstrip("/")
AUTH_TOKEN = os.environ.get("EC_AUTH_TOKEN", "") or os.environ.get("EC_ADMIN_TOKEN", "")
USERNAME = os.environ.get("EC_USERNAME", "")
PASSWORD = os.environ.get("EC_PASSWORD", "")
VERIFY_SSL = os.environ.get("EC_VERIFY_SSL", "false").lower() not in ("false", "0", "no")

if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE = "/api/1.4"


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def _get_token():
    """Return auth token from env or by authenticating with username/password."""
    if AUTH_TOKEN:
        return AUTH_TOKEN
    if not USERNAME or not PASSWORD:
        die("EC_AUTH_TOKEN not set and EC_USERNAME/EC_PASSWORD not provided.")
    pw = PASSWORD
    try:
        base64.b64decode(pw, validate=True)
    except Exception:
        pw = base64.b64encode(pw.encode()).decode()
    r = requests.post(
        f"{INSTANCE}{API_BASE}/desktop/authentication",
        json={"username": USERNAME, "password": pw, "auth_type": "local_authentication"},
        headers={"Content-Type": "application/json"},
        verify=VERIFY_SSL,
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    token = (
        data.get("message_response", {})
        .get("authentication", {})
        .get("auth_data", {})
        .get("auth_token")
    )
    if not token:
        die(f"Authentication failed: {json.dumps(data)}")
    return token


class ECClient:
    """REST client for Endpoint Central API v1.4."""

    def __init__(self):
        if not INSTANCE:
            die("EC_INSTANCE_URL not set.")
        self.base = f"{INSTANCE}{API_BASE}"
        self.token = _get_token()
        self.session = requests.Session()
        self.session.headers.update({"Authorization": self.token})
        self.session.verify = VERIFY_SSL

    def get(self, path, params=None, timeout=30):
        url = f"{self.base}/{path.lstrip('/')}"
        r = self.session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def post(self, path, json_body=None, timeout=30):
        url = f"{self.base}/{path.lstrip('/')}"
        r = self.session.post(url, json=json_body, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_all(self, path, params=None, key=None, limit=None):
        """Paginate through all results for an endpoint.

        Args:
            path: API path
            params: extra query params
            key: response key containing the array (auto-detected if None)
            limit: max total records to fetch (None = all)
        Returns:
            list of all result objects
        """
        params = dict(params or {})
        page = 1
        page_limit = min(limit or 1000, 1000)
        all_items = []

        while True:
            params["page"] = page
            params["pagelimit"] = page_limit
            data = self.get(path, params)
            resp = data.get("message_response", data)

            if key is None:
                for k, v in resp.items():
                    if isinstance(v, list):
                        key = k
                        break

            items = resp.get(key, []) if key else []
            if not items:
                break

            all_items.extend(items)

            if limit and len(all_items) >= limit:
                all_items = all_items[:limit]
                break

            total = resp.get("total")
            if total is not None and len(all_items) >= total:
                break

            if len(items) < page_limit:
                break

            page += 1

        return all_items

    def search(self, path, search_type, column, value, params=None, limit=100):
        """Search within a paginated endpoint."""
        params = dict(params or {})
        params["searchtype"] = search_type
        params["searchcolumn"] = column
        params["searchvalue"] = value
        return self.get_all(path, params, limit=limit)

    # -- Convenience methods --------------------------------------------------

    def discover(self):
        return self.get("desktop/discover")

    def server_properties(self):
        return self.get("desktop/serverproperties")

    # Inventory
    def inventory_summary(self):
        return self.get("inventory/allsummary")

    def inventory_computers(self, **filters):
        return self.get("som/computers", params=filters)

    def inventory_software(self, **filters):
        return self.get("inventory/software", params=filters)

    def inventory_hardware(self, **filters):
        return self.get("inventory/hardware", params=filters)

    def computer_detail(self, resource_id):
        return self.get(f"inventory/compdetailssummary", params={"resid": resource_id})

    def installed_software(self, resource_id):
        return self.get("inventory/installedsoftware", params={"resid": resource_id})

    def software_computers(self, software_id):
        return self.get("som/computers", params={"swid": software_id})

    def metering_rules(self):
        return self.get("inventory/swmeteringsummary")

    def metering_usage(self, rule_id):
        return self.get("som/computers", params={"swmeruleid": rule_id})

    def licensed_software(self):
        return self.get("inventory/licensesoftware")

    def software_licenses(self, software_id):
        return self.get("inventory/licenses", params={"swid": software_id})

    def scan_computers(self):
        return self.get("inventory/scancomputers")

    def trigger_scan_all(self):
        return self.post("inventory/computers/scanall")

    def trigger_scan(self, resource_ids):
        return self.post("inventory/computers/scan", json_body={"resource_ids": resource_ids})

    # Patch management
    def patch_alldetails(self, patch_id, **filters):
        filters["patchid"] = patch_id
        return self.get("patch/allpatchdetails", params=filters)

    def patch_systems(self, **filters):
        return self.get("patch/allsystems", params=filters)

    def patch_scan_status(self, **filters):
        return self.get("patch/scandetails", params=filters)

    def patch_approve(self, patch_ids):
        return self.post("patch/approve", json_body={"patch_ids": patch_ids})

    def patch_decline(self, patch_ids):
        return self.post("patch/decline", json_body={"patch_ids": patch_ids})

    def patch_scan(self):
        return self.post("patch/scan")

    # SoM
    def som_computers(self, **filters):
        return self.get("som/computers", params=filters)

    def som_remote_offices(self):
        return self.get("som/remoteoffice")

    def som_install_agent(self, resource_ids):
        return self.post("som/computers/installagent", json_body={"resource_ids": resource_ids})

    def som_uninstall_agent(self, resource_ids):
        return self.post("som/computers/uninstallagent", json_body={"resource_ids": resource_ids})

    # Filter params
    def filter_params(self):
        return self.get("inventory/filterparams")


def _main():
    """Quick CLI for testing: python3 ec_client.py <command>"""
    import argparse
    parser = argparse.ArgumentParser(prog="ec_client.py")
    parser.add_argument("command", choices=["test", "discover", "properties", "computers", "software"])
    args = parser.parse_args()

    client = ECClient()

    if args.command == "test":
        d = client.discover()
        resp = d.get("message_response", {})
        print(json.dumps({"success": True, "server": resp}, indent=2))
    elif args.command == "discover":
        print(json.dumps(client.discover(), indent=2))
    elif args.command == "properties":
        print(json.dumps(client.server_properties(), indent=2))
    elif args.command == "computers":
        data = client.som_computers(pagelimit=10)
        resp = data.get("message_response", {})
        computers = resp.get("computers", [])
        print(json.dumps({"total": resp.get("total"), "count": len(computers), "computers": computers[:10]}, indent=2))
    elif args.command == "software":
        data = client.inventory_software()
        resp = data.get("message_response", {})
        sw = resp.get("software", [])
        print(json.dumps({"count": len(sw), "software": sw[:10]}, indent=2))


if __name__ == "__main__":
    _main()
