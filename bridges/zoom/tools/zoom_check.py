#!/usr/bin/env python3
"""
Zoom Bridge Health Check

Validates Zoom S2S OAuth credentials and tests API connectivity.
Designed to run from inside the bridge container or locally for debugging.

Usage:
    python3 zoom_check.py              # Full health check
    python3 zoom_check.py --quick      # Token-only check (no API calls)
    python3 zoom_check.py --verbose    # Detailed output with user counts
"""

import sys
import json
import time
import os
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_env_path)


def check_env_vars() -> dict:
    """Verify required environment variables are set."""
    required = ["ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"]
    missing = [v for v in required if not os.getenv(v)]
    return {
        "env_vars_ok": len(missing) == 0,
        "missing": missing,
    }


def check_token() -> dict:
    """Attempt to obtain an S2S OAuth token."""
    account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
    client_id = os.getenv("ZOOM_CLIENT_ID", "")
    client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")

    if not all([account_id, client_id, client_secret]):
        return {"token_ok": False, "error": "Missing credentials"}

    auth_str = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

    start = time.time()
    try:
        resp = requests.post(
            "https://zoom.us/oauth/token",
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "account_credentials",
                "account_id": account_id,
            },
            timeout=30,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        if resp.status_code == 200:
            token_data = resp.json()
            return {
                "token_ok": True,
                "expires_in": token_data.get("expires_in"),
                "token_type": token_data.get("token_type"),
                "scope": token_data.get("scope", ""),
                "latency_ms": elapsed_ms,
            }
        else:
            return {
                "token_ok": False,
                "status": resp.status_code,
                "error": resp.text,
                "latency_ms": elapsed_ms,
            }
    except requests.RequestException as e:
        return {"token_ok": False, "error": str(e)}


def check_api(token: str = None) -> dict:
    """Test API access by fetching account info and user count."""
    if not token:
        # Get a fresh token
        account_id = os.getenv("ZOOM_ACCOUNT_ID", "")
        client_id = os.getenv("ZOOM_CLIENT_ID", "")
        client_secret = os.getenv("ZOOM_CLIENT_SECRET", "")
        auth_str = base64.b64encode(
            f"{client_id}:{client_secret}".encode()
        ).decode()
        resp = requests.post(
            "https://zoom.us/oauth/token",
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "account_credentials",
                "account_id": account_id,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return {"api_ok": False, "error": "Could not obtain token"}
        token = resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    results = {}

    # Check account info
    try:
        resp = requests.get(
            "https://api.zoom.us/v2/users/me",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            me = resp.json()
            results["authenticated_as"] = me.get("email", "unknown")
            results["account_id"] = me.get("account_id", "unknown")
        else:
            results["users_me_error"] = f"{resp.status_code}: {resp.text[:200]}"
    except requests.RequestException as e:
        results["users_me_error"] = str(e)

    # Check user listing (tests admin scope)
    try:
        resp = requests.get(
            "https://api.zoom.us/v2/users",
            headers=headers,
            params={"page_size": 1, "status": "active"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            results["total_active_users"] = data.get("total_records", 0)
            results["users_api_ok"] = True
        else:
            results["users_api_ok"] = False
            results["users_api_error"] = f"{resp.status_code}: {resp.text[:200]}"
    except requests.RequestException as e:
        results["users_api_ok"] = False
        results["users_api_error"] = str(e)

    # Check account info endpoint
    try:
        resp = requests.get(
            "https://api.zoom.us/v2/accounts/me",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            acct = resp.json()
            results["account_name"] = acct.get("account_name", "unknown")
            results["vanity_url"] = acct.get("vanity_url", "")
            results["account_api_ok"] = True
        else:
            results["account_api_ok"] = False
            results["account_api_error"] = f"{resp.status_code}: {resp.text[:200]}"
    except requests.RequestException as e:
        results["account_api_ok"] = False
        results["account_api_error"] = str(e)

    results["api_ok"] = results.get("users_api_ok", False) and results.get(
        "account_api_ok", False
    )
    return results


def main():
    verbose = "--verbose" in sys.argv
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("Zoom Bridge Health Check")
    print("=" * 60)

    # Step 1: Environment variables
    env_result = check_env_vars()
    if env_result["env_vars_ok"]:
        print("[PASS] Environment variables configured")
    else:
        print(f"[FAIL] Missing env vars: {', '.join(env_result['missing'])}")
        sys.exit(1)

    # Step 2: Token generation
    token_result = check_token()
    if token_result["token_ok"]:
        print(
            f"[PASS] Token obtained "
            f"(expires_in={token_result['expires_in']}s, "
            f"latency={token_result['latency_ms']}ms)"
        )
        if verbose:
            scopes = token_result.get("scope", "")
            print(f"       Scopes: {scopes}")
    else:
        print(f"[FAIL] Token request failed: {token_result.get('error', 'unknown')}")
        sys.exit(1)

    if quick:
        print("\n[DONE] Quick check passed (token only)")
        sys.exit(0)

    # Step 3: API connectivity
    api_result = check_api()
    if api_result.get("api_ok"):
        print(f"[PASS] API access confirmed")
        print(f"       Account: {api_result.get('account_name', '?')}")
        print(f"       Authenticated as: {api_result.get('authenticated_as', '?')}")
        print(f"       Active users: {api_result.get('total_active_users', '?')}")
        if api_result.get("vanity_url"):
            print(f"       Vanity URL: {api_result['vanity_url']}")
    else:
        print("[FAIL] API access check failed")
        for k, v in api_result.items():
            if "error" in k:
                print(f"       {k}: {v}")
        sys.exit(1)

    print("\n[DONE] All checks passed")

    if verbose:
        print("\n--- Full Results ---")
        print(json.dumps({
            "env": env_result,
            "token": {k: v for k, v in token_result.items() if k != "scope"},
            "api": api_result,
        }, indent=2))


if __name__ == "__main__":
    main()
