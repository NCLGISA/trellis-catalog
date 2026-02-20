#!/usr/bin/env python3
"""
Microsoft 365 license inventory and assignment tool via Microsoft Graph.

Provides license SKU inventory, per-user license queries, and license
utilization reports for the tenant.

Usage:
    python3 license_check.py inventory          # Show all SKUs with usage
    python3 license_check.py user <email>       # Show licenses for a user
    python3 license_check.py unlicensed         # List users without licenses
    python3 license_check.py assign <email> <sku-part-number>
    python3 license_check.py remove <email> <sku-part-number>
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from graph_client import GraphClient


# Common M365 SKU part numbers and friendly names
SKU_FRIENDLY_NAMES = {
    "ENTERPRISEPACK": "Office 365 E3",
    "ENTERPRISEPREMIUM": "Office 365 E5",
    "SPE_E3": "Microsoft 365 E3",
    "SPE_E5": "Microsoft 365 E5",
    "EXCHANGESTANDARD": "Exchange Online (Plan 1)",
    "EXCHANGEENTERPRISE": "Exchange Online (Plan 2)",
    "O365_BUSINESS_ESSENTIALS": "Microsoft 365 Business Basic",
    "O365_BUSINESS_PREMIUM": "Microsoft 365 Business Standard",
    "SMB_BUSINESS_PREMIUM": "Microsoft 365 Business Premium",
    "POWER_BI_STANDARD": "Power BI (Free)",
    "POWER_BI_PRO": "Power BI Pro",
    "PROJECTPREMIUM": "Project Plan 5",
    "PROJECTPROFESSIONAL": "Project Plan 3",
    "VISIOCLIENT": "Visio Plan 2",
    "EMS_E3": "Enterprise Mobility + Security E3",
    "EMS_E5": "Enterprise Mobility + Security E5",
    "STREAM": "Microsoft Stream",
    "FLOW_FREE": "Power Automate (Free)",
    "TEAMS_EXPLORATORY": "Microsoft Teams Exploratory",
    "WINDOWS_STORE": "Windows Store for Business",
    "AAD_PREMIUM": "Azure AD Premium P1",
    "AAD_PREMIUM_P2": "Azure AD Premium P2",
    "INTUNE_A": "Microsoft Intune Plan 1",
    "ATP_ENTERPRISE": "Microsoft Defender for Office 365 (Plan 1)",
    "THREAT_INTELLIGENCE": "Microsoft Defender for Office 365 (Plan 2)",
    "RIGHTSMANAGEMENT": "Azure Information Protection Plan 1",
    "MCOSTANDARD": "Skype for Business Online (Plan 2)",
}


def friendly_name(sku_part_number: str) -> str:
    return SKU_FRIENDLY_NAMES.get(sku_part_number, sku_part_number)


def cmd_inventory(client: GraphClient):
    """Show all subscribed SKUs with usage counts."""
    skus = client.list_subscribed_skus()
    skus.sort(key=lambda s: s.get("consumedUnits", 0), reverse=True)

    print(f"License Inventory ({len(skus)} SKUs):\n")
    print(f"  {'SKU':45s}  {'Consumed':>10s}  {'Available':>10s}  {'Total':>10s}")
    print(f"  {'─' * 45}  {'─' * 10}  {'─' * 10}  {'─' * 10}")

    total_consumed = 0
    total_available = 0
    for s in skus:
        name = friendly_name(s.get("skuPartNumber", "?"))
        consumed = s.get("consumedUnits", 0)
        enabled = s.get("prepaidUnits", {}).get("enabled", 0)
        available = enabled - consumed
        total_consumed += consumed
        total_available += max(available, 0)

        if consumed > 0 or enabled > 0:
            warning = " ⚠️" if available <= 0 and enabled > 0 else ""
            print(f"  {name:45s}  {consumed:10d}  {available:10d}  {enabled:10d}{warning}")

    print(f"\n  Total consumed: {total_consumed}, Total available: {total_available}")


def cmd_user(client: GraphClient, user_id: str):
    """Show licenses assigned to a specific user."""
    user = client.get_user(user_id, select="id,displayName,mail")
    licenses = client.get_user_licenses(user_id)

    print(f"Licenses for {user.get('displayName', user_id)} ({user.get('mail', '')}):\n")
    if not licenses:
        print("  No licenses assigned.")
        return

    for lic in licenses:
        name = friendly_name(lic.get("skuPartNumber", "?"))
        plans = lic.get("servicePlans", [])
        enabled_plans = [p for p in plans if p.get("provisioningStatus") == "Success"]
        disabled_plans = [p for p in plans if p.get("provisioningStatus") == "Disabled"]
        print(f"  {name}")
        print(f"    Enabled service plans: {len(enabled_plans)}, Disabled: {len(disabled_plans)}")
        for p in enabled_plans[:10]:
            print(f"      ✓ {p.get('servicePlanName', '?')}")
        if len(enabled_plans) > 10:
            print(f"      ... and {len(enabled_plans) - 10} more")


def cmd_unlicensed(client: GraphClient):
    """List users without any licenses assigned."""
    users = client.list_users(
        select="id,displayName,mail,userPrincipalName,accountEnabled,assignedLicenses,department",
    )
    unlicensed = [
        u for u in users
        if u.get("accountEnabled") and not u.get("assignedLicenses")
    ]
    unlicensed.sort(key=lambda u: u.get("displayName", ""))

    print(f"Enabled users without licenses: {len(unlicensed)}\n")
    for u in unlicensed:
        print(f"  {u.get('displayName', '?'):40s}  {u.get('mail', ''):40s}  {u.get('department', '')}")


def cmd_assign(client: GraphClient, user_id: str, sku_part_number: str):
    """Assign a license to a user by SKU part number."""
    skus = client.list_subscribed_skus()
    sku = next((s for s in skus if s.get("skuPartNumber") == sku_part_number), None)
    if not sku:
        print(f"ERROR: SKU '{sku_part_number}' not found. Available SKUs:")
        for s in skus:
            if s.get("prepaidUnits", {}).get("enabled", 0) > 0:
                print(f"  {s['skuPartNumber']:40s}  ({friendly_name(s['skuPartNumber'])})")
        sys.exit(1)

    result = client.assign_license(user_id, sku["skuId"])
    if result.get("ok"):
        print(f"License '{friendly_name(sku_part_number)}' assigned to {user_id}")
    else:
        print(f"ERROR: {json.dumps(result, indent=2)}")


def cmd_remove(client: GraphClient, user_id: str, sku_part_number: str):
    """Remove a license from a user by SKU part number."""
    skus = client.list_subscribed_skus()
    sku = next((s for s in skus if s.get("skuPartNumber") == sku_part_number), None)
    if not sku:
        print(f"ERROR: SKU '{sku_part_number}' not found.")
        sys.exit(1)

    result = client.remove_license(user_id, sku["skuId"])
    if result.get("ok"):
        print(f"License '{friendly_name(sku_part_number)}' removed from {user_id}")
    else:
        print(f"ERROR: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 license_check.py <command> [args]")
        print()
        print("Commands:")
        print("  inventory                     Show all SKUs with usage")
        print("  user <email>                  Show licenses for a user")
        print("  unlicensed                    List enabled users without licenses")
        print("  assign <email> <sku-part>     Assign a license to a user")
        print("  remove <email> <sku-part>     Remove a license from a user")
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1]

    if command == "inventory":
        cmd_inventory(client)
    elif command == "user" and len(sys.argv) > 2:
        cmd_user(client, sys.argv[2])
    elif command == "unlicensed":
        cmd_unlicensed(client)
    elif command == "assign" and len(sys.argv) > 3:
        cmd_assign(client, sys.argv[2], sys.argv[3])
    elif command == "remove" and len(sys.argv) > 3:
        cmd_remove(client, sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command or missing argument: {command}")
        sys.exit(1)
