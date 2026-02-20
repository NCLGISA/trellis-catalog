"""
Zoom Bridge Read-Only Test Battery

Exercises every read-only API category against the live Zoom tenant
and produces a compact pass/fail summary. No mutations, no side effects.

Usage: python3 zoom_bridge_tests.py
"""

import sys
import time
import json
from datetime import date, datetime
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from zoom_client import ZoomClient


# ── Test Framework ─────────────────────────────────────────────────────

class TestResult:
    def __init__(self, num, category, name, status, detail=""):
        self.num = num
        self.category = category
        self.name = name
        self.status = status
        self.detail = detail


results = []
test_counter = 0


def run_test(category, name, fn):
    """Run a single test function, catch exceptions, record result."""
    global test_counter
    test_counter += 1
    num = test_counter
    try:
        detail = fn()
        results.append(TestResult(num, category, name, "PASS", detail or ""))
    except Exception as e:
        results.append(TestResult(num, category, name, "FAIL", str(e)[:120]))


def print_report(elapsed):
    """Print the final structured report."""
    today_str = date.today().isoformat()
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)

    print(f"\n{'=' * 100}")
    print(f"  Zoom Bridge Test Battery")
    print(f"  Date: {today_str}  Tenant: example.zoom.us")
    print(f"{'=' * 100}")
    print(f"{'#':>3}  {'Category':<24} {'Test':<42} {'Status':<7} Detail")
    print(f"{'-' * 100}")

    for r in results:
        marker = "PASS" if r.status == "PASS" else "FAIL"
        print(f"{r.num:>3}  {r.category:<24} {r.name:<42} {marker:<7} {r.detail[:60]}")

    print(f"{'-' * 100}")
    print(f"RESULT: {passed}/{total} PASSED  |  {failed} FAILED  |  Runtime: {elapsed:.1f}s")
    print(f"{'=' * 100}\n")


# ── Shared State ───────────────────────────────────────────────────────
# Some tests stash values for later tests to avoid redundant API calls.

shared = {}


# ── Category 1: Bridge Health ──────────────────────────────────────────

def test_connection_check(client):
    def fn():
        info = client.test_connection()
        assert info.get("ok"), f"Connection failed: {info.get('error')}"
        shared["owner_email"] = info.get("authenticated_as", "")
        plan = info.get("plan", "?")
        auth = info.get("authenticated_as", "?")
        return f"Plan: {plan}, Auth: {auth}"
    run_test("Bridge Health", "Connection check", fn)


# ── Category 2: Account and Licensing ──────────────────────────────────

def test_account_plan(client):
    def fn():
        info = client.get_account_info()
        plan = info.get("plan_base", {}).get("type", "?")
        owner = info.get("owner_email", "?")
        vanity = info.get("vanity_url", "?")
        return f"{plan} plan, owner: {owner}"
    run_test("Account/Licensing", "Account plan info", fn)


def test_account_settings(client):
    def fn():
        s = client.get_account_settings()
        sched = s.get("schedule_meeting", {})
        waiting = "on" if sched.get("waiting_room", False) else "off"
        passcode = "on" if sched.get("require_password_for_scheduling_new_meetings", False) else "off"
        e2ee = "on" if s.get("in_meeting", {}).get("e2e_encryption", False) else "off"
        return f"Waiting room: {waiting}, Passcode req: {passcode}, E2EE: {e2ee}"
    run_test("Account/Licensing", "Account security settings", fn)


def test_user_license_breakdown(client):
    def fn():
        users = client.list_users()
        shared["all_users"] = users
        type_map = {1: "Basic", 2: "Licensed", 3: "On-Prem"}
        counts = Counter(type_map.get(u.get("type"), "Other") for u in users)
        total = len(users)
        parts = ", ".join(f"{v} {k}" for k, v in counts.most_common())
        return f"{total} total ({parts})"
    run_test("Account/Licensing", "User license breakdown", fn)


# ── Category 3: Zoom Phone Infrastructure ──────────────────────────────

def test_phone_user_count(client):
    def fn():
        users = client.phone_list_users()
        shared["phone_users"] = users
        count = len(users)
        assert count > 700, f"Expected >700 phone users, got {count}"
        depts = Counter((u.get("department") or "Unassigned") for u in users)
        top3 = ", ".join(f"{d} ({c})" for d, c in depts.most_common(3))
        return f"{count} phone users. Top depts: {top3}"
    run_test("Phone Infrastructure", "Phone user count", fn)


