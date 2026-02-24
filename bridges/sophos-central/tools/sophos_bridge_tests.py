#!/usr/bin/env python3
"""
Sophos Central Bridge Battery Test

Comprehensive read-only test covering all API areas to verify the bridge
has proper access to the Sophos Central APIs.

Usage:
  python3 sophos_bridge_tests.py
"""

import sys
import json
import os

sys.path.insert(0, os.path.dirname(__file__))

results = []


def test(category, name, fn):
    """Run a test and record the result."""
    try:
        result = fn()
        count = ""
        if isinstance(result, list):
            count = f" ({len(result)} items)"
        elif isinstance(result, dict):
            items = result.get("items")
            if items is not None:
                count = f" ({len(items)} items)"
            else:
                count = " (ok)"
        results.append(("PASS", category, name, count))
        print(f"  PASS  {name}{count}")
        return result
    except Exception as e:
        results.append(("FAIL", category, name, str(e)))
        print(f"  FAIL  {name}: {e}")
        return None


def main():
    print("=" * 70)
    print("Sophos Central Bridge Battery Test")
    print("=" * 70)

    from sophos_client import SophosClient
    client = SophosClient()

    # ── Category 1: Authentication & Tenant ─────────────────────────────
    print("\n[1/8] Authentication & Tenant Discovery")
    test("Auth", "Whoami / tenant discovery", lambda: client.whoami())
    test("Auth", "Token refresh (force)", lambda: (client._authenticate(), client.whoami())[1])

    # ── Category 2: Endpoints ───────────────────────────────────────────
    print("\n[2/8] Endpoints")
    ep_data = test("Endpoints", "List endpoints (page 1)", lambda: client.endpoints(pageSize=5))
    sample_ep = None
    if ep_data and ep_data.get("items"):
        sample_ep = ep_data["items"][0]
        ep_id = sample_ep["id"]
        test("Endpoints", f"Get endpoint detail ({sample_ep.get('hostname', ep_id)[:30]})",
             lambda: client.endpoint(ep_id))
        test("Endpoints", "Get tamper protection status",
             lambda: client.endpoint_tamper_protection(ep_id))

    test("Endpoints", "List endpoint groups", lambda: client.endpoint_groups(pageSize=5))

    # ── Category 3: Alerts ──────────────────────────────────────────────
    print("\n[3/8] Alerts")
    test("Alerts", "List alerts", lambda: client.alerts(pageSize=10))

    # ── Category 4: Directory ───────────────────────────────────────────
    print("\n[4/8] Directory (Users & Groups)")
    test("Directory", "List directory users", lambda: client.directory_users(pageSize=5))
    test("Directory", "List directory user groups", lambda: client.directory_user_groups(pageSize=5))

    # ── Category 5: Policies ────────────────────────────────────────────
    print("\n[5/8] Policies")
    pol_data = test("Policies", "List policies", lambda: client.policies(pageSize=10))
    if pol_data and pol_data.get("items"):
        sample_pol = pol_data["items"][0]
        test("Policies", f"Get policy detail ({sample_pol.get('name', '')[:30]})",
             lambda: client.policy(sample_pol["id"]))

    # ── Category 6: Settings ────────────────────────────────────────────
    print("\n[6/8] Settings")
    test("Settings", "List allowed items", lambda: client.allowed_items(pageSize=10))
    test("Settings", "List blocked items", lambda: client.blocked_items(pageSize=10))
    test("Settings", "List scanning exclusions", lambda: client.scanning_exclusions(pageSize=10))
    test("Settings", "List exploit mitigation apps", lambda: client.exploit_mitigation_apps(pageSize=5))
    test("Settings", "List web control local sites", lambda: client.web_control_local_sites(pageSize=10))
    test("Settings", "Get global tamper protection", lambda: client.global_tamper_protection())
    test("Settings", "Get installer downloads", lambda: client.installer_downloads())

    # ── Category 7: Account Health & SIEM ───────────────────────────────
    print("\n[7/8] Account Health & SIEM")
    test("Health", "Account health check", lambda: client.account_health_check())
    test("SIEM", "SIEM events (first page)", lambda: client.siem_events(limit=200))

    # ── Category 8: XDR / Data Lake ─────────────────────────────────────
    print("\n[8/8] XDR / Data Lake")
    test("XDR", "List XDR query categories", lambda: client.xdr_query_categories())
    test("XDR", "List saved queries", lambda: client.xdr_queries(pageSize=5))

    # ── Admins & Roles (bonus) ──────────────────────────────────────────
    print("\n[bonus] Admins & Roles")
    test("Admin", "List admins", lambda: client.admins(pageSize=10))
    test("Admin", "List roles", lambda: client.roles())

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed")

    if failed:
        print(f"\nFailed tests:")
        for status, cat, name, detail in results:
            if status == "FAIL":
                print(f"  [{cat}] {name}: {detail}")

    print("=" * 70)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
