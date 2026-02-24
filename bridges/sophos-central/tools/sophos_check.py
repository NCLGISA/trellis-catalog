#!/usr/bin/env python3
"""Sophos Central bridge health check.

Validates OAuth2 authentication, tenant discovery, and API connectivity.
Exit 0 = healthy, exit 1 = unhealthy.
"""

import json
import sys
import os

try:
    from sophos_client import SophosClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from sophos_client import SophosClient


def main():
    results = {"bridge": "sophos-central", "checks": []}

    try:
        client = SophosClient()
        results["checks"].append({"name": "auth", "status": "pass"})
        results["account"] = client.whoami()
    except SystemExit:
        results["checks"].append({"name": "auth", "status": "fail", "error": "Authentication failed"})
        print(json.dumps(results))
        sys.exit(1)
    except Exception as e:
        results["checks"].append({"name": "auth", "status": "fail", "error": str(e)})
        print(json.dumps(results))
        sys.exit(1)

    try:
        data = client.endpoints(pageSize=1, pageTotal=True)
        pages = data.get("pages", {})
        total = pages.get("total", "unknown")
        items = data.get("items", [])
        results["checks"].append({"name": "endpoints", "status": "pass"})
        results["endpoint_count"] = total if isinstance(total, int) else len(items)
    except Exception as e:
        results["checks"].append({"name": "endpoints", "status": "warn", "error": str(e)})

    try:
        data = client.alerts(pageSize=1, pageTotal=True)
        pages = data.get("pages", {})
        total = pages.get("total", 0)
        results["checks"].append({"name": "alerts", "status": "pass"})
        results["active_alerts"] = total if isinstance(total, int) else 0
    except Exception as e:
        results["checks"].append({"name": "alerts", "status": "warn", "error": str(e)})

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total_checks = len(results["checks"])
    results["summary"] = f"{passed}/{total_checks} checks passed"
    results["healthy"] = all(c["status"] != "fail" for c in results["checks"])

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
