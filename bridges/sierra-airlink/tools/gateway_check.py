#!/usr/bin/env python3
"""
Sierra AirLink Gateway Inventory Tool

Subcommands:
    list               All gateways with IMEI, MAC, serial, state, type
    info <uid>         Gateway details
    search <query>     Find by IMEI, serial number, or MAC address

Usage:
    python3 gateway_check.py list
    python3 gateway_check.py info abc123def456
    python3 gateway_check.py search "353270"
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from airlink_client import AirLinkClient


def ts_to_str(ts) -> str:
    if not ts:
        return "never"
    try:
        dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OSError):
        return str(ts)


def cmd_list(client: AirLinkClient):
    gateways = client.list_gateways(
        fields="uid,imei,serialNumber,macAddress,type,state,creationDate"
    )
    print(f"Total gateways: {len(gateways)}\n")
    print(f"{'IMEI':20s}  {'Serial':20s}  {'MAC':18s}  {'Type':20s}  {'State':12s}  {'Created'}")
    print("-" * 120)
    for g in gateways:
        imei = g.get("imei") or ""
        serial = g.get("serialNumber") or ""
        mac = g.get("macAddress") or ""
        gtype = g.get("type") or ""
        state = g.get("state") or "?"
        created = ts_to_str(g.get("creationDate"))
        print(f"{imei:20s}  {serial:20s}  {mac:18s}  {gtype:20s}  {state:12s}  {created}")


def cmd_info(client: AirLinkClient, uid: str):
    try:
        g = client.get_gateway(uid)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Gateway: {uid}")
    print(f"  UID:          {g.get('uid')}")
    print(f"  IMEI:         {g.get('imei') or 'n/a'}")
    print(f"  Serial:       {g.get('serialNumber') or 'n/a'}")
    print(f"  MAC:          {g.get('macAddress') or 'n/a'}")
    print(f"  Type:         {g.get('type') or 'n/a'}")
    print(f"  State:        {g.get('state') or '?'}")
    print(f"  Created:      {ts_to_str(g.get('creationDate'))}")

    labels = g.get("labels") or []
    if labels:
        print(f"  Labels:       {', '.join(labels)}")

    metadata = g.get("metadata") or []
    if metadata:
        print(f"  Metadata:")
        for m in metadata:
            key = m.get("key", "?") if isinstance(m, dict) else str(m)
            val = m.get("value", "?") if isinstance(m, dict) else ""
            print(f"    {key}: {val}")


def cmd_search(client: AirLinkClient, query: str):
    by_imei = client.list_gateways(
        fields="uid,imei,serialNumber,macAddress,type,state",
        imei=query,
    )
    by_serial = client.list_gateways(
        fields="uid,imei,serialNumber,macAddress,type,state",
        serialNumber=query,
    )
    by_mac = client.list_gateways(
        fields="uid,imei,serialNumber,macAddress,type,state",
        macAddress=query,
    )

    seen = set()
    results = []
    for g in by_imei + by_serial + by_mac:
        uid = g.get("uid")
        if uid and uid not in seen:
            seen.add(uid)
            results.append(g)

    print(f"Search '{query}': {len(results)} result(s)\n")
    if not results:
        return

    print(f"{'IMEI':20s}  {'Serial':20s}  {'MAC':18s}  {'Type':20s}  {'UID'}")
    print("-" * 110)
    for g in results:
        imei = g.get("imei") or ""
        serial = g.get("serialNumber") or ""
        mac = g.get("macAddress") or ""
        gtype = g.get("type") or ""
        uid = g.get("uid") or ""
        print(f"{imei:20s}  {serial:20s}  {mac:18s}  {gtype:20s}  {uid}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 gateway_check.py <list|info|search> [args]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    client = AirLinkClient()

    if cmd == "list":
        cmd_list(client)
    elif cmd == "info":
        if len(sys.argv) < 3:
            print("Usage: python3 gateway_check.py info <uid>")
            sys.exit(1)
        cmd_info(client, sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python3 gateway_check.py search <query>")
            sys.exit(1)
        cmd_search(client, sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: list, info, search")
        sys.exit(1)


if __name__ == "__main__":
    main()
