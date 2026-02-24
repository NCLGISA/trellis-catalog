#!/usr/bin/env python3
"""Splunk unified CLI.

Subcommands:
    search   <SPL>       Run an ad-hoc search (async, polls until done)
    oneshot  <SPL>       Run a quick search (blocks, returns results directly)
    jobs     list|status|results|cancel
    savedsearches list|detail|run
    indexes  list
    alerts   list
    info                 Server info and current user context

Usage:
    python3 splunk.py search "index=main error" --earliest -1h --max 500
    python3 splunk.py oneshot "index=_internal | stats count by sourcetype" --earliest -15m
    python3 splunk.py jobs list
    python3 splunk.py jobs status --sid <sid>
    python3 splunk.py jobs results --sid <sid> --count 200
    python3 splunk.py jobs cancel --sid <sid>
    python3 splunk.py savedsearches list
    python3 splunk.py savedsearches detail --name "My Saved Search"
    python3 splunk.py savedsearches run --name "My Saved Search"
    python3 splunk.py indexes list
    python3 splunk.py alerts list
    python3 splunk.py info
"""

import argparse
import json
import os
import sys

try:
    from splunk_client import SplunkClient
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from splunk_client import SplunkClient


def cmd_search(client, args):
    result = client.search(
        args.spl,
        earliest=args.earliest,
        latest=args.latest,
        max_count=args.max,
        exec_mode="normal",
        timeout_secs=args.timeout,
    )
    print(json.dumps(result, indent=2))


def cmd_oneshot(client, args):
    result = client.search(
        args.spl,
        earliest=args.earliest,
        latest=args.latest,
        max_count=args.max,
        exec_mode="oneshot",
    )
    print(json.dumps(result, indent=2))


def cmd_jobs(client, args):
    action = args.action

    if action == "list":
        jobs = client.list_jobs(count=args.count)
        print(json.dumps({"count": len(jobs), "jobs": jobs}, indent=2))

    elif action == "status":
        if not args.sid:
            print("Error: --sid is required for jobs status", file=sys.stderr)
            sys.exit(1)
        status = client.job_status(args.sid)
        content = status.get("content", status)
        print(json.dumps({
            "sid": args.sid,
            "dispatchState": content.get("dispatchState", ""),
            "isDone": content.get("isDone", False),
            "resultCount": content.get("resultCount", 0),
            "runDuration": content.get("runDuration", 0),
            "eventCount": content.get("eventCount", 0),
            "scanCount": content.get("scanCount", 0),
            "doneProgress": content.get("doneProgress", 0),
        }, indent=2))

    elif action == "results":
        if not args.sid:
            print("Error: --sid is required for jobs results", file=sys.stderr)
            sys.exit(1)
        results = client.job_results(args.sid, count=args.count, offset=args.offset)
        print(json.dumps({"count": len(results), "results": results}, indent=2))

    elif action == "cancel":
        if not args.sid:
            print("Error: --sid is required for jobs cancel", file=sys.stderr)
            sys.exit(1)
        client.cancel_job(args.sid)
        print(json.dumps({"sid": args.sid, "status": "cancelled"}, indent=2))


def cmd_savedsearches(client, args):
    action = args.action

    if action == "list":
        searches = client.saved_searches(count=args.count)
        print(json.dumps({"count": len(searches), "saved_searches": searches}, indent=2))

    elif action == "detail":
        if not args.name:
            print("Error: --name is required for savedsearches detail", file=sys.stderr)
            sys.exit(1)
        detail = client.saved_search_detail(args.name)
        print(json.dumps(detail, indent=2))

    elif action == "run":
        if not args.name:
            print("Error: --name is required for savedsearches run", file=sys.stderr)
            sys.exit(1)
        sid = client.dispatch_saved_search(
            args.name, earliest=args.earliest, latest=args.latest
        )
        print(json.dumps({"name": args.name, "sid": sid, "status": "dispatched"}, indent=2))


def cmd_indexes(client, args):
    indexes = client.indexes(count=args.count)
    active = [i for i in indexes if not i.get("disabled")]
    print(json.dumps({"count": len(active), "indexes": active}, indent=2))


def cmd_alerts(client, args):
    alerts = client.fired_alerts(count=args.count)
    print(json.dumps({"count": len(alerts), "alerts": alerts}, indent=2))


def cmd_info(client, args):
    info = client.server_info()
    user = client.current_user()
    print(json.dumps({
        "server_name": info.get("serverName", ""),
        "version": info.get("version", ""),
        "build": info.get("build", ""),
        "os_name": info.get("os_name", ""),
        "cpu_arch": info.get("cpu_arch", ""),
        "guid": info.get("guid", ""),
        "license_state": info.get("licenseState", ""),
        "current_user": user.get("username", ""),
        "roles": user.get("roles", []),
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="splunk.py",
        description="Splunk unified CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Run an ad-hoc SPL search (async)")
    p_search.add_argument("spl", help="SPL query string")
    p_search.add_argument("--earliest", default="-24h", help="Earliest time (default: -24h)")
    p_search.add_argument("--latest", default="now", help="Latest time (default: now)")
    p_search.add_argument("--max", type=int, default=10000, help="Max results (default: 10000)")
    p_search.add_argument("--timeout", type=int, default=300, help="Poll timeout seconds (default: 300)")

    p_oneshot = sub.add_parser("oneshot", help="Run a quick SPL search (blocking)")
    p_oneshot.add_argument("spl", help="SPL query string")
    p_oneshot.add_argument("--earliest", default="-1h", help="Earliest time (default: -1h)")
    p_oneshot.add_argument("--latest", default="now", help="Latest time (default: now)")
    p_oneshot.add_argument("--max", type=int, default=100, help="Max results (default: 100)")

    p_jobs = sub.add_parser("jobs", help="Manage search jobs")
    p_jobs.add_argument("action", choices=["list", "status", "results", "cancel"])
    p_jobs.add_argument("--sid", help="Search job ID")
    p_jobs.add_argument("--count", type=int, default=20, help="Number of results/jobs (default: 20)")
    p_jobs.add_argument("--offset", type=int, default=0, help="Result offset (default: 0)")

    p_saved = sub.add_parser("savedsearches", help="Saved searches")
    p_saved.add_argument("action", choices=["list", "detail", "run"])
    p_saved.add_argument("--name", help="Saved search name")
    p_saved.add_argument("--earliest", help="Override earliest time")
    p_saved.add_argument("--latest", help="Override latest time")
    p_saved.add_argument("--count", type=int, default=50, help="Number of results (default: 50)")

    p_indexes = sub.add_parser("indexes", help="List indexes")
    p_indexes.add_argument("action", nargs="?", default="list", choices=["list"], help="Action (default: list)")
    p_indexes.add_argument("--count", type=int, default=100, help="Max indexes (default: 100)")

    p_alerts = sub.add_parser("alerts", help="List fired alerts")
    p_alerts.add_argument("action", nargs="?", default="list", choices=["list"], help="Action (default: list)")
    p_alerts.add_argument("--count", type=int, default=50, help="Max alerts (default: 50)")

    sub.add_parser("info", help="Server info and current user")

    args = parser.parse_args()
    client = SplunkClient()

    commands = {
        "search": cmd_search,
        "oneshot": cmd_oneshot,
        "jobs": cmd_jobs,
        "savedsearches": cmd_savedsearches,
        "indexes": cmd_indexes,
        "alerts": cmd_alerts,
        "info": cmd_info,
    }
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
