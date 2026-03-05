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
UniFi WLAN Management Tool

Wireless network configuration, status, and management for UniFi controllers.

Usage:
    python3 unifi_wlans.py list [--site SITE]
    python3 unifi_wlans.py detail <wlan_id> [--site SITE]
    python3 unifi_wlans.py summary [--site SITE]
    python3 unifi_wlans.py enable <wlan_id> [--site SITE]
    python3 unifi_wlans.py disable <wlan_id> [--site SITE]
    python3 unifi_wlans.py set-password <wlan_id> <password> [--site SITE]

Read operations are safe. enable/disable/set-password will mutate WLAN config.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient


def cmd_list(client, args):
    """List all wireless networks with key attributes."""
    wlans = client.list_wlans(site=args.site)
    rows = []
    for w in wlans:
        rows.append({
            "name": w.get("name", "?"),
            "id": w.get("_id", ""),
            "enabled": w.get("enabled", True),
            "security": w.get("security", "?"),
            "wpa_mode": w.get("wpa_mode", ""),
            "is_guest": w.get("is_guest", False),
            "vlan_enabled": w.get("vlan_enabled", False),
            "vlan": w.get("vlan", ""),
            "band": w.get("wlan_band", "both"),
            "hide_ssid": w.get("hide_ssid", False),
            "mac_filter_enabled": w.get("mac_filter_enabled", False),
            "usergroup_id": w.get("usergroup_id", ""),
        })
    print(json.dumps(rows, indent=2))


def cmd_detail(client, args):
    """Get full configuration for a single WLAN."""
    wlan = client.get_wlan(args.wlan_id, site=args.site)
    if not wlan:
        print(json.dumps({"error": f"WLAN {args.wlan_id} not found"}))
        sys.exit(1)
    print(json.dumps(wlan, indent=2, default=str))


def cmd_summary(client, args):
    """Print WLAN summary -- counts by security type and status."""
    wlans = client.list_wlans(site=args.site)
    enabled = sum(1 for w in wlans if w.get("enabled", True))
    disabled = len(wlans) - enabled
    guest = sum(1 for w in wlans if w.get("is_guest", False))

    by_security = {}
    for w in wlans:
        sec = w.get("security", "open")
        by_security[sec] = by_security.get(sec, 0) + 1

    summary = {
        "total_wlans": len(wlans),
        "enabled": enabled,
        "disabled": disabled,
        "guest_networks": guest,
        "by_security": by_security,
        "wlan_names": [w.get("name", "?") for w in wlans],
    }
    print(json.dumps(summary, indent=2))


def cmd_enable(client, args):
    result = client.enable_wlan(args.wlan_id, site=args.site)
    print(json.dumps({"action": "enable", "wlan_id": args.wlan_id, "result": result}, indent=2))


def cmd_disable(client, args):
    result = client.disable_wlan(args.wlan_id, site=args.site)
    print(json.dumps({"action": "disable", "wlan_id": args.wlan_id, "result": result}, indent=2))


def cmd_set_password(client, args):
    """Update the WPA passphrase for a WLAN."""
    result = client.update_wlan(args.wlan_id, {"x_passphrase": args.password}, site=args.site)
    print(json.dumps({"action": "set-password", "wlan_id": args.wlan_id, "result": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="UniFi WLAN Management")
    parser.add_argument("command", choices=["list", "detail", "summary",
                                            "enable", "disable", "set-password"])
    parser.add_argument("wlan_id", nargs="?", help="WLAN ID")
    parser.add_argument("password", nargs="?", help="New WPA password (for set-password)")
    parser.add_argument("--site", default=None, help="Site name")
    args = parser.parse_args()

    if args.command in ("detail", "enable", "disable") and not args.wlan_id:
        parser.error(f"{args.command} requires a WLAN ID argument")
    if args.command == "set-password" and (not args.wlan_id or not args.password):
        parser.error("set-password requires WLAN ID and password arguments")

    client = UniFiClient()
    try:
        {
            "list": cmd_list,
            "detail": cmd_detail,
            "summary": cmd_summary,
            "enable": cmd_enable,
            "disable": cmd_disable,
            "set-password": cmd_set_password,
        }[args.command](client, args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
