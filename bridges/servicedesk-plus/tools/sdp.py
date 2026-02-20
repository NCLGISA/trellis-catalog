#!/usr/bin/env python3
"""ServiceDesk Plus Cloud — Unified CLI.

Reads SDP_CLIENT_ID, SDP_CLIENT_SECRET, SDP_REFRESH_TOKEN from environment
(auto-injected by Tendril credential vault).

Usage:
    python3 sdp.py <module> <action> [options]

Modules: changes, requests, problems, solutions, assets, cmdb, announcements
"""

import argparse
import json
import os
import sys
import urllib.parse

import requests as http

SDP = os.environ.get("SDP_INSTANCE_URL", "")
if not SDP:
    die("SDP_INSTANCE_URL not set. Configure it to your SDP Cloud URL, e.g. https://yourorg.sdpondemand.manageengine.com")
ZOHO = "https://accounts.zoho.com"


# ---------------------------------------------------------------------------
# Shared auth & API helpers
# ---------------------------------------------------------------------------

def get_token():
    cid = os.environ.get("SDP_CLIENT_ID", "")
    secret = os.environ.get("SDP_CLIENT_SECRET", "")
    refresh = os.environ.get("SDP_REFRESH_TOKEN", "")
    if not all([cid, secret, refresh]):
        die("Missing SDP credentials. Configure bridge_credentials for servicedesk-plus.")
    r = http.post(f"{ZOHO}/oauth/v2/token", data={
        "refresh_token": refresh, "grant_type": "refresh_token",
        "client_id": cid, "client_secret": secret,
    })
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        die("No access_token in Zoho response")
    return token


def hdrs(token):
    return {"Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/vnd.manageengine.sdp.v3+json"}


def api_get(path, token, params=None):
    url = f"{SDP}/api/v3/{path}"
    if params:
        url += "?input_data=" + urllib.parse.quote(json.dumps(params))
    r = http.get(url, headers=hdrs(token))
    r.raise_for_status()
    return r.json()


def api_post(path, token, data):
    r = http.post(f"{SDP}/api/v3/{path}", headers=hdrs(token),
                  data={"input_data": json.dumps(data)})
    r.raise_for_status()
    return r.json()


def api_put(path, token, data):
    r = http.put(f"{SDP}/api/v3/{path}", headers=hdrs(token),
                 data={"input_data": json.dumps(data)})
    r.raise_for_status()
    return r.json()


def api_delete(path, token):
    r = http.delete(f"{SDP}/api/v3/{path}", headers=hdrs(token))
    r.raise_for_status()
    return r.json()


