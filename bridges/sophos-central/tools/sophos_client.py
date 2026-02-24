#!/usr/bin/env python3
"""Sophos Central REST API client.

Handles OAuth2 authentication via id.sophos.com, automatic tenant/region
discovery via /whoami/v1, and paginated access to the Common, Endpoint,
SIEM, Account Health, and XDR Query APIs.

Environment:
    SOPHOS_CLIENT_ID       OAuth2 client ID
    SOPHOS_CLIENT_SECRET   OAuth2 client secret
"""

import json
import os
import sys
import time

import requests

IDP_TOKEN_URL = "https://id.sophos.com/api/v2/oauth2/token"
GLOBAL_API = "https://api.central.sophos.com"

CLIENT_ID = os.environ.get("SOPHOS_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SOPHOS_CLIENT_SECRET", "")


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


class SophosClient:
    """REST client for Sophos Central APIs."""

    def __init__(self):
        if not CLIENT_ID or not CLIENT_SECRET:
            die("SOPHOS_CLIENT_ID and SOPHOS_CLIENT_SECRET must be set.")

        self.session = requests.Session()
        self._token = None
        self._token_expiry = 0
        self.tenant_id = None
        self.api_host = None
        self.id_type = None

        self._authenticate()
        self._discover()

    # -- Auth ---------------------------------------------------------------

    def _authenticate(self):
        r = requests.post(
            IDP_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if r.status_code != 200:
            die(f"Sophos auth failed ({r.status_code}): {r.text}")
        body = r.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + body.get("expires_in", 3600) - 60
        self.session.headers.update({"Authorization": f"Bearer {self._token}"})

    def _ensure_token(self):
        if time.time() >= self._token_expiry:
            self._authenticate()
            self.session.headers.update({
                "Authorization": f"Bearer {self._token}",
                "X-Tenant-ID": self.tenant_id,
            })

    def _discover(self):
        r = self.session.get(f"{GLOBAL_API}/whoami/v1", timeout=15)
        if r.status_code != 200:
            die(f"Sophos whoami failed ({r.status_code}): {r.text}")
        body = r.json()
        self.tenant_id = body["id"]
        self.id_type = body.get("idType", "tenant")
        hosts = body.get("apiHosts", {})
        self.api_host = hosts.get("dataRegion", hosts.get("global", GLOBAL_API))
        self.session.headers.update({"X-Tenant-ID": self.tenant_id})

    # -- HTTP helpers -------------------------------------------------------

    def get(self, path, params=None, timeout=30):
        self._ensure_token()
        url = f"{self.api_host}/{path.lstrip('/')}"
        r = self.session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def post(self, path, json_body=None, timeout=30):
        self._ensure_token()
        url = f"{self.api_host}/{path.lstrip('/')}"
        r = self.session.post(url, json=json_body, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def delete(self, path, timeout=30):
        self._ensure_token()
        url = f"{self.api_host}/{path.lstrip('/')}"
        r = self.session.delete(url, timeout=timeout)
        r.raise_for_status()
        if r.content:
            return r.json()
        return {"status": "deleted"}

    def patch(self, path, json_body=None, timeout=30):
        self._ensure_token()
        url = f"{self.api_host}/{path.lstrip('/')}"
        r = self.session.patch(url, json=json_body, timeout=timeout)
        r.raise_for_status()
        return r.json()

    # -- Pagination ---------------------------------------------------------

    def get_all(self, path, params=None, limit=None):
        params = dict(params or {})
        all_items = []
        page_size = min(limit or 500, 500)
        params["pageSize"] = page_size

        while True:
            data = self.get(path, params)
            items = data.get("items", [])
            all_items.extend(items)

            if limit and len(all_items) >= limit:
                return all_items[:limit]

            pages = data.get("pages", {})
            next_key = pages.get("nextKey")
            if next_key:
                params["pageFromKey"] = next_key
            else:
                current = pages.get("current")
                total = pages.get("total")
                if current and total and current < total:
                    params["page"] = current + 1
                else:
                    break

            if len(items) < page_size:
                break

        return all_items

    # ===== Common API - Alerts ==============================================

    def alerts(self, **filters):
        return self.get("common/v1/alerts", params=filters or None)

    def alert(self, alert_id):
        return self.get(f"common/v1/alerts/{alert_id}")

    def alert_action(self, alert_id, action, message=None):
        body = {"action": action}
        if message:
            body["message"] = message
        return self.post(f"common/v1/alerts/{alert_id}/actions", json_body=body)

    def alerts_action(self, action, alert_ids=None, filters=None):
        body = {"action": action}
        if alert_ids:
            body["items"] = alert_ids
        if filters:
            body.update(filters)
        return self.post("common/v1/alerts/actions", json_body=body)

    # ===== Common API - Directory ==========================================

    def directory_users(self, **filters):
        return self.get("common/v1/directory/users", params=filters or None)

    def directory_users_all(self, limit=None, **filters):
        return self.get_all("common/v1/directory/users", params=filters or None, limit=limit)

    def directory_user(self, user_id):
        return self.get(f"common/v1/directory/users/{user_id}")

    def directory_user_groups(self, **filters):
        return self.get("common/v1/directory/user-groups", params=filters or None)

    def directory_user_groups_all(self, limit=None, **filters):
        return self.get_all("common/v1/directory/user-groups", params=filters or None, limit=limit)

    def directory_user_group(self, group_id):
        return self.get(f"common/v1/directory/user-groups/{group_id}")

    # ===== Common API - Admins & Roles =====================================

    def admins(self, **filters):
        return self.get("common/v1/admins", params=filters or None)

    def admin(self, admin_id):
        return self.get(f"common/v1/admins/{admin_id}")

    def roles(self):
        return self.get("common/v1/roles")

    # ===== Endpoint API - Endpoints ========================================

    def endpoints(self, **filters):
        return self.get("endpoint/v1/endpoints", params=filters or None)

    def endpoints_all(self, limit=None, **filters):
        return self.get_all("endpoint/v1/endpoints", params=filters or None, limit=limit)

    def endpoint(self, endpoint_id):
        return self.get(f"endpoint/v1/endpoints/{endpoint_id}")

    def endpoint_isolation(self, endpoint_id, enabled, comment=None):
        body = {"enabled": enabled}
        if comment:
            body["comment"] = comment
        return self.patch(f"endpoint/v1/endpoints/{endpoint_id}/isolation", json_body=body)

    def endpoint_scan(self, endpoint_id):
        return self.post(f"endpoint/v1/endpoints/{endpoint_id}/scans")

    def endpoint_tamper_protection(self, endpoint_id, enabled=None):
        if enabled is None:
            return self.get(f"endpoint/v1/endpoints/{endpoint_id}/tamper-protection")
        return self.post(f"endpoint/v1/endpoints/{endpoint_id}/tamper-protection", json_body={"enabled": enabled})

    # ===== Endpoint API - Endpoint Groups ==================================

    def endpoint_groups(self, **filters):
        return self.get("endpoint/v1/endpoint-groups", params=filters or None)

    def endpoint_group(self, group_id):
        return self.get(f"endpoint/v1/endpoint-groups/{group_id}")

    def endpoint_group_endpoints(self, group_id, **filters):
        return self.get(f"endpoint/v1/endpoint-groups/{group_id}/endpoints", params=filters or None)

    # ===== Endpoint API - Policies =========================================

    def policies(self, **filters):
        return self.get("endpoint/v1/policies", params=filters or None)

    def policies_all(self, limit=None, **filters):
        return self.get_all("endpoint/v1/policies", params=filters or None, limit=limit)

    def policy(self, policy_id):
        return self.get(f"endpoint/v1/policies/{policy_id}")

    # ===== Endpoint API - Settings =========================================

    def allowed_items(self, **filters):
        return self.get("endpoint/v1/settings/allowed-items", params=filters or None)

    def add_allowed_item(self, item_type, properties, comment=None, origin_person_id=None, origin_endpoint_id=None):
        body = {"type": item_type, "properties": properties}
        if comment:
            body["comment"] = comment
        if origin_person_id:
            body["originPersonId"] = origin_person_id
        if origin_endpoint_id:
            body["originEndpointId"] = origin_endpoint_id
        return self.post("endpoint/v1/settings/allowed-items", json_body=body)

    def delete_allowed_item(self, item_id):
        return self.delete(f"endpoint/v1/settings/allowed-items/{item_id}")

    def blocked_items(self, **filters):
        return self.get("endpoint/v1/settings/blocked-items", params=filters or None)

    def add_blocked_item(self, item_type, properties, comment=None):
        body = {"type": item_type, "properties": properties}
        if comment:
            body["comment"] = comment
        return self.post("endpoint/v1/settings/blocked-items", json_body=body)

    def delete_blocked_item(self, item_id):
        return self.delete(f"endpoint/v1/settings/blocked-items/{item_id}")

    def scanning_exclusions(self, **filters):
        return self.get("endpoint/v1/settings/exclusions/scanning", params=filters or None)

    def add_scanning_exclusion(self, value, exclusion_type, scan_mode="onDemandAndOnAccess", comment=None):
        body = {"value": value, "type": exclusion_type, "scanMode": scan_mode}
        if comment:
            body["comment"] = comment
        return self.post("endpoint/v1/settings/exclusions/scanning", json_body=body)

    def delete_scanning_exclusion(self, exclusion_id):
        return self.delete(f"endpoint/v1/settings/exclusions/scanning/{exclusion_id}")

    def exploit_mitigation_apps(self, **filters):
        return self.get("endpoint/v1/settings/exploit-mitigation/applications", params=filters or None)

    def web_control_local_sites(self, **filters):
        return self.get("endpoint/v1/settings/web-control/local-sites", params=filters or None)

    def add_web_control_local_site(self, url, tags=None, comment=None):
        body = {"url": url}
        if tags:
            body["tags"] = tags
        if comment:
            body["comment"] = comment
        return self.post("endpoint/v1/settings/web-control/local-sites", json_body=body)

    def delete_web_control_local_site(self, site_id):
        return self.delete(f"endpoint/v1/settings/web-control/local-sites/{site_id}")

    def global_tamper_protection(self):
        return self.get("endpoint/v1/settings/tamper-protection")

    # ===== Endpoint API - Downloads ========================================

    def installer_downloads(self):
        return self.get("endpoint/v1/downloads")

    # ===== Account Health Check ============================================

    def account_health_check(self):
        return self.get("account-health-check/v1/health-check")

    # ===== SIEM Events & Alerts ============================================

    def siem_events(self, limit=200, from_date=None, cursor=None):
        params = {"limit": max(limit, 200)}
        if from_date:
            params["from_date"] = from_date
        if cursor:
            params["cursor"] = cursor
        return self.get("siem/v1/events", params=params)

    def siem_alerts(self, limit=200, from_date=None, cursor=None):
        params = {"limit": max(limit, 200)}
        if from_date:
            params["from_date"] = from_date
        if cursor:
            params["cursor"] = cursor
        return self.get("siem/v1/alerts", params=params)

    # ===== XDR / Data Lake Queries =========================================

    def xdr_queries(self, **filters):
        return self.get("xdr-query/v1/queries", params=filters or None)

    def xdr_queries_all(self, limit=None):
        return self.get_all("xdr-query/v1/queries", limit=limit)

    def xdr_query_categories(self):
        return self.get("xdr-query/v1/queries/categories")

    def xdr_run(self, query_sql, from_date=None, to_date=None, variables=None):
        body = {"adHocQuery": {"template": query_sql}}
        if from_date:
            body["from"] = from_date
        if to_date:
            body["to"] = to_date
        if variables:
            body["adHocQuery"]["variables"] = [
                {"name": k, "dataType": "text", "value": v}
                for k, v in variables.items()
            ]
        return self.post("xdr-query/v1/queries/runs", json_body=body)

    def xdr_run_status(self, run_id):
        return self.get(f"xdr-query/v1/queries/runs/{run_id}")

    def xdr_run_results(self, run_id, limit=None):
        params = {}
        if limit:
            params["pageSize"] = limit
        return self.get(f"xdr-query/v1/queries/runs/{run_id}/results", params=params or None)

    # ===== Convenience =====================================================

    def whoami(self):
        return {"id": self.tenant_id, "idType": self.id_type, "apiHost": self.api_host}


def _main():
    import argparse
    parser = argparse.ArgumentParser(prog="sophos_client.py")
    parser.add_argument("command", choices=["test", "whoami", "endpoints", "alerts"])
    args = parser.parse_args()
    client = SophosClient()
    if args.command == "test":
        print(json.dumps({"success": True, "account": client.whoami()}, indent=2))
    elif args.command == "whoami":
        print(json.dumps(client.whoami(), indent=2))
    elif args.command == "endpoints":
        data = client.endpoints(pageSize=10)
        items = data.get("items", [])
        print(json.dumps({"count": len(items), "endpoints": [{"id": e.get("id"), "hostname": e.get("hostname"), "os": e.get("os", {}).get("name"), "health": e.get("health", {}).get("overall")} for e in items]}, indent=2))
    elif args.command == "alerts":
        data = client.alerts(pageSize=10)
        items = data.get("items", [])
        print(json.dumps({"count": len(items), "alerts": [{"id": a.get("id"), "severity": a.get("severity"), "category": a.get("category"), "description": a.get("description")} for a in items]}, indent=2))


if __name__ == "__main__":
    _main()
