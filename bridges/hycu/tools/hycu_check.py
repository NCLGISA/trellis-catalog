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

"""HYCU bridge health check — verifies API connectivity and basic access."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from hycu_client import HYCUClient


def check(label, fn):
    try:
        result = fn()
        ok = result is not None
        detail = ""
        if isinstance(result, dict):
            if "entities" in result and result["entities"] is not None:
                detail = f"{len(result['entities'])} items"
            elif "error" in result:
                ok = False
                detail = result["error"]
        print(f"  {'PASS' if ok else 'FAIL'}: {label}" + (f" ({detail})" if detail else ""))
        return ok, result
    except Exception as e:
        print(f"  FAIL: {label} ({e})")
        return False, None


def main():
    print("HYCU Bridge Health Check")
    print("=" * 50)

    try:
        client = HYCUClient()
    except SystemExit:
        print("FAIL: Cannot initialize client (missing credentials)")
        sys.exit(1)

    print(f"Server: {client.server}:{client.port}")
    print()

    passed = 0
    failed = 0

    ok, ctrl = check("Controller info", client.get_controller)
    passed += ok; failed += not ok

    ok, sw = check("Software version", client.get_software_version)
    passed += ok; failed += not ok
    if ok and sw:
        ver = sw.get("entities", [{}])[0].get("version", sw.get("version", "?")) if sw.get("entities") else sw.get("version", "?")
        print(f"         Version: {ver}")

    ok, _ = check("Controller state", client.get_controller_state)
    passed += ok; failed += not ok

    ok, lic = check("License", client.get_license)
    passed += ok; failed += not ok

    ok, _ = check("Scheduler state", client.get_scheduler_state)
    passed += ok; failed += not ok

    ok, vms = check("List VMs", lambda: client.list_vms(page_size=10))
    passed += ok; failed += not ok

    ok, _ = check("List policies", client.list_policies)
    passed += ok; failed += not ok

    ok, _ = check("List targets", client.list_targets)
    passed += ok; failed += not ok

    ok, _ = check("List jobs", lambda: client.list_jobs(page_size=10))
    passed += ok; failed += not ok

    ok, _ = check("List events", lambda: client.list_events(page_size=10))
    passed += ok; failed += not ok

    ok, _ = check("List applications", client.list_applications)
    passed += ok; failed += not ok

    ok, _ = check("List shares", client.list_shares)
    passed += ok; failed += not ok

    ok, _ = check("List volume groups", client.list_volume_groups)
    passed += ok; failed += not ok

    ok, _ = check("List archives", client.list_archives)
    passed += ok; failed += not ok

    ok, _ = check("List users", client.list_users)
    passed += ok; failed += not ok

    ok, _ = check("List backup windows", client.list_backup_windows)
    passed += ok; failed += not ok

    ok, _ = check("List credential groups", client.list_credential_groups)
    passed += ok; failed += not ok

    ok, _ = check("List webhooks", client.list_webhooks)
    passed += ok; failed += not ok

    ok, _ = check("List reports", client.list_reports)
    passed += ok; failed += not ok

    ok, _ = check("List networks", client.list_networks)
    passed += ok; failed += not ok

    print()
    total = passed + failed
    print(f"Results: {passed}/{total} passed, {failed}/{total} failed")

    if json_mode:
        print(json.dumps({"passed": passed, "failed": failed, "total": total}))

    sys.exit(0 if failed == 0 else 1)


json_mode = "--json" in sys.argv

if __name__ == "__main__":
    main()
