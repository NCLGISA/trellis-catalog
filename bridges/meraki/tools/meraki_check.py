#!/usr/bin/env python3
"""
Meraki Bridge Health Check

Validates:
  1. MERAKI_API_KEY environment variable is set
  2. API key is valid and can access the organization
  3. Reports organization, network, and device summary

Usage:
  python3 meraki_check.py
"""

import os
import sys
import json


def main():
    print("=" * 60)
    print("Meraki Bridge Health Check")
    print("=" * 60)

    # Check environment
    api_key = os.getenv("MERAKI_API_KEY", "")
    print(f"\n[1/4] MERAKI_API_KEY: {'set (' + api_key[:8] + '...)' if api_key else 'NOT SET'}")
    if not api_key:
        print("  FAIL: Set MERAKI_API_KEY in docker-compose.yml or .env")
        sys.exit(1)
    print("  PASS")

    # Test API access
    from meraki_client import MerakiClient
    client = MerakiClient()

    print("\n[2/4] Organization access:")
    try:
        org = client.get_org()
        print(f"  Organization: {org.get('name')}")
        print(f"  Org ID:       {org.get('id')}")
        print(f"  Licensing:    {org.get('licensing', {}).get('model', 'unknown')}")
        print(f"  API enabled:  {org.get('api', {}).get('enabled', 'unknown')}")
        print(f"  Cloud region: {org.get('cloud', {}).get('region', {}).get('name', 'unknown')}")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    print("\n[3/4] Network access:")
    try:
        networks = client.list_networks()
        print(f"  Total networks: {len(networks)}")
        from collections import Counter
        product_types = Counter()
        for n in networks:
            for pt in n.get("productTypes", []):
                product_types[pt] += 1
        print("  Product types across networks:")
        for pt, count in product_types.most_common():
            print(f"    {pt:20s}  {count} networks")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    print("\n[4/4] Device access:")
    try:
        overview = client.get_device_status_overview()
        counts = overview.get("counts", {}).get("byStatus", {})
        total = sum(counts.values())
        print(f"  Total devices: {total}")
        for status, count in sorted(counts.items()):
            print(f"    {status:12s}  {count}")

        admins = client.list_admins()
        print(f"  Organization admins: {len(admins)}")
        for a in admins:
            mfa = "MFA" if a.get("twoFactorAuthEnabled") else "no-MFA"
            print(f"    {a.get('name', '?'):25s}  {a.get('orgAccess', '?'):6s}  {mfa}")
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All checks passed. Meraki bridge is operational.")
    print("=" * 60)


if __name__ == "__main__":
    main()
