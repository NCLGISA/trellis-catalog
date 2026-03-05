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
Health check for the Azure Resource Manager bridge.

Validates environment variables are set and tests ARM API connectivity.
Reports cloud environment (commercial vs usgovernment) in output.

Usage:
    python3 arm_check.py
"""

import os
import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from arm_client import ArmClient, AZURE_CLOUD, ARM_BASE


def check():
    """Run health checks and report status."""
    checks = {"cloud": AZURE_CLOUD, "arm_endpoint": ARM_BASE}

    required_vars = [
        "AZURE_TENANT_ID", "ARM_CLIENT_ID", "ARM_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"
    ]
    env_status = {}
    all_set = True
    for var in required_vars:
        val = os.getenv(var, "")
        if val:
            env_status[var] = "set"
        else:
            env_status[var] = "MISSING"
            all_set = False
    checks["environment"] = env_status

    if not all_set:
        checks["api_connection"] = {"ok": False, "error": "Missing environment variables"}
        print(json.dumps(checks, indent=2))
        sys.exit(1)

    try:
        client = ArmClient()
        result = client.test_connection()
        checks["api_connection"] = result
    except Exception as e:
        checks["api_connection"] = {"ok": False, "error": str(e)}

    if checks["api_connection"].get("ok"):
        try:
            vms = client.list_vms()
            checks["permission_test"] = {
                "ok": True,
                "test": "Microsoft.Compute/virtualMachines/read",
                "result": f"Successfully listed VMs ({len(vms)} found)",
            }
        except Exception as e:
            checks["permission_test"] = {
                "ok": False,
                "test": "Microsoft.Compute/virtualMachines/read",
                "error": str(e),
            }

    print(json.dumps(checks, indent=2))

    if checks["api_connection"].get("ok"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    check()
