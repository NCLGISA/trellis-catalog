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
Microsoft Purview Bridge Battery Test

Read-only test battery to validate certificate authentication and all
Security & Compliance PowerShell cmdlet categories accessible via CBA.

Usage:
    python3 purview_bridge_tests.py           # Run full battery
    python3 purview_bridge_tests.py --json    # JSON output
"""

import sys
import json
import time
from datetime import datetime

sys.path.insert(0, "/opt/bridge/data/tools")
from purview_client import PurviewClient


def run_tests(client: PurviewClient, as_json: bool = False):
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
                elif result.get("dlp_policies") is not None:
                    detail = f"{result['dlp_policies']} DLP, {result.get('sensitivity_labels', 0)} labels"
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

    test("Certificate authentication (IPPSSession)", "Connection",
         lambda: client.test_connection())

    test("Get-DlpCompliancePolicy", "DLP",
         lambda: client.run_cmdlet("Get-DlpCompliancePolicy"))

    test("Get-DlpComplianceRule", "DLP",
         lambda: client.run_cmdlet("Get-DlpComplianceRule"))

    test("Get-RetentionCompliancePolicy", "Retention",
         lambda: client.run_cmdlet("Get-RetentionCompliancePolicy"))

    test("Get-ComplianceTag (retention labels)", "Retention",
         lambda: client.run_cmdlet("Get-ComplianceTag"))

    test("Get-Label (sensitivity labels)", "Sensitivity Labels",
         lambda: client.run_cmdlet("Get-Label"))

    test("Get-LabelPolicy", "Sensitivity Labels",
         lambda: client.run_cmdlet("Get-LabelPolicy"))

    test("Get-ProtectionAlert", "Alert Policies",
         lambda: client.run_cmdlet("Get-ProtectionAlert"))

    test("Get-ComplianceCase", "eDiscovery",
         lambda: client.run_cmdlet("Get-ComplianceCase"))

    test("Get-InformationBarrierPolicy", "Information Barriers",
         lambda: client.run_cmdlet("Get-InformationBarrierPolicy"))

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

    print(f"Microsoft Purview Bridge Battery Test")
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
    client = PurviewClient()
    run_tests(client, as_json=as_json)


if __name__ == "__main__":
    main()
