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

"""Confluence Cloud bridge health check.

Validates connectivity to the Confluence site.  When per-operator
credentials (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN) are available,
also validates authentication and space access.  When only the shared
CONFLUENCE_URL is set, performs a connect-only check so the Docker
healthcheck can pass without operator secrets baked into the container.

Exits 0 on success, 1 on any failure.
"""

import json
import os
import sys

import requests

CHECKS = []

CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "").rstrip("/")
CONFLUENCE_EMAIL = os.environ.get("CONFLUENCE_EMAIL", "")
CONFLUENCE_API_TOKEN = os.environ.get("CONFLUENCE_API_TOKEN", "")


def check(name, fn):
    try:
        result = fn()
        CHECKS.append({"name": name, "status": "pass", **result})
    except Exception as exc:
        CHECKS.append({"name": name, "status": "fail", "error": str(exc)})


def main():
    results = {"bridge": "confluence", "checks": CHECKS}

    if not CONFLUENCE_URL:
        results["checks"] = [{"name": "connect", "status": "fail",
                               "error": "CONFLUENCE_URL not set"}]
        results["summary"] = "0/1 checks passed"
        results["healthy"] = False
        print(json.dumps(results, indent=2))
        sys.exit(1)

    has_operator_creds = bool(CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN)

    def do_connect():
        resp = requests.get(f"{CONFLUENCE_URL}/_edge/tenant_info", timeout=10)
        resp.raise_for_status()
        return {"base_url": CONFLUENCE_URL}

    check("connect", do_connect)

    if has_operator_creds:
        sys.path.insert(0, os.path.dirname(__file__))
        from confluence_client import ConfluenceClient
        client = ConfluenceClient()

        def do_auth():
            user = client.get_current_user()
            return {
                "user": user.get("displayName", ""),
                "email": user.get("email", ""),
                "account_type": user.get("accountType", ""),
            }

        check("auth", do_auth)

        def do_spaces():
            data = client.list_spaces(limit=5)
            spaces = data.get("results", [])
            return {
                "space_count": len(spaces),
                "sample": [s.get("name", "") for s in spaces[:3]],
            }

        check("spaces", do_spaces)

    passed = sum(1 for c in CHECKS if c["status"] == "pass")
    total = len(CHECKS)
    results["summary"] = f"{passed}/{total} checks passed"
    results["healthy"] = passed == total

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
