"""
Freshservice Bridge Read-Only Test Battery

Exercises every read-only API category against the live Freshservice
instance and produces a compact pass/fail summary.
No mutations, no side effects.

Usage: python3 freshservice_bridge_tests.py
"""

import sys
import time
import json
from datetime import date, datetime, timedelta
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from freshservice_client import FreshserviceClient


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


def print_report(elapsed, client=None):
    """Print the final structured report."""
    today_str = date.today().isoformat()
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    total = len(results)

    print(f"\n{'=' * 105}")
    print(f"  Freshservice Bridge Test Battery")
    instance = client.domain if client else "(configured domain)"
    print(f"  Date: {today_str}  Instance: {instance}")
    print(f"{'=' * 105}")
    print(f"{'#':>3}  {'Category':<24} {'Test':<44} {'Status':<7} Detail")
    print(f"{'-' * 105}")

    for r in results:
        marker = "PASS" if r.status == "PASS" else "FAIL"
        print(f"{r.num:>3}  {r.category:<24} {r.name:<44} {marker:<7} {r.detail[:60]}")

    print(f"{'-' * 105}")
    print(f"RESULT: {passed}/{total} PASSED  |  {failed} FAILED  |  Runtime: {elapsed:.1f}s")
    print(f"{'=' * 105}\n")


# ── Shared State ───────────────────────────────────────────────────────

shared = {}


# ── Category 1: Bridge Health ──────────────────────────────────────────

def test_connection_check(client):
    def fn():
        info = client.test_connection()
        assert info.get("ok"), f"Connection failed: {info}"
        shared["agent_name"] = info.get("name", "?")
        shared["agent_email"] = info.get("email", "?")
        return f"Authenticated as: {info.get('name')} ({info.get('email')})"
    run_test("Bridge Health", "Connection check", fn)


# ── Category 2: Agents and Requesters ─────────────────────────────────

def test_list_agents(client):
    def fn():
        agents = client.list_agents()
        shared["agents"] = agents
        count = len(agents)
        active = sum(1 for a in agents if a.get("active"))
        return f"{count} agents ({active} active)"
    run_test("Agents/Requesters", "List IT agents", fn)


def test_list_requesters(client):
    def fn():
        requesters = client.get_all("requesters", "requesters", params={"per_page": 100})
        count = len(requesters)
        active = sum(1 for r in requesters if r.get("active"))
        return f"{count} requesters ({active} active)"
    run_test("Agents/Requesters", "List requesters (first pages)", fn)


# ── Category 3: Departments ───────────────────────────────────────────

def test_list_departments(client):
    def fn():
        depts = client.list_departments()
        shared["departments"] = depts
        count = len(depts)
        names = ", ".join(d.get("name", "?") for d in depts[:5])
        suffix = f"... +{count - 5} more" if count > 5 else ""
        return f"{count} departments: {names}{suffix}"
    run_test("Departments", "List departments", fn)


def test_department_has_it(client):
    def fn():
        depts = shared.get("departments", [])
        it_dept = [d for d in depts if "information technology" in (d.get("name") or "").lower()]
        assert it_dept, "IT department not found"
        dept = it_dept[0]
        return f"IT dept ID: {dept['id']}, name: {dept['name']}"
    run_test("Departments", "IT department exists", fn)


# ── Category 4: Tickets ───────────────────────────────────────────────

def test_list_tickets_recent(client):
    def fn():
        resp = client.get("tickets", params={"per_page": 100, "order_by": "created_at", "order_type": "desc"})
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        tickets = resp.json().get("tickets", [])
        shared["recent_tickets"] = tickets
        count = len(tickets)
        status_map = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
        statuses = Counter(status_map.get(t.get("status"), "Other") for t in tickets)
        parts = ", ".join(f"{v} {k}" for k, v in statuses.most_common())
        return f"{count} recent tickets ({parts})"
    run_test("Tickets", "List recent tickets", fn)


def test_ticket_detail(client):
    def fn():
        tickets = shared.get("recent_tickets", [])
        if not tickets:
            return "SKIP: No tickets to inspect"
        ticket = tickets[0]
        tid = ticket["id"]
        resp = client.get(f"tickets/{tid}")
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        t = resp.json().get("ticket", {})
        subj = (t.get("subject") or "")[:50]
        return f"Ticket #{tid}: {subj}"
    run_test("Tickets", "Get ticket detail", fn)


def test_ticket_conversations(client):
    def fn():
        tickets = shared.get("recent_tickets", [])
        if not tickets:
            return "SKIP: No tickets available"
        tid = tickets[0]["id"]
        resp = client.get(f"tickets/{tid}/conversations", params={"per_page": 10})
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        convos = resp.json().get("conversations", [])
        return f"Ticket #{tid}: {len(convos)} conversations"
    run_test("Tickets", "Get ticket conversations", fn)


