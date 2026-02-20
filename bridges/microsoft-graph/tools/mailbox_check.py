#!/usr/bin/env python3
"""
Mailbox diagnostics for Exchange Online via Microsoft Graph.

Checks mailbox settings, forwarding rules, delegates, folder sizes,
and inbox rules for a given user.

Usage:
    python3 mailbox_check.py <user-email-or-upn>
    python3 mailbox_check.py user@example.com
    python3 mailbox_check.py user@example.com --json
"""

import sys
import json

# Import from sibling module
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from graph_client import GraphClient


def check_mailbox(client: GraphClient, user_id: str, as_json: bool = False) -> dict:
    """Run comprehensive mailbox diagnostics for a user."""
    results = {"user": user_id, "checks": {}}

    # 1. User info
    try:
        user = client.get_user(
            user_id,
            select="id,displayName,mail,userPrincipalName,accountEnabled,"
                   "jobTitle,department,assignedLicenses",
        )
        results["checks"]["user_info"] = {
            "displayName": user.get("displayName"),
            "mail": user.get("mail"),
            "upn": user.get("userPrincipalName"),
            "accountEnabled": user.get("accountEnabled"),
            "jobTitle": user.get("jobTitle"),
            "department": user.get("department"),
            "licenseCount": len(user.get("assignedLicenses", [])),
        }
    except Exception as e:
        results["checks"]["user_info"] = {"error": str(e)}

    # 2. Mailbox settings (auto-reply, timezone, forwarding)
    try:
        settings = client.get_mailbox_settings(user_id)
        auto_reply = settings.get("automaticRepliesSetting", {})
        results["checks"]["mailbox_settings"] = {
            "timeZone": settings.get("timeZone"),
            "language": settings.get("language", {}).get("displayName"),
            "autoReplyStatus": auto_reply.get("status"),
            "autoReplyScheduled": auto_reply.get("scheduledStartDateTime"),
        }
    except Exception as e:
        results["checks"]["mailbox_settings"] = {"error": str(e)}

    # 3. Mail folders with sizes
    try:
        folders = client.get_mail_folders(user_id)
        folder_summary = []
        for f in folders:
            folder_summary.append({
                "name": f.get("displayName"),
                "totalItems": f.get("totalItemCount", 0),
                "unreadItems": f.get("unreadItemCount", 0),
                "sizeBytes": f.get("sizeInBytes", 0),
            })
        folder_summary.sort(key=lambda x: x["totalItems"], reverse=True)
        results["checks"]["mail_folders"] = folder_summary
    except Exception as e:
        results["checks"]["mail_folders"] = {"error": str(e)}

    # 4. Inbox rules (forwarding, auto-move)
    try:
        rules = client.get_inbox_rules(user_id)
        rule_summary = []
        for r in rules:
            rule_info = {
                "name": r.get("displayName"),
                "enabled": r.get("isEnabled"),
                "sequence": r.get("sequence"),
            }
            if r.get("actions", {}).get("forwardTo"):
                rule_info["forwardTo"] = [
                    a.get("emailAddress", {}).get("address")
                    for a in r["actions"]["forwardTo"]
                ]
            if r.get("actions", {}).get("redirectTo"):
                rule_info["redirectTo"] = [
                    a.get("emailAddress", {}).get("address")
                    for a in r["actions"]["redirectTo"]
                ]
            if r.get("actions", {}).get("moveToFolder"):
                rule_info["moveToFolder"] = r["actions"]["moveToFolder"]
            if r.get("actions", {}).get("delete"):
                rule_info["autoDelete"] = True
            rule_summary.append(rule_info)
        results["checks"]["inbox_rules"] = rule_summary
    except Exception as e:
        results["checks"]["inbox_rules"] = {"error": str(e)}

    # 5. Calendar permissions
    try:
        perms = client.get_calendar_permissions(user_id)
        perm_summary = []
        for p in perms:
            email_addr = p.get("emailAddress", {})
            perm_summary.append({
                "user": email_addr.get("address") or email_addr.get("name", "Default"),
                "role": p.get("role"),
                "allowedRoles": p.get("allowedRoles"),
            })
        results["checks"]["calendar_permissions"] = perm_summary
    except Exception as e:
        results["checks"]["calendar_permissions"] = {"error": str(e)}

    # 6. Licenses
    try:
        licenses = client.get_user_licenses(user_id)
        lic_summary = [
            {"skuPartNumber": lic.get("skuPartNumber"), "skuId": lic.get("skuId")}
            for lic in licenses
        ]
        results["checks"]["licenses"] = lic_summary
    except Exception as e:
        results["checks"]["licenses"] = {"error": str(e)}

    if as_json:
        return results

    # Print human-readable report
    print(f"=== Mailbox Diagnostics: {user_id} ===\n")

    ui = results["checks"].get("user_info", {})
    if "error" not in ui:
        enabled = "ENABLED" if ui.get("accountEnabled") else "DISABLED"
        print(f"  Name:       {ui.get('displayName', '?')}")
        print(f"  Email:      {ui.get('mail', '?')}")
        print(f"  Department: {ui.get('department', '?')}")
        print(f"  Title:      {ui.get('jobTitle', '?')}")
        print(f"  Account:    {enabled}")
        print(f"  Licenses:   {ui.get('licenseCount', 0)}")
    else:
        print(f"  User info error: {ui['error']}")

    print()
    ms = results["checks"].get("mailbox_settings", {})
    if "error" not in ms:
        print(f"  Timezone:   {ms.get('timeZone', '?')}")
        print(f"  Auto-reply: {ms.get('autoReplyStatus', '?')}")
    else:
        print(f"  Mailbox settings error: {ms['error']}")

    print()
    folders = results["checks"].get("mail_folders", [])
    if isinstance(folders, list):
        print(f"  Mail Folders ({len(folders)}):")
        for f in folders[:10]:
            size_mb = f.get("sizeBytes", 0) / (1024 * 1024)
            print(f"    {f['name']:25s}  {f['totalItems']:6d} items  ({size_mb:.1f} MB)  unread={f['unreadItems']}")
    elif isinstance(folders, dict) and "error" in folders:
        print(f"  Mail folders error: {folders['error']}")

    print()
    rules = results["checks"].get("inbox_rules", [])
    if isinstance(rules, list):
        if rules:
            print(f"  Inbox Rules ({len(rules)}):")
            for r in rules:
                status = "ON" if r.get("enabled") else "OFF"
                print(f"    [{status}] {r.get('name', '?')}")
                if r.get("forwardTo"):
                    print(f"          -> FORWARDS TO: {', '.join(r['forwardTo'])}")
                if r.get("redirectTo"):
                    print(f"          -> REDIRECTS TO: {', '.join(r['redirectTo'])}")
                if r.get("autoDelete"):
                    print(f"          -> AUTO-DELETE")
        else:
            print("  Inbox Rules: None")
    elif isinstance(rules, dict) and "error" in rules:
        print(f"  Inbox rules error: {rules['error']}")

    print()
    perms = results["checks"].get("calendar_permissions", [])
    if isinstance(perms, list) and perms:
        print(f"  Calendar Permissions ({len(perms)}):")
        for p in perms:
            print(f"    {p.get('user', '?'):40s}  role={p.get('role', '?')}")

    print()
    lics = results["checks"].get("licenses", [])
    if isinstance(lics, list) and lics:
        print(f"  Licenses ({len(lics)}):")
        for lic in lics:
            print(f"    {lic.get('skuPartNumber', '?')}")
    elif isinstance(lics, list):
        print("  Licenses: None")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 mailbox_check.py <user-email-or-upn> [--json]")
        sys.exit(1)

    user_id = sys.argv[1]
    as_json = "--json" in sys.argv

    client = GraphClient()

    if as_json:
        result = check_mailbox(client, user_id, as_json=True)
        print(json.dumps(result, indent=2))
    else:
        check_mailbox(client, user_id)
