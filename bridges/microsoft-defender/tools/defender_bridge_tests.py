#!/usr/bin/env python3
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Comprehensive read-only battery test for the Microsoft Defender bridge.

Tests connectivity and permissions across all three API surfaces:
Defender XDR/MDE, Sentinel ARM, and Log Analytics.

Usage:
    python3 defender_bridge_tests.py           # Full battery
    python3 defender_bridge_tests.py --quick   # Security API only
"""

import sys
import os
import traceback

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient

PASS = 0
FAIL = 0
SKIP = 0


def test(name: str, fn, skip_if: bool = False):
    global PASS, FAIL, SKIP
    if skip_if:
        print(f"  [SKIP] {name}")
        SKIP += 1
        return
    try:
        result = fn()
        if result:
            print(f"  [PASS] {name}")
            PASS += 1
        else:
            print(f"  [FAIL] {name} -- returned falsy")
            FAIL += 1
    except Exception as e:
        print(f"  [FAIL] {name} -- {e}")
        FAIL += 1


def run_battery():
    global PASS, FAIL, SKIP

    client = DefenderClient()
    has_sentinel = bool(os.getenv("SENTINEL_SUBSCRIPTION_ID"))

    # ── Category 1: Security API Connectivity ──────────────────────────
    print("\n1. Security API Connectivity")

    test("XDR API token acquisition", lambda: client._get_token(
        "https://api.security.microsoft.com/.default"
    ))

    test("MDE API token acquisition", lambda: client._get_token(
        "https://api.securitycenter.microsoft.com/.default"
    ))

    test("ARM API token acquisition", lambda: client._get_token(
        "https://management.azure.com/.default"
    ), skip_if=not has_sentinel)

    # ── Category 2: Defender XDR Incidents ─────────────────────────────
    print("\n2. Defender XDR Incidents")

    test("List incidents (top 5)", lambda: (
        client.security_get("/api/incidents", params={"$top": 5}).status_code == 200
    ))

    # ── Category 3: Advanced Hunting ───────────────────────────────────
    print("\n3. Advanced Hunting")

    test("Execute simple KQL", lambda: (
        "Results" in client.advanced_hunt("IdentityLogonEvents | take 1")
        or "error" not in client.advanced_hunt("IdentityLogonEvents | take 1")
    ))

    test("Schema table enumeration", lambda: (
        client.advanced_hunt("search * | distinct $table | take 5")
        .get("Results") is not None
    ))

    # ── Category 4: MDE Machines ───────────────────────────────────────
    print("\n4. MDE Machine Inventory")

    test("List machines (top 5)", lambda: (
        client.mde_get("/api/machines", params={"$top": 5}).status_code == 200
    ))

    test("Machine search by name", lambda: (
        client.mde_get("/api/machines",
            params={"$filter": "contains(computerDnsName,'a')", "$top": 3}
        ).status_code == 200
    ))

    # ── Category 5: MDE Vulnerabilities ────────────────────────────────
    print("\n5. MDE Vulnerability Management")

    test("List vulnerabilities (top 5)", lambda: (
        client.mde_get("/api/vulnerabilities", params={"$top": 5}).status_code == 200
    ))

    test("List software inventory (top 5)", lambda: (
        client.mde_get("/api/Software", params={"$top": 5}).status_code == 200
    ))

    test("List recommendations (top 5)", lambda: (
        client.mde_get("/api/recommendations", params={"$top": 5}).status_code == 200
    ))

    # ── Category 6: MDE Indicators ─────────────────────────────────────
    print("\n6. MDE Threat Indicators")

    test("List indicators", lambda: (
        client.mde_get("/api/indicators").status_code == 200
    ))

    # ── Category 7: Sentinel Analytics Rules ───────────────────────────
    print("\n7. Sentinel Analytics Rules")

    test("List analytics rules", lambda: (
        client.sentinel_get("alertRules").status_code == 200
    ), skip_if=not has_sentinel)

    test("List automation rules", lambda: (
        client.sentinel_get("automationRules").status_code == 200
    ), skip_if=not has_sentinel)

    # ── Category 8: Sentinel Watchlists ────────────────────────────────
    print("\n8. Sentinel Watchlists")

    test("List watchlists", lambda: (
        client.sentinel_get("watchlists").status_code == 200
    ), skip_if=not has_sentinel)

    # ── Category 9: Log Analytics ──────────────────────────────────────
    print("\n9. Log Analytics Workspace")

    test("Execute workspace query", lambda: (
        "error" not in client.query_logs("print test='hello'", timespan="PT5M")
    ), skip_if=not has_sentinel)

    test("Query workspace tables", lambda: (
        client.query_logs(
            "search * | where TimeGenerated > ago(1d) | distinct $table | take 10",
            timespan="P1D"
        ).get("tables") is not None
    ), skip_if=not has_sentinel)

    # ── Summary ────────────────────────────────────────────────────────
    total = PASS + FAIL + SKIP
    print(f"\n{'═' * 50}")
    print(f"Battery Results: {PASS} passed, {FAIL} failed, {SKIP} skipped ({total} total)")

    if FAIL:
        print("Status: FAIL")
        sys.exit(1)
    else:
        print("Status: PASS")


if __name__ == "__main__":
    print("Microsoft Defender Bridge -- Battery Test\n")
    run_battery()
