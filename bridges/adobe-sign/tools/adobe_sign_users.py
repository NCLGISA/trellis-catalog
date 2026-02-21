#!/usr/bin/env python3
"""
Adobe Sign Users Tool

List, inspect, and search users in the Adobe Sign account.

Usage:
    python3 adobe_sign_users.py list [--limit N]
    python3 adobe_sign_users.py info <user_id>
    python3 adobe_sign_users.py search <email_or_name>
    python3 adobe_sign_users.py groups <user_id>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adobe_sign_client import AdobeSignClient


def cmd_list(client, args):
    limit = 50
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    users = client.list_users(
        page_size=min(limit, 100),
        max_pages=max(1, limit // 100),
    )
    users = users[:limit]

    print(f"Users ({len(users)} shown):")
    print(f"{'Name':30s}  {'Email':40s}  {'Status'}")
    print("-" * 85)
    for u in users:
        name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or "?"
        email = u.get("email", "?")
        status = u.get("userStatus", u.get("status", "?"))
        print(f"{name:30s}  {email:40s}  {status}")


def cmd_info(client, user_id):
    user = client.get_user(user_id)
    print(json.dumps(user, indent=2, default=str))


def cmd_search(client, query):
    users = client.list_users(page_size=100, max_pages=10)
    query_lower = query.lower()
    matches = []
    for u in users:
        email = u.get("email", "").lower()
        name = f"{u.get('firstName', '')} {u.get('lastName', '')}".lower()
        if query_lower in email or query_lower in name:
            matches.append(u)

    if not matches:
        print(f"No users matching '{query}'")
        return

    print(f"Users matching '{query}' ({len(matches)} found):")
    print(f"{'Name':30s}  {'Email':40s}  {'ID'}")
    print("-" * 100)
    for u in matches:
        name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip() or "?"
        email = u.get("email", "?")
        uid = u.get("id", "?")
        print(f"{name:30s}  {email:40s}  {uid}")


def cmd_groups(client, user_id):
    groups = client.get_user_groups(user_id)
    if not groups:
        print(f"No groups for user {user_id}")
        return

    print(f"Groups for user {user_id} ({len(groups)} groups):")
    for g in groups:
        gid = g.get("id", "?")
        name = g.get("name", "?")
        is_admin = g.get("isGroupAdmin", False)
        role = "admin" if is_admin else "member"
        print(f"  {name:30s}  {gid}  ({role})")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = AdobeSignClient()

    if action == "list":
        cmd_list(client, sys.argv[2:])
    elif action == "info" and len(sys.argv) >= 3:
        cmd_info(client, sys.argv[2])
    elif action == "search" and len(sys.argv) >= 3:
        cmd_search(client, " ".join(sys.argv[2:]))
    elif action == "groups" and len(sys.argv) >= 3:
        cmd_groups(client, sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
