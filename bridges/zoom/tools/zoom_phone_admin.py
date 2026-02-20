#!/usr/bin/env python3
"""
Zoom Phone Admin -- Voicemail settings management and call reporting.

Usage:
    python3 zoom_phone_admin.py voicemail <user-email>              Show voicemail settings
    python3 zoom_phone_admin.py voicemail-set <user-email> <json>   Update voicemail settings
    python3 zoom_phone_admin.py call-report <from> <to>             Account-level call summary
    python3 zoom_phone_admin.py call-report <from> <to> --dept <d>  Department call summary
    python3 zoom_phone_admin.py user-report <user-email> <from> <to>  User call summary
    python3 zoom_phone_admin.py aa-list                             List auto attendants
    python3 zoom_phone_admin.py aa-detail <aa-id>                   Auto attendant detail
    python3 zoom_phone_admin.py cq-members <queue-name>            List call queue members
    python3 zoom_phone_admin.py cq-add <queue-id> <user-id>        Add member to call queue
    python3 zoom_phone_admin.py cq-remove <queue-id> <member-id>   Remove from call queue
    python3 zoom_phone_admin.py settings <user-email>               Phone user settings
"""

import sys
import json
from datetime import datetime, timedelta
from collections import Counter, defaultdict

sys.path.insert(0, "/opt/bridge/data/tools")
from zoom_client import ZoomClient


def print_json(obj):
    print(json.dumps(obj, indent=2, default=str))


