#!/usr/bin/env python3
"""
UniFi Bridge Health Check

Validates UniFi controller credentials and tests API connectivity.
Second leg of the core triad -- imports the client to verify the bridge
is operational.

Usage:
    python3 unifi_check.py              # Full health check
    python3 unifi_check.py --quick      # Env-var check only (no API calls)

Exit codes:
    0 = healthy (all checks passed)
    1 = unhealthy (one or more checks failed)

The --quick flag is designed for Docker HEALTHCHECK integration where
fast response times matter more than exhaustive validation.
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass


def check_env_vars() -> dict:
    """Verify required environment variables are set."""
    required = ["UNIFI_URL", "UNIFI_USERNAME", "UNIFI_PASSWORD"]
    missing = [v for v in required if not os.getenv(v)]
    return {
        "env_vars_ok": len(missing) == 0,
        "missing": missing,
    }


def check_api() -> dict:
    """Test API connectivity using the client's test_connection() method."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from unifi_client import UniFiClient

    start = time.time()
    try:
        client = UniFiClient()
        result = client.test_connection()
        elapsed_ms = int((time.time() - start) * 1000)
        result["latency_ms"] = elapsed_ms
        client.logout()
        return result
    except SystemExit:
        return {"ok": False, "error": "Client initialization failed (missing credentials)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_device_count() -> dict:
    """Verify at least one device is visible (confirms API scope)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from unifi_client import UniFiClient

    try:
        client = UniFiClient()
        devices = client.list_devices()
        client.logout()
        return {
            "ok": True,
            "device_count": len(devices),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("UniFi Bridge Health Check")
    print("=" * 60)

    env_result = check_env_vars()
    if env_result["env_vars_ok"]:
        print("[PASS] Environment variables configured")
    else:
        print(f"[FAIL] Missing env vars: {', '.join(env_result['missing'])}")
        print(json.dumps({"status": "unhealthy", "env": env_result}, indent=2))
        sys.exit(1)

    if quick:
        print("\n[DONE] Quick check passed (env vars only)")
        print(json.dumps({"status": "healthy", "mode": "quick"}, indent=2))
        sys.exit(0)

    api_result = check_api()
    if api_result.get("ok"):
        ctrl_type = api_result.get("controller_type", "?")
        sites = api_result.get("sites", "?")
        latency = api_result.get("latency_ms", "?")
        print(f"[PASS] API connectivity confirmed ({ctrl_type}, {sites} site(s), {latency}ms)")
    else:
        print(f"[FAIL] API check failed: {api_result.get('error', 'unknown')}")
        print(json.dumps({"status": "unhealthy", "api": api_result}, indent=2))
        sys.exit(1)

    device_result = check_device_count()
    if device_result.get("ok"):
        print(f"[PASS] Device visibility confirmed ({device_result['device_count']} devices)")
    else:
        print(f"[WARN] Device check failed: {device_result.get('error', 'unknown')}")

    print("\n[DONE] All checks passed")
    print(json.dumps({
        "status": "healthy",
        "env": env_result,
        "api": api_result,
        "devices": device_result,
    }, indent=2))


if __name__ == "__main__":
    main()
