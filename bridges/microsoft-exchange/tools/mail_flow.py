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
Exchange Online Mail Flow Tool

Message trace and transport rule management.
These operations are not available through Microsoft Graph API.

Usage:
    python3 mail_flow.py trace --sender user@example.com               # Trace by sender
    python3 mail_flow.py trace --recipient user@example.com            # Trace by recipient
    python3 mail_flow.py trace --sender user@example.com --days 7      # Last 7 days
    python3 mail_flow.py trace --messageid <message-id>                # Trace specific message
    python3 mail_flow.py rules                                          # List transport rules
    python3 mail_flow.py rule-detail <rule-name>                       # Rule details
"""

import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, "/opt/bridge/data/tools")
from exchange_client import ExchangeClient


def message_trace(client: ExchangeClient, sender: str = None, recipient: str = None,
                  message_id: str = None, days: int = 2):
    """Run a message trace."""
    params = {}
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")
    params["StartDate"] = start
    params["EndDate"] = end

    if sender:
        params["SenderAddress"] = sender
    if recipient:
        params["RecipientAddress"] = recipient
    if message_id:
        params["MessageId"] = message_id

    if not any([sender, recipient, message_id]):
        print("ERROR: Must specify --sender, --recipient, or --messageid")
        sys.exit(1)

    result = client.run_cmdlet("Get-MessageTrace", params)

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    messages = result["data"] if isinstance(result["data"], list) else []

    filter_desc = []
    if sender:
        filter_desc.append(f"sender={sender}")
    if recipient:
        filter_desc.append(f"recipient={recipient}")
    if message_id:
        filter_desc.append(f"messageid={message_id[:30]}...")

    print(f"Message Trace ({', '.join(filter_desc)}, last {days} days): {len(messages)}")
    print()
    print(f"{'Status':<14} {'Sender':<30} {'Recipient':<30} {'Subject':<30} {'Date'}")
    print("-" * 120)

    for m in messages:
        status = (m.get("Status") or "?")[:13]
        sender_addr = (m.get("SenderAddress") or "?")[:29]
        recipient_addr = (m.get("RecipientAddress") or "?")[:29]
        subject = (m.get("Subject") or "?")[:29]
        received = (m.get("Received") or "?")[:19]
        print(f"{status:<14} {sender_addr:<30} {recipient_addr:<30} {subject:<30} {received}")

    if not messages:
        print("No messages found matching the criteria.")


def list_transport_rules(client: ExchangeClient):
    """List all transport (mail flow) rules."""
    result = client.run_cmdlet("Get-TransportRule", {
        "ResultSize": "Unlimited",
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    rules = result["data"] if isinstance(result["data"], list) else []

    print(f"Transport Rules: {len(rules)}")
    print()
    print(f"{'State':<10} {'Priority':>8} {'Name':<50} {'Mode'}")
    print("-" * 80)

    for r in sorted(rules, key=lambda x: x.get("Priority", 999)):
        state = "ON" if r.get("State") == "Enabled" else "OFF"
        priority = r.get("Priority", "?")
        name = (r.get("Name") or "?")[:49]
        mode = r.get("Mode", "?")
        print(f"{state:<10} {priority:>8} {name:<50} {mode}")


def rule_detail(client: ExchangeClient, rule_name: str):
    """Show detailed information for a transport rule."""
    result = client.run_cmdlet("Get-TransportRule", {
        "Identity": rule_name,
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]

    print(json.dumps(data, indent=2, default=str))


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = ExchangeClient()
    command = sys.argv[1].lower()

    if command == "trace":
        sender = None
        recipient = None
        message_id = None
        days = 2

        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--sender" and i + 1 < len(args):
                sender = args[i + 1]
                i += 2
            elif args[i] == "--recipient" and i + 1 < len(args):
                recipient = args[i + 1]
                i += 2
            elif args[i] == "--messageid" and i + 1 < len(args):
                message_id = args[i + 1]
                i += 2
            elif args[i] == "--days" and i + 1 < len(args):
                days = int(args[i + 1])
                i += 2
            else:
                i += 1

        message_trace(client, sender=sender, recipient=recipient,
                      message_id=message_id, days=days)

    elif command == "rules":
        list_transport_rules(client)

    elif command in ("rule-detail", "ruledetail"):
        if len(sys.argv) < 3:
            print("Usage: mail_flow.py rule-detail <rule-name>")
            sys.exit(1)
        rule_detail(client, " ".join(sys.argv[2:]))

    else:
        print(f"Unknown command: {command}")
        print("Commands: trace, rules, rule-detail")
        sys.exit(1)


if __name__ == "__main__":
    main()