def test_call_queue_count(client):
    def fn():
        queues = client.phone_list_call_queues()
        shared["call_queues"] = queues
        count = len(queues)
        assert count > 80, f"Expected >80 call queues, got {count}"
        return f"{count} call queues"
    run_test("Phone Infrastructure", "Call queue count", fn)


def test_dept_building_inspections(client):
    def fn():
        dept = client.phone_department("Building Inspections")
        u_count = len(dept["users"])
        aa_count = len(dept["auto_attendants"])
        cq_count = len(dept["call_queues"])
        members = []
        for cq in dept["call_queues"]:
            members.extend(cq.get("members", []))
        return f"{u_count} users, {aa_count} AAs, {cq_count} CQs, {len(members)} queue members"
    run_test("Phone Infrastructure", "Dept: Building Inspections", fn)


def test_dept_info_tech(client):
    def fn():
        dept = client.phone_department("Information Technology")
        u_count = len(dept["users"])
        aa_count = len(dept["auto_attendants"])
        cq_count = len(dept["call_queues"])
        return f"{u_count} users, {aa_count} AAs, {cq_count} CQs"
    run_test("Phone Infrastructure", "Dept: Information Technology", fn)


def test_auto_attendant_count(client):
    def fn():
        resp = client.get("/phone/auto_receptionists", params={"page_size": 100})
        data = resp.json()
        aas = data.get("auto_receptionists", [])
        count = len(aas)
        assert count > 60, f"Expected >60 auto attendants, got {count}"
        return f"{count} auto attendants"
    run_test("Phone Infrastructure", "Auto attendant count", fn)


# ── Category 4: Call Recordings and Transcripts ────────────────────────

def test_recordings_today_total(client):
    def fn():
        today_str = date.today().isoformat()
        recs = client.phone_recordings(today_str)
        shared["today_recordings"] = recs
        count = len(recs)
        with_transcript = sum(1 for r in recs if r.get("has_transcript"))
        return f"{count} recordings today, {with_transcript} with transcripts"
    run_test("Recordings/Transcripts", "Total recordings today", fn)


def test_recordings_building_inspections(client):
    def fn():
        today_str = date.today().isoformat()
        recs = client.phone_recordings(today_str, department="Building Inspections")
        shared["bi_recordings"] = recs
        count = len(recs)
        total_dur = sum(r.get("duration", 0) for r in recs)
        return f"{count} recordings, {total_dur}s total duration"
    run_test("Recordings/Transcripts", "Recordings: Building Inspections", fn)


def test_transcript_read(client):
    def fn():
        all_recs = shared.get("today_recordings", [])
        with_transcript = [r for r in all_recs if r.get("has_transcript") and r.get("transcript_url")]
        if not with_transcript:
            return "SKIP: No transcripts available today"
        rec = with_transcript[0]
        lines = client.phone_transcript(rec["transcript_url"])
        assert len(lines) > 0, "Transcript returned 0 lines"
        speakers = set(l["speaker"] for l in lines)
        return f"{len(lines)} lines, {len(speakers)} speakers from call {rec.get('caller', '?')}"
    run_test("Recordings/Transcripts", "Transcript retrieval", fn)


# ── Category 5: Call Logs ──────────────────────────────────────────────

def test_account_call_logs(client):
    def fn():
        today_str = date.today().isoformat()
        logs = client.phone_account_call_logs(today_str, today_str)
        count = len(logs)
        inbound = sum(1 for l in logs if l.get("direction") == "inbound")
        outbound = sum(1 for l in logs if l.get("direction") == "outbound")
        return f"{count} call log entries (in: {inbound}, out: {outbound})"
    run_test("Call Logs", "Account call logs today", fn)


def test_user_call_logs(client):
    def fn():
        phone_users = shared.get("phone_users", [])
        it_users = [u for u in phone_users if "information technology" in (u.get("department") or "").lower()]
        if not it_users:
            return "SKIP: No IT phone users found"
        user = it_users[0]
        user_id = user.get("id") or user.get("email")
        today_str = date.today().isoformat()
        logs = client.phone_user_call_logs(user_id, today_str, today_str)
        return f"{len(logs)} calls for {user.get('name', '?')} today"
    run_test("Call Logs", "IT user call logs today", fn)


# ── Category 6: Meetings ──────────────────────────────────────────────

