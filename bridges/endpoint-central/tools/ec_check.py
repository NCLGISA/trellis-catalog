#!/usr/bin/env python3
"""Endpoint Central bridge health check.

Validates API connectivity and auth token, reports server info.
Exit 0 = healthy, exit 1 = unhealthy.
"""

import json
import sys
import os

try:
    from ec_client import ECClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from ec_client import ECClient


def main():
    results = {"bridge": "endpoint-central", "checks": []}

    try:
        client = ECClient()
        results["checks"].append({"name": "auth", "status": "pass"})
    except SystemExit:
        results["checks"].append({"name": "auth", "status": "fail", "error": "Authentication failed"})
        print(json.dumps(results))
        sys.exit(1)
    except Exception as e:
        results["checks"].append({"name": "auth", "status": "fail", "error": str(e)})
        print(json.dumps(results))
        sys.exit(1)

    try:
        data = client.discover()
        resp = data.get("message_response", {})
        results["checks"].append({"name": "discover", "status": "pass"})
        results["server"] = resp
    except Exception as e:
        results["checks"].append({"name": "discover", "status": "fail", "error": str(e)})
        print(json.dumps(results))
        sys.exit(1)

    try:
        data = client.server_properties()
        resp = data.get("message_response", {})
        props = resp.get("serverproperties", resp)
        domains = props.get("domains", [])
        groups = props.get("customgroups", [])
        offices = props.get("branchoffices", [])
        results["checks"].append({"name": "properties", "status": "pass"})
        results["domains"] = len(domains)
        results["custom_groups"] = len(groups)
        results["branch_offices"] = len(offices)
    except Exception as e:
        results["checks"].append({"name": "properties", "status": "warn", "error": str(e)})

    try:
        data = client.inventory_summary()
        resp = data.get("message_response", {})
        results["checks"].append({"name": "inventory", "status": "pass"})
        results["inventory_summary"] = resp
    except Exception as e:
        results["checks"].append({"name": "inventory", "status": "warn", "error": str(e)})

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total = len(results["checks"])
    results["summary"] = f"{passed}/{total} checks passed"
    results["healthy"] = all(c["status"] != "fail" for c in results["checks"])

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
