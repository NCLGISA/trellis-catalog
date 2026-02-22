#!/usr/bin/env python3
"""
Sierra AirLink Alert Monitoring Tool

Subcommands:
    rules              List all alert rules
    active             Systems currently in alert state
    history            Recent alert events (last 7 days by default)

Usage:
    python3 alert_check.py rules
    python3 alert_check.py active
    python3 alert_check.py history
    python3 alert_check.py history --days 30
"""

import sys
import json
import time
from datetime import datetime, timezone, timedelta
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


def cmd_rules(client: AirLinkClient):
    rules = client.list_alert_rules()
    print(f"Total alert rules: {len(rules)}\n")
    if not rules:
        print("No alert rules configured.")
        return

    print(f"{'Name':40s}  {'Active':8s}  {'Stateful':10s}  {'Target':10s}  {'Conditions'}")
    print("-" * 100)
    for r in rules:
        name = r.get("name") or "?"
        active = "yes" if r.get("active") else "no"
        stateful = "yes" if r.get("stateful") else "no"
        target = r.get("targetType") or "?"
        conditions = r.get("conditions") or []
        cond_count = str(len(conditions))
        print(f"{name:40s}  {active:8s}  {stateful:10s}  {target:10s}  {cond_count}")


def cmd_active(client: AirLinkClient):
    alerts = client.list_current_alerts()
    active = [a for a in alerts if a.get("state", False)]

    print(f"Current alert states: {len(alerts)} total, {len(active)} active\n")
    if not active:
        print("No systems currently in alert state.")
        return

    print(f"{'System':40s}  {'Rule':30s}  {'Since'}")
    print("-" * 100)
    for a in active:
        sys_name = a.get("target", {}).get("name", "?") if isinstance(a.get("target"), dict) else a.get("targetId", "?")
        rule_name = a.get("rule", {}).get("name", "?") if isinstance(a.get("rule"), dict) else a.get("ruleId", "?")
        since = ts_to_str(a.get("date") or a.get("stateChangeDate"))
        print(f"{str(sys_name):40s}  {str(rule_name):30s}  {since}")


def cmd_history(client: AirLinkClient, days: int = 7):
    now_ms = int(time.time() * 1000)
    from_ms = now_ms - (days * 86400 * 1000)

    history = client.list_alert_history(**{
        "from": str(from_ms),
        "to": str(now_ms),
    })

    print(f"Alert history (last {days} days): {len(history)} event(s)\n")
    if not history:
        print("No alert events in this period.")
        return

    print(f"{'Date':24s}  {'System':30s}  {'Rule':30s}  {'State'}")
    print("-" * 100)
    for h in history:
        date = ts_to_str(h.get("date"))
        sys_name = h.get("target", {}).get("name", "?") if isinstance(h.get("target"), dict) else h.get("targetId", "?")
        rule_name = h.get("rule", {}).get("name", "?") if isinstance(h.get("rule"), dict) else h.get("ruleId", "?")
        state = h.get("state", "?")
        print(f"{date:24s}  {str(sys_name):30s}  {str(rule_name):30s}  {state}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 alert_check.py <rules|active|history> [--days N]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    client = AirLinkClient()

    if cmd == "rules":
        cmd_rules(client)
    elif cmd == "active":
        cmd_active(client)
    elif cmd == "history":
        days = 7
        if "--days" in sys.argv:
            idx = sys.argv.index("--days")
            if idx + 1 < len(sys.argv):
                try:
                    days = int(sys.argv[idx + 1])
                except ValueError:
                    pass
        cmd_history(client, days)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: rules, active, history")
        sys.exit(1)


if __name__ == "__main__":
    main()