def test_dashboard_meetings_today(client):
    def fn():
        today_str = date.today().isoformat()
        meetings = client.dashboard_meetings(today_str, today_str)
        count = len(meetings)
        total_participants = sum(m.get("participants", 0) for m in meetings)
        return f"{count} meetings today, {total_participants} total participants"
    run_test("Meetings", "Dashboard meetings today", fn)


def test_scheduled_meetings(client):
    def fn():
        owner = shared.get("owner_email", "me")
        meetings = client.list_meetings(owner, "scheduled")
        count = len(meetings)
        return f"{count} scheduled meetings for {owner}"
    run_test("Meetings", "Scheduled meetings (owner)", fn)


def test_daily_usage_report(client):
    def fn():
        report = client.report_daily(2026, 2)
        dates = report.get("dates", [])
        assert len(dates) > 0, "No daily usage data returned"
        total_meetings = sum(d.get("meetings", 0) for d in dates)
        total_participants = sum(d.get("participants", 0) for d in dates)
        return f"{len(dates)} days reported, {total_meetings} meetings, {total_participants} participants this month"
    run_test("Meetings", "Daily usage report (Feb 2026)", fn)


# ── Category 7: Reports ───────────────────────────────────────────────

def test_active_hosts(client):
    def fn():
        today_str = date.today().isoformat()
        month_start = today_str[:8] + "01"
        users = client.report_users(month_start, today_str)
        sorted_users = sorted(users, key=lambda u: u.get("meetings", 0), reverse=True)
        top5 = sorted_users[:5]
        lines = "; ".join(f"{u.get('email','?').split('@')[0]}={u.get('meetings',0)}" for u in top5)
        return f"{len(users)} hosts, top 5: {lines}"
    run_test("Reports", "Most active hosts this month", fn)


def test_operation_logs(client):
    def fn():
        today_str = date.today().isoformat()
        logs = client.report_operation_logs(today_str, today_str)
        count = len(logs)
        actions = Counter(l.get("action", "?") for l in logs)
        top3 = ", ".join(f"{a} ({c})" for a, c in actions.most_common(3))
        summary = f"{count} admin actions" + (f". Top: {top3}" if top3 else "")
        return summary
    run_test("Reports", "Admin operation logs today", fn)


# ── Category 8: Groups, Rooms, Webinars ───────────────────────────────

def test_groups(client):
    def fn():
        groups = client.list_groups()
        count = len(groups)
        names = ", ".join(g.get("name", "?") for g in groups[:5])
        suffix = f"... +{count - 5} more" if count > 5 else ""
        return f"{count} groups: {names}{suffix}"
    run_test("Groups/Rooms/Webinars", "Zoom groups", fn)


def test_rooms(client):
    def fn():
        rooms = client.list_rooms()
        count = len(rooms)
        if count == 0:
            return "0 rooms (none configured)"
        names = ", ".join(r.get("name", "?") for r in rooms[:5])
        return f"{count} rooms: {names}"
    run_test("Groups/Rooms/Webinars", "Zoom Rooms", fn)


def test_webinars(client):
    def fn():
        owner = shared.get("owner_email", "me")
        webinars = client.list_webinars(owner)
        count = len(webinars)
        return f"{count} webinars for {owner}"
    run_test("Groups/Rooms/Webinars", "Webinars (owner)", fn)


# ── Main ───────────────────────────────────────────────────────────────

def main():
    start = time.time()
    client = ZoomClient()

    # Category 1: Bridge Health
    test_connection_check(client)

    # Category 2: Account and Licensing
    test_account_plan(client)
    test_account_settings(client)
    test_user_license_breakdown(client)

    # Category 3: Zoom Phone Infrastructure
    test_phone_user_count(client)
    test_call_queue_count(client)
    test_dept_building_inspections(client)
    test_dept_info_tech(client)
    test_auto_attendant_count(client)

    # Category 4: Call Recordings and Transcripts
    test_recordings_today_total(client)
    test_recordings_building_inspections(client)
    test_transcript_read(client)

    # Category 5: Call Logs
    test_account_call_logs(client)
    test_user_call_logs(client)

    # Category 6: Meetings
    test_dashboard_meetings_today(client)
    test_scheduled_meetings(client)
    test_daily_usage_report(client)

    # Category 7: Reports
    test_active_hosts(client)
    test_operation_logs(client)

    # Category 8: Groups, Rooms, Webinars
    test_groups(client)
    test_rooms(client)
    test_webinars(client)

    elapsed = time.time() - start
    print_report(elapsed)

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