def out(obj):
    print(json.dumps(obj))


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def safe(d, *keys):
    """Safely navigate nested dicts, returning None on missing keys."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def list_params(limit, sort_field="created_time", status=None, search_field="status.name"):
    p = {"list_info": {"row_count": limit, "sort_field": sort_field, "sort_order": "desc"}}
    if status:
        p["list_info"]["search_criteria"] = {"field": search_field, "condition": "is", "value": status}
    return p


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

def change_url(cid):
    return f"{SDP}/app/itdesk/changes/ChangeDetails.do?CHANGEID={cid}"


def register_changes(sub):
    p = sub.add_parser("changes", help="Change request management")
    s = p.add_subparsers(dest="action", required=True)

    c = s.add_parser("create")
    c.add_argument("--title", required=True)
    c.add_argument("--description", required=True)
    c.add_argument("--change-type", default="Standard")
    c.add_argument("--risk", default="Medium")
    c.add_argument("--impact", default="3 - Low")
    c.add_argument("--urgency", default="3 - Low")
    c.add_argument("--priority", default="5 - Standard")
    c.add_argument("--roll-out-plan")
    c.add_argument("--back-out-plan")

    g = s.add_parser("get")
    g.add_argument("--change-id", required=True)

    u = s.add_parser("update")
    u.add_argument("--change-id", required=True)
    u.add_argument("--description")
    u.add_argument("--stage")
    u.add_argument("--status")

    cl = s.add_parser("close")
    cl.add_argument("--change-id", required=True)
    cl.add_argument("--description")

    ls = s.add_parser("list")
    ls.add_argument("--status")
    ls.add_argument("--limit", type=int, default=20)

    an = s.add_parser("add-note")
    an.add_argument("--change-id", required=True)
    an.add_argument("--text", required=True)
    an.add_argument("--public", action="store_true")


def run_changes(args, token):
    if args.action == "create":
        change = {"title": args.title, "description": args.description,
                  "change_type": {"name": args.change_type}, "risk": {"name": args.risk},
                  "impact": {"name": args.impact}, "urgency": {"name": args.urgency},
                  "priority": {"name": args.priority}}
        if args.roll_out_plan:
            change["roll_out_plan"] = {"roll_out_plan_description": args.roll_out_plan}
        if args.back_out_plan:
            change["back_out_plan"] = {"back_out_plan_description": args.back_out_plan}
        c = api_post("changes", token, {"change": change})["change"]
        out({"success": True, "change_id": str(c["id"]), "title": c["title"],
             "status": safe(c, "status", "name"), "url": change_url(c["id"])})

    elif args.action == "get":
        c = api_get(f"changes/{args.change_id}", token)["change"]
        out({"success": True, "change_id": str(c["id"]), "title": c["title"],
             "status": safe(c, "status", "name"), "stage": safe(c, "stage", "name"),
             "change_type": safe(c, "change_type", "name"), "risk": safe(c, "risk", "name"),
             "priority": safe(c, "priority", "name"),
             "created_time": safe(c, "created_time", "display_value"),
             "url": change_url(c["id"])})

    elif args.action == "update":
        change = {}
        if args.description: change["description"] = args.description
        if args.stage: change["stage"] = {"name": args.stage}
        if args.status: change["status"] = {"name": args.status}
        if not change: die("No update fields provided")
        c = api_put(f"changes/{args.change_id}", token, {"change": change})["change"]
        out({"success": True, "change_id": str(c["id"]), "title": c["title"],
             "status": safe(c, "status", "name"), "stage": safe(c, "stage", "name"),
             "url": change_url(c["id"])})

    elif args.action == "close":
        change = {"status": {"name": "Completed"}, "stage": {"name": "Close"}}
        if args.description: change["description"] = args.description
        c = api_put(f"changes/{args.change_id}", token, {"change": change})["change"]
        out({"success": True, "change_id": str(c["id"]), "title": c["title"],
             "status": safe(c, "status", "name"), "url": change_url(c["id"])})

    elif args.action == "list":
        data = api_get("changes", token, list_params(args.limit, status=args.status))
        changes = [{"change_id": str(c["id"]), "title": c["title"],
                     "status": safe(c, "status", "name"), "stage": safe(c, "stage", "name"),
                     "change_type": safe(c, "change_type", "name"),
                     "created": safe(c, "created_time", "display_value"),
                     "url": change_url(c["id"])} for c in data.get("changes", [])]
        out({"success": True, "count": len(changes), "changes": changes})

    elif args.action == "add-note":
        note = {"description": args.text, "show_to_requester": args.public}
        r = api_post(f"changes/{args.change_id}/notes", token, {"change_note": note})
        out({"success": True, "change_id": args.change_id,
             "note_id": str(r["change_note"]["id"]), "message": "Note added"})


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

def request_url(rid):
    return f"{SDP}/app/itdesk/WorkOrder.do?woMode=viewWO&woID={rid}"


def register_requests(sub):
    p = sub.add_parser("requests", help="Service request / ticket management")
    s = p.add_subparsers(dest="action", required=True)

    c = s.add_parser("create")
    c.add_argument("--subject", required=True)
    c.add_argument("--description", required=True)
    c.add_argument("--priority", default="5 - Standard")
    c.add_argument("--urgency", default="3 - Low")
    c.add_argument("--impact", default="3 - Low")
    c.add_argument("--category")
    c.add_argument("--subcategory")

    g = s.add_parser("get")
    g.add_argument("--request-id", required=True)

    u = s.add_parser("update")
    u.add_argument("--request-id", required=True)
    u.add_argument("--subject")
    u.add_argument("--description")
    u.add_argument("--status")
    u.add_argument("--priority")

    an = s.add_parser("add-note")
    an.add_argument("--request-id", required=True)
    an.add_argument("--text", required=True)
    an.add_argument("--public", action="store_true")

    cl = s.add_parser("close")
    cl.add_argument("--request-id", required=True)
    cl.add_argument("--close-comment")

    ls = s.add_parser("list")
    ls.add_argument("--status")
    ls.add_argument("--limit", type=int, default=20)


def run_requests(args, token):
    if args.action == "create":
        req = {"subject": args.subject, "description": args.description,
               "priority": {"name": args.priority}, "urgency": {"name": args.urgency},
               "impact": {"name": args.impact}}
        if args.category: req["category"] = {"name": args.category}
        if args.subcategory: req["subcategory"] = {"name": args.subcategory}
        r = api_post("requests", token, {"request": req})["request"]
        out({"success": True, "request_id": str(r["id"]), "subject": r["subject"],
             "status": safe(r, "status", "name"), "url": request_url(r["id"])})

    elif args.action == "get":
        r = api_get(f"requests/{args.request_id}", token)["request"]
        out({"success": True, "request_id": str(r["id"]), "subject": r["subject"],
             "status": safe(r, "status", "name"), "priority": safe(r, "priority", "name"),
             "created_time": safe(r, "created_time", "display_value"),
             "technician": safe(r, "technician", "name"), "url": request_url(r["id"])})

    elif args.action == "update":
        req = {}
        if args.subject: req["subject"] = args.subject
        if args.description: req["description"] = args.description
        if args.status: req["status"] = {"name": args.status}
        if args.priority: req["priority"] = {"name": args.priority}
        if not req: die("No update fields provided")
        r = api_put(f"requests/{args.request_id}", token, {"request": req})["request"]
        out({"success": True, "request_id": str(r["id"]), "subject": r["subject"],
             "status": safe(r, "status", "name"), "url": request_url(r["id"])})

    elif args.action == "add-note":
        note = {"description": args.text, "show_to_requester": args.public}
        r = api_post(f"requests/{args.request_id}/notes", token, {"request_note": note})
        out({"success": True, "request_id": args.request_id,
             "note_id": str(r["request_note"]["id"]), "message": "Note added"})

    elif args.action == "close":
        req = {"status": {"name": "Closed"}}
        if args.close_comment:
            req["closure_info"] = {"requester_ack_resolution": True,
                                   "closure_comments": args.close_comment}
        r = api_put(f"requests/{args.request_id}", token, {"request": req})["request"]
        out({"success": True, "request_id": str(r["id"]), "subject": r["subject"],
             "status": safe(r, "status", "name"), "url": request_url(r["id"])})

    elif args.action == "list":
        data = api_get("requests", token, list_params(args.limit, status=args.status))
        reqs = [{"request_id": str(r["id"]), "subject": r["subject"],
                 "status": safe(r, "status", "name"), "priority": safe(r, "priority", "name"),
                 "created": safe(r, "created_time", "display_value"),
                 "technician": safe(r, "technician", "name"),
                 "url": request_url(r["id"])} for r in data.get("requests", [])]
        out({"success": True, "count": len(reqs), "requests": reqs})


# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------

def problem_url(pid):
    return f"{SDP}/app/itdesk/problem/ProblemDetails.do?PROBLEMID={pid}"


def register_problems(sub):
    p = sub.add_parser("problems", help="ITIL problem management")
    s = p.add_subparsers(dest="action", required=True)

    c = s.add_parser("create")
    c.add_argument("--title", required=True)
    c.add_argument("--description", required=True)
    c.add_argument("--priority", default="5 - Standard")
    c.add_argument("--urgency", default="3 - Low")
    c.add_argument("--impact", default="3 - Low")
    c.add_argument("--status", default="Open")

    g = s.add_parser("get")
    g.add_argument("--problem-id", required=True)

    u = s.add_parser("update")
    u.add_argument("--problem-id", required=True)
    u.add_argument("--title")
    u.add_argument("--description")
    u.add_argument("--status")
    u.add_argument("--priority")
    u.add_argument("--root-cause")
    u.add_argument("--workaround")

    cl = s.add_parser("close")
    cl.add_argument("--problem-id", required=True)
    cl.add_argument("--description")

    ls = s.add_parser("list")
    ls.add_argument("--status")
    ls.add_argument("--limit", type=int, default=20)

    an = s.add_parser("add-note")
    an.add_argument("--problem-id", required=True)
    an.add_argument("--text", required=True)
    an.add_argument("--public", action="store_true")


def run_problems(args, token):
    if args.action == "create":
        prob = {"title": args.title, "description": args.description,
                "priority": {"name": args.priority}, "urgency": {"name": args.urgency},
                "impact": {"name": args.impact}, "status": {"name": args.status}}
        p = api_post("problems", token, {"problem": prob})["problem"]
        out({"success": True, "problem_id": str(p["id"]), "title": p["title"],
             "status": safe(p, "status", "name"), "url": problem_url(p["id"])})

    elif args.action == "get":
        p = api_get(f"problems/{args.problem_id}", token)["problem"]
        out({"success": True, "problem_id": str(p["id"]), "title": p["title"],
             "status": safe(p, "status", "name"), "priority": safe(p, "priority", "name"),
             "created_time": safe(p, "created_time", "display_value"),
             "root_cause": p.get("root_cause"), "workaround": p.get("workaround"),
             "url": problem_url(p["id"])})

    elif args.action == "update":
        prob = {}
        if args.title: prob["title"] = args.title
        if args.description: prob["description"] = args.description
        if args.status: prob["status"] = {"name": args.status}
        if args.priority: prob["priority"] = {"name": args.priority}
        if args.root_cause: prob["root_cause"] = args.root_cause
        if args.workaround: prob["workaround"] = args.workaround
        if not prob: die("No update fields provided")
        p = api_put(f"problems/{args.problem_id}", token, {"problem": prob})["problem"]
        out({"success": True, "problem_id": str(p["id"]), "title": p["title"],
             "status": safe(p, "status", "name"), "url": problem_url(p["id"])})

    elif args.action == "close":
        prob = {"status": {"name": "Closed"}}
        if args.description: prob["description"] = args.description
        p = api_put(f"problems/{args.problem_id}", token, {"problem": prob})["problem"]
        out({"success": True, "problem_id": str(p["id"]), "title": p["title"],
             "status": safe(p, "status", "name"), "url": problem_url(p["id"])})

    elif args.action == "list":
        data = api_get("problems", token, list_params(args.limit, status=args.status))
        probs = [{"problem_id": str(p["id"]), "title": p["title"],
                  "status": safe(p, "status", "name"), "priority": safe(p, "priority", "name"),
                  "created": safe(p, "created_time", "display_value"),
                  "url": problem_url(p["id"])} for p in data.get("problems", [])]
        out({"success": True, "count": len(probs), "problems": probs})

    elif args.action == "add-note":
        note = {"description": args.text, "show_to_requester": args.public}
        r = api_post(f"problems/{args.problem_id}/notes", token, {"problem_note": note})
        out({"success": True, "problem_id": args.problem_id,
             "note_id": str(r["problem_note"]["id"]), "message": "Note added"})


# ---------------------------------------------------------------------------
# Solutions (Knowledge Base)
# ---------------------------------------------------------------------------

def solution_url(sid):
    return f"{SDP}/app/itdesk/solution/SolutionDetails.do?SOLUTIONID={sid}"


def register_solutions(sub):
    p = sub.add_parser("solutions", help="Knowledge base articles")
    s = p.add_subparsers(dest="action", required=True)

    c = s.add_parser("create")
    c.add_argument("--title", required=True)
    c.add_argument("--description", required=True)
    c.add_argument("--topic-id")

    g = s.add_parser("get")
    g.add_argument("--solution-id", required=True)

    ls = s.add_parser("list")
    ls.add_argument("--limit", type=int, default=20)

    se = s.add_parser("search")
    se.add_argument("--query", required=True)
    se.add_argument("--limit", type=int, default=10)


def run_solutions(args, token):
    if args.action == "create":
        sol = {"title": args.title, "description": args.description}
        if args.topic_id: sol["topic"] = {"id": args.topic_id}
        s = api_post("solutions", token, {"solution": sol})["solution"]
        out({"success": True, "solution_id": str(s["id"]), "title": s["title"],
             "url": solution_url(s["id"])})

    elif args.action == "get":
        s = api_get(f"solutions/{args.solution_id}", token)["solution"]
        out({"success": True, "solution_id": str(s["id"]), "title": s["title"],
             "description": s.get("description", ""),
             "topic": safe(s, "topic", "name"),
             "created_time": safe(s, "created_time", "display_value"),
             "url": solution_url(s["id"])})

    elif args.action == "list":
        data = api_get("solutions", token, list_params(args.limit, sort_field="created_time"))
        sols = [{"solution_id": str(s["id"]), "title": s["title"],
                 "topic": safe(s, "topic", "name"),
                 "created": safe(s, "created_time", "display_value"),
                 "url": solution_url(s["id"])} for s in data.get("solutions", [])]
        out({"success": True, "count": len(sols), "solutions": sols})

    elif args.action == "search":
        params = {"list_info": {"row_count": args.limit, "search_criteria": {
            "field": "title", "condition": "like", "value": args.query}}}
        data = api_get("solutions", token, params)
        sols = [{"solution_id": str(s["id"]), "title": s["title"],
                 "topic": safe(s, "topic", "name"),
                 "url": solution_url(s["id"])} for s in data.get("solutions", [])]
        out({"success": True, "count": len(sols), "query": args.query, "solutions": sols})


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

def asset_url(aid):
    return f"{SDP}/app/itdesk/asset/AssetDetails.do?ASSETID={aid}"


def register_assets(sub):
    p = sub.add_parser("assets", help="Asset inventory management")
    s = p.add_subparsers(dest="action", required=True)

    g = s.add_parser("get")
    g.add_argument("--asset-id", required=True)

    ls = s.add_parser("list")
    ls.add_argument("--limit", type=int, default=20)

    se = s.add_parser("search")
    se.add_argument("--name", help="Search by asset name")
    se.add_argument("--serial", help="Search by serial number")
    se.add_argument("--tag", help="Search by asset tag")
    se.add_argument("--limit", type=int, default=20)


def run_assets(args, token):
    if args.action == "get":
        a = api_get(f"assets/{args.asset_id}", token)["asset"]
        out({"success": True, "asset_id": str(a["id"]), "name": a.get("name"),
             "serial_number": a.get("serial_number"), "asset_tag": a.get("asset_tag"),
             "product": safe(a, "product", "name"), "state": safe(a, "asset_state", "name"),
             "assigned_to": safe(a, "user", "name"),
             "url": asset_url(a["id"])})

    elif args.action == "list":
        data = api_get("assets", token, {"list_info": {"row_count": args.limit,
                       "sort_field": "name", "sort_order": "asc"}})
        assets = [{"asset_id": str(a["id"]), "name": a.get("name"),
                   "serial_number": a.get("serial_number"), "asset_tag": a.get("asset_tag"),
                   "state": safe(a, "asset_state", "name"),
                   "url": asset_url(a["id"])} for a in data.get("assets", [])]
        out({"success": True, "count": len(assets), "assets": assets})

    elif args.action == "search":
        criteria = []
        if args.name:
            criteria.append({"field": "name", "condition": "like", "value": args.name})
        if args.serial:
            criteria.append({"field": "serial_number", "condition": "like", "value": args.serial})
        if args.tag:
            criteria.append({"field": "asset_tag", "condition": "like", "value": args.tag})
        if not criteria: die("Provide at least one of: --name, --serial, --tag")
        search = criteria[0]
        data = api_get("assets", token, {"list_info": {"row_count": args.limit,
                       "search_criteria": search}})
        assets = [{"asset_id": str(a["id"]), "name": a.get("name"),
                   "serial_number": a.get("serial_number"), "asset_tag": a.get("asset_tag"),
                   "state": safe(a, "asset_state", "name"),
                   "url": asset_url(a["id"])} for a in data.get("assets", [])]
        out({"success": True, "count": len(assets), "query": vars(args), "assets": assets})


# ---------------------------------------------------------------------------
# CMDB (Configuration Items)
# ---------------------------------------------------------------------------

def register_cmdb(sub):
    p = sub.add_parser("cmdb", help="CMDB configuration items")
    s = p.add_subparsers(dest="action", required=True)

    g = s.add_parser("get")
    g.add_argument("--ci-id", required=True)

    ls = s.add_parser("list")
    ls.add_argument("--ci-type-id", help="Filter by CI type ID")
    ls.add_argument("--limit", type=int, default=20)

    se = s.add_parser("search")
    se.add_argument("--name", required=True)
    se.add_argument("--limit", type=int, default=20)


def run_cmdb(args, token):
    if args.action == "get":
        data = api_get(f"cmdb/{args.ci_id}", token)
        items = data.get("cmdb", [])
        if isinstance(items, list) and items:
            ci = items[0]
        elif isinstance(items, dict):
            ci = items
        else:
            die(f"CI {args.ci_id} not found")
            return
        out({"success": True, "ci_id": str(ci["id"]), "name": ci.get("name"),
             "ci_type": safe(ci, "ci_type", "name"),
             "ci_type_display": safe(ci, "ci_type", "display_name"),
             "state": safe(ci, "state", "name"),
             "description": ci.get("description")})

    elif args.action == "list":
        params = {"list_info": {"row_count": args.limit, "sort_field": "name", "sort_order": "asc"}}
        if args.ci_type_id:
            params["list_info"]["search_criteria"] = {"field": "ci_type.id", "condition": "is",
                                                       "value": args.ci_type_id}
        data = api_get("cmdb", token, params)
        cis = [{"ci_id": str(ci["id"]), "name": ci.get("name"),
                "ci_type": safe(ci, "ci_type", "name"),
                "ci_type_display": safe(ci, "ci_type", "display_name"),
                "state": safe(ci, "state", "name")} for ci in data.get("cmdb", [])]
        out({"success": True, "count": len(cis), "cmdb": cis})

    elif args.action == "search":
        params = {"list_info": {"row_count": args.limit, "search_criteria": {
            "field": "name", "condition": "like", "value": args.name}}}
        data = api_get("cmdb", token, params)
        cis = [{"ci_id": str(ci["id"]), "name": ci.get("name"),
                "ci_type": safe(ci, "ci_type", "name"),
                "ci_type_display": safe(ci, "ci_type", "display_name"),
                "state": safe(ci, "state", "name")} for ci in data.get("cmdb", [])]
        out({"success": True, "count": len(cis), "query": args.name, "cmdb": cis})


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

def register_announcements(sub):
    p = sub.add_parser("announcements", help="Service announcements")
    s = p.add_subparsers(dest="action", required=True)

    c = s.add_parser("create")
    c.add_argument("--title", required=True)
    c.add_argument("--description", required=True)

    g = s.add_parser("get")
    g.add_argument("--announcement-id", required=True)

    ls = s.add_parser("list")
    ls.add_argument("--limit", type=int, default=20)

    d = s.add_parser("delete")
    d.add_argument("--announcement-id", required=True)


def run_announcements(args, token):
    if args.action == "create":
        ann = {"title": args.title, "description": args.description}
        a = api_post("announcements", token, {"announcement": ann})["announcement"]
        out({"success": True, "announcement_id": str(a["id"]), "title": a["title"]})

    elif args.action == "get":
        a = api_get(f"announcements/{args.announcement_id}", token)["announcement"]
        out({"success": True, "announcement_id": str(a["id"]), "title": a["title"],
             "description": a.get("description"),
             "created_time": safe(a, "created_time", "display_value")})

    elif args.action == "list":
        data = api_get("announcements", token, {"list_info": {"row_count": args.limit,
                       "sort_field": "created_time", "sort_order": "desc"}})
        anns = [{"announcement_id": str(a["id"]), "title": a["title"],
                 "created": safe(a, "created_time", "display_value")
                 } for a in data.get("announcements", [])]
        out({"success": True, "count": len(anns), "announcements": anns})

    elif args.action == "delete":
        api_delete(f"announcements/{args.announcement_id}", token)
        out({"success": True, "announcement_id": args.announcement_id, "message": "Deleted"})


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

MODULES = {
    "changes": (register_changes, run_changes),
    "requests": (register_requests, run_requests),
    "problems": (register_problems, run_problems),
    "solutions": (register_solutions, run_solutions),
    "assets": (register_assets, run_assets),
    "cmdb": (register_cmdb, run_cmdb),
    "announcements": (register_announcements, run_announcements),
}


def main():
    parser = argparse.ArgumentParser(description="ServiceDesk Plus Cloud CLI",
                                     prog="sdp.py")
    sub = parser.add_subparsers(dest="module", required=True,
                                 help="SDP module")

    for register_fn, _ in MODULES.values():
        register_fn(sub)

    args = parser.parse_args()
    token = get_token()
    _, run_fn = MODULES[args.module]
    run_fn(args, token)


if __name__ == "__main__":
    try:
        main()
    except http.HTTPError as e:
        print(f"SDP API error: {e.response.status_code} {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
