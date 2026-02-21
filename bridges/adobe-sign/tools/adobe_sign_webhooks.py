#!/usr/bin/env python3
"""
Adobe Sign Webhooks Tool

Manage webhook subscriptions for real-time event notifications.

Usage:
    python3 adobe_sign_webhooks.py list
    python3 adobe_sign_webhooks.py info <webhook_id>
    python3 adobe_sign_webhooks.py create --name NAME --url URL [--events EVENT1,EVENT2] [--scope ACCOUNT|GROUP|USER|RESOURCE]
    python3 adobe_sign_webhooks.py delete <webhook_id>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adobe_sign_client import AdobeSignClient


def cmd_list(client):
    webhooks = client.list_webhooks()
    print(f"Webhooks ({len(webhooks)}):")
    print(f"{'Status':12s}  {'Scope':10s}  {'Name':40s}  {'URL'}")
    print("-" * 100)
    for w in webhooks:
        status = w.get("status", "?")
        scope = w.get("scope", "?")
        name = w.get("name", "Untitled")[:40]
        url = w.get("webhookUrlInfo", {}).get("url", "?")
        print(f"{status:12s}  {scope:10s}  {name:40s}  {url}")


def cmd_info(client, webhook_id):
    webhook = client.get_webhook(webhook_id)
    print(json.dumps(webhook, indent=2, default=str))


def cmd_create(client, args):
    name = None
    url = None
    events_str = "AGREEMENT_ALL"
    scope = "ACCOUNT"

    i = 0
    while i < len(args):
        if args[i] == "--name" and i + 1 < len(args):
            name = args[i + 1]
            i += 2
        elif args[i] == "--url" and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        elif args[i] == "--events" and i + 1 < len(args):
            events_str = args[i + 1]
            i += 2
        elif args[i] == "--scope" and i + 1 < len(args):
            scope = args[i + 1].upper()
            i += 2
        else:
            i += 1

    if not name:
        print("ERROR: --name is required", file=sys.stderr)
        sys.exit(1)
    if not url:
        print("ERROR: --url is required", file=sys.stderr)
        sys.exit(1)

    events = [e.strip() for e in events_str.split(",")]
    result = client.create_webhook(name=name, url=url, scope=scope, events=events)
    webhook_id = result.get("id", "?")
    print(f"Webhook created: {webhook_id}")
    print(json.dumps(result, indent=2))


def cmd_delete(client, webhook_id):
    client.delete_webhook(webhook_id)
    print(f"Webhook {webhook_id} deleted")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = AdobeSignClient()

    if action == "list":
        cmd_list(client)
    elif action == "info" and len(sys.argv) >= 3:
        cmd_info(client, sys.argv[2])
    elif action == "create":
        cmd_create(client, sys.argv[2:])
    elif action == "delete" and len(sys.argv) >= 3:
        cmd_delete(client, sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
