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
Microsoft Purview Alert Policy Management Tool

List and inspect alert policies configured in the Security & Compliance center.

License requirements:
  E3: Basic alert policies (system-generated)
  E5: Advanced alert policies, custom alert categories

Usage:
    python3 alert_policy.py list                       # List all alert policies
    python3 alert_policy.py detail <name>              # Policy details
    python3 alert_policy.py by-category                # Group by category
    python3 alert_policy.py summary                    # Alert policy summary
"""

import sys
import json
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from purview_client import PurviewClient


def list_policies(client: PurviewClient):
    result = client.run_cmdlet("Get-ProtectionAlert")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    alerts = result["data"] if isinstance(result["data"], list) else []
    print(f"Protection Alert Policies: {len(alerts)}")
    print()
    print(f"{'Severity':<10} {'Category':<28} {'Name':<50} {'Enabled'}")
    print("-" * 100)

    for a in sorted(alerts, key=lambda x: x.get("Severity", "")):
        severity = (a.get("Severity") or "?")[:9]
        category = (a.get("Category") or "?")[:27]
        name = (a.get("Name") or "?")[:49]
        enabled = "ON" if a.get("IsEnabled") else "OFF"
        print(f"{severity:<10} {category:<28} {name:<50} {enabled}")


def policy_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-ProtectionAlert", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def by_category(client: PurviewClient):
    result = client.run_cmdlet("Get-ProtectionAlert")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    alerts = result["data"] if isinstance(result["data"], list) else []
    categories = {}
    for a in alerts:
        cat = a.get("Category") or "Unknown"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(a)

    print(f"Alert Policies by Category")
    print(f"=" * 80)

    for cat in sorted(categories.keys()):
        items = categories[cat]
        print(f"\n── {cat} ({len(items)}) ──")
        for a in items:
            severity = (a.get("Severity") or "?")[:8]
            name = (a.get("Name") or "?")[:55]
            enabled = "ON" if a.get("IsEnabled") else "OFF"
            print(f"  [{severity:<8}] {name:<55} {enabled}")


def summary(client: PurviewClient):
    result = client.run_cmdlet("Get-ProtectionAlert")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    alerts = result["data"] if isinstance(result["data"], list) else []

    print(f"Alert Policy Summary")
    print(f"=" * 60)
    print(f"Total alert policies: {len(alerts)}")
    print()

    severities = Counter(a.get("Severity", "Unknown") for a in alerts)
    print("By severity:")
    for s, c in severities.most_common():
        print(f"  {s:<20} {c}")

    categories = Counter(a.get("Category", "Unknown") for a in alerts)
    print()
    print("By category:")
    for cat, c in categories.most_common():
        print(f"  {cat:<30} {c}")

    enabled = sum(1 for a in alerts if a.get("IsEnabled"))
    disabled = len(alerts) - enabled
    print()
    print(f"Enabled: {enabled}")
    print(f"Disabled: {disabled}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = PurviewClient()
    command = sys.argv[1].lower()

    if command == "list":
        list_policies(client)
    elif command == "detail":
        if len(sys.argv) < 3:
            print("Usage: alert_policy.py detail <name>")
            sys.exit(1)
        policy_detail(client, " ".join(sys.argv[2:]))
    elif command in ("by-category", "bycategory"):
        by_category(client)
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
