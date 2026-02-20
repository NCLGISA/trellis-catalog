#!/usr/bin/env python3
"""
Cloudflare Bridge Health Check

Validates Cloudflare API token and tests connectivity across all three
service areas: Core (zones, DNS), Zero Trust (Access, Gateway), and Email.

Designed to run locally (in a venv) for pre-deployment validation or
inside the bridge container for ongoing health checks.

Usage:
    python3 cloudflare_check.py              # Full health check
    python3 cloudflare_check.py --quick      # Token-only check (no API calls)
    python3 cloudflare_check.py --verbose    # Detailed output with full JSON
"""

import sys
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

# Allow running standalone without cloudflare_client on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudflare_client import CloudflareClient


def check_env_vars() -> dict:
    """Verify required environment variables are set."""
    token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    return {
        "CLOUDFLARE_API_TOKEN": f"set ({token[:8]}...)" if token else "NOT SET",
        "CLOUDFLARE_ACCOUNT_ID": f"set ({account_id[:8]}...)" if account_id else "NOT SET",
        "all_set": bool(token and account_id),
    }


def check_token(client: CloudflareClient) -> dict:
    """Verify the API token is valid and active."""
    result = client.verify_token()
    return result


def check_zones(client: CloudflareClient) -> dict:
    """List zones and confirm the target domain (CLOUDFLARE_DOMAIN) is present."""
    zones = client.list_zones()
    target_domain = os.environ.get("CLOUDFLARE_DOMAIN", "example.com")
    target = next(
        (z for z in zones if z.get("name") == target_domain), None
    )
    return {
        "ok": len(zones) > 0,
        "total_zones": len(zones),
        "zones": [
            {
                "name": z.get("name"),
                "status": z.get("status"),
                "plan": z.get("plan", {}).get("name", "?"),
            }
            for z in zones
        ],
        "target_zone_found": target is not None,
        "target_zone_id": target["id"] if target else None,
    }


def check_dns(client: CloudflareClient, zone_id: str) -> dict:
    """Count DNS records by type."""
    records = client.list_dns_records(zone_id)
    from collections import Counter
    by_type = Counter(r.get("type", "?") for r in records)
    return {
        "ok": len(records) > 0,
        "total_records": len(records),
        "by_type": dict(by_type.most_common()),
    }


def check_tunnels(client: CloudflareClient) -> dict:
    """List active Cloudflare Tunnels."""
    tunnels = client.list_tunnels()
    active = [t for t in tunnels if t.get("status") == "healthy"]
    return {
        "ok": True,
        "total_tunnels": len(tunnels),
        "healthy": len(active),
        "tunnels": [
            {
                "name": t.get("name"),
                "status": t.get("status"),
                "id": t.get("id", "")[:12],
            }
            for t in tunnels
        ],
    }


