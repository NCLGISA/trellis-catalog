#!/usr/bin/env python3
"""
Shared Mailbox Delegation, Distribution List Management, and Room Calendar Admin.

Usage:
    python3 mailbox_admin.py delegates <mailbox>              List delegates on a mailbox
    python3 mailbox_admin.py grant <mailbox> <delegate>       Grant calendar delegate access
    python3 mailbox_admin.py dl-list                          List distribution groups
    python3 mailbox_admin.py dl-search <query>                Search distribution groups
    python3 mailbox_admin.py dl-members <group-name-or-id>    List DL members
    python3 mailbox_admin.py dl-add <group-id> <user-email>   Add member to DL
    python3 mailbox_admin.py dl-remove <group-id> <user-id>   Remove member from DL
    python3 mailbox_admin.py rooms                            List all conference rooms
    python3 mailbox_admin.py room-calendar <room-email>       Show room calendar (next 7 days)
    python3 mailbox_admin.py shared-mailboxes                 List shared mailboxes
"""

import sys
import json

sys.path.insert(0, "/opt/bridge/data/tools")
from graph_client import GraphClient


def print_json(obj):
    print(json.dumps(obj, indent=2, default=str))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1].lower()
    client = GraphClient()

    if action == "delegates":
        if len(sys.argv) < 3:
            print("Usage: mailbox_admin.py delegates <mailbox-upn>")
            sys.exit(1)
        perms = client.list_mailbox_permissions(sys.argv[2])
        print(f"Calendar delegates for {sys.argv[2]}:")
        for p in perms:
            addr = p.get("emailAddress", {})
            name = addr.get("name", "?")
            email = addr.get("address", "?")
            role = p.get("role", "?")
            print(f"  {name:30s}  {email:40s}  role={role}")
        if not perms:
            print("  (no delegates)")

    elif action == "grant":
        if len(sys.argv) < 4:
            print("Usage: mailbox_admin.py grant <mailbox-upn> <delegate-email> [role]")
            sys.exit(1)
        mailbox = sys.argv[2]
        delegate = sys.argv[3]
        role = sys.argv[4] if len(sys.argv) > 4 else "editor"
        result = client.grant_mailbox_delegate(mailbox, delegate, role)
        print_json(result)

    elif action == "dl-list":
        groups = client.list_distribution_groups()
        print(f"Distribution groups: {len(groups)}")
        for g in groups:
            name = g.get('displayName') or '?'
            mail = g.get('mail') or ''
            print(f"  {name:40s}  {mail:40s}")

    elif action == "dl-search":
        if len(sys.argv) < 3:
            print("Usage: mailbox_admin.py dl-search <query>")
            sys.exit(1)
        groups = client.search_distribution_groups(sys.argv[2])
        print(f"Matching distribution groups: {len(groups)}")
        for g in groups:
            name = g.get('displayName') or '?'
            mail = g.get('mail') or ''
            print(f"  {name:40s}  {mail:40s}  id={g['id']}")

    elif action == "dl-members":
        if len(sys.argv) < 3:
            print("Usage: mailbox_admin.py dl-members <group-name-or-id>")
            sys.exit(1)
        group_ref = sys.argv[2]
        # If it doesn't look like a GUID, search by name first
        if "-" not in group_ref or len(group_ref) < 30:
            results = client.search_distribution_groups(group_ref)
            if not results:
                print(f"No distribution group matching '{group_ref}'")
                sys.exit(1)
            group_ref = results[0]["id"]
            print(f"Group: {results[0].get('displayName')} ({results[0].get('mail')})")

        members = client.list_distribution_group_members(group_ref)
        print(f"Members: {len(members)}")
        for m in members:
            name = m.get('displayName') or '?'
            mail = m.get('mail') or ''
            print(f"  {name:30s}  {mail:40s}  id={m['id']}")

    elif action == "dl-add":
        if len(sys.argv) < 4:
            print("Usage: mailbox_admin.py dl-add <group-id> <user-email>")
            sys.exit(1)
        user = client.get_user(sys.argv[3], select="id,displayName,mail")
        result = client.add_distribution_group_member(sys.argv[2], user["id"])
        if result.get("ok"):
            print(f"Added {user.get('displayName')} ({user.get('mail')}) to group")
        else:
            print_json(result)

    elif action == "dl-remove":
        if len(sys.argv) < 4:
            print("Usage: mailbox_admin.py dl-remove <group-id> <user-id>")
            sys.exit(1)
        result = client.remove_distribution_group_member(sys.argv[2], sys.argv[3])
        print_json(result)

    elif action == "rooms":
        try:
            rooms = client.list_rooms()
        except Exception as e:
            if "403" in str(e):
                print("Note: Place.Read.All permission may still be propagating (allow 5-15 min).")
                print("Falling back to room mailbox search via users...")
                rooms = []
            else:
                raise
        if rooms:
            print(f"Conference rooms: {len(rooms)}")
            for r in rooms:
                cap = r.get("capacity", "?")
                print(f"  {r.get('displayName', '?'):40s}  {r.get('emailAddress', ''):40s}  capacity={cap}")
        else:
            try:
                room_lists = client.list_room_lists()
                if room_lists:
                    print(f"Room lists found: {len(room_lists)}")
                    for rl in room_lists:
                        print(f"  {rl.get('displayName', '?'):40s}  {rl.get('emailAddress', '')}")
                else:
                    print("  (no rooms or room lists found -- rooms may not be configured as resources)")
            except Exception:
                print("  (rooms endpoint not yet accessible -- Place.Read.All permission may need time to propagate)")

    elif action == "room-calendar":
        if len(sys.argv) < 3:
            print("Usage: mailbox_admin.py room-calendar <room-email> [start] [end]")
            sys.exit(1)
        room = sys.argv[2]
        start = sys.argv[3] if len(sys.argv) > 3 else None
        end = sys.argv[4] if len(sys.argv) > 4 else None
        events = client.get_room_calendar(room, start=start, end=end)
        print(f"Room calendar for {room} ({len(events)} events):")
        for e in events:
            subj = e.get("subject", "(no subject)")
            organizer = e.get("organizer", {}).get("emailAddress", {}).get("name", "?")
            s = e.get("start", {}).get("dateTime", "?")[:16]
            en = e.get("end", {}).get("dateTime", "?")[:16]
            print(f"  {s} - {en}  {subj:40s}  organizer={organizer}")
        if not events:
            print("  (no events in this period)")

    elif action == "shared-mailboxes":
        shared = client.list_shared_mailboxes()
        print(f"Shared mailboxes (disabled accounts with mail): {len(shared)}")
        for s in shared:
            name = s.get('displayName') or '?'
            mail = s.get('mail') or ''
            print(f"  {name:40s}  {mail:40s}")

    else:
        print(f"Unknown action: {action}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
