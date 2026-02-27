#!/usr/bin/env python3
"""Confluence Cloud bridge health check.

Validates credentials and connectivity to the Confluence REST API.
Exits 0 on success, 1 on any failure.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

CHECKS = []


def check(name, fn):
    try:
        result = fn()
        CHECKS.append({"name": name, "status": "pass", **result})
    except SystemExit:
        CHECKS.append({"name": name, "status": "fail", "error": "client exited"})
    except Exception as exc:
        CHECKS.append({"name": name, "status": "fail", "error": str(exc)})


def main():
    from confluence_client import ConfluenceClient

    results = {"bridge": "confluence", "checks": CHECKS}
    client = None

    def do_connect():
        nonlocal client
        client = ConfluenceClient()
        return {"base_url": client.base_url}

    check("connect", do_connect)

    if client is None:
        results["summary"] = "0/3 checks passed"
        results["healthy"] = False
        print(json.dumps(results, indent=2))
        sys.exit(1)

    def do_auth():
        user = client.get_current_user()
        return {
            "user": user.get("displayName", ""),
            "email": user.get("email", ""),
            "account_type": user.get("accountType", ""),
        }

    check("auth", do_auth)

    def do_spaces():
        data = client.list_spaces(limit=5)
        spaces = data.get("results", [])
        return {
            "space_count": len(spaces),
            "sample": [s.get("name", "") for s in spaces[:3]],
        }

    check("spaces", do_spaces)

    passed = sum(1 for c in CHECKS if c["status"] == "pass")
    total = len(CHECKS)
    results["summary"] = f"{passed}/{total} checks passed"
    results["healthy"] = passed == total

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