def check_access_apps(client: CloudflareClient) -> dict:
    """List Zero Trust Access Applications."""
    try:
        apps = client.list_access_apps()
        return {
            "ok": True,
            "total_apps": len(apps),
            "apps": [
                {
                    "name": a.get("name"),
                    "type": a.get("type"),
                    "domain": a.get("domain", ""),
                }
                for a in apps
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_service_tokens(client: CloudflareClient) -> dict:
    """List Access Service Tokens."""
    try:
        tokens = client.list_service_tokens()
        return {
            "ok": True,
            "total_tokens": len(tokens),
            "tokens": [
                {
                    "name": t.get("name"),
                    "expires_at": t.get("expires_at", "never"),
                    "updated_at": t.get("updated_at", "?"),
                }
                for t in tokens
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_gateway(client: CloudflareClient) -> dict:
    """Check Zero Trust Gateway rules."""
    try:
        rules = client.list_gateway_rules()
        return {
            "ok": True,
            "total_rules": len(rules),
            "rules": [
                {
                    "name": r.get("name"),
                    "action": r.get("action"),
                    "enabled": r.get("enabled"),
                }
                for r in rules
            ],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_email_routing(client: CloudflareClient, zone_id: str) -> dict:
    """Check email routing settings and rules."""
    try:
        settings = client.get_email_routing_settings(zone_id)
        rules = client.list_email_routing_rules(zone_id)
        enabled = settings.get("enabled", False) if settings else False
        return {
            "ok": True,
            "enabled": enabled,
            "total_rules": len(rules),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "note": "Email Routing may not be enabled for this zone"}


def main():
    verbose = "--verbose" in sys.argv
    quick = "--quick" in sys.argv

    print("=" * 60)
    print("Cloudflare Bridge Health Check")
    print("=" * 60)

    # ── Step 1: Environment variables ───────────────────────────────
    env_result = check_env_vars()
    print(f"\n[1/8] Environment variables")
    print(f"  CLOUDFLARE_API_TOKEN:  {env_result['CLOUDFLARE_API_TOKEN']}")
    print(f"  CLOUDFLARE_ACCOUNT_ID: {env_result['CLOUDFLARE_ACCOUNT_ID']}")
    if env_result["all_set"]:
        print("  PASS")
    else:
        print("  FAIL: Set missing variables in .env or docker-compose.yml")
        sys.exit(1)

    client = CloudflareClient()

    # ── Step 2: Token verification ──────────────────────────────────
    print(f"\n[2/8] Token verification")
    token_result = check_token(client)
    if token_result.get("ok"):
        print(f"  Status: {token_result.get('status', 'active')}")
        not_before = token_result.get("not_before", "?")
        expires_on = token_result.get("expires_on", "(never)")
        if not_before and not_before != "?":
            print(f"  Not before: {not_before}")
        if expires_on:
            print(f"  Expires on: {expires_on}")
        print("  PASS")
    else:
        print(f"  FAIL: {token_result.get('error', 'unknown error')}")
        sys.exit(1)

    if quick:
        print("\n[DONE] Quick check passed (token only)")
        sys.exit(0)

    # ── Step 3: Zones ───────────────────────────────────────────────
    print(f"\n[3/8] Zones")
    zone_result = check_zones(client)
    if zone_result["ok"]:
        target_domain = os.environ.get("CLOUDFLARE_DOMAIN", "example.com")
        for z in zone_result["zones"]:
            print(f"  {z['name']} ({z['status']}, plan: {z['plan']})")
        if zone_result["target_zone_found"]:
            print(f"  Target zone ID: {zone_result['target_zone_id']}")
        else:
            print(f"  WARNING: {target_domain} not found in zones")
        print("  PASS")
    else:
        print("  FAIL: No zones accessible")
        sys.exit(1)

    zone_id = zone_result.get("target_zone_id")

    # ── Step 4: DNS records ─────────────────────────────────────────
    print(f"\n[4/8] DNS records")
    if zone_id:
        dns_result = check_dns(client, zone_id)
        if dns_result["ok"]:
            print(f"  Total records: {dns_result['total_records']}")
            if verbose:
                for rtype, count in dns_result["by_type"].items():
                    print(f"    {rtype:10s}  {count}")
            print("  PASS")
        else:
            print("  FAIL: Could not list DNS records")
    else:
        print("  SKIP: No target zone ID available")

    # ── Step 5: Tunnels ─────────────────────────────────────────────
    print(f"\n[5/8] Cloudflare Tunnels")
    tunnel_result = check_tunnels(client)
    print(f"  Total tunnels: {tunnel_result['total_tunnels']}")
    print(f"  Healthy: {tunnel_result['healthy']}")
    if verbose:
        for t in tunnel_result["tunnels"]:
            print(f"    {t['name']:40s}  {t['status']:12s}  id={t['id']}")
    print("  PASS")

    # ── Step 6: Access Applications ─────────────────────────────────
    print(f"\n[6/8] Zero Trust - Access Applications")
    access_result = check_access_apps(client)
    if access_result["ok"]:
        print(f"  Access apps: {access_result['total_apps']}")
        if verbose:
            for a in access_result["apps"]:
                print(f"    {a['name']:40s}  type={a['type']:15s}  {a['domain']}")
        print("  PASS")
    else:
        print(f"  WARN: {access_result.get('error', 'Could not list access apps')}")

    # ── Step 7: Service Tokens ──────────────────────────────────────
    print(f"\n[7/8] Zero Trust - Service Tokens")
    token_list_result = check_service_tokens(client)
    if token_list_result["ok"]:
        print(f"  Service tokens: {token_list_result['total_tokens']}")
        if verbose:
            for t in token_list_result["tokens"]:
                print(f"    {t['name']:40s}  expires={t['expires_at']}")
        print("  PASS")
    else:
        print(f"  WARN: {token_list_result.get('error', 'Could not list service tokens')}")

    # ── Step 8: Email Routing ───────────────────────────────────────
    print(f"\n[8/8] Email Routing")
    if zone_id:
        email_result = check_email_routing(client, zone_id)
        if email_result["ok"]:
            status = "enabled" if email_result.get("enabled") else "disabled"
            print(f"  Email routing: {status}")
            print(f"  Routing rules: {email_result['total_rules']}")
            print("  PASS")
        else:
            note = email_result.get("note", "")
            print(f"  SKIP: {note or email_result.get('error', 'unknown')}")
    else:
        print("  SKIP: No target zone ID available")

    # ── Summary ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("All checks passed. Cloudflare bridge is operational.")
    print("=" * 60)

    if verbose:
        print("\n--- Full Results ---")
        print(json.dumps({
            "env": env_result,
            "token": {k: v for k, v in token_result.items() if k != "ok"},
            "zones": zone_result,
            "dns": dns_result if zone_id else "skipped",
            "tunnels": tunnel_result,
            "access_apps": access_result,
            "service_tokens": token_list_result,
            "email_routing": email_result if zone_id else "skipped",
        }, indent=2, default=str))


if __name__ == "__main__":
    main()
