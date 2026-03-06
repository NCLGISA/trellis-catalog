#!/usr/bin/env python3
"""
ArcGIS Online - Portal Administration

Organization info, usage reports, credit consumption, and role management.

Usage:
    python3 arcgis_online_admin.py org-info
    python3 arcgis_online_admin.py credits
    python3 arcgis_online_admin.py usage --days 30
    python3 arcgis_online_admin.py roles
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arcgis_online_client import ArcGISOnlineClient


def cmd_org_info(client, args):
    result = client.get("portals/self")
    sub = result.get("subscriptionInfo", {})
    print(f"Organization: {result.get('name')}")
    print(f"ID: {result.get('id')}")
    print(f"URL Key: {result.get('urlKey')}")
    print(f"Region: {result.get('region')}")
    print(f"Subscription: {sub.get('type', 'unknown')}")
    print(f"Max Users: {sub.get('maxUsers', 'unlimited')}")
    print(f"Available Credits: {result.get('availableCredits', 'n/a')}")
    print(f"Default Basemap: {result.get('defaultBasemap', {}).get('title', 'n/a')}")
    print(f"Created: {result.get('created')}")
    print(f"Modified: {result.get('modified')}")

    helpers = result.get("helperServices", {})
    print(f"\nHelper Services:")
    for svc_name, svc_val in helpers.items():
        if isinstance(svc_val, dict) and "url" in svc_val:
            print(f"  {svc_name}: {svc_val['url']}")
        elif isinstance(svc_val, list):
            for s in svc_val:
                if isinstance(s, dict) and "url" in s:
                    print(f"  {svc_name}: {s['url']}")


def cmd_credits(client, args):
    result = client.get("portals/self")
    available = result.get("availableCredits", "n/a")
    print(f"Available Credits: {available}")

    sub = result.get("subscriptionInfo", {})
    print(f"Subscription Type: {sub.get('type', 'unknown')}")
    print(f"Expiration: {sub.get('expDate', 'n/a')}")


def cmd_usage(client, args):
    end_time = int(time.time() * 1000)
    start_time = end_time - (args.days * 86400 * 1000)

    result = client.get("portals/self/usage", params={
        "startTime": start_time,
        "endTime": end_time,
        "period": "1d",
        "vars": "credits,num",
    })
    data = result.get("data", [])
    if not data:
        print("No usage data available for the specified period")
        return

    print(f"Usage report ({args.days} days)")
    print(json.dumps(result, indent=2, default=str))


def cmd_roles(client, args):
    result = client.get("portals/self/roles", params={"num": 100})
    roles = result.get("roles", [])
    print(f"Custom roles: {len(roles)}")
    print()
    for role in roles:
        print(f"  {role.get('id', '?'):20s}  {role.get('name', '?'):30s}  {role.get('description', '')[:60]}")

    print("\nBuilt-in roles: org_admin, org_publisher, org_user")


def main():
    parser = argparse.ArgumentParser(description="ArcGIS Online Portal Admin")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("org-info")
    sub.add_parser("credits")

    p_u = sub.add_parser("usage")
    p_u.add_argument("--days", type=int, default=30)

    sub.add_parser("roles")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = ArcGISOnlineClient()
    cmds = {
        "org-info": cmd_org_info, "credits": cmd_credits,
        "usage": cmd_usage, "roles": cmd_roles,
    }
    cmds[args.command](client, args)


if __name__ == "__main__":
    main()
