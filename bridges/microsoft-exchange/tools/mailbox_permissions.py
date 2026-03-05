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
Exchange Online Mailbox Permission Management Tool

Full mailbox delegation (FullAccess, Send-As, Send-on-Behalf) and
per-folder permissions. These operations are not available through
Microsoft Graph API (Graph only exposes calendar permissions).

Usage:
    python3 mailbox_permissions.py check <mailbox>                  # All permissions for a mailbox
    python3 mailbox_permissions.py full-access <mailbox>            # FullAccess delegates
    python3 mailbox_permissions.py send-as <mailbox>                # Send-As permissions
    python3 mailbox_permissions.py send-on-behalf <mailbox>         # Send-on-Behalf permissions
    python3 mailbox_permissions.py folder <mailbox> [folder]        # Folder permissions (default: inbox)
    python3 mailbox_permissions.py grant-full <mailbox> <user>      # Grant FullAccess
    python3 mailbox_permissions.py revoke-full <mailbox> <user>     # Revoke FullAccess
    python3 mailbox_permissions.py grant-sendas <mailbox> <user>    # Grant Send-As
    python3 mailbox_permissions.py revoke-sendas <mailbox> <user>   # Revoke Send-As
"""

import sys
import json

sys.path.insert(0, "/opt/bridge/data/tools")
from exchange_client import ExchangeClient


def check_all_permissions(client: ExchangeClient, mailbox: str):
    """Show all permissions for a mailbox."""
    print(f"=== Mailbox Permissions: {mailbox} ===\n")

    result = client.run_cmdlet("Get-MailboxPermission", {"Identity": mailbox})
    if result["ok"]:
        perms = result["data"] if isinstance(result["data"], list) else []
        real_perms = [p for p in perms
                      if p.get("User", "").lower() not in ("nt authority\\self", "")]
        if real_perms:
            print(f"FullAccess ({len(real_perms)}):")
            for p in real_perms:
                user = p.get("User", "?")
                rights = ", ".join(p.get("AccessRights", []))
                inherited = "inherited" if p.get("IsInherited") else "direct"
                print(f"  {user:<40} [{rights}] ({inherited})")
        else:
            print("FullAccess: None")
    else:
        print(f"FullAccess: error ({result['error'][:40]})")

    print()

    result = client.run_cmdlet("Get-RecipientPermission", {"Identity": mailbox})
    if result["ok"]:
        perms = result["data"] if isinstance(result["data"], list) else []
        real_perms = [p for p in perms
                      if p.get("Trustee", "").lower() not in ("nt authority\\self", "")]
        if real_perms:
            print(f"Send-As ({len(real_perms)}):")
            for p in real_perms:
                trustee = p.get("Trustee", "?")
                rights = ", ".join(p.get("AccessRights", []))
                print(f"  {trustee:<40} [{rights}]")
        else:
            print("Send-As: None")
    else:
        print(f"Send-As: error ({result['error'][:40]})")

    print()

    result = client.run_cmdlet("Get-Mailbox", {"Identity": mailbox})
    if result["ok"]:
        data = result["data"]
        if isinstance(data, list) and data:
            data = data[0]
        delegates = data.get("GrantSendOnBehalfTo", []) if isinstance(data, dict) else []
        if delegates:
            print(f"Send-on-Behalf ({len(delegates)}):")
            for d in delegates:
                print(f"  {d}")
        else:
            print("Send-on-Behalf: None")
    else:
        print(f"Send-on-Behalf: error ({result['error'][:40]})")


def full_access(client: ExchangeClient, mailbox: str):
    """List FullAccess permissions."""
    result = client.run_cmdlet("Get-MailboxPermission", {"Identity": mailbox})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    perms = result["data"] if isinstance(result["data"], list) else []
    real_perms = [p for p in perms
                  if p.get("User", "").lower() not in ("nt authority\\self", "")]

    print(f"FullAccess Permissions for {mailbox}: {len(real_perms)}")
    print()
    for p in real_perms:
        user = p.get("User", "?")
        rights = ", ".join(p.get("AccessRights", []))
        inherited = "inherited" if p.get("IsInherited") else "direct"
        deny = " [DENY]" if p.get("Deny") else ""
        print(f"  {user:<40} [{rights}] ({inherited}){deny}")


def send_as(client: ExchangeClient, mailbox: str):
    """List Send-As permissions."""
    result = client.run_cmdlet("Get-RecipientPermission", {"Identity": mailbox})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    perms = result["data"] if isinstance(result["data"], list) else []
    real_perms = [p for p in perms
                  if p.get("Trustee", "").lower() not in ("nt authority\\self", "")]

    print(f"Send-As Permissions for {mailbox}: {len(real_perms)}")
    print()
    for p in real_perms:
        trustee = p.get("Trustee", "?")
        rights = ", ".join(p.get("AccessRights", []))
        print(f"  {trustee:<40} [{rights}]")


def send_on_behalf(client: ExchangeClient, mailbox: str):
    """List Send-on-Behalf permissions."""
    result = client.run_cmdlet("Get-Mailbox", {"Identity": mailbox})
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    data = result["data"]
    if isinstance(data, list) and data:
        data = data[0]

    delegates = data.get("GrantSendOnBehalfTo", []) if isinstance(data, dict) else []

    print(f"Send-on-Behalf Permissions for {mailbox}: {len(delegates)}")
    print()
    for d in delegates:
        print(f"  {d}")


def folder_permissions(client: ExchangeClient, mailbox: str, folder: str = "Inbox"):
    """List permissions for a specific mailbox folder."""
    identity = f"{mailbox}:\\{folder}"
    result = client.run_cmdlet("Get-MailboxFolderPermission", {"Identity": identity})

    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    perms = result["data"] if isinstance(result["data"], list) else []

    print(f"Folder Permissions for {identity}: {len(perms)}")
    print()
    print(f"{'User':<40} {'Access Rights'}")
    print("-" * 70)

    for p in perms:
        user = p.get("User", {})
        if isinstance(user, dict):
            user_name = user.get("DisplayName") or user.get("ADRecipient") or "?"
        else:
            user_name = str(user)
        rights = ", ".join(p.get("AccessRights", []))
        print(f"  {user_name:<38} {rights}")


def grant_full_access(client: ExchangeClient, mailbox: str, user: str):
    """Grant FullAccess permission to a mailbox."""
    result = client.run_cmdlet("Add-MailboxPermission", {
        "Identity": mailbox,
        "User": user,
        "AccessRights": "FullAccess",
        "InheritanceType": "All",
        "AutoMapping": True,
        "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(f"Granted FullAccess on {mailbox} to {user}")


def revoke_full_access(client: ExchangeClient, mailbox: str, user: str):
    """Revoke FullAccess permission from a mailbox."""
    result = client.run_cmdlet("Remove-MailboxPermission", {
        "Identity": mailbox,
        "User": user,
        "AccessRights": "FullAccess",
        "InheritanceType": "All",
        "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(f"Revoked FullAccess on {mailbox} from {user}")


def grant_send_as(client: ExchangeClient, mailbox: str, user: str):
    """Grant Send-As permission."""
    result = client.run_cmdlet("Add-RecipientPermission", {
        "Identity": mailbox,
        "Trustee": user,
        "AccessRights": "SendAs",
        "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(f"Granted Send-As on {mailbox} to {user}")


def revoke_send_as(client: ExchangeClient, mailbox: str, user: str):
    """Revoke Send-As permission."""
    result = client.run_cmdlet("Remove-RecipientPermission", {
        "Identity": mailbox,
        "Trustee": user,
        "AccessRights": "SendAs",
        "Confirm": False,
    })
    if not result["ok"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(f"Revoked Send-As on {mailbox} from {user}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = ExchangeClient()
    command = sys.argv[1].lower()

    if command == "check":
        if len(sys.argv) < 3:
            print("Usage: mailbox_permissions.py check <mailbox>")
            sys.exit(1)
        check_all_permissions(client, sys.argv[2])
    elif command in ("full-access", "fullaccess"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_permissions.py full-access <mailbox>")
            sys.exit(1)
        full_access(client, sys.argv[2])
    elif command in ("send-as", "sendas"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_permissions.py send-as <mailbox>")
            sys.exit(1)
        send_as(client, sys.argv[2])
    elif command in ("send-on-behalf", "sendonbehalf"):
        if len(sys.argv) < 3:
            print("Usage: mailbox_permissions.py send-on-behalf <mailbox>")
            sys.exit(1)
        send_on_behalf(client, sys.argv[2])
    elif command == "folder":
        if len(sys.argv) < 3:
            print("Usage: mailbox_permissions.py folder <mailbox> [folder-name]")
            sys.exit(1)
        folder = sys.argv[3] if len(sys.argv) > 3 else "Inbox"
        folder_permissions(client, sys.argv[2], folder)
    elif command in ("grant-full", "grantfull"):
        if len(sys.argv) < 4:
            print("Usage: mailbox_permissions.py grant-full <mailbox> <user>")
            sys.exit(1)
        grant_full_access(client, sys.argv[2], sys.argv[3])
    elif command in ("revoke-full", "revokefull"):
        if len(sys.argv) < 4:
            print("Usage: mailbox_permissions.py revoke-full <mailbox> <user>")
            sys.exit(1)
        revoke_full_access(client, sys.argv[2], sys.argv[3])
    elif command in ("grant-sendas", "grantsendas"):
        if len(sys.argv) < 4:
            print("Usage: mailbox_permissions.py grant-sendas <mailbox> <user>")
            sys.exit(1)
        grant_send_as(client, sys.argv[2], sys.argv[3])
    elif command in ("revoke-sendas", "revokesendas"):
        if len(sys.argv) < 4:
            print("Usage: mailbox_permissions.py revoke-sendas <mailbox> <user>")
            sys.exit(1)
        revoke_send_as(client, sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {command}")
        print("Commands: check, full-access, send-as, send-on-behalf, folder, grant-full, revoke-full, grant-sendas, revoke-sendas")
        sys.exit(1)


if __name__ == "__main__":
    main()
