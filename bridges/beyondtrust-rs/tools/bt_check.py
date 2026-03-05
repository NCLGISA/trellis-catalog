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
BeyondTrust Remote Support -- Health Check

Validates OAuth2 authentication and appliance health.
Exit code 0 = healthy, non-zero = unhealthy.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from bt_client import BTClient, BTAuthError, BTAPIError, strip_ns, xml_to_dict, print_json


def main():
    try:
        client = BTClient()
    except BTAuthError as e:
        print(f"UNHEALTHY: {e}")
        sys.exit(1)

    errors = []
    result = {"status": "healthy", "checks": {}}

    # 1. Authenticate
    try:
        client._authenticate()
        result["checks"]["auth"] = "ok"
    except BTAuthError as e:
        result["checks"]["auth"] = f"FAILED: {e}"
        errors.append("auth")

    # 2. Check appliance health
    if not errors:
        try:
            root = client.command("check_health")
            root = strip_ns(root)
            health = xml_to_dict(root)
            healthy = health.get("healthy", "0")
            result["checks"]["appliance_health"] = {
                "healthy": healthy == "1",
                "hostname": health.get("site", {}).get("_text", "unknown"),
                "version": health.get("version", "unknown"),
            }
            if healthy != "1":
                errors.append("appliance_health")
        except BTAPIError as e:
            result["checks"]["appliance_health"] = f"FAILED: {e}"
            errors.append("appliance_health")

    # 3. Get API info
    if not errors:
        try:
            root = client.command("get_api_info")
            root = strip_ns(root)
            info = xml_to_dict(root)
            result["checks"]["api_info"] = {
                "api_version": info.get("api_version", "unknown"),
            }
        except BTAPIError:
            result["checks"]["api_info"] = "unavailable (non-critical)"

    if errors:
        result["status"] = "unhealthy"
        result["failed_checks"] = errors

    print_json(result)
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
