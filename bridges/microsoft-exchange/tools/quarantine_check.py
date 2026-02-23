"""
Exchange Online Quarantine Management Tool

List, search, preview, release, and delete quarantined email messages.
These operations are not available through Microsoft Graph API.

Usage:
    python3 quarantine_check.py list                           # Recent quarantined messages
    python3 quarantine_check.py list --days 7                  # Last 7 days
    python3 quarantine_check.py search <sender-or-subject>     # Search by sender or subject
    python3 quarantine_check.py detail <identity>              # Full details for a message
    python3 quarantine_check.py release <identity>             # Release from quarantine
    python3 quarantine_check.py release-all --sender <addr>    # Release all from a sender
    python3 quarantine_check.py delete <identity>              # Delete from quarantine
    python3 quarantine_check.py summary                        # Quarantine statistics
"""

import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, "/opt/bridge/data/tools")
from exchange_client import ExchangeClient


def list_quarantine(client: ExchangeClient, days: int = 3, page_size: int = 50):
    """List recent quarantined messages."""
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")

    result = client.run_cmdlet("Get-QuarantineMessage", {
        "StartReceivedDate": start,
        "EndReceivedDate": end,
        "PageSize": str(page_size),
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    messages = result["data"]
    if isinstance(messages, str):
        print(messages)
        return

    print(f"Quarantined Messages (last {days} days): {len(messages)}")
    print()
    print(f"{'Type':<12} {'Direction':<10} {'Sender':<35} {'Subject':<40} {'Received'}")
    print("-" * 115)

    for m in messages:
        qtype = (m.get("QuarantineTypes") or m.get("Type") or "?")[:11]
        direction = (m.get("Direction") or "?")[:9]
        sender = (m.get("SenderAddress") or "?")[:34]
        subject = (m.get("Subject") or "?")[:39]
        received = (m.get("ReceivedTime") or "?")[:19]
        print(f"{qtype:<12} {direction:<10} {sender:<35} {subject:<40} {received}")


def search_quarantine(client: ExchangeClient, query: str):
    """Search quarantine by sender address or subject."""
    start = (datetime.utcnow() - timedelta(days=30)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")

    result = client.run_cmdlet("Get-QuarantineMessage", {
        "SenderAddress": query,
        "StartReceivedDate": start,
        "EndReceivedDate": end,
    })

    if result["ok"] and result["data"] and isinstance(result["data"], list) and len(result["data"]) > 0:
        messages = result["data"]
        print(f"Quarantine matches for sender '{query}': {len(messages)}")
    else:
        result = client.run_cmdlet("Get-QuarantineMessage", {
            "Subject": query,
            "StartReceivedDate": start,
            "EndReceivedDate": end,
        })
        if not result["ok"]:
            print(f"ERROR: {result['error']}")
            sys.exit(1)
        messages = result["data"] if isinstance(result["data"], list) else []
        print(f"Quarantine matches for subject '{query}': {len(messages)}")

    if not messages:
        print("No matches found.")
        return

    print()
    for m in messages:
        identity = m.get("Identity", "?")
        sender = m.get("SenderAddress", "?")
        subject = m.get("Subject", "?")
        recipient = m.get("RecipientAddress") or ", ".join(m.get("RecipientAddress", []) if isinstance(m.get("RecipientAddress"), list) else [str(m.get("RecipientAddress", "?"))])
        received = m.get("ReceivedTime", "?")
        qtype = m.get("QuarantineTypes") or m.get("Type") or "?"

        print(f"  Identity:  {identity}")
        print(f"  Sender:    {sender}")
        print(f"  Recipient: {recipient}")
        print(f"  Subject:   {subject}")
        print(f"  Type:      {qtype}")
        print(f"  Received:  {received}")
        print()


def detail_message(client: ExchangeClient, identity: str):
    """Get full details for a quarantined message."""
    result = client.run_cmdlet("Get-QuarantineMessage", {
        "Identity": identity,
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]

    print(json.dumps(data, indent=2, default=str))


def release_message(client: ExchangeClient, identity: str):
    """Release a message from quarantine."""
    result = client.run_cmdlet("Release-QuarantineMessage", {
        "Identity": identity,
        "ReleaseToAll": True,
        "Confirm": False,
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Released: {identity}")
    if result["data"]:
        print(json.dumps(result["data"], indent=2, default=str))


def release_all_from_sender(client: ExchangeClient, sender: str):
    """Release all quarantined messages from a specific sender."""
    start = (datetime.utcnow() - timedelta(days=30)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")

    result = client.run_cmdlet("Get-QuarantineMessage", {
        "SenderAddress": sender,
        "StartReceivedDate": start,
        "EndReceivedDate": end,
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    messages = result["data"] if isinstance(result["data"], list) else []
    if not messages:
        print(f"No quarantined messages from {sender}")
        return

    print(f"Releasing {len(messages)} messages from {sender}...")
    for m in messages:
        identity = m.get("Identity")
        if identity:
            r = client.run_cmdlet("Release-QuarantineMessage", {
                "Identity": identity,
                "ReleaseToAll": True,
                "Confirm": False,
            })
            status = "OK" if r["ok"] else f"FAILED: {r.get('error', '?')[:40]}"
            subject = (m.get("Subject") or "?")[:50]
            print(f"  [{status}] {subject}")


def delete_message(client: ExchangeClient, identity: str):
    """Delete a message from quarantine."""
    result = client.run_cmdlet("Delete-QuarantineMessage", {
        "Identity": identity,
        "Confirm": False,
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Deleted: {identity}")


def summary(client: ExchangeClient):
    """Quarantine statistics summary."""
    start = (datetime.utcnow() - timedelta(days=7)).strftime("%m/%d/%Y")
    end = datetime.utcnow().strftime("%m/%d/%Y")

    result = client.run_cmdlet("Get-QuarantineMessage", {
        "StartReceivedDate": start,
        "EndReceivedDate": end,
        "PageSize": "200",
    })

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    messages = result["data"] if isinstance(result["data"], list) else []

    from collections import Counter
    types = Counter(m.get("QuarantineTypes") or m.get("Type") or "Unknown" for m in messages)
    directions = Counter(m.get("Direction", "Unknown") for m in messages)
    senders = Counter(m.get("SenderAddress", "Unknown") for m in messages)

    print(f"Quarantine Summary (last 7 days)")
    print(f"=" * 60)
    print(f"Total messages: {len(messages)}")
    print()
    print(f"By type:")
    for t, c in types.most_common():
        print(f"  {t:<30} {c}")
    print()
    print(f"By direction:")
    for d, c in directions.most_common():
        print(f"  {d:<30} {c}")
    print()
    print(f"Top senders:")
    for s, c in senders.most_common(10):
        print(f"  {s:<45} {c}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = ExchangeClient()
    command = sys.argv[1].lower()

    if command == "list":
        days = 3
        if "--days" in sys.argv:
            idx = sys.argv.index("--days")
            days = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 3
        list_quarantine(client, days=days)
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: quarantine_check.py search <sender-or-subject>")
            sys.exit(1)
        search_quarantine(client, " ".join(sys.argv[2:]))
    elif command == "detail":
        if len(sys.argv) < 3:
            print("Usage: quarantine_check.py detail <identity>")
            sys.exit(1)
        detail_message(client, sys.argv[2])
    elif command == "release":
        if len(sys.argv) < 3:
            print("Usage: quarantine_check.py release <identity>")
            sys.exit(1)
        release_message(client, sys.argv[2])
    elif command in ("release-all", "releaseall"):
        if "--sender" not in sys.argv:
            print("Usage: quarantine_check.py release-all --sender <address>")
            sys.exit(1)
        idx = sys.argv.index("--sender")
        sender = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        if not sender:
            print("Usage: quarantine_check.py release-all --sender <address>")
            sys.exit(1)
        release_all_from_sender(client, sender)
    elif command == "delete":
        if len(sys.argv) < 3:
            print("Usage: quarantine_check.py delete <identity>")
            sys.exit(1)
        delete_message(client, sys.argv[2])
    elif command == "summary":
        summary(client)
    else:
        print(f"Unknown command: {command}")
        print("Commands: list, search, detail, release, release-all, delete, summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
