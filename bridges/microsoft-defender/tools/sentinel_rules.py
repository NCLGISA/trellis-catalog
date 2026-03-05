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
Sentinel analytics rules and automation rules management.

Lists, enables, and disables Sentinel detection rules and SOAR automation
rules via the Sentinel ARM API.

Usage:
    python3 sentinel_rules.py analytics                    # List analytics rules
    python3 sentinel_rules.py analytics --enabled          # Only enabled rules
    python3 sentinel_rules.py analytics --disabled         # Only disabled rules
    python3 sentinel_rules.py analytics-detail <rule-id>   # Rule detail
    python3 sentinel_rules.py enable <rule-id>             # Enable a rule
    python3 sentinel_rules.py disable <rule-id>            # Disable a rule
    python3 sentinel_rules.py automation                   # List automation rules
    python3 sentinel_rules.py summary                      # Rule statistics
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient


def cmd_analytics(client: DefenderClient, enabled_only: bool = False, disabled_only: bool = False):
    rules = client.sentinel_get_all("alertRules")

    if enabled_only:
        rules = [r for r in rules if r.get("properties", {}).get("enabled")]
    elif disabled_only:
        rules = [r for r in rules if not r.get("properties", {}).get("enabled")]

    if not rules:
        print("No analytics rules found.")
        return

    print(f"Sentinel Analytics Rules: {len(rules)}\n")
    print(f"  {'Status':8s}  {'Severity':12s}  {'Kind':15s}  {'Name'}")
    print(f"  {'─'*8}  {'─'*12}  {'─'*15}  {'─'*50}")

    for r in sorted(rules, key=lambda x: (x.get("properties") or {}).get("displayName") or ""):
        props = r.get("properties") or {}
        status = "Enabled" if props.get("enabled") else "Disabled"
        sev = (props.get("severity") or "?")[:12]
        kind = (r.get("kind") or "?")[:15]
        name = (props.get("displayName") or r.get("name") or "?")[:50]
        print(f"  {status:8s}  {sev:12s}  {kind:15s}  {name}")


def cmd_analytics_detail(client: DefenderClient, rule_id: str):
    resp = client.sentinel_get(f"alertRules/{rule_id}")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    rule = resp.json()
    props = rule.get("properties", {})
    kind = rule.get("kind", "?")

    print(f"Analytics Rule: {props.get('displayName', '?')}")
    print(f"  ID:          {rule.get('name', '?')}")
    print(f"  Kind:        {kind}")
    print(f"  Enabled:     {props.get('enabled', False)}")
    print(f"  Severity:    {props.get('severity', '?')}")
    print(f"  Description: {props.get('description', '?')}")

    if kind == "Scheduled":
        print(f"  Query Period:    {props.get('queryPeriod', '?')}")
        print(f"  Query Frequency: {props.get('queryFrequency', '?')}")
        print(f"  Trigger Op:      {props.get('triggerOperator', '?')} {props.get('triggerThreshold', '?')}")
        query = props.get("query", "")
        if query:
            print(f"\n  KQL Query:")
            for line in query.strip().split("\n"):
                print(f"    {line}")

    tactics = props.get("tactics", [])
    if tactics:
        print(f"\n  MITRE Tactics: {', '.join(tactics)}")

    techniques = props.get("techniques", [])
    if techniques:
        print(f"  MITRE Techniques: {', '.join(techniques)}")


def _toggle_rule(client: DefenderClient, rule_id: str, enable: bool):
    resp = client.sentinel_get(f"alertRules/{rule_id}")
    if resp.status_code != 200:
        print(f"ERROR: Cannot fetch rule: {resp.status_code} {resp.text}")
        return

    rule = resp.json()
    rule["properties"]["enabled"] = enable

    put_resp = client.sentinel_put(f"alertRules/{rule_id}", rule)
    if put_resp.status_code in (200, 201):
        state = "enabled" if enable else "disabled"
        print(f"Rule '{rule.get('properties', {}).get('displayName', rule_id)}' {state}.")
    else:
        print(f"ERROR: {put_resp.status_code} {put_resp.text}")


def cmd_enable(client: DefenderClient, rule_id: str):
    _toggle_rule(client, rule_id, True)


def cmd_disable(client: DefenderClient, rule_id: str):
    _toggle_rule(client, rule_id, False)


def cmd_automation(client: DefenderClient):
    rules = client.sentinel_get_all("automationRules")

    if not rules:
        print("No automation rules found.")
        return

    print(f"Sentinel Automation Rules: {len(rules)}\n")
    for r in rules:
        props = r.get("properties", {})
        print(f"  {props.get('displayName', '?')}")
        print(f"    Order:   {props.get('order', '?')}")
        print(f"    Enabled: {not props.get('isDisabled', False)}")
        actions = props.get("actions", [])
        if actions:
            print(f"    Actions: {len(actions)}")
            for a in actions:
                print(f"      - {a.get('actionType', '?')}")
        print()


def cmd_summary(client: DefenderClient):
    analytics = client.sentinel_get_all("alertRules")
    automation = client.sentinel_get_all("automationRules")

    enabled = sum(1 for r in analytics if r.get("properties", {}).get("enabled"))
    disabled = len(analytics) - enabled

    by_kind = {}
    by_severity = {}
    for r in analytics:
        kind = r.get("kind", "Unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        sev = r.get("properties", {}).get("severity", "Unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    print(f"Sentinel Rules Summary\n")
    print(f"  Analytics Rules: {len(analytics)} (enabled: {enabled}, disabled: {disabled})")
    print(f"  Automation Rules: {len(automation)}")

    print("\n  Analytics by Kind:")
    for kind, count in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f"    {kind:20s}  {count}")

    if by_severity:
        print("\n  Analytics by Severity:")
        for sev, count in sorted(by_severity.items()):
            print(f"    {sev:20s}  {count}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    enabled_only = "--enabled" in sys.argv
    disabled_only = "--disabled" in sys.argv
    args = [a for a in sys.argv[2:] if not a.startswith("--")]

    if cmd == "analytics":
        cmd_analytics(client, enabled_only=enabled_only, disabled_only=disabled_only)
    elif cmd == "analytics-detail" and args:
        cmd_analytics_detail(client, args[0])
    elif cmd == "enable" and args:
        cmd_enable(client, args[0])
    elif cmd == "disable" and args:
        cmd_disable(client, args[0])
    elif cmd == "automation":
        cmd_automation(client)
    elif cmd == "summary":
        cmd_summary(client)
    else:
        print(__doc__.strip())
        sys.exit(1)
