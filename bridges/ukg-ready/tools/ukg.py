#!/usr/bin/env python3
"""UKG Ready CLI -- unified interface for the UKG Ready REST API (V2)."""

import argparse
import json
import sys

from ukg_client import UKGClient


def jprint(obj):
    print(json.dumps(obj, indent=2, default=str))


# ======================================================================
# Employees
# ======================================================================

def cmd_employees(client, args):
    if args.action == "list":
        data = client.get("employees")
        employees = data.get("employees", data if isinstance(data, list) else [])
        if args.active_only:
            employees = [e for e in employees if e.get("status") == "Active"]
        jprint({"count": len(employees), "employees": employees})

    elif args.action == "get":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}")
        jprint(data)

    elif args.action == "demographics":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/demographics")
        jprint(data)

    elif args.action == "pay-info":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/pay-info")
        jprint(data)

    elif args.action == "badges":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/badges")
        jprint(data)

    elif args.action == "contacts":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/contacts")
        jprint(data)

    elif args.action == "profiles":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/profiles")
        jprint(data)

    elif args.action == "attendance":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/attendance")
        jprint(data)

    elif args.action == "holidays":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/holidays")
        jprint(data)

    elif args.action == "search":
        if not args.query:
            print("--query required", file=sys.stderr); sys.exit(1)
        data = client.get("employees", params={"q": args.query})
        employees = data.get("employees", data if isinstance(data, list) else [])
        jprint({"count": len(employees), "employees": employees})


# ======================================================================
# Compensation
# ======================================================================

def cmd_compensation(client, args):
    if not args.id:
        print("--id required", file=sys.stderr); sys.exit(1)

    if args.action == "total":
        data = client.get(f"employees/{args.id}/compensation/total")
        jprint(data)

    elif args.action == "history":
        data = client.get(f"employees/{args.id}/compensation/history")
        jprint(data)

    elif args.action == "additional":
        data = client.get(f"employees/{args.id}/compensation/additional")
        jprint(data)


# ======================================================================
# Config
# ======================================================================

def cmd_config(client, args):
    if args.action == "cost-centers":
        params = {}
        if args.tree_index:
            params["tree_index"] = args.tree_index
        else:
            params["tree_index"] = "0"
        data = client.get("config/cost-centers", params=params)
        jprint(data)

    elif args.action == "cost-center-lists":
        data = client.get("config/cost-center-lists")
        jprint(data)


# ======================================================================
# Notifications
# ======================================================================

def cmd_notifications(client, args):
    if args.action == "mailbox":
        params = {}
        if args.created_from:
            params["created_from"] = args.created_from
        if args.created_to:
            params["created_to"] = args.created_to
        if not params:
            from datetime import datetime, timedelta
            today = datetime.utcnow()
            params["created_from"] = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            params["created_to"] = today.strftime("%Y-%m-%d")
        data = client.get("notifications/mailbox-items", params=params)
        jprint(data)

    elif args.action == "todo":
        if not args.id:
            print("--id required", file=sys.stderr); sys.exit(1)
        data = client.get(f"employees/{args.id}/to-do-items")
        jprint(data)


# ======================================================================
# Info
# ======================================================================

def cmd_info(client, _args):
    jprint(client.info())


# ======================================================================
# Argument parser
# ======================================================================

def build_parser():
    parser = argparse.ArgumentParser(description="UKG Ready CLI")
    sub = parser.add_subparsers(dest="module", required=True)

    # -- employees --
    p_emp = sub.add_parser("employees", help="Employee management")
    p_emp.add_argument(
        "action",
        choices=["list", "get", "demographics", "pay-info", "badges", "contacts",
                 "profiles", "attendance", "holidays", "search"],
    )
    p_emp.add_argument("--id", help="Employee ID")
    p_emp.add_argument("--query", "-q", help="Search query string")
    p_emp.add_argument("--active-only", action="store_true", help="Active employees only")
    p_emp.set_defaults(func=cmd_employees)

    # -- compensation --
    p_comp = sub.add_parser("compensation", help="Employee compensation")
    p_comp.add_argument("action", choices=["total", "history", "additional"])
    p_comp.add_argument("--id", help="Employee ID", required=True)
    p_comp.set_defaults(func=cmd_compensation)

    # -- config --
    p_cfg = sub.add_parser("config", help="Company configuration")
    p_cfg.add_argument("action", choices=["cost-centers", "cost-center-lists"])
    p_cfg.add_argument("--tree-index", default="0", help="Cost center tree index (default: 0)")
    p_cfg.set_defaults(func=cmd_config)

    # -- notifications --
    p_notif = sub.add_parser("notifications", help="Notifications and mailbox")
    p_notif.add_argument("action", choices=["mailbox", "todo"])
    p_notif.add_argument("--id", help="Employee ID (for todo)")
    p_notif.add_argument("--created-from", help="Start date YYYY-MM-DD (mailbox)")
    p_notif.add_argument("--created-to", help="End date YYYY-MM-DD (mailbox)")
    p_notif.set_defaults(func=cmd_notifications)

    # -- info --
    p_info = sub.add_parser("info", help="Connection info and token status")
    p_info.set_defaults(func=cmd_info)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    client = UKGClient()
    args.func(client, args)


if __name__ == "__main__":
    main()
