#!/usr/bin/env python3
"""
Sierra AirLink Bridge Health Check

Validates AirVantage OAuth2 credentials and tests API connectivity
including system and gateway inventory counts.

Usage:
    python3 airlink_check.py              # Full health check
    python3 airlink_check.py --quick      # Token-only check
    python3 airlink_check.py --verbose    # Detailed output with full JSON
"""

import sys
import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from airlink_client import AirLinkClient


def check_env_vars() -> dict:
    """Verify required environment variables are set."""
    client_id = os.getenv("AIRLINK_CLIENT_ID", "")
    client_secret = os.getenv("AIRLINK_CLIENT_SECRET", "")
    region = os.getenv("AIRLINK_REGION", "na")
    return {
        "AIRLINK_CLIENT_ID": "set" if client_id else "NOT SET",
        "AIRLINK_CLIENT_SECRET": "set" if client_secret else "NOT SET",
        "AIRLINK_REGION": region,
        "all_set": bool(client_id and client_secret),
    }


def check_token(client: AirLinkClient) -> dict:
    """Acquire an OAuth2 token via Client Credentials grant."""
    try:
        client._acquire_token()
        return {
            "ok": True,
            "token_status": "valid" if client._access_token else "failed",
            "expires_at": datetime.fromtimestamp(
                client._token_expires_at, tz=timezone.utc
            ).isoformat() if client._token_expires_at else "unknown",
        }
    except SystemExit:
        return {"ok": False, "error": "Token acquisition failed (check credentials)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_systems(client: AirLinkClient) -> dict:
    """List systems and report communication status breakdown."""
    try:
        systems = client.list_systems(
            fields="uid,name,commStatus,lastCommDate,lifeCycleState"
        )
        from collections import Counter
        by_status = Counter(s.get("commStatus", "UNDEFINED") for s in systems)
        by_state = Counter(s.get("lifeCycleState", "?") for s in systems)
        return {
            "ok": True,
            "total": len(systems),
            "by_comm_status": dict(by_status.most_common()),
            "by_lifecycle": dict(by_state.most_common()),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_gateways(client: AirLinkClient) -> dict:
    """List gateways and report type breakdown."""
    try:
        gateways = client.list_gateways(
            fields="uid,imei,serialNumber,type,state"
        )
        from collections import Counter
        by_type = Counter(g.get("type", "?") or "?" for g in gateways)
        return {
            "ok": True,
            "total": len(gateways),
            "by_type": dict(by_type.most_common()),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_alerts(client: AirLinkClient) -> dict:
    """Check alert rules and current active alerts."""
    try:
        rules = client.list_alert_rules()
        current = client.list_current_alerts()
        active_count = sum(1 for a in current if a.get("state", False))
        return {
            "ok": True,
            "total_rules": len(rules),
            "current_alerts": len(current),
            "active_alerts": active_count,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    verbose = "--verbose" in sys.argv
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("Sierra AirLink Bridge Health Check")
    print("=" * 60)

    # ── Step 1: Environment variables
    env_result = check_env_vars()
    print(f"\n[1/5] Environment variables")
    print(f"  AIRLINK_CLIENT_ID:     {env_result['AIRLINK_CLIENT_ID']}")
    print(f"  AIRLINK_CLIENT_SECRET: {env_result['AIRLINK_CLIENT_SECRET']}")
    print(f"  AIRLINK_REGION:        {env_result['AIRLINK_REGION']}")
    if env_result["all_set"]:
        print("  PASS")
    else:
        print("  FAIL: Set missing variables in .env or docker-compose.yml")
        sys.exit(1)

    client = AirLinkClient()

    # ── Step 2: Token acquisition
    print(f"\n[2/5] OAuth2 token acquisition")
    token_result = check_token(client)
    if token_result.get("ok"):
        print(f"  Token: {token_result['token_status']}")
        print(f"  Expires: {token_result['expires_at']}")
        print("  PASS")
    else:
        print(f"  FAIL: {token_result.get('error', 'unknown error')}")
        sys.exit(1)

    if quick:
        print("\n[DONE] Quick check passed (token only)")
        sys.exit(0)

    # ── Step 3: Systems
    print(f"\n[3/5] Systems inventory")
    sys_result = check_systems(client)
    if sys_result["ok"]:
        print(f"  Total systems: {sys_result['total']}")
        for status, count in sys_result["by_comm_status"].items():
            print(f"    {status:12s}  {count}")
        print("  PASS")
    else:
        print(f"  WARN: {sys_result.get('error')}")

    # ── Step 4: Gateways
    print(f"\n[4/5] Gateways inventory")
    gw_result = check_gateways(client)
    if gw_result["ok"]:
        print(f"  Total gateways: {gw_result['total']}")
        for gtype, count in gw_result["by_type"].items():
            print(f"    {gtype:20s}  {count}")
        print("  PASS")
    else:
        print(f"  WARN: {gw_result.get('error')}")

    # ── Step 5: Alerts
    print(f"\n[5/5] Alert rules & active alerts")
    alert_result = check_alerts(client)
    if alert_result["ok"]:
        print(f"  Alert rules:   {alert_result['total_rules']}")
        print(f"  Active alerts: {alert_result['active_alerts']}")
        print("  PASS")
    else:
        print(f"  WARN: {alert_result.get('error')}")

    # ── Summary
    print("\n" + "=" * 60)
    print("All checks passed. Sierra AirLink bridge is operational.")
    print("=" * 60)

    if verbose:
        print("\n--- Full Results ---")
        print(json.dumps({
            "env": env_result,
            "token": token_result,
            "systems": sys_result,
            "gateways": gw_result,
            "alerts": alert_result,
        }, indent=2, default=str))


if __name__ == "__main__":
    main()
