#!/usr/bin/env python3
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
UniFi Client Management Tool

Connected and historical client tracking, block/unblock, and client analytics
for UniFi network infrastructure.

Usage:
    python3 unifi_clients.py list [--site SITE]
    python3 unifi_clients.py detail <mac> [--site SITE]
    python3 unifi_clients.py summary [--site SITE]
    python3 unifi_clients.py history [--site SITE]
    python3 unifi_clients.py block <mac> [--site SITE]
    python3 unifi_clients.py unblock <mac> [--site SITE]
    python3 unifi_clients.py reconnect <mac> [--site SITE]

Read operations are safe. block/unblock/reconnect will mutate client state.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient


def _format_bytes(b):
    """Human-readable byte count."""
    if b is None:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _format_uptime(seconds):
    """Human-readable duration."""
    if not seconds:
        return "0s"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h{m}m"
    if m > 0:
        return f"{m}m{s}s"
    return f"{s}s"


def cmd_list(client, args):
    """List currently connected clients."""
    clients = client.list_clients(site=args.site)
    rows = []
    for c in clients:
        rows.append({
            "hostname": c.get("hostname", c.get("name", c.get("mac", "?"))),
            "mac": c.get("mac"),
            "ip": c.get("ip", ""),
            "is_wired": c.get("is_wired", False),
            "network": c.get("network", ""),
            "essid": c.get("essid", ""),
            "ap_mac": c.get("ap_mac", ""),
            "signal": c.get("signal") if not c.get("is_wired") else None,
            "satisfaction": c.get("satisfaction"),
            "tx_bytes": c.get("tx_bytes", 0),
            "rx_bytes": c.get("rx_bytes", 0),
            "uptime": _format_uptime(c.get("uptime")),
        })
    rows.sort(key=lambda r: r["hostname"].lower())
    print(json.dumps(rows, indent=2))


def cmd_detail(client, args):
    """Get detailed info for a single client."""
    c = client.get_client(args.mac, site=args.site)
    if not c:
        print(json.dumps({"error": f"Client {args.mac} not found or not connected"}))
        sys.exit(1)

    detail = {
        "hostname": c.get("hostname", c.get("name", "?")),
        "mac": c.get("mac"),
        "ip": c.get("ip"),
        "is_wired": c.get("is_wired", False),
        "is_guest": c.get("is_guest", False),
        "blocked": c.get("blocked", False),
        "network": c.get("network", ""),
        "essid": c.get("essid", ""),
        "radio": c.get("radio", ""),
        "radio_proto": c.get("radio_proto", ""),
        "channel": c.get("channel"),
        "ap_mac": c.get("ap_mac", ""),
        "signal": c.get("signal"),
        "noise": c.get("noise"),
        "satisfaction": c.get("satisfaction"),
        "tx_rate": c.get("tx_rate"),
        "rx_rate": c.get("rx_rate"),
        "tx_bytes": c.get("tx_bytes", 0),
        "tx_bytes_human": _format_bytes(c.get("tx_bytes")),
        "rx_bytes": c.get("rx_bytes", 0),
        "rx_bytes_human": _format_bytes(c.get("rx_bytes")),
        "uptime": _format_uptime(c.get("uptime")),
        "first_seen": c.get("first_seen"),
        "last_seen": c.get("last_seen"),
        "oui": c.get("oui", ""),
        "sw_port": c.get("sw_port"),
        "vlan": c.get("vlan"),
    }
    print(json.dumps(detail, indent=2, default=str))


def cmd_summary(client, args):
    """Print client count summary by type and network."""
    clients = client.list_clients(site=args.site)
    wired = sum(1 for c in clients if c.get("is_wired", False))
    wireless = len(clients) - wired
    guests = sum(1 for c in clients if c.get("is_guest", False))

    by_network = {}
    by_essid = {}
    for c in clients:
        net = c.get("network", "unknown")
        by_network[net] = by_network.get(net, 0) + 1
        if not c.get("is_wired", False):
            ssid = c.get("essid", "unknown")
            by_essid[ssid] = by_essid.get(ssid, 0) + 1

    summary = {
        "total_connected": len(clients),
        "wired": wired,
        "wireless": wireless,
        "guests": guests,
        "by_network": dict(sorted(by_network.items(), key=lambda x: -x[1])),
        "by_ssid": dict(sorted(by_essid.items(), key=lambda x: -x[1])),
    }
    print(json.dumps(summary, indent=2))


def cmd_history(client, args):
    """List all known users (historical), not just currently connected."""
    users = client.list_all_users(site=args.site)
    rows = []
    for u in users:
        last_seen = u.get("last_seen")
        if last_seen:
            last_seen = datetime.fromtimestamp(last_seen, tz=timezone.utc).isoformat()
        rows.append({
            "hostname": u.get("hostname", u.get("name", u.get("mac", "?"))),
            "mac": u.get("mac"),
            "oui": u.get("oui", ""),
            "blocked": u.get("blocked", False),
            "last_seen": last_seen,
            "fixed_ip": u.get("fixed_ip", ""),
            "note": u.get("note", ""),
        })
    rows.sort(key=lambda r: r["hostname"].lower())
    print(json.dumps(rows, indent=2))


def cmd_block(client, args):
    result = client.block_client(args.mac, site=args.site)
    print(json.dumps({"action": "block", "mac": args.mac, "result": result}, indent=2))


def cmd_unblock(client, args):
    result = client.unblock_client(args.mac, site=args.site)
    print(json.dumps({"action": "unblock", "mac": args.mac, "result": result}, indent=2))


def cmd_reconnect(client, args):
    result = client.reconnect_client(args.mac, site=args.site)
    print(json.dumps({"action": "reconnect", "mac": args.mac, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="UniFi Client Management")
    parser.add_argument("command", choices=["list", "detail", "summary", "history",
                                            "block", "unblock", "reconnect"])
    parser.add_argument("mac", nargs="?", help="Client MAC address")
    parser.add_argument("--site", default=None, help="Site name")
    args = parser.parse_args()

    if args.command in ("detail", "block", "unblock", "reconnect") and not args.mac:
        parser.error(f"{args.command} requires a MAC address argument")

    client = UniFiClient()
    try:
        {
            "list": cmd_list,
            "detail": cmd_detail,
            "summary": cmd_summary,
            "history": cmd_history,
            "block": cmd_block,
            "unblock": cmd_unblock,
            "reconnect": cmd_reconnect,
        }[args.command](client, args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
