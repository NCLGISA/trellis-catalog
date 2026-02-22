#!/usr/bin/env python3
"""
Sierra AirLink System Inventory & Status Tool

Subcommands:
    list               All systems with name, state, commStatus, lastCommDate
    search <query>     Find by name, IMEI, or serial number
    info <uid>         Full system details including gateway, subscription, apps
    status             Communication status summary (OK/ERROR/WARNING counts)
    offline            Systems with commStatus ERROR or no recent communication

Usage:
    python3 system_check.py list
    python3 system_check.py search "RV50"
    python3 system_check.py info abc123def456
    python3 system_check.py status
    python3 system_check.py offline
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from airlink_client import AirLinkClient


def ts_to_str(ts) -> str:
    """Convert AirVantage millisecond timestamp to readable string."""
    if not ts:
        return "never"
    try:
        dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OSError):
        return str(ts)


def cmd_list(client: AirLinkClient):
    systems = client.list_systems(
        fields="uid,name,commStatus,lastCommDate,lifeCycleState,gateway"
    )
    print(f"Total systems: {len(systems)}\n")
    print(f"{'Name':40s}  {'Comm':10s}  {'State':12s}  {'Last Comm':24s}  {'IMEI'}")
    print("-" * 110)
    for s in systems:
        name = s.get("name") or "?"
        comm = s.get("commStatus") or "?"
        state = s.get("lifeCycleState") or "?"
        last = ts_to_str(s.get("lastCommDate"))
        gw = s.get("gateway") or {}
        imei = gw.get("imei") or ""
        print(f"{name:40s}  {comm:10s}  {state:12s}  {last:24s}  {imei}")


def cmd_search(client: AirLinkClient, query: str):
    by_name = client.list_systems(
        fields="uid,name,commStatus,lastCommDate,lifeCycleState,gateway",
        name=query,
    )

    by_gateway = client.list_systems(
        fields="uid,name,commStatus,lastCommDate,lifeCycleState,gateway",
        gateway=f"imei:{query}",
    )

    by_serial = client.list_systems(
        fields="uid,name,commStatus,lastCommDate,lifeCycleState,gateway",
        gateway=f"serialNumber:{query}",
    )

    seen = set()
    results = []
    for s in by_name + by_gateway + by_serial:
        uid = s.get("uid")
        if uid and uid not in seen:
            seen.add(uid)
            results.append(s)

    print(f"Search '{query}': {len(results)} result(s)\n")
    if not results:
        return

    print(f"{'Name':40s}  {'Comm':10s}  {'State':12s}  {'UID'}")
    print("-" * 90)
    for s in results:
        name = s.get("name") or "?"
        comm = s.get("commStatus") or "?"
        state = s.get("lifeCycleState") or "?"
        uid = s.get("uid") or "?"
        print(f"{name:40s}  {comm:10s}  {state:12s}  {uid}")


def cmd_info(client: AirLinkClient, uid: str):
    try:
        s = client.get_system(uid)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"System: {s.get('name', '?')}")
    print(f"  UID:            {s.get('uid')}")
    print(f"  Type:           {s.get('type', '?')}")
    print(f"  Lifecycle:      {s.get('lifeCycleState', '?')}")
    print(f"  Comm Status:    {s.get('commStatus', '?')}")
    print(f"  Last Comm:      {ts_to_str(s.get('lastCommDate'))}")
    print(f"  Created:        {ts_to_str(s.get('creationDate'))}")
    print(f"  Activated:      {ts_to_str(s.get('activationDate'))}")
    print(f"  Sync Status:    {s.get('syncStatus', '?')}")

    gw = s.get("gateway")
    if gw:
        print(f"\n  Gateway:")
        print(f"    UID:          {gw.get('uid', '?')}")
        print(f"    IMEI:         {gw.get('imei') or 'n/a'}")
        print(f"    Serial:       {gw.get('serialNumber') or 'n/a'}")
        print(f"    MAC:          {gw.get('macAddress') or 'n/a'}")
        print(f"    Type:         {gw.get('type') or 'n/a'}")

    sub = s.get("subscription")
    if sub:
        print(f"\n  Subscription:")
        print(f"    Identifier:   {sub.get('identifier') or 'n/a'}")
        print(f"    Operator:     {sub.get('operator') or 'n/a'}")
        print(f"    IP:           {sub.get('ipAddress') or 'n/a'}")
        print(f"    State:        {sub.get('state') or 'n/a'}")

    apps = s.get("applications") or []
    if apps:
        print(f"\n  Applications ({len(apps)}):")
        for a in apps:
            print(f"    {a.get('name', '?')} rev={a.get('revision', '?')} type={a.get('type', '?')}")

    labels = s.get("labels") or []
    if labels:
        print(f"\n  Labels: {', '.join(labels)}")

    data = s.get("data")
    if data:
        print(f"\n  Device Data:")
        for key in sorted(data.keys()):
            print(f"    {key:25s}  {data[key]}")


def cmd_status(client: AirLinkClient):
    systems = client.list_systems(fields="uid,name,commStatus,lifeCycleState")
    total = len(systems)

    by_comm = Counter(s.get("commStatus", "UNDEFINED") for s in systems)
    by_state = Counter(s.get("lifeCycleState", "?") for s in systems)

    print(f"Total systems: {total}\n")
    print("Communication Status:")
    for status in ["OK", "WARNING", "ERROR", "UNDEFINED"]:
        count = by_comm.get(status, 0)
        pct = (count / total * 100) if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {status:12s}  {count:4d}  ({pct:5.1f}%)  {bar}")

    print("\nLifecycle State:")
    for state, count in by_state.most_common():
        pct = (count / total * 100) if total else 0
        print(f"  {state:14s}  {count:4d}  ({pct:5.1f}%)")


def cmd_offline(client: AirLinkClient):
    error_systems = client.list_systems(
        fields="uid,name,commStatus,lastCommDate,lifeCycleState,gateway",
        commStatus="ERROR",
    )

    print(f"Systems with commStatus=ERROR: {len(error_systems)}\n")
    if not error_systems:
        print("No offline systems found.")
        return

    print(f"{'Name':40s}  {'Last Comm':24s}  {'State':12s}  {'IMEI'}")
    print("-" * 100)
    for s in error_systems:
        name = s.get("name") or "?"
        last = ts_to_str(s.get("lastCommDate"))
        state = s.get("lifeCycleState") or "?"
        gw = s.get("gateway") or {}
        imei = gw.get("imei") or ""
        print(f"{name:40s}  {last:24s}  {state:12s}  {imei}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 system_check.py <list|search|info|status|offline> [args]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    client = AirLinkClient()

    if cmd == "list":
        cmd_list(client)
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python3 system_check.py search <query>")
            sys.exit(1)
        cmd_search(client, sys.argv[2])
    elif cmd == "info":
        if len(sys.argv) < 3:
            print("Usage: python3 system_check.py info <uid>")
            sys.exit(1)
        cmd_info(client, sys.argv[2])
    elif cmd == "status":
        cmd_status(client)
    elif cmd == "offline":
        cmd_offline(client)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: list, search, info, status, offline")
        sys.exit(1)


if __name__ == "__main__":
    main()
