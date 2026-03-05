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
UniFi Device Management Tool

Inventory, status, firmware, and lifecycle operations for UniFi network
devices (access points, switches, gateways, security appliances).

Usage:
    python3 unifi_devices.py list [--site SITE]
    python3 unifi_devices.py detail <mac> [--site SITE]
    python3 unifi_devices.py summary [--site SITE]
    python3 unifi_devices.py firmware [--site SITE]
    python3 unifi_devices.py restart <mac> [--site SITE]
    python3 unifi_devices.py adopt <mac> [--site SITE]
    python3 unifi_devices.py upgrade <mac> [--site SITE]
    python3 unifi_devices.py provision <mac> [--site SITE]

All read operations are safe. Write operations (restart, adopt, upgrade,
provision) will mutate device state.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient

DEVICE_TYPE_NAMES = {
    "uap": "Access Point",
    "usw": "Switch",
    "ugw": "Gateway",
    "uxg": "Gateway (Next-Gen)",
    "udm": "Dream Machine",
    "usw-flex": "Switch Flex",
}


def cmd_list(client, args):
    """List all devices with key attributes."""
    devices = client.list_devices(site=args.site)
    rows = []
    for d in devices:
        rows.append({
            "name": d.get("name", d.get("hostname", d.get("mac", "?"))),
            "mac": d.get("mac", ""),
            "model": d.get("model", "?"),
            "type": DEVICE_TYPE_NAMES.get(d.get("type", ""), d.get("type", "?")),
            "ip": d.get("ip", ""),
            "status": "online" if d.get("state", 0) == 1 else "offline",
            "firmware": d.get("version", "?"),
            "uptime_hours": round(d.get("uptime", 0) / 3600, 1),
            "clients": d.get("num_sta", 0),
            "upgradable": d.get("upgradable", False),
        })
    print(json.dumps(rows, indent=2))


def cmd_detail(client, args):
    """Get detailed information for a single device."""
    dev = client.get_device(args.mac, site=args.site)
    if not dev:
        print(json.dumps({"error": f"Device {args.mac} not found"}))
        sys.exit(1)

    detail = {
        "name": dev.get("name", dev.get("hostname", "?")),
        "mac": dev.get("mac"),
        "model": dev.get("model"),
        "type": DEVICE_TYPE_NAMES.get(dev.get("type", ""), dev.get("type")),
        "serial": dev.get("serial", "?"),
        "ip": dev.get("ip"),
        "firmware": dev.get("version"),
        "upgradable": dev.get("upgradable", False),
        "upgrade_to": dev.get("upgrade_to_firmware"),
        "status": "online" if dev.get("state", 0) == 1 else "offline",
        "adopted": dev.get("adopted", False),
        "uptime_hours": round(dev.get("uptime", 0) / 3600, 1),
        "last_seen": dev.get("last_seen"),
        "clients": dev.get("num_sta", 0),
        "satisfaction": dev.get("satisfaction"),
        "cpu_usage": dev.get("system-stats", {}).get("cpu"),
        "mem_usage": dev.get("system-stats", {}).get("mem"),
        "tx_bytes": dev.get("tx_bytes"),
        "rx_bytes": dev.get("rx_bytes"),
    }

    if dev.get("type") == "uap":
        detail["radio_table"] = dev.get("radio_table", [])
        detail["channel_2g"] = None
        detail["channel_5g"] = None
        for radio in dev.get("radio_table", []):
            if radio.get("radio") == "ng":
                detail["channel_2g"] = radio.get("channel")
            elif radio.get("radio") == "na":
                detail["channel_5g"] = radio.get("channel")

    if dev.get("port_table"):
        detail["ports"] = [
            {
                "port": p.get("port_idx"),
                "name": p.get("name", ""),
                "speed": p.get("speed", 0),
                "up": p.get("up", False),
                "poe": p.get("poe_enable", False),
            }
            for p in dev.get("port_table", [])
        ]

    print(json.dumps(detail, indent=2, default=str))


def cmd_summary(client, args):
    """Print a summary of all devices by type and status."""
    devices = client.list_devices(site=args.site)
    by_type = {}
    online = 0
    offline = 0
    upgradable = 0

    for d in devices:
        dtype = DEVICE_TYPE_NAMES.get(d.get("type", ""), d.get("type", "unknown"))
        by_type[dtype] = by_type.get(dtype, 0) + 1
        if d.get("state", 0) == 1:
            online += 1
        else:
            offline += 1
        if d.get("upgradable"):
            upgradable += 1

    summary = {
        "total_devices": len(devices),
        "online": online,
        "offline": offline,
        "upgradable": upgradable,
        "by_type": by_type,
    }
    print(json.dumps(summary, indent=2))


def cmd_firmware(client, args):
    """List firmware status for all devices."""
    devices = client.list_devices(site=args.site)
    rows = []
    for d in devices:
        rows.append({
            "name": d.get("name", d.get("hostname", d.get("mac", "?"))),
            "mac": d.get("mac"),
            "model": d.get("model"),
            "current_firmware": d.get("version"),
            "upgradable": d.get("upgradable", False),
            "upgrade_to": d.get("upgrade_to_firmware"),
        })
    print(json.dumps(rows, indent=2))


def cmd_restart(client, args):
    """Restart a device by MAC address."""
    result = client.restart_device(args.mac, site=args.site)
    print(json.dumps({"action": "restart", "mac": args.mac, "result": result}, indent=2))


def cmd_adopt(client, args):
    """Adopt a device by MAC address."""
    result = client.adopt_device(args.mac, site=args.site)
    print(json.dumps({"action": "adopt", "mac": args.mac, "result": result}, indent=2))


def cmd_upgrade(client, args):
    """Trigger firmware upgrade on a device."""
    result = client.upgrade_device(args.mac, site=args.site)
    print(json.dumps({"action": "upgrade", "mac": args.mac, "result": result}, indent=2))


def cmd_provision(client, args):
    """Force re-provision a device."""
    result = client.force_provision(args.mac, site=args.site)
    print(json.dumps({"action": "provision", "mac": args.mac, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="UniFi Device Management")
    parser.add_argument("command", choices=["list", "detail", "summary", "firmware",
                                            "restart", "adopt", "upgrade", "provision"])
    parser.add_argument("mac", nargs="?", help="Device MAC address (for detail/restart/adopt/upgrade/provision)")
    parser.add_argument("--site", default=None, help="Site name")
    args = parser.parse_args()

    if args.command in ("detail", "restart", "adopt", "upgrade", "provision") and not args.mac:
        parser.error(f"{args.command} requires a MAC address argument")

    client = UniFiClient()
    try:
        {
            "list": cmd_list,
            "detail": cmd_detail,
            "summary": cmd_summary,
            "firmware": cmd_firmware,
            "restart": cmd_restart,
            "adopt": cmd_adopt,
            "upgrade": cmd_upgrade,
            "provision": cmd_provision,
        }[args.command](client, args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