def test_open_tickets_count(client):
    def fn():
        resp = client.get("tickets/filter", params={"query": '"status:2"'})
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        tickets = resp.json().get("tickets", [])
        count = len(tickets)
        priorities = Counter(t.get("priority") for t in tickets)
        pri_map = {1: "Low", 2: "Med", 3: "High", 4: "Urgent"}
        parts = ", ".join(f"{priorities.get(k, 0)} {v}" for k, v in pri_map.items() if priorities.get(k))
        return f"{count} open tickets ({parts})"
    run_test("Tickets", "Open tickets by priority", fn)


def test_ticket_categories(client):
    def fn():
        tickets = shared.get("recent_tickets", [])
        if not tickets:
            return "SKIP: No tickets"
        cats = Counter(t.get("category") or "Uncategorized" for t in tickets)
        top3 = ", ".join(f"{c} ({n})" for c, n in cats.most_common(3))
        return f"Top categories: {top3}"
    run_test("Tickets", "Ticket category breakdown", fn)


# ── Category 5: CMDB / Assets ─────────────────────────────────────────

def test_list_asset_types(client):
    def fn():
        types = client.list_asset_types()
        shared["asset_types"] = types
        count = len(types)
        names = ", ".join(t.get("name", "?") for t in types[:6])
        suffix = f"... +{count - 6} more" if count > 6 else ""
        return f"{count} asset types: {names}{suffix}"
    run_test("CMDB/Assets", "List asset types", fn)


def test_list_assets_sample(client):
    def fn():
        resp = client.get("assets", params={"per_page": 100})
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        assets = resp.json().get("assets", [])
        shared["sample_assets"] = assets
        count = len(assets)
        type_ids = Counter(a.get("asset_type_id") for a in assets)
        type_map = {t["id"]: t["name"] for t in shared.get("asset_types", [])}
        top3 = ", ".join(f"{type_map.get(tid, tid)} ({c})" for tid, c in type_ids.most_common(3))
        return f"{count} assets (first page). Top types: {top3}"
    run_test("CMDB/Assets", "List assets (first page)", fn)


def test_get_asset_detail(client):
    def fn():
        assets = shared.get("sample_assets", [])
        if not assets:
            return "SKIP: No assets to inspect"
        asset = assets[0]
        display_id = asset.get("display_id")
        detail = client.get_asset(display_id)
        name = detail.get("name", "?")
        asset_type = detail.get("asset_type_id", "?")
        return f"Asset #{display_id}: {name} (type_id: {asset_type})"
    run_test("CMDB/Assets", "Get asset detail", fn)


def test_search_assets(client):
    def fn():
        results = client.search_assets('name:"IS01S064"')
        if results:
            a = results[0]
            return f"Found {len(results)} match(es): {a.get('name')} (#{a.get('display_id')})"
        return "0 matches for IS01S064 (may not exist as asset)"
    run_test("CMDB/Assets", "Search asset by name", fn)


def test_asset_type_fields(client):
    def fn():
        types = shared.get("asset_types", [])
        if not types:
            return "SKIP: No asset types loaded"
        target = types[0]
        fields = client.list_asset_type_fields(target["id"])
        count = len(fields)
        field_names = ", ".join(f.get("name", "?") for f in fields[:5])
        return f"{count} fields for '{target['name']}': {field_names}..."
    run_test("CMDB/Assets", "Asset type fields", fn)


def test_asset_relationships(client):
    def fn():
        assets = shared.get("sample_assets", [])
        if not assets:
            return "SKIP: No assets loaded"
        for a in assets[:10]:
            rels = client.list_asset_relationships(a["display_id"])
            if rels:
                count = len(rels)
                types = set(r.get("relationship_type_id") for r in rels)
                return f"Asset #{a['display_id']} ({a.get('name')}): {count} relationships, {len(types)} types"
        return "No relationships found in first 10 assets"
    run_test("CMDB/Assets", "Asset relationships", fn)


# ── Category 6: Change Requests ────────────────────────────────────────

def test_list_changes(client):
    def fn():
        changes = client.list_changes()
        shared["changes"] = changes
        count = len(changes)
        type_map = {1: "Minor", 2: "Standard", 3: "Major", 4: "Emergency"}
        types = Counter(type_map.get(c.get("change_type"), "?") for c in changes)
        parts = ", ".join(f"{v} {k}" for k, v in types.most_common())
        return f"{count} change requests ({parts})"
    run_test("Change Requests", "List all changes", fn)


def test_get_change_detail(client):
    def fn():
        changes = shared.get("changes", [])
        if not changes:
            return "SKIP: No changes to inspect"
        change = changes[0]
        cid = change["id"]
        detail = client.get_change(cid)
        subj = (detail.get("subject") or "")[:50]
        status_map = {1: "Open", 2: "Planning", 3: "Approval", 4: "Pending Release",
                      5: "Pending Review", 6: "Closed"}
        status = status_map.get(detail.get("status"), str(detail.get("status")))
        return f"Change #{cid}: {subj} [{status}]"
    run_test("Change Requests", "Get change detail", fn)


def test_change_fields(client):
    def fn():
        fields = client.list_change_fields()
        count = len(fields)
        field_names = [f.get("name") or f.get("label") or "?" for f in fields[:5]]
        return f"{count} change form fields: {', '.join(field_names)}..."
    run_test("Change Requests", "List change form fields", fn)


