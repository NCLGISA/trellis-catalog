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

"""NextDNS bridge integration test battery.

Validates API connectivity and exercises read-only endpoints. Requires
NEXTDNS_API_KEY and (optionally) NEXTDNS_PROFILE to be set.

Exit 0 = all tests passed, exit 1 = one or more failures.
"""

import json
import sys
import os

try:
    from nextdns_client import NextDNSClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from nextdns_client import NextDNSClient


def run_test(name, fn):
    try:
        result = fn()
        return {"name": name, "status": "pass", "detail": result}
    except Exception as e:
        return {"name": name, "status": "fail", "error": str(e)}


def main():
    results = {"bridge": "nextdns", "tests": []}

    try:
        client = NextDNSClient()
    except SystemExit:
        results["tests"].append({
            "name": "init",
            "status": "fail",
            "error": "Failed to initialize client -- check NEXTDNS_API_KEY",
        })
        print(json.dumps(results, indent=2))
        sys.exit(1)

    # -- Account-level tests
    def test_list_profiles():
        profiles = client.list_profiles()
        return {"profile_count": len(profiles)}

    results["tests"].append(run_test("list_profiles", test_list_profiles))

    # -- Profile-scoped tests (only if a profile is configured)
    if client.profile_id:
        def test_get_profile():
            data = client.get_profile()
            name = data.get("data", data).get("name", "")
            return {"profile_name": name}

        def test_security():
            data = client.get_security()
            d = data.get("data", data)
            return {"threat_intel": d.get("threatIntelligenceFeeds")}

        def test_privacy():
            data = client.get_privacy()
            d = data.get("data", data)
            return {"disguised_trackers": d.get("disguisedTrackers")}

        def test_denylist():
            data = client.get_denylist()
            items = data.get("data", data) if isinstance(data.get("data"), list) else []
            return {"entry_count": len(items)}

        def test_allowlist():
            data = client.get_allowlist()
            items = data.get("data", data) if isinstance(data.get("data"), list) else []
            return {"entry_count": len(items)}

        def test_settings():
            data = client.get_settings()
            return {"has_data": bool(data)}

        def test_analytics_status():
            data = client.analytics_status(**{"from": "-24h", "limit": 5})
            return {"entries": len(data.get("data", []))}

        def test_logs():
            data = client.logs(limit=5)
            return {"log_entries": len(data.get("data", []))}

        for name, fn in [
            ("get_profile", test_get_profile),
            ("security_settings", test_security),
            ("privacy_settings", test_privacy),
            ("denylist", test_denylist),
            ("allowlist", test_allowlist),
            ("profile_settings", test_settings),
            ("analytics_status", test_analytics_status),
            ("logs", test_logs),
        ]:
            results["tests"].append(run_test(name, fn))
    else:
        results["tests"].append({
            "name": "profile_scoped",
            "status": "skip",
            "detail": "NEXTDNS_PROFILE not set -- skipping profile-scoped tests",
        })

    passed = sum(1 for t in results["tests"] if t["status"] == "pass")
    failed = sum(1 for t in results["tests"] if t["status"] == "fail")
    skipped = sum(1 for t in results["tests"] if t["status"] == "skip")
    total = len(results["tests"])
    results["summary"] = f"{passed} passed, {failed} failed, {skipped} skipped / {total} total"
    results["success"] = failed == 0

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
