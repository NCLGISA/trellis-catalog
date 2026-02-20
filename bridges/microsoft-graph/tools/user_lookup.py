#!/usr/bin/env python3
"""
Entra ID user and group lookup via Microsoft Graph.

Provides user search, group membership queries, and bulk user operations
for onboarding/offboarding workflows.

Usage:
    python3 user_lookup.py search <query>
    python3 user_lookup.py get <user-email-or-upn>
    python3 user_lookup.py groups <user-email-or-upn>
    python3 user_lookup.py members <group-name>
    python3 user_lookup.py disabled
    python3 user_lookup.py sign-ins <user-email-or-upn>
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from graph_client import GraphClient


def cmd_search(client: GraphClient, query: str):
    """Search users by name or email."""
    users = client.search_users(
        query,
        select="id,displayName,mail,userPrincipalName,accountEnabled,jobTitle,department",
    )
    print(f"Found {len(users)} users matching '{query}':\n")
    for u in users:
        enabled = "enabled" if u.get("accountEnabled") else "DISABLED"
        print(f"  {u.get('displayName', '?'):35s}  {u.get('mail', ''):40s}  {enabled}")
        if u.get("jobTitle") or u.get("department"):
            print(f"  {'':35s}  {u.get('jobTitle', ''):20s}  {u.get('department', '')}")


def cmd_get(client: GraphClient, user_id: str):
    """Get detailed info for a specific user."""
    user = client.get_user(
        user_id,
        select="id,displayName,mail,userPrincipalName,accountEnabled,"
               "jobTitle,department,officeLocation,mobilePhone,businessPhones,"
               "createdDateTime,lastPasswordChangeDateTime,assignedLicenses,"
               "onPremisesSyncEnabled,onPremisesLastSyncDateTime",
    )
    print(json.dumps(user, indent=2))


def cmd_groups(client: GraphClient, user_id: str):
    """List groups a user belongs to."""
    user = client.get_user(user_id, select="id,displayName")
    user_obj_id = user["id"]

    resp = client.get(f"users/{user_obj_id}/memberOf")
    resp.raise_for_status()
    memberships = resp.json().get("value", [])

    print(f"Group memberships for {user.get('displayName', user_id)} ({len(memberships)}):\n")
    for m in memberships:
        obj_type = m.get("@odata.type", "").replace("#microsoft.graph.", "")
        print(f"  [{obj_type:15s}]  {m.get('displayName', '?')}")


def cmd_members(client: GraphClient, group_name: str):
    """List members of a group by group name."""
    groups = client.list_groups(filter_expr=f"displayName eq '{group_name}'")
    if not groups:
        groups = client.search_users(group_name)
        print(f"No group found with exact name '{group_name}'.")
        if groups:
            print("Did you mean one of these users?")
            for g in groups[:5]:
                print(f"  {g.get('displayName', '?')}")
        return

    group = groups[0]
    members = client.list_group_members(group["id"])
    print(f"Members of '{group.get('displayName')}' ({len(members)}):\n")
    for m in members:
        obj_type = m.get("@odata.type", "").replace("#microsoft.graph.", "")
        print(f"  {m.get('displayName', '?'):40s}  {m.get('mail', ''):40s}  [{obj_type}]")


def cmd_disabled(client: GraphClient):
    """List disabled user accounts."""
    users = client.list_users(
        select="id,displayName,mail,userPrincipalName,accountEnabled,department",
        filter_expr="accountEnabled eq false",
    )
    print(f"Disabled accounts: {len(users)}\n")
    for u in users:
        print(f"  {u.get('displayName', '?'):40s}  {u.get('mail', ''):40s}  {u.get('department', '')}")


def cmd_signins(client: GraphClient, user_id: str):
    """Show recent sign-in activity for a user."""
    user = client.get_user(user_id, select="id,displayName")
    signins = client.list_sign_ins(user_id=user["id"], top=20)

    print(f"Recent sign-ins for {user.get('displayName', user_id)} ({len(signins)}):\n")
    for s in signins:
        status = s.get("status", {})
        error_code = status.get("errorCode", 0)
        result = "OK" if error_code == 0 else f"FAIL({error_code})"
        app = s.get("appDisplayName", "?")
        ip = s.get("ipAddress", "?")
        dt = s.get("createdDateTime", "?")
        location = s.get("location", {})
        city = location.get("city", "")
        state = location.get("state", "")
        loc_str = f"{city}, {state}" if city else ""
        print(f"  {dt[:19]:20s}  {result:12s}  {app:30s}  {ip:15s}  {loc_str}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 user_lookup.py <command> [args]")
        print()
        print("Commands:")
        print("  search <query>        Search users by name or email")
        print("  get <user>            Get detailed user info")
        print("  groups <user>         List groups for a user")
        print("  members <group-name>  List members of a group")
        print("  disabled              List disabled accounts")
        print("  sign-ins <user>       Show recent sign-in activity")
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1]

    if command == "search" and len(sys.argv) > 2:
        cmd_search(client, " ".join(sys.argv[2:]))
    elif command == "get" and len(sys.argv) > 2:
        cmd_get(client, sys.argv[2])
    elif command == "groups" and len(sys.argv) > 2:
        cmd_groups(client, sys.argv[2])
    elif command == "members" and len(sys.argv) > 2:
        cmd_members(client, " ".join(sys.argv[2:]))
    elif command == "disabled":
        cmd_disabled(client)
    elif command in ("sign-ins", "signins") and len(sys.argv) > 2:
        cmd_signins(client, sys.argv[2])
    else:
        print(f"Unknown command or missing argument: {command}")
        sys.exit(1)
