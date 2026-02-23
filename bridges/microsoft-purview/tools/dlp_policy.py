"""
Microsoft Purview DLP Policy Management Tool

List, inspect, and audit Data Loss Prevention policies and rules.

License requirements:
  E3: Core DLP (Exchange, SharePoint, OneDrive) with basic reporting
  E5: + Endpoint DLP (Windows/macOS device monitoring)

Usage:
    python3 dlp_policy.py list                           # List all DLP policies
    python3 dlp_policy.py detail <policy-name>           # Policy details
    python3 dlp_policy.py rules                          # List all DLP rules
    python3 dlp_policy.py rules <policy-name>            # Rules for a specific policy
    python3 dlp_policy.py rule-detail <rule-name>        # Detailed rule configuration
    python3 dlp_policy.py sensitive-types                # List sensitive information types
    python3 dlp_policy.py summary                        # DLP policy summary
"""

import sys
import json
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from purview_client import PurviewClient


def list_policies(client: PurviewClient):
    result = client.run_cmdlet("Get-DlpCompliancePolicy")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    policies = result["data"] if isinstance(result["data"], list) else []
    print(f"DLP Compliance Policies: {len(policies)}")
    print()
    print(f"{'Mode':<10} {'Name':<55} {'Workloads'}")
    print("-" * 100)

    for p in policies:
        mode = (p.get("Mode") or "?")[:9]
        name = (p.get("Name") or "?")[:54]
        workloads = str(p.get("Workload") or "?")[:30]
        print(f"{mode:<10} {name:<55} {workloads}")


def policy_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-DlpCompliancePolicy", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def list_rules(client: PurviewClient, policy_name: str = None):
    params = {}
    if policy_name:
        params["Policy"] = policy_name

    result = client.run_cmdlet("Get-DlpComplianceRule", params if params else None)
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    rules = result["data"] if isinstance(result["data"], list) else []

    header = f"DLP Rules for '{policy_name}'" if policy_name else "All DLP Rules"
    print(f"{header}: {len(rules)}")
    print()
    print(f"{'Mode':<10} {'Policy':<40} {'Rule':<40} {'Priority':>8}")
    print("-" * 100)

    for r in sorted(rules, key=lambda x: x.get("Priority", 999)):
        mode = (r.get("Mode") or "?")[:9]
        policy = (r.get("ParentPolicyName") or "?")[:39]
        name = (r.get("Name") or "?")[:39]
        priority = r.get("Priority", "?")
        print(f"{mode:<10} {policy:<40} {name:<40} {priority:>8}")


def rule_detail(client: PurviewClient, name: str):
    result = client.run_cmdlet("Get-DlpComplianceRule", {"Identity": name})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]
    print(json.dumps(data, indent=2, default=str))


def list_sensitive_types(client: PurviewClient):
    result = client.run_cmdlet("Get-DlpSensitiveInformationType")
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    types = result["data"] if isinstance(result["data"], list) else []
    print(f"Sensitive Information Types: {len(types)}")
    print()

    publishers = Counter(t.get("Publisher") or "Unknown" for t in types)
    print("By publisher:")
    for pub, count in publishers.most_common():
        print(f"  {pub:<50} {count}")
    print()
    print(f"{'Name':<60} {'Publisher'}")
    print("-" * 90)
    for t in sorted(types, key=lambda x: x.get("Name", "")):
        name = (t.get("Name") or "?")[:59]
        pub = (t.get("Publisher") or "?")[:29]
        print(f"{name:<60} {pub}")


def summary(client: PurviewClient):
    policies = client.run_cmdlet("Get-DlpCompliancePolicy")
    rules = client.run_cmdlet("Get-DlpComplianceRule")

    if not policies["ok"]:
        print(f"ERROR getting policies: {policies['error']}")
        sys.exit(1)

    p_list = policies["data"] if isinstance(policies["data"], list) else []
    r_list = rules["data"] if isinstance(rules["data"], list) else [] if rules["ok"] else []

    print(f"DLP Policy Summary")
    print(f"=" * 60)
    print(f"Total policies: {len(p_list)}")
    print(f"Total rules: {len(r_list)}")
    print()

    modes = Counter(p.get("Mode", "Unknown") for p in p_list)
    print("Policies by mode:")
    for m, c in modes.most_common():
        print(f"  {m:<20} {c}")

    print()
    workloads = Counter()
    for p in p_list:
        wl = str(p.get("Workload") or "Unknown")
        workloads[wl] += 1
    print("Policies by workload:")
    for w, c in workloads.most_common():
        print(f"  {w:<40} {c}")


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
            print("Usage: dlp_policy.py detail <policy-name>")
            sys.exit(1)
        policy_detail(client, " ".join(sys.argv[2:]))
    elif command == "rules":
        policy = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        list_rules(client, policy)
    elif command in ("rule-detail", "ruledetail"):
        if len(sys.argv) < 3:
            print("Usage: dlp_policy.py rule-detail <rule-name>")
            sys.exit(1)
        rule_detail(client, " ".join(sys.argv[2:]))
    elif command in ("sensitive-types", "sensitivetypes", "sit"):
        list_sensitive_types(client)
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
