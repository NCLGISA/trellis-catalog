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

"""UKG Ready bridge health check.

Validates authentication, token acquisition, and employee endpoint access.
Exits 0 on success, 1 on any failure.  Outputs JSON for the Tendril
healthcheck framework.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

CHECKS = []


def check(name, fn):
    try:
        result = fn()
        CHECKS.append({"name": name, "status": "pass", **result})
    except SystemExit:
        CHECKS.append({"name": name, "status": "fail", "error": "client exited"})
    except Exception as exc:
        CHECKS.append({"name": name, "status": "fail", "error": str(exc)})


def main():
    import requests
    from ukg_client import UKGClient, UKG_BASE_URL, UKG_API_KEY, UKG_COMPANY_SHORT_NAME

    results = {"bridge": "ukg-ready", "checks": CHECKS}
    client = None

    # 1. Login / token acquisition
    def do_login():
        nonlocal client
        client = UKGClient()
        return {
            "company_id": client.company_id,
            "base_url": client.base_url,
        }

    check("auth", do_login)

    if client is None:
        results["summary"] = "0/2 checks passed"
        results["healthy"] = False
        print(json.dumps(results, indent=2))
        sys.exit(1)

    # 2. Employee endpoint
    def do_employees():
        url = client.url("employees")
        resp = client.session.get(url)
        if not resp.ok:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        employees = data.get("employees", [])
        active = sum(1 for e in employees if e.get("status") == "Active")
        return {"employee_count": len(employees), "active_count": active}

    check("employees", do_employees)

    passed = sum(1 for c in CHECKS if c["status"] == "pass")
    total = len(CHECKS)
    results["summary"] = f"{passed}/{total} checks passed"
    results["healthy"] = passed == total

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
