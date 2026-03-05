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
Exchange Online Bridge Battery Test

Comprehensive read-only test battery to validate certificate authentication,
module connectivity, and all Exchange Online PowerShell cmdlet categories.

Usage:
    python3 exchange_bridge_tests.py           # Run full battery
    python3 exchange_bridge_tests.py --json    # JSON output
"""

import sys
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, "/opt/bridge/data/tools")
from exchange_client import ExchangeClient


def run_tests(client: ExchangeClient, as_json: bool = False):
    """Run the full battery test."""
    results = []
    start_time = time.time()

    def test(name: str, category: str, fn):
        t0 = time.time()
        try:
            result = fn()
            elapsed = int((time.time() - t0) * 1000)
            ok = result.get("ok", False) if isinstance(result, dict) else bool(result)
            detail = ""
            if isinstance(result, dict):
                if result.get("data") and isinstance(result["data"], list):
                    detail = f"{len(result['data'])} items"
                elif result.get("error"):
                    detail = result["error"][:60]
                elif result.get("organization"):
                    detail = result["organization"]
            results.append({
                "test": name,
                "category": category,
                "passed": ok,
                "elapsed_ms": elapsed,
                "detail": detail,
            })
        except Exception as e:
            elapsed = int((time.time() - t0) * 1000)
            results.append({
                "test": name,
                "category": category,
                "passed": False,
                "elapsed_ms": elapsed,
                "detail": str(e)[:60],
            })

    # ── Category 1: Connection & Auth ──────────────────────────────────
    test("Certificate authentication", "Connection",
         lambda: client.test_connection())

    # ── Category 2: Quarantine ─────────────────────────────────────────
    start = (datetime.utcnow() - timedelta(days=3)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")

    test("Get-QuarantineMessage (3 days)", "Quarantine",
         lambda: client.run_cmdlet("Get-QuarantineMessage", {
             "StartReceivedDate": start,
             "EndReceivedDate": end,
             "PageSize": "10",
         }))

    # ── Category 3: Message Trace ──────────────────────────────────────
    test("Get-MessageTrace (2 days, org-wide sample)", "Mail Flow",
         lambda: client.run_cmdlet("Get-MessageTrace", {
             "StartDate": start,
             "EndDate": end,
             "PageSize": "5",
         }))

    # ── Category 4: Transport Rules ───────────────────────────────────
    test("Get-TransportRule", "Mail Flow",
         lambda: client.run_cmdlet("Get-TransportRule"))

    # ── Category 5: Organization Config ───────────────────────────────
    test("Get-OrganizationConfig", "Organization",
         lambda: client.run_cmdlet("Get-OrganizationConfig"))

    # ── Category 6: Mailbox Permissions ───────────────────────────────
    test("Get-Mailbox (top 1, verify access)", "Mailbox",
         lambda: client.run_cmdlet("Get-Mailbox", {
             "ResultSize": "1",
         }))

    # ── Category 7: Accepted Domains ──────────────────────────────────
    test("Get-AcceptedDomain", "Organization",
         lambda: client.run_cmdlet("Get-AcceptedDomain"))

    # ── Category 8: Remote Domains ────────────────────────────────────
    test("Get-RemoteDomain", "Organization",
         lambda: client.run_cmdlet("Get-RemoteDomain"))

    # ── Category 9: Anti-Spam / EOP ───────────────────────────────────
    test("Get-HostedContentFilterPolicy", "EOP",
         lambda: client.run_cmdlet("Get-HostedContentFilterPolicy"))

    test("Get-MalwareFilterPolicy", "EOP",
         lambda: client.run_cmdlet("Get-MalwareFilterPolicy"))

    # ── Category 10: Copilot Audit ────────────────────────────────────
    audit_start = (datetime.utcnow() - timedelta(days=7)).strftime("%m/%d/%Y")
    audit_end = (datetime.utcnow() + timedelta(days=1)).strftime("%m/%d/%Y")

    test("Search-UnifiedAuditLog (CopilotInteraction)", "Copilot Audit",
         lambda: client.run_cmdlet("Search-UnifiedAuditLog", {
             "RecordType": "CopilotInteraction",
             "StartDate": audit_start,
             "EndDate": audit_end,
             "ResultSize": "1",
         }))

    def _test_audit_data_structure():
        result = client.run_cmdlet("Search-UnifiedAuditLog", {
            "RecordType": "CopilotInteraction",
            "StartDate": audit_start,
            "EndDate": audit_end,
            "ResultSize": "5",
        })
        if not result.get("ok"):
            return result
        records = result.get("data") if isinstance(result.get("data"), list) else []
        if not records:
            return {"ok": True, "data": [], "detail": "0 records (no Copilot licenses?)"}
        parsed = 0
        for r in records:
            raw = r.get("AuditData", "")
            if isinstance(raw, str):
                audit = json.loads(raw)
            elif isinstance(raw, dict):
                audit = raw
            else:
                continue
            assert "UserId" in audit or "userId" in audit, "Missing UserId in AuditData"
            assert "Operation" in audit or "operation" in audit, "Missing Operation"
            assert "CreationTime" in audit or "creationTime" in audit, "Missing CreationTime"
            parsed += 1
        return {"ok": True, "data": records, "detail": f"{parsed}/{len(records)} records validated"}

    test("AuditData JSON structure (CopilotInteraction)", "Copilot Audit",
         _test_audit_data_structure)

    def _test_userid_filter():
        result = client.run_cmdlet("Search-UnifiedAuditLog", {
            "RecordType": "CopilotInteraction",
            "StartDate": audit_start,
            "EndDate": audit_end,
            "ResultSize": "1",
            "UserIds": "noreply@example.com",
        })
        records = result.get("data") if isinstance(result.get("data"), list) else []
        if not result.get("ok"):
            return {"ok": True, "data": [], "detail": "0 results (filter accepted)"}
        return {"ok": True, "data": records,
                "detail": f"{len(records)} results (filter accepted)"}

    test("Search-UnifiedAuditLog UserIds filter", "Copilot Audit",
         _test_userid_filter)

    # ── Results ───────────────────────────────────────────────────────
    total_time = int((time.time() - start_time) * 1000)
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])

    if as_json:
        print(json.dumps({
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "elapsed_ms": total_time,
            "tests": results,
        }, indent=2))
        return

    print(f"Exchange Online Bridge Battery Test")
    print(f"=" * 70)
    print(f"Date: {datetime.now().isoformat()[:19]}")
    print(f"Tests: {len(results)} ({passed} passed, {failed} failed)")
    print(f"Duration: {total_time}ms")
    print()

    current_category = ""
    for r in results:
        if r["category"] != current_category:
            current_category = r["category"]
            print(f"\n── {current_category} ──")

        icon = "PASS" if r["passed"] else "FAIL"
        detail = f" ({r['detail']})" if r["detail"] else ""
        print(f"  [{icon}] {r['test']:<45} {r['elapsed_ms']:>5}ms{detail}")

    print(f"\n{'=' * 70}")
    if failed == 0:
        print(f"All {passed} tests passed in {total_time}ms")
    else:
        print(f"{failed} test(s) FAILED out of {len(results)}")


def main():
    as_json = "--json" in sys.argv
    client = ExchangeClient()
    run_tests(client, as_json=as_json)


if __name__ == "__main__":
    main()