def fmt_dur(seconds):
    """Format seconds as HH:MM:SS."""
    if not seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    action = sys.argv[1].lower()
    client = ZoomClient()

    if action == "voicemail":
        if len(sys.argv) < 3:
            print("Usage: zoom_phone_admin.py voicemail <user-email>")
            sys.exit(1)
        email = sys.argv[2]
        resp = client.get(f"phone/users/{email}/settings")
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            sys.exit(1)
        settings = resp.json()
        vm = settings.get("voice_mail", [])
        status = settings.get("status", "?")
        ext = settings.get("extension_number", "?")
        desk = settings.get("desk_phone", {})
        devices = desk.get("devices", [])

        print(f"Phone settings for {email}:")
        print(f"  Status:          {status}")
        print(f"  Extension:       {ext}")
        print(f"  Company number:  {settings.get('company_number', '?')}")
        print(f"  Outbound caller: {settings.get('outbound_caller', {}).get('number', '?')}")

        # Desk phones
        if devices:
            print(f"\n  Desk phones ({len(devices)}):")
            for d in devices:
                print(f"    {d.get('display_name', '?'):30s}  type={d.get('device_type', '?'):15s}  mac={d.get('mac_address', '?')}  status={d.get('status', '?')}")

        # Voicemail access
        print(f"\n  Voicemail access ({len(vm)} entries):")
        for v in vm:
            print(f"    user_id={v.get('access_user_id', '?')}  download={v.get('download')}  delete={v.get('delete')}")
        if not vm:
            print("    (no voicemail delegates)")

        # Outbound caller IDs
        caller_ids = settings.get("outbound_caller_ids", [])
        if caller_ids:
            print(f"\n  Outbound caller IDs ({len(caller_ids)}):")
            for c in caller_ids:
                default = " (default)" if c.get("is_default") else ""
                print(f"    {c.get('number', '?'):18s}  {c.get('name', '?')}{default}")

        # Delegation
        delegation = settings.get("delegation", {})
        print(f"\n  Delegation:      locked={delegation.get('locked', '?')}, privacy={delegation.get('privacy', '?')}")

    elif action == "voicemail-set":
        if len(sys.argv) < 4:
            print("Usage: zoom_phone_admin.py voicemail-set <user-email> '<json>'")
            print("Example: voicemail-set user@email.com '{\"ring_duration\": 30}'")
            sys.exit(1)
        email = sys.argv[2]
        updates = json.loads(sys.argv[3])
        body = updates
        resp = client.patch(f"phone/users/{email}/settings", json_data=body)
        if resp.status_code == 204:
            print(f"Voicemail settings updated for {email}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")

    elif action == "call-report":
        if len(sys.argv) < 4:
            print("Usage: zoom_phone_admin.py call-report <from-date> <to-date> [--dept <name>]")
            sys.exit(1)
        from_date = sys.argv[2]
        to_date = sys.argv[3]
        dept_filter = None
        if "--dept" in sys.argv:
            dept_idx = sys.argv.index("--dept")
            if dept_idx + 1 < len(sys.argv):
                dept_filter = sys.argv[dept_idx + 1]

        logs = client.phone_account_call_logs(from_date, to_date)
        if dept_filter:
            # Filter by matching department in owner or callee/caller
            phone_users = client.phone_list_users()
            dept_emails = {
                u["email"].lower()
                for u in phone_users
                if u.get("department", "").lower() == dept_filter.lower()
            }
            filtered = []
            for log in logs:
                owner_email = log.get("owner", {}).get("email", "").lower()
                if owner_email in dept_emails:
                    filtered.append(log)
            logs = filtered

        # Aggregate
        total = len(logs)
        inbound = sum(1 for l in logs if l.get("direction") == "inbound")
        outbound = sum(1 for l in logs if l.get("direction") == "outbound")
        total_duration = sum(l.get("duration", 0) for l in logs)
        missed = sum(1 for l in logs if l.get("result") == "no_answer")
        voicemail = sum(1 for l in logs if l.get("result") == "voicemail")

        dept_label = f" (dept: {dept_filter})" if dept_filter else ""
        print(f"Call Report {from_date} to {to_date}{dept_label}")
        print(f"  Total calls:      {total}")
        print(f"  Inbound:          {inbound}")
        print(f"  Outbound:         {outbound}")
        print(f"  Missed/No answer: {missed}")
        print(f"  Voicemail:        {voicemail}")
        print(f"  Total duration:   {fmt_dur(total_duration)}")
        avg_dur = total_duration / total if total else 0
        print(f"  Avg duration:     {fmt_dur(avg_dur)}")

        # Top callers/callees
        callers = Counter()
        for l in logs:
            name = l.get("caller_name") or l.get("caller_number", "Unknown")
            callers[name] += 1
        print(f"\n  Top 10 callers:")
        for name, count in callers.most_common(10):
            print(f"    {name:30s}  {count} calls")

    elif action == "user-report":
        if len(sys.argv) < 5:
            print("Usage: zoom_phone_admin.py user-report <user-email> <from> <to>")
            sys.exit(1)
        email = sys.argv[2]
        from_date = sys.argv[3]
        to_date = sys.argv[4]
        logs = client.phone_user_call_logs(email, from_date, to_date)
        total = len(logs)
        inbound = sum(1 for l in logs if l.get("direction") == "inbound")
        outbound = total - inbound
        total_dur = sum(l.get("duration", 0) for l in logs)
        missed = sum(1 for l in logs if l.get("result") == "no_answer")

        print(f"Call report for {email} ({from_date} to {to_date})")
        print(f"  Total calls:      {total}")
        print(f"  Inbound:          {inbound}")
        print(f"  Outbound:         {outbound}")
        print(f"  Missed:           {missed}")
        print(f"  Total duration:   {fmt_dur(total_dur)}")
        print(f"\n  Recent calls:")
        for l in logs[:20]:
            direction = l.get("direction", "?")[:3]
            name = l.get("caller_name") or l.get("callee_name") or "?"
            number = l.get("caller_number") or l.get("callee_number") or "?"
            dur = fmt_dur(l.get("duration", 0))
            result = l.get("result", "?")
            dt = l.get("date_time", "?")[:19]
            print(f"    {dt}  {direction}  {name:25s}  {number:15s}  {dur:>8s}  {result}")

    elif action == "aa-list":
        resp = client.get("phone/auto_receptionists")
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            sys.exit(1)
        data = resp.json()
        aas = data.get("auto_receptionists", [])
        print(f"Auto Attendants: {len(aas)}")
        for aa in aas:
            name = aa.get("name", "?")
            ext = str(aa.get("extension_number", "?"))
            status = aa.get("status", "?")
            print(f"  {name:40s}  ext={ext:6s}  status={status}  id={aa.get('id', '?')}")

    elif action == "aa-detail":
        if len(sys.argv) < 3:
            print("Usage: zoom_phone_admin.py aa-detail <auto-attendant-id>")
            sys.exit(1)
        aa_id = sys.argv[2]
        resp = client.get(f"phone/auto_receptionists/{aa_id}")
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            sys.exit(1)
        print_json(resp.json())

    elif action == "cq-members":
        if len(sys.argv) < 3:
            print("Usage: zoom_phone_admin.py cq-members <queue-name-or-id>")
            sys.exit(1)
        queue_ref = sys.argv[2]
        queues = client.phone_list_call_queues()
        target = None
        for q in queues:
            if q["id"] == queue_ref or q.get("name", "").lower() == queue_ref.lower():
                target = q
                break
        if not target:
            # Partial match
            for q in queues:
                if queue_ref.lower() in q.get("name", "").lower():
                    target = q
                    break
        if not target:
            print(f"Call queue '{queue_ref}' not found")
            sys.exit(1)

        resp = client.get(f"phone/call_queues/{target['id']}")
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            sys.exit(1)
        detail = resp.json()
        members_obj = detail.get("members", {})
        if isinstance(members_obj, dict):
            members = members_obj.get("users", [])
        elif isinstance(members_obj, list):
            members = members_obj
        else:
            members = []
        print(f"Call Queue: {detail.get('name')} (ext {detail.get('extension_number', '?')})")
        print(f"Members: {len(members)}")
        for m in members:
            if isinstance(m, dict):
                name = m.get("name", "?")
                recv = m.get("receive_call", "?")
                print(f"  {name:30s}  receive_call={recv}  id={m.get('id', '?')}")
            else:
                print(f"  {m}")

    elif action == "cq-add":
        if len(sys.argv) < 4:
            print("Usage: zoom_phone_admin.py cq-add <queue-id> <user-id>")
            sys.exit(1)
        queue_id = sys.argv[2]
        user_id = sys.argv[3]
        body = {"members": [{"id": user_id}]}
        resp = client.post(f"phone/call_queues/{queue_id}/members", json_data=body)
        if resp.status_code in (200, 201, 204):
            print(f"Added user {user_id} to call queue {queue_id}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")

    elif action == "cq-remove":
        if len(sys.argv) < 4:
            print("Usage: zoom_phone_admin.py cq-remove <queue-id> <member-id>")
            sys.exit(1)
        queue_id = sys.argv[2]
        member_id = sys.argv[3]
        resp = client.delete(f"phone/call_queues/{queue_id}/members/{member_id}")
        if resp.status_code in (200, 204):
            print(f"Removed member {member_id} from call queue {queue_id}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")

    elif action == "settings":
        if len(sys.argv) < 3:
            print("Usage: zoom_phone_admin.py settings <user-email>")
            sys.exit(1)
        email = sys.argv[2]
        resp = client.get(f"phone/users/{email}/settings")
        if resp.status_code != 200:
            print(f"Error {resp.status_code}: {resp.text}")
            sys.exit(1)
        settings = resp.json()
        print(f"Phone settings for {email}:")
        print_json(settings)

    else:
        print(f"Unknown action: {action}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
