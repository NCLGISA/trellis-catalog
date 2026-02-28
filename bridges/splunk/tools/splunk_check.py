#!/usr/bin/env python3
"""Splunk bridge health check.

Validates connectivity to the Splunk REST API.  When per-operator
credentials (SPLUNK_TOKEN) are available, also validates authentication,
user context, and index access.  When only the shared SPLUNK_URL is set,
performs a connect-only check so the Docker healthcheck can pass without
operator secrets baked into the container.

Exit 0 = healthy, exit 1 = unhealthy.
"""

import json
import os
import sys

import requests

SPLUNK_URL = os.environ.get("SPLUNK_URL", "").rstrip("/")
SPLUNK_TOKEN = os.environ.get("SPLUNK_TOKEN", "")
SPLUNK_VERIFY_TLS = os.environ.get("SPLUNK_VERIFY_TLS", "true").lower() != "false"


def main():
    results = {"bridge": "splunk", "checks": []}

    if not SPLUNK_URL:
        results["checks"] = [{"name": "connect", "status": "fail",
                               "error": "SPLUNK_URL not set"}]
        results["summary"] = "0/1 checks passed"
        results["healthy"] = False
        print(json.dumps(results, indent=2))
        sys.exit(1)

    has_operator_creds = bool(SPLUNK_TOKEN)

    try:
        resp = requests.get(
            f"{SPLUNK_URL}/services/server/info?output_mode=json",
            verify=SPLUNK_VERIFY_TLS, timeout=10,
            **({"headers": {"Authorization": f"Bearer {SPLUNK_TOKEN}"}} if has_operator_creds else {}),
        )
        if has_operator_creds:
            resp.raise_for_status()
            results["checks"].append({"name": "connect", "status": "pass"})
        else:
            # Without auth, 401 proves the API is reachable
            if resp.status_code in (200, 401):
                results["checks"].append({"name": "connect", "status": "pass",
                                           "note": "API reachable (no operator token)"})
            else:
                results["checks"].append({"name": "connect", "status": "fail",
                                           "error": f"Unexpected status {resp.status_code}"})
    except Exception as e:
        results["checks"].append({"name": "connect", "status": "fail", "error": str(e)})

    if has_operator_creds and results["checks"][0]["status"] == "pass":
        sys.path.insert(0, os.path.dirname(__file__))
        from splunk_client import SplunkClient
        client = SplunkClient()

        try:
            info = client.server_info()
            results["checks"].append({"name": "auth", "status": "pass"})
            results["server"] = {
                "name": info.get("serverName", ""),
                "version": info.get("version", ""),
                "build": info.get("build", ""),
            }
        except Exception as e:
            results["checks"].append({"name": "auth", "status": "fail", "error": str(e)})

        try:
            user = client.current_user()
            results["checks"].append({"name": "user_context", "status": "pass"})
            results["user"] = user.get("username", "unknown")
            results["roles"] = user.get("roles", [])
        except Exception as e:
            results["checks"].append({"name": "user_context", "status": "warn", "error": str(e)})

        try:
            indexes = client.indexes()
            active = [i for i in indexes if not i.get("disabled")]
            results["checks"].append({"name": "indexes", "status": "pass"})
            results["index_count"] = len(active)
        except Exception as e:
            results["checks"].append({"name": "indexes", "status": "warn", "error": str(e)})

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total = len(results["checks"])
    results["summary"] = f"{passed}/{total} checks passed"
    results["healthy"] = all(c["status"] != "fail" for c in results["checks"])

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
