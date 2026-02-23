"""
Exchange Online Mailbox Conversion Tool

Convert user mailboxes to shared mailboxes and manage forwarding.
These operations are not available through Microsoft Graph API.

Usage:
    python3 mailbox_convert.py info <mailbox>                        # Mailbox type and properties
    python3 mailbox_convert.py to-shared <mailbox>                   # Convert to shared mailbox
    python3 mailbox_convert.py to-user <mailbox>                     # Convert back to user mailbox
    python3 mailbox_convert.py set-forwarding <mailbox> <target>     # Set mail forwarding
    python3 mailbox_convert.py clear-forwarding <mailbox>            # Remove forwarding
    python3 mailbox_convert.py check-forwarding <mailbox>            # Check forwarding status
"""

import sys
import json
import subprocess

sys.path.insert(0, "/opt/bridge/data/tools")
from exchange_client import ExchangeClient


def mailbox_info(client: ExchangeClient, mailbox: str):
    """Show mailbox type and key properties."""
    result = client.run_cmdlet("Get-Mailbox", {"Identity": mailbox})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]

    if not isinstance(data, dict):
        print(f"No mailbox found for {mailbox}")
        sys.exit(1)

    print(f"=== Mailbox Info: {mailbox} ===\n")
    print(f"  Display Name:       {data.get('DisplayName', '?')}")
    print(f"  UPN:                {data.get('UserPrincipalName', '?')}")
    print(f"  Primary SMTP:       {data.get('PrimarySmtpAddress', '?')}")
    print(f"  Mailbox Type:       {data.get('RecipientTypeDetails', '?')}")
    print(f"  Is Shared:          {data.get('RecipientTypeDetails') == 'SharedMailbox'}")

    fwd = data.get("ForwardingAddress")
    fwd_smtp = data.get("ForwardingSmtpAddress")
    deliver = data.get("DeliverToMailboxAndForward")

    print(f"  Forwarding To:      {fwd or fwd_smtp or 'None'}")
    print(f"  Deliver & Forward:  {deliver}")

    delegates = data.get("GrantSendOnBehalfTo", [])
    print(f"  Send-on-Behalf:     {len(delegates)} delegate(s)")

    archive = data.get("ArchiveStatus")
    print(f"  Archive Status:     {archive or 'None'}")


def convert_to_shared(client: ExchangeClient, mailbox: str):
    """Convert a user mailbox to shared."""
    result = client.run_cmdlet("Set-Mailbox", {
        "Identity": mailbox, "Type": "Shared", "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Converted {mailbox} to Shared Mailbox")

    verify = client.run_cmdlet("Get-Mailbox", {"Identity": mailbox})
    if verify["ok"]:
        data = verify["data"]
        if isinstance(data, list) and data:
            data = data[0]
        mtype = data.get("RecipientTypeDetails", "?") if isinstance(data, dict) else "?"
        print(f"  Verified type: {mtype}")


def convert_to_user(client: ExchangeClient, mailbox: str):
    """Convert a shared mailbox back to user."""
    result = client.run_cmdlet("Set-Mailbox", {
        "Identity": mailbox, "Type": "Regular", "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(f"Converted {mailbox} to User Mailbox")


def set_forwarding(client: ExchangeClient, mailbox: str, target: str):
    """Set mail forwarding on a mailbox."""
    result = client.run_cmdlet("Set-Mailbox", {
        "Identity": mailbox,
        "ForwardingSmtpAddress": f"smtp:{target}",
        "DeliverToMailboxAndForward": True,
        "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(f"Forwarding set on {mailbox} -> {target} (deliver and forward)")


def clear_forwarding(client: ExchangeClient, mailbox: str):
    """Remove forwarding from a mailbox."""
    script = client._build_connect_script()
    script += (
        f"Set-Mailbox -Identity '{mailbox}' "
        f"-ForwardingAddress $null -ForwardingSmtpAddress $null "
        f"-DeliverToMailboxAndForward $false -Confirm:$false\n"
        f"Write-Output 'OK'\n"
        f"Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue\n"
    )

    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=60,
    )

    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()[:200]}")
        sys.exit(1)
    print(f"Forwarding cleared on {mailbox}")


def check_forwarding(client: ExchangeClient, mailbox: str):
    """Check forwarding status for a mailbox."""
    result = client.run_cmdlet("Get-Mailbox", {"Identity": mailbox})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]

    if not isinstance(data, dict):
        print(f"No mailbox found for {mailbox}")
        sys.exit(1)

    fwd = data.get("ForwardingAddress")
    fwd_smtp = data.get("ForwardingSmtpAddress")
    deliver = data.get("DeliverToMailboxAndForward")

    print(f"Forwarding Status for {mailbox}:")
    print(f"  Forwarding Address:     {fwd or 'None'}")
    print(f"  Forwarding SMTP:        {fwd_smtp or 'None'}")
    print(f"  Deliver to Mailbox Too: {deliver}")

    if not fwd and not fwd_smtp:
        print(f"\n  Status: No forwarding configured")
    else:
        target = fwd or fwd_smtp
        if deliver:
            print(f"\n  Status: Forwarding to {target} AND delivering to mailbox")
        else:
            print(f"\n  Status: Forwarding to {target} ONLY (no local delivery)")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = ExchangeClient()
    command = sys.argv[1].lower()

    if command == "info":
        if len(sys.argv) < 3:
            print("Usage: mailbox_convert.py info <mailbox>")
            sys.exit(1)
        mailbox_info(client, sys.argv[2])
    elif command in ("to-shared", "toshared"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_convert.py to-shared <mailbox>")
            sys.exit(1)
        convert_to_shared(client, sys.argv[2])
    elif command in ("to-user", "touser"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_convert.py to-user <mailbox>")
            sys.exit(1)
        convert_to_user(client, sys.argv[2])
    elif command in ("set-forwarding", "setforwarding"):
        if len(sys.argv) < 4:
            print("Usage: mailbox_convert.py set-forwarding <mailbox> <target-email>")
            sys.exit(1)
        set_forwarding(client, sys.argv[2], sys.argv[3])
    elif command in ("clear-forwarding", "clearforwarding"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_convert.py clear-forwarding <mailbox>")
            sys.exit(1)
        clear_forwarding(client, sys.argv[2])
    elif command in ("check-forwarding", "checkforwarding"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_convert.py check-forwarding <mailbox>")
            sys.exit(1)
        check_forwarding(client, sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        print("Commands: info, to-shared, to-user, set-forwarding, clear-forwarding, check-forwarding")
        sys.exit(1)


if __name__ == "__main__":
    main()
