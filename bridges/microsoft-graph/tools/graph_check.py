#!/usr/bin/env python3
"""Microsoft Graph bridge health check.

Validates environment variables and tests API connectivity.

Modes:
    --quick   Token acquisition + single /users?$top=1 call only.
              Designed for Docker healthcheck with tight timeout.
    (default) Full check including organization info and domains.

Exit 0 = healthy, exit 1 = unhealthy.
"""

import json
import os
import sys

import requests

TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def main():
    quick = "--quick" in sys.argv
    checks = {}

    required = {"AZURE_TENANT_ID": TENANT_ID, "AZURE_CLIENT_ID": CLIENT_ID,
                "AZURE_CLIENT_SECRET": CLIENT_SECRET}
    env_status = {k: ("set" if v else "MISSING") for k, v in required.items()}
    checks["environment"] = env_status

    if not all(required.values()):
        checks["api_connection"] = {"ok": False, "error": "Missing environment variables"}
        print(json.dumps(checks, indent=2))
        sys.exit(1)

    try:
        resp = requests.post(
            TOKEN_URL.format(tenant=TENANT_ID),
            data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                  "client_secret": CLIENT_SECRET,
                  "scope": "https://graph.microsoft.com/.default"},
            timeout=10,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
    except Exception as e:
        checks["api_connection"] = {"ok": False, "error": f"Token acquisition failed: {e}"}
        print(json.dumps(checks, indent=2))
        sys.exit(1)

    try:
        r = requests.get(f"{GRAPH_BASE}/users?$select=id&$top=1",
                         headers=headers, timeout=10)
        r.raise_for_status()
        checks["api_connection"] = {"ok": True, "users_accessible": True}
    except Exception as e:
        checks["api_connection"] = {"ok": False, "error": str(e)}
        print(json.dumps(checks, indent=2))
        sys.exit(1)

    if not quick:
        try:
            r = requests.get(f"{GRAPH_BASE}/organization",
                             headers=headers, timeout=10)
            r.raise_for_status()
            org = r.json().get("value", [{}])[0]
            checks["organization"] = {
                "ok": True,
                "tenant_id": org.get("id"),
                "display_name": org.get("displayName"),
            }
        except Exception as e:
            checks["organization"] = {"ok": False, "error": str(e)}

        try:
            r = requests.get(f"{GRAPH_BASE}/domains",
                             headers=headers, timeout=10)
            r.raise_for_status()
            domains = r.json().get("value", [])
            checks["domains"] = {
                "ok": True,
                "verified": [d["id"] for d in domains if d.get("isVerified")],
                "default": next((d["id"] for d in domains if d.get("isDefault")), None),
            }
        except Exception as e:
            checks["domains"] = {"ok": False, "error": str(e)}

    healthy = checks["api_connection"].get("ok", False)
    print(json.dumps(checks, indent=2))
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
