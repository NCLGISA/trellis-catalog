#!/usr/bin/env python3
"""
UniFi Statistics and Analytics Tool

DPI (Deep Packet Inspection), traffic analytics, site health, and event
monitoring for UniFi controllers.

Usage:
    python3 unifi_stats.py health [--site SITE]
    python3 unifi_stats.py dpi [--site SITE]
    python3 unifi_stats.py events [--site SITE] [--limit N]
    python3 unifi_stats.py alarms [--site SITE]
    python3 unifi_stats.py rogues [--site SITE]
    python3 unifi_stats.py traffic [--site SITE] [--interval hourly|daily|5minutes]
    python3 unifi_stats.py dashboard [--site SITE]

All operations are read-only.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient


def _format_bytes(b):
    if b is None:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def cmd_health(client, args):
    """Site health overview -- all subsystems."""
    health = client.site_health(site=args.site)
    rows = []
    for h in health:
        row = {
            "subsystem": h.get("subsystem", "?"),
            "status": h.get("status", "?"),
            "num_ap": h.get("num_ap"),
            "num_sta": h.get("num_sta"),
            "num_user": h.get("num_user"),
            "num_guest": h.get("num_guest"),
            "tx_bytes": h.get("tx_bytes-r"),
            "rx_bytes": h.get("rx_bytes-r"),
        }
        row = {k: v for k, v in row.items() if v is not None}
        rows.append(row)
    print(json.dumps(rows, indent=2))


def cmd_dpi(client, args):
    """DPI (Deep Packet Inspection) statistics."""
    stats = client.get_dpi_stats(site=args.site)
    if not stats:
        print(json.dumps({"message": "No DPI data available (DPI may not be enabled)"}))
        return
    print(json.dumps(stats, indent=2, default=str))


def cmd_events(client, args):
    """Recent events from the controller."""
    events = client.list_events(site=args.site, limit=args.limit)
    rows = []
    for e in events:
        ts = e.get("time") or e.get("datetime")
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts,
                                       tz=timezone.utc).isoformat()
        rows.append({
            "time": ts,
            "key": e.get("key", ""),
            "msg": e.get("msg", ""),
            "subsystem": e.get("subsystem", ""),
            "ap": e.get("ap", ""),
            "client": e.get("user", e.get("client", "")),
        })
    print(json.dumps(rows, indent=2))


def cmd_alarms(client, args):
    """Active alarms."""
    alarms = client.list_alarms(site=args.site)
    rows = []
    for a in alarms:
        ts = a.get("time") or a.get("datetime")
        if isinstance(ts, (int, float)):
            ts = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts,
                                       tz=timezone.utc).isoformat()
        rows.append({
            "time": ts,
            "key": a.get("key", ""),
            "msg": a.get("msg", ""),
            "archived": a.get("archived", False),
            "ap": a.get("ap", ""),
            "device_mac": a.get("device_mac", ""),
        })
    print(json.dumps(rows, indent=2))


def cmd_rogues(client, args):
    """Detected rogue access points."""
    rogues = client.list_rogue_aps(site=args.site)
    rows = []
    for r in rogues:
        rows.append({
            "bssid": r.get("bssid", "?"),
            "essid": r.get("essid", ""),
            "channel": r.get("channel"),
            "rssi": r.get("rssi"),
            "security": r.get("security", ""),
            "oui": r.get("oui", ""),
            "is_rogue": r.get("is_rogue", False),
            "ap_mac": r.get("ap_mac", ""),
            "last_seen": r.get("last_seen"),
        })
    rows.sort(key=lambda r: -(r.get("rssi") or -100))
    print(json.dumps(rows, indent=2))


def cmd_traffic(client, args):
    """Site traffic statistics."""
    interval = args.interval or "hourly"
    stats = client.get_site_stats(site=args.site, interval=interval)
    if not stats:
        print(json.dumps({"message": f"No {interval} traffic data available"}))
        return
    print(json.dumps(stats, indent=2, default=str))


def cmd_dashboard(client, args):
    """Combined dashboard view -- health + device/client counts + recent events."""
    health = client.site_health(site=args.site)
    devices = client.list_devices(site=args.site)
    clients_list = client.list_clients(site=args.site)
    events = client.list_events(site=args.site, limit=5)
    alarms = client.list_alarms(site=args.site)

    online_devices = sum(1 for d in devices if d.get("state", 0) == 1)
    offline_devices = len(devices) - online_devices
    upgradable = sum(1 for d in devices if d.get("upgradable"))

    wired_clients = sum(1 for c in clients_list if c.get("is_wired", False))
    wireless_clients = len(clients_list) - wired_clients

    subsystem_status = {h.get("subsystem", "?"): h.get("status", "?") for h in health}

    recent_events = []
    for e in events[:5]:
        recent_events.append({
            "key": e.get("key", ""),
            "msg": e.get("msg", "")[:80],
        })

    dashboard = {
        "subsystems": subsystem_status,
        "devices": {
            "total": len(devices),
            "online": online_devices,
            "offline": offline_devices,
            "upgradable": upgradable,
        },
        "clients": {
            "total": len(clients_list),
            "wired": wired_clients,
            "wireless": wireless_clients,
        },
        "active_alarms": len(alarms),
        "recent_events": recent_events,
    }
    print(json.dumps(dashboard, indent=2))


def main():
    parser = argparse.ArgumentParser(description="UniFi Statistics and Analytics")
    parser.add_argument("command", choices=["health", "dpi", "events", "alarms",
                                            "rogues", "traffic", "dashboard"])
    parser.add_argument("--site", default=None, help="Site name")
    parser.add_argument("--limit", type=int, default=50, help="Result limit (for events)")
    parser.add_argument("--interval", default=None,
                        choices=["5minutes", "hourly", "daily"],
                        help="Stats interval (for traffic)")
    args = parser.parse_args()

    client = UniFiClient()
    try:
        {
            "health": cmd_health,
            "dpi": cmd_dpi,
            "events": cmd_events,
            "alarms": cmd_alarms,
            "rogues": cmd_rogues,
            "traffic": cmd_traffic,
            "dashboard": cmd_dashboard,
        }[args.command](client, args)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
