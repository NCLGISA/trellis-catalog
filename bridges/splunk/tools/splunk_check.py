#!/usr/bin/env python3
"""Splunk bridge health check.

Validates bearer token authentication, API connectivity, and index access.
Exit 0 = healthy, exit 1 = unhealthy.
"""

import json
import sys
import os

try:
    from splunk_client import SplunkClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from splunk_client import SplunkClient


def main():
    results = {"bridge": "splunk", "checks": []}

    try:
        client = SplunkClient()
        info = client.server_info()
        results["checks"].append({"name": "auth", "status": "pass"})
        results["server"] = {
            "name": info.get("serverName", ""),
            "version": info.get("version", ""),
            "build": info.get("build", ""),
        }
    except SystemExit:
        results["checks"].append({"name": "auth", "status": "fail", "error": "Authentication failed -- check SPLUNK_URL and SPLUNK_TOKEN"})
        print(json.dumps(results))
        sys.exit(1)
    except Exception as e:
        results["checks"].append({"name": "auth", "status": "fail", "error": str(e)})
        print(json.dumps(results))
        sys.exit(1)

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
    total_checks = len(results["checks"])
    results["summary"] = f"{passed}/{total_checks} checks passed"
    results["healthy"] = all(c["status"] != "fail" for c in results["checks"])

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
