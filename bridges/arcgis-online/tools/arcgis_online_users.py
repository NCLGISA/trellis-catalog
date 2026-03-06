#!/usr/bin/env python3
"""
ArcGIS Online - User and Group Administration

List users, view profiles, manage groups and membership.

Usage:
    python3 arcgis_online_users.py list-users
    python3 arcgis_online_users.py list-users --num 50
    python3 arcgis_online_users.py user <username>
    python3 arcgis_online_users.py search-users "john"
    python3 arcgis_online_users.py list-groups
    python3 arcgis_online_users.py group <group_id>
    python3 arcgis_online_users.py group-members <group_id>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arcgis_online_client import ArcGISOnlineClient


def cmd_list_users(client, args):
    result = client.get("portals/self/users", params={
        "start": args.start, "num": args.num, "sortField": "username", "sortOrder": "asc",
    })
    users = result.get("users", [])
    total = result.get("total", 0)
    print(f"Total users: {total} | Showing: {len(users)}")
    print()
    for u in users:
        role = u.get("role", "?")
        print(f"  {u['username']:30s}  {role:15s}  {u.get('fullName', '')}")


def cmd_user(client, args):
    result = client.get(f"community/users/{args.username}")
    print(json.dumps(result, indent=2))


def cmd_search_users(client, args):
    result = client.get("community/users", params={
        "q": args.query, "num": args.num, "start": args.start,
    })
    users = result.get("results", [])
    total = result.get("total", 0)
    print(f"Total matches: {total} | Showing: {len(users)}")
    for u in users:
        print(f"  {u['username']:30s}  {u.get('fullName', '')}")


def cmd_list_groups(client, args):
    result = client.get("community/groups", params={
        "q": args.query or "*", "num": args.num, "start": args.start,
        "sortField": "title", "sortOrder": "asc",
    })
    groups = result.get("results", [])
    total = result.get("total", 0)
    print(f"Total groups: {total} | Showing: {len(groups)}")
    print()
    for g in groups:
        owner = g.get("owner", "?")
        access = g.get("access", "?")
        print(f"  {g['id']}  {g['title']:40s}  owner={owner}  access={access}")


def cmd_group(client, args):
    result = client.get(f"community/groups/{args.group_id}")
    print(json.dumps(result, indent=2))


def cmd_group_members(client, args):
    result = client.get(f"community/groups/{args.group_id}/users")
    owner = result.get("owner", "?")
    admins = result.get("admins", [])
    users = result.get("users", [])
    print(f"Owner: {owner}")
    print(f"Admins ({len(admins)}):")
    for a in admins:
        print(f"  {a}")
    print(f"Members ({len(users)}):")
    for u in users:
        print(f"  {u}")


def main():
    parser = argparse.ArgumentParser(description="ArcGIS Online User and Group Admin")
    sub = parser.add_subparsers(dest="command")

    p_lu = sub.add_parser("list-users")
    p_lu.add_argument("--num", type=int, default=25)
    p_lu.add_argument("--start", type=int, default=1)

    p_u = sub.add_parser("user")
    p_u.add_argument("username")

    p_su = sub.add_parser("search-users")
    p_su.add_argument("query")
    p_su.add_argument("--num", type=int, default=25)
    p_su.add_argument("--start", type=int, default=1)

    p_lg = sub.add_parser("list-groups")
    p_lg.add_argument("--query", default=None)
    p_lg.add_argument("--num", type=int, default=25)
    p_lg.add_argument("--start", type=int, default=1)

    p_g = sub.add_parser("group")
    p_g.add_argument("group_id")

    p_gm = sub.add_parser("group-members")
    p_gm.add_argument("group_id")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = ArcGISOnlineClient()
    cmds = {
        "list-users": cmd_list_users, "user": cmd_user, "search-users": cmd_search_users,
        "list-groups": cmd_list_groups, "group": cmd_group, "group-members": cmd_group_members,
    }
    cmds[args.command](client, args)


if __name__ == "__main__":
    main()
