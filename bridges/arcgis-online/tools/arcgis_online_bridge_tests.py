#!/usr/bin/env python3
"""
ArcGIS Online Bridge - Integration Test Battery

Read-only tests that verify API connectivity, authentication, and
basic data access across all tool categories. Run after deployment
to validate the bridge is fully operational.

Usage:
    python3 /opt/bridge/data/tools/arcgis_online_bridge_tests.py
    python3 /opt/bridge/data/tools/arcgis_online_bridge_tests.py --json
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import os

results = []
start_time = time.time()


def run_test(category, name, fn):
    try:
        detail = fn()
        results.append({"category": category, "name": name, "status": "PASS", "detail": detail or ""})
    except Exception as e:
        results.append({"category": category, "name": name, "status": "FAIL", "detail": str(e)})


def skip_test(category, name, reason):
    results.append({"category": category, "name": name, "status": "SKIP", "detail": reason})


# ── Tests ──────────────────────────────────────────────────────────

def test_env_vars():
    for var in ["ARCGIS_ORG_URL", "ARCGIS_CLIENT_ID", "ARCGIS_CLIENT_SECRET"]:
        assert os.getenv(var), f"{var} is not set"
    return "All required env vars present"


def test_token():
    from arcgis_online_client import ArcGISOnlineClient
    client = ArcGISOnlineClient()
    token = client._get_token()
    assert token, "Token is empty"
    return f"Token acquired ({len(token)} chars)"


def test_org_info():
    from arcgis_online_client import ArcGISOnlineClient
    client = ArcGISOnlineClient()
    result = client.test_connection()
    assert result["ok"], f"Connection failed: {result.get('error')}"
    return f"Org: {result.get('org_name')} ({result.get('subscription_type')})"


def test_content_search():
    from arcgis_online_client import ArcGISOnlineClient
    client = ArcGISOnlineClient()
    result = client.search("*", num=1)
    assert "results" in result, "No results key in search response"
    total = result.get("total", 0)
    return f"Search OK, {total} total items in org"


def test_users():
    from arcgis_online_client import ArcGISOnlineClient
    client = ArcGISOnlineClient()
    result = client.get("portals/self/users", params={"start": 1, "num": 1})
    assert "users" in result, "No users key in response"
    total = result.get("total", 0)
    return f"Users endpoint OK, {total} users in org"


def test_groups():
    from arcgis_online_client import ArcGISOnlineClient
    client = ArcGISOnlineClient()
    result = client.get("community/groups", params={"q": "*", "num": 1})
    total = result.get("total", 0)
    return f"Groups endpoint OK, {total} groups found"


def test_geocode_service():
    from arcgis_online_client import ArcGISOnlineClient
    client = ArcGISOnlineClient()
    result = client.get("portals/self")
    geocode_url = None
    for helper in result.get("helperServices", {}).get("geocode", []):
        geocode_url = helper.get("url")
        break
    if not geocode_url:
        geocode_url = result.get("helperServices", {}).get("geocode", {}).get("url")
    assert geocode_url, "No geocode service URL found in portal config"
    return f"Geocode service: {geocode_url}"


# ── Run all tests ──────────────────────────────────────────────────

def main():
    print("ArcGIS Online Bridge Test Battery")
    print("=" * 50)
    print()

    run_test("Bridge Health", "Environment variables", test_env_vars)
    run_test("Bridge Health", "OAuth2 token acquisition", test_token)
    run_test("API Connectivity", "Organization info", test_org_info)
    run_test("Content", "Search items", test_content_search)
    run_test("Users & Groups", "List users", test_users)
    run_test("Users & Groups", "List groups", test_groups)
    run_test("Geocoding", "Geocode service discovery", test_geocode_service)

    elapsed = time.time() - start_time
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    print()
    current_category = ""
    for r in results:
        if r["category"] != current_category:
            current_category = r["category"]
            print(f"  [{current_category}]")
        icon = {"PASS": "+", "FAIL": "X", "SKIP": "-"}[r["status"]]
        print(f"    [{icon}] {r['name']}: {r['detail']}")

    print()
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped ({elapsed:.1f}s)")

    report = {
        "bridge": "arcgis-online",
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "elapsed_seconds": round(elapsed, 1),
        "tests": results,
    }

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
