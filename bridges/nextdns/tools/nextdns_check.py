#!/usr/bin/env python3
"""NextDNS bridge health check.

Validates API key authentication and profile accessibility.
Exit 0 = healthy, exit 1 = unhealthy.
"""

import json
import sys
import os

try:
    from nextdns_client import NextDNSClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from nextdns_client import NextDNSClient


def main():
    results = {"bridge": "nextdns", "checks": []}

    try:
        client = NextDNSClient()
        profiles = client.list_profiles()
        results["checks"].append({"name": "auth", "status": "pass"})
        results["profile_count"] = len(profiles)
        results["profiles"] = [
            {"id": p.get("id", ""), "name": p.get("name", "")}
            for p in profiles[:10]
        ]
    except SystemExit:
        results["checks"].append({
            "name": "auth",
            "status": "fail",
            "error": "Authentication failed -- check NEXTDNS_API_KEY",
        })
        print(json.dumps(results))
        sys.exit(1)
    except Exception as e:
        results["checks"].append({"name": "auth", "status": "fail", "error": str(e)})
        print(json.dumps(results))
        sys.exit(1)

    if client.profile_id:
        try:
            profile = client.get_profile()
            data = profile.get("data", profile)
            results["checks"].append({"name": "default_profile", "status": "pass"})
            results["default_profile"] = {
                "id": client.profile_id,
                "name": data.get("name", ""),
            }
        except Exception as e:
            results["checks"].append({
                "name": "default_profile",
                "status": "warn",
                "error": str(e),
            })
    else:
        results["checks"].append({
            "name": "default_profile",
            "status": "warn",
            "error": "NEXTDNS_PROFILE not set -- profile-scoped commands require --profile flag",
        })

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total_checks = len(results["checks"])
    results["summary"] = f"{passed}/{total_checks} checks passed"
    results["healthy"] = all(c["status"] != "fail" for c in results["checks"])

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
