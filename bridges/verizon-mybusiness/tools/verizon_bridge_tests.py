#!/usr/bin/env python3
"""
Verizon MyBusiness Bridge Battery Test

Comprehensive read-only test covering all API areas to verify the bridge
has proper credentials, a valid session, and access to fleet, billing,
device, and dashboard endpoints.

Usage:
  python3 verizon_bridge_tests.py
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

results = []


def test(category, name, fn):
    """Run a test and record the result."""
    try:
        result = fn()
        count = ""
        if isinstance(result, list):
            count = f" ({len(result)} items)"
        elif isinstance(result, dict):
            keys = len(result)
            count = f" ({keys} keys)"
        results.append(("PASS", category, name, count))
        print(f"  PASS  {name}{count}")
        return result
    except Exception as e:
        msg = str(e)
        if len(msg) > 120:
            msg = msg[:120] + "..."
        results.append(("FAIL", category, name, msg))
        print(f"  FAIL  {name}: {msg}")
        return None


def skip(category, name, reason):
    """Record a skipped test."""
    results.append(("SKIP", category, name, reason))
    print(f"  SKIP  {name}: {reason}")


def main():
    print("=" * 70)
    print("Verizon MyBusiness Bridge Battery Test")
    print("=" * 70)

    from verizon_client import credentials_available, VerizonClient

    # ── Category 1: Credentials ───────────────────────────────────────
    print("\n[1/7] Credentials")
    has_creds = test("Credentials", "VZ_USERNAME configured",
                     lambda: _check_env("VZ_USERNAME"))
    test("Credentials", "VZ_PASSWORD configured",
         lambda: _check_env("VZ_PASSWORD"))
    test("Credentials", "credentials_available() returns True",
         lambda: _assert_true(credentials_available(), "credentials not available"))

    # ── Category 2: Auth Endpoint Reachability ────────────────────────
    print("\n[2/7] Auth Endpoints")
    test("Auth", "ForgeRock login page reachable",
         lambda: _check_url_reachable("https://mblogin.verizonwireless.com/account/business/login/unifiedlogin"))
    test("Auth", "Portal base URL reachable",
         lambda: _check_url_reachable("https://mb.verizonwireless.com"))
    test("Auth", "SSO endpoint reachable",
         lambda: _check_url_reachable("https://sso.verizonenterprise.com"))

    # ── Category 3: Session ───────────────────────────────────────────
    print("\n[3/7] Session")
    session_dir = Path(os.getenv("VZ_SESSION_DIR", "/opt/bridge/data/session"))
    cookies_file = session_dir / "cookies.json"

    client = None
    if not cookies_file.exists():
        skip("Session", "Cookie file exists", "no cookies file -- authenticate first")
        skip("Session", "Session alive", "no session")
    else:
        test("Session", "Cookie file exists",
             lambda: _assert_true(cookies_file.exists(), "missing"))
        cookie_count = test("Session", "Cookies loadable",
                            lambda: _load_cookies(cookies_file))
        try:
            client = VerizonClient()
            test("Session", "Session alive",
                 lambda: _assert_true(client.is_session_alive(), "session expired"))
        except Exception as e:
            skip("Session", "Session alive", str(e))

    if client is None:
        print("\n  !! No active session -- skipping API tests.")
        print("  !! Authenticate first: python3 auth_session.py initiate")
        _print_summary()
        return

    # ── Category 4: Fleet Inventory ───────────────────────────────────
    print("\n[4/7] Fleet Inventory")
    counts = test("Fleet", "Retrieve line summary count",
                  lambda: client.retrieve_line_summary_count())
    if counts:
        lc = counts.get("lineCounts", {})
        print(f"         Total: {lc.get('total', '?')} | Active: {lc.get('active', '?')} "
              f"| 5G: {lc.get('5G', '?')} | 4G: {lc.get('4G', '?')}")

    fleet = test("Fleet", "Retrieve entitled MTN (full fleet)",
                 lambda: client.retrieve_entitled_mtn())
    fleet_lines = []
    if fleet:
        fleet_lines = fleet.get("mtnDetails", [])
        print(f"         {len(fleet_lines)} lines returned")

    # ── Category 5: Billing ───────────────────────────────────────────
    print("\n[5/7] Billing")
    billing = test("Billing", "Get billing accounts",
                   lambda: client.get_billing_accounts())
    if billing:
        accounts = billing.get("accountInfo", [])
        for acct in accounts:
            print(f"         {acct.get('accountNumber', '?')}: "
                  f"${acct.get('totalBalanceDue', 0):,.2f}")

    # ── Category 6: Device Detail ─────────────────────────────────────
    print("\n[6/7] Device Detail")
    if fleet_lines:
        sample = fleet_lines[0]
        mtn = sample.get("mtn", "")
        account = sample.get("accountNumber", "")
        user_name = sample.get("userName", "unknown")

        device_info = test("Device", f"Retrieve device info ({mtn})",
                           lambda: client.retrieve_mtn_device_info(mtn, account))
        if device_info:
            info = device_info.get("deviceInformation", {})
            imei = info.get("deviceId", "").strip()
            model = info.get("modelName", "").strip()
            print(f"         IMEI: {imei} | Model: {model}")

        test("Device", f"Retrieve user info ({mtn})",
             lambda: client.retrieve_user_info(mtn, account))
    else:
        skip("Device", "Retrieve device info", "no fleet lines available")
        skip("Device", "Retrieve user info", "no fleet lines available")

    # ── Category 7: Dashboard ─────────────────────────────────────────
    print("\n[7/7] Dashboard")
    test("Dashboard", "Get MBT data (dashboard summary)",
         lambda: client.get_mbt_data())
    upgrade = test("Dashboard", "Get line & upgrade eligible count",
                   lambda: client.get_line_upgrade_eligible())
    if upgrade:
        print(f"         Total lines: {upgrade.get('totalLines', '?')} | "
              f"Upgrade eligible: {upgrade.get('totalUpgradeLines', '?')}")
    test("Dashboard", "Get total orders",
         lambda: client.get_total_orders())

    _print_summary()


def _check_env(var_name):
    val = os.getenv(var_name, "").strip()
    if not val:
        raise RuntimeError(f"{var_name} not set")
    return {"set": True, "length": len(val)}


def _assert_true(condition, msg):
    if not condition:
        raise RuntimeError(msg)
    return {"ok": True}


def _check_url_reachable(url):
    import httpx
    resp = httpx.head(url, follow_redirects=True, timeout=10.0)
    if resp.status_code >= 500:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return {"status": resp.status_code}


def _load_cookies(path):
    raw = json.loads(path.read_text())
    if not isinstance(raw, list) or len(raw) == 0:
        raise RuntimeError("cookie file empty or invalid")
    return {"count": len(raw)}


def _print_summary():
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    skipped = sum(1 for r in results if r[0] == "SKIP")
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")

    if failed:
        print(f"\nFailed tests:")
        for status, cat, name, detail in results:
            if status == "FAIL":
                print(f"  [{cat}] {name}: {detail}")

    print("=" * 70)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
