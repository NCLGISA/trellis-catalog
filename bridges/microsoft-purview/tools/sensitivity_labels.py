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
Microsoft Purview Sensitivity Label Management Tool

Read-only operations on sensitivity labels and label policies.

License requirements:
  E3: Manual labeling only
  E5: + Auto-labeling, ML-based classification, meeting labels, conditional access

Usage:
    python3 sensitivity_labels.py list                    # List all sensitivity labels
    python3 sensitivity_labels.py detail <label-name>     # Label details
    python3 sensitivity_labels.py policies                # List label policies
    python3 sensitivity_labels.py policy-detail <name>    # Policy details
    python3 sensitivity_labels.py auto-labeling           # List auto-labeling policies (E5)
    python3 sensitivity_labels.py summary                 # Label inventory summary
"""

import sys
import json
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from purview_client import PurviewClient


def list_labels(client: PurviewClient):
    result = client.run_cmdlet("Get-Label")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    labels = result["data"] if isinstance(result["data"], list) else []
    print(f"Sensitivity Labels: {len(labels)}")
    print()
    print(f"{'Priority':>8} {'Name':<40} {'Display Name':<35} {'Parent'}")
    print("-" * 100)

    for l in sorted(labels, key=lambda x: x.get("Priority", 999)):
        priority = l.get("Priority", "?")
        name = (l.get("Name") or "?")[:39]
        display = (l.get("DisplayName") or "?")[:34]
        parent = (l.get("ParentLabelDisplay") or l.get("ParentId") or "-")[:20]
        print(f"{priority:>8} {name:<40} {display:<35} {parent}")


def label_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-Label", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def list_policies(client: PurviewClient):
    result = client.run_cmdlet("Get-LabelPolicy")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    policies = result["data"] if isinstance(result["data"], list) else []
    print(f"Label Policies: {len(policies)}")
    print()
    print(f"{'Mode':<10} {'Name':<45} {'Labels'}")
    print("-" * 90)

    for p in policies:
        mode = (p.get("Mode") or "?")[:9]
        name = (p.get("Name") or "?")[:44]
        label_list = p.get("Labels") or []
        if isinstance(label_list, list):
            labels = ", ".join(str(l)[:15] for l in label_list[:3])
            if len(label_list) > 3:
                labels += f" (+{len(label_list) - 3} more)"
        else:
            labels = str(label_list)[:30]
        print(f"{mode:<10} {name:<45} {labels}")


def policy_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-LabelPolicy", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def list_auto_labeling(client: PurviewClient):
    result = client.run_cmdlet("Get-AutoSensitivityLabelPolicy")
    if not result["ok"]:
        if "not recognized" in result.get("error", "").lower():
            print("Auto-labeling policies require Microsoft 365 E5 or equivalent.")
            print("This cmdlet is not available with the current license/configuration.")
            return
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    policies = result["data"] if isinstance(result["data"], list) else []
    if not policies:
        print("No auto-labeling policies found.")
        print("Note: Auto-labeling requires Microsoft 365 E5 or E5 Information Protection add-on.")
        return

    print(f"Auto-Labeling Policies: {len(policies)}")
    print()
    for p in policies:
        name = p.get("Name", "?")
        mode = p.get("Mode", "?")
        enabled = p.get("Enabled", "?")
        print(f"  {name:<45} mode={mode} enabled={enabled}")


def summary(client: PurviewClient):
    labels = client.run_cmdlet("Get-Label")
    policies = client.run_cmdlet("Get-LabelPolicy")

    l_list = labels["data"] if labels["ok"] and isinstance(labels["data"], list) else []
    p_list = policies["data"] if policies["ok"] and isinstance(policies["data"], list) else []

    print(f"Sensitivity Label Summary")
    print(f"=" * 60)
    print(f"Labels: {len(l_list)}")
    print(f"Label policies: {len(p_list)}")
    print()

    if l_list:
        top_level = [l for l in l_list if not l.get("ParentId")]
        sub_labels = [l for l in l_list if l.get("ParentId")]
        print(f"Top-level labels: {len(top_level)}")
        print(f"Sub-labels: {len(sub_labels)}")
        print()
        print("Label hierarchy:")
        for l in sorted(l_list, key=lambda x: x.get("Priority", 999)):
            indent = "    " if l.get("ParentId") else "  "
            display = l.get("DisplayName") or l.get("Name") or "?"
            priority = l.get("Priority", "?")
            print(f"{indent}[{priority}] {display}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = PurviewClient()
    command = sys.argv[1].lower()

    if command == "list":
        list_labels(client)
    elif command == "detail":
        if len(sys.argv) < 3:
            print("Usage: sensitivity_labels.py detail <label-name>")
            sys.exit(1)
        label_detail(client, " ".join(sys.argv[2:]))
    elif command == "policies":
        list_policies(client)
    elif command in ("policy-detail", "policydetail"):
        if len(sys.argv) < 3:
            print("Usage: sensitivity_labels.py policy-detail <name>")
            sys.exit(1)
        policy_detail(client, " ".join(sys.argv[2:]))
    elif command in ("auto-labeling", "autolabeling"):
        list_auto_labeling(client)
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
