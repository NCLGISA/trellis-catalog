"""
Microsoft Purview Retention Policy and Label Management Tool

Read-only operations on retention policies, rules, and compliance tags (labels).
Write operations (New/Set-RetentionCompliancePolicy) are blocked by Microsoft
for certificate-based authentication and must be done via the Purview portal.

License requirements:
  E3: Basic retention labels and policies
  E5: Advanced retention with auto-apply, ML classification, disposition review

Usage:
    python3 retention_policy.py policies                     # List retention policies
    python3 retention_policy.py policy-detail <name>         # Policy details
    python3 retention_policy.py rules                        # List retention rules
    python3 retention_policy.py labels                       # List retention/compliance tags
    python3 retention_policy.py label-detail <name>          # Label details
    python3 retention_policy.py summary                      # Retention summary
"""

import sys
import json
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from purview_client import PurviewClient


def list_policies(client: PurviewClient):
    result = client.run_cmdlet("Get-RetentionCompliancePolicy")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    policies = result["data"] if isinstance(result["data"], list) else []
    print(f"Retention Compliance Policies: {len(policies)}")
    print()
    print(f"{'Enabled':<9} {'Mode':<10} {'Name':<55} {'Workloads'}")
    print("-" * 100)

    for p in policies:
        enabled = "ON" if p.get("Enabled") else "OFF"
        mode = (p.get("Mode") or "?")[:9]
        name = (p.get("Name") or "?")[:54]
        workloads = str(p.get("Workload") or "?")[:20]
        print(f"{enabled:<9} {mode:<10} {name:<55} {workloads}")


def policy_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-RetentionCompliancePolicy", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def list_rules(client: PurviewClient):
    result = client.run_cmdlet("Get-RetentionComplianceRule")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    rules = result["data"] if isinstance(result["data"], list) else []
    print(f"Retention Compliance Rules: {len(rules)}")
    print()
    print(f"{'Action':<16} {'Duration':<12} {'Policy':<40} {'Name'}")
    print("-" * 100)

    for r in rules:
        action = (r.get("RetentionComplianceAction") or "?")[:15]
        duration = str(r.get("RetentionDuration") or "?")[:11]
        policy = (r.get("Policy") or "?")[:39]
        name = (r.get("Name") or "?")[:40]
        print(f"{action:<16} {duration:<12} {policy:<40} {name}")


def list_labels(client: PurviewClient):
    result = client.run_cmdlet("Get-ComplianceTag")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    labels = result["data"] if isinstance(result["data"], list) else []
    print(f"Compliance Tags (Retention Labels): {len(labels)}")
    print()
    print(f"{'Action':<10} {'Duration':<12} {'Name':<55} {'Comment'}")
    print("-" * 100)

    for l in labels:
        action = (l.get("RetentionAction") or "?")[:9]
        duration = str(l.get("RetentionDuration") or "?")[:11]
        name = (l.get("Name") or "?")[:54]
        comment = (l.get("Comment") or "")[:25]
        print(f"{action:<10} {duration:<12} {name:<55} {comment}")


def label_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-ComplianceTag", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def summary(client: PurviewClient):
    policies = client.run_cmdlet("Get-RetentionCompliancePolicy")
    labels = client.run_cmdlet("Get-ComplianceTag")

    p_list = policies["data"] if policies["ok"] and isinstance(policies["data"], list) else []
    l_list = labels["data"] if labels["ok"] and isinstance(labels["data"], list) else []

    print(f"Retention Summary")
    print(f"=" * 60)
    print(f"Retention policies: {len(p_list)}")
    print(f"Retention labels (tags): {len(l_list)}")
    print()

    if p_list:
        modes = Counter(p.get("Mode", "Unknown") for p in p_list)
        print("Policies by mode:")
        for m, c in modes.most_common():
            print(f"  {m:<20} {c}")
        print()

    if l_list:
        actions = Counter(l.get("RetentionAction", "Unknown") for l in l_list)
        print("Labels by retention action:")
        for a, c in actions.most_common():
            print(f"  {a:<20} {c}")

        durations = Counter(str(l.get("RetentionDuration", "Unknown")) for l in l_list)
        print()
        print("Labels by retention duration:")
        for d, c in durations.most_common(10):
            print(f"  {d:<20} {c}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = PurviewClient()
    command = sys.argv[1].lower()

    if command == "policies":
        list_policies(client)
    elif command in ("policy-detail", "policydetail"):
        if len(sys.argv) < 3:
            print("Usage: retention_policy.py policy-detail <name>")
            sys.exit(1)
        policy_detail(client, " ".join(sys.argv[2:]))
    elif command == "rules":
        list_rules(client)
    elif command == "labels":
        list_labels(client)
    elif command in ("label-detail", "labeldetail"):
        if len(sys.argv) < 3:
            print("Usage: retention_policy.py label-detail <name>")
            sys.exit(1)
        label_detail(client, " ".join(sys.argv[2:]))
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
