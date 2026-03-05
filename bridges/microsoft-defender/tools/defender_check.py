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
Health check for the Microsoft Defender bridge.

Validates environment variables and tests API connectivity to all three
API surfaces: Defender XDR/MDE, Sentinel ARM, and Log Analytics.

Usage:
    python3 defender_check.py           # Full health check
    python3 defender_check.py --quick   # Env vars only (no API calls)
"""

import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

REQUIRED_VARS = [
    ("AZURE_TENANT_ID", "Entra ID tenant"),
    ("DEFENDER_CLIENT_ID", "App registration client ID"),
    ("DEFENDER_CLIENT_SECRET", "App registration client secret"),
]

SENTINEL_VARS = [
    ("SENTINEL_SUBSCRIPTION_ID", "Azure subscription ID"),
    ("SENTINEL_RESOURCE_GROUP", "Sentinel resource group"),
    ("SENTINEL_WORKSPACE_NAME", "Log Analytics workspace name"),
    ("SENTINEL_WORKSPACE_ID", "Log Analytics workspace GUID"),
]


def check_env() -> bool:
    ok = True
    for var, desc in REQUIRED_VARS:
        val = os.getenv(var, "")
        if val:
            print(f"  [OK]   {var}")
        else:
            print(f"  [FAIL] {var} -- {desc}")
            ok = False

    sentinel_configured = False
    for var, desc in SENTINEL_VARS:
        val = os.getenv(var, "")
        if val:
            print(f"  [OK]   {var}")
            sentinel_configured = True
        else:
            print(f"  [SKIP] {var} -- {desc} (optional)")

    return ok, sentinel_configured


def check_api(sentinel: bool) -> bool:
    from defender_client import DefenderClient

    client = DefenderClient()
    ok = True

    print("\n  Testing Defender XDR API...")
    result = client.test_security_api()
    if result["ok"]:
        print("  [OK]   Defender XDR API")
    else:
        print(f"  [FAIL] Defender XDR API (HTTP {result['status']})")
        ok = False

    print("  Testing MDE API...")
    result = client.test_mde_api()
    if result["ok"]:
        print("  [OK]   MDE API")
    else:
        print(f"  [FAIL] MDE API (HTTP {result['status']})")
        ok = False

    if sentinel:
        print("  Testing Sentinel ARM API...")
        result = client.test_sentinel_api()
        if result["ok"]:
            print("  [OK]   Sentinel API")
        else:
            print(f"  [FAIL] Sentinel API (HTTP {result['status']})")
            ok = False

        print("  Testing Log Analytics query...")
        result = client.test_log_analytics()
        if result["ok"]:
            print("  [OK]   Log Analytics")
        else:
            print(f"  [FAIL] Log Analytics")
            ok = False

    return ok


def main():
    quick = "--quick" in sys.argv

    print("Microsoft Defender Bridge Health Check\n")
    print("Environment variables:")
    env_ok, sentinel = check_env()

    if not env_ok:
        print("\nResult: FAIL (missing required env vars)")
        sys.exit(1)

    if quick:
        print("\nResult: OK (env vars only)")
        sys.exit(0)

    print("\nAPI connectivity:")
    api_ok = check_api(sentinel)

    if api_ok:
        print("\nResult: OK")
    else:
        print("\nResult: FAIL (API connectivity issues)")
        sys.exit(1)


if __name__ == "__main__":
    main()