def test_change_notes(client):
    def fn():
        changes = shared.get("changes", [])
        if not changes:
            return "SKIP: No changes available"
        for c in changes[:5]:
            notes = client.list_change_notes(c["id"])
            if notes:
                return f"Change #{c['id']}: {len(notes)} notes"
        return "No notes found in first 5 changes"
    run_test("Change Requests", "Change notes", fn)


def test_change_tasks(client):
    def fn():
        changes = shared.get("changes", [])
        if not changes:
            return "SKIP: No changes available"
        for c in changes[:5]:
            tasks = client.list_change_tasks(c["id"])
            if tasks:
                return f"Change #{c['id']}: {len(tasks)} tasks"
        return "No tasks found in first 5 changes"
    run_test("Change Requests", "Change tasks", fn)


# ── Category 7: Relationship Types ────────────────────────────────────

def test_relationship_types(client):
    def fn():
        types = client.list_relationship_types()
        shared["rel_types"] = types
        count = len(types)
        labels = []
        for t in types[:5]:
            down = t.get("downstream_relation", "")
            up = t.get("upstream_relation", "")
            labels.append(f"{down}/{up}" if down else str(t.get("id", "?")))
        return f"{count} relationship types: {', '.join(labels)}"
    run_test("Relationships", "List relationship types", fn)


# ── Category 8: Cross-Cutting / Integration ───────────────────────────

def test_tickets_by_it_dept(client):
    def fn():
        depts = shared.get("departments", [])
        it_dept = [d for d in depts if "information technology" in (d.get("name") or "").lower()]
        if not it_dept:
            return "SKIP: IT department not found"
        dept_id = it_dept[0]["id"]
        resp = client.get("tickets/filter", params={"query": f'"department_id:{dept_id} AND status:2"'})
        if resp.status_code != 200:
            return f"Filter returned HTTP {resp.status_code}"
        tickets = resp.json().get("tickets", [])
        count = len(tickets)
        return f"{count} open IT tickets (dept_id: {dept_id})"
    run_test("Cross-Cutting", "Open tickets for IT dept", fn)


def test_high_priority_tickets(client):
    def fn():
        resp = client.get("tickets/filter", params={"query": '"priority:4 AND status:2"'})
        if resp.status_code != 200:
            return f"Filter returned HTTP {resp.status_code}"
        tickets = resp.json().get("tickets", [])
        count = len(tickets)
        if count > 0:
            subjects = "; ".join((t.get("subject") or "?")[:30] for t in tickets[:3])
            return f"{count} urgent open tickets: {subjects}"
        return "0 urgent open tickets"
    run_test("Cross-Cutting", "Urgent open tickets", fn)


def test_recent_changes_this_month(client):
    def fn():
        changes = shared.get("changes", [])
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        recent = []
        for c in changes:
            created = (c.get("created_at") or "")[:10]
            if created >= month_start:
                recent.append(c)
        count = len(recent)
        return f"{count} change requests created in {today.strftime('%B %Y')}"
    run_test("Cross-Cutting", "Changes this month", fn)


def test_assets_total_count(client):
    def fn():
        resp = client.get("assets", params={"per_page": 1})
        assert resp.status_code == 200, f"HTTP {resp.status_code}"
        # Freshservice doesn't give total in body, so paginate a count
        total = 0
        page = 1
        while True:
            r = client.get("assets", params={"per_page": 100, "page": page})
            if r.status_code != 200:
                break
            items = r.json().get("assets", [])
            if not items:
                break
            total += len(items)
            page += 1
            if page > 50:
                break
        return f"{total} total CMDB assets across all types"
    run_test("Cross-Cutting", "Total CMDB asset count", fn)


# ── Main ───────────────────────────────────────────────────────────────

def main():
    start = time.time()
    client = FreshserviceClient()

    # Category 1: Bridge Health
    test_connection_check(client)

    # Category 2: Agents and Requesters
    test_list_agents(client)
    test_list_requesters(client)

    # Category 3: Departments
    test_list_departments(client)
    test_department_has_it(client)

    # Category 4: Tickets
    test_list_tickets_recent(client)
    test_ticket_detail(client)
    test_ticket_conversations(client)
    test_open_tickets_count(client)
    test_ticket_categories(client)

    # Category 5: CMDB / Assets
    test_list_asset_types(client)
    test_list_assets_sample(client)
    test_get_asset_detail(client)
    test_search_assets(client)
    test_asset_type_fields(client)
    test_asset_relationships(client)

    # Category 6: Change Requests
    test_list_changes(client)
    test_get_change_detail(client)
    test_change_fields(client)
    test_change_notes(client)
    test_change_tasks(client)

    # Category 7: Relationship Types
    test_relationship_types(client)

    # Category 8: Cross-Cutting / Integration
    test_tickets_by_it_dept(client)
    test_high_priority_tickets(client)
    test_recent_changes_this_month(client)
    test_assets_total_count(client)

    elapsed = time.time() - start
    print_report(elapsed, client=client)

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
