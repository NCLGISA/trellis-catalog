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

"""NAVEX PolicyTech bridge health check.

Validates API key and connectivity to the OpenSearch endpoint.
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
    from policytech_client import PolicyTechClient

    results = {"bridge": "navex-policytech", "checks": CHECKS}
    client = None

    def do_connect():
        nonlocal client
        client = PolicyTechClient()
        return {
            "base_url": client.base_url,
            "api_url": client.api_url,
        }

    check("connect", do_connect)

    if client is None:
        results["summary"] = "0/2 checks passed"
        results["healthy"] = False
        print(json.dumps(results, indent=2))
        sys.exit(1)

    def do_search():
        result = client.search("policy", items_per_page=5)
        return {
            "total_results": result.get("total_results", 0),
            "sample_count": len(result.get("documents", [])),
        }

    check("search", do_search)

    passed = sum(1 for c in CHECKS if c["status"] == "pass")
    total = len(CHECKS)
    results["summary"] = f"{passed}/{total} checks passed"
    results["healthy"] = passed == total

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
