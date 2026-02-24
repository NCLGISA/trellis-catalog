#!/usr/bin/env python3
"""Sophos Central -- Unified CLI.

Reads SOPHOS_CLIENT_ID, SOPHOS_CLIENT_SECRET from environment
(auto-injected by Tendril credential vault).

Usage:
    python3 sophos.py <module> <action> [options]

Modules: endpoints, alerts, directory, policies, settings, health, siem, xdr
"""

import argparse
import json
import sys

from sophos_client import SophosClient


def out(obj):
    print(json.dumps(obj))


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def register_endpoints(sub):
    p = sub.add_parser("endpoints", help="Managed endpoints")
    s = p.add_subparsers(dest="action", required=True)
    ls = s.add_parser("list")
    ls.add_argument("--limit", type=int, default=50)
    ls.add_argument("--health", help="good, suspicious, bad, unknown")
    ls.add_argument("--type", dest="etype", help="computer, server")
    ls.add_argument("--search", help="Search hostname or IP")
    ls.add_argument("--isolation", help="isolated, notIsolated")
    ls.add_argument("--group", help="Endpoint group ID")
    det = s.add_parser("detail")
    det.add_argument("--id", required=True, dest="endpoint_id")
    sc = s.add_parser("scan")
    sc.add_argument("--id", required=True, dest="endpoint_id")
    iso = s.add_parser("isolate")
    iso.add_argument("--id", required=True, dest="endpoint_id")
    iso.add_argument("--comment")
    deiso = s.add_parser("deisolate")
    deiso.add_argument("--id", required=True, dest="endpoint_id")
    deiso.add_argument("--comment")
    tp = s.add_parser("tamper")
    tp.add_argument("--id", required=True, dest="endpoint_id")
    tp.add_argument("--enable", action="store_true", default=None)
    tp.add_argument("--disable", action="store_true", default=None)
    gr = s.add_parser("groups")
    gr.add_argument("--limit", type=int, default=100)
    grm = s.add_parser("group-members")
    grm.add_argument("--group-id", required=True, dest="group_id")
    grm.add_argument("--limit", type=int, default=50)


def run_endpoints(args, client):
    if args.action == "list":
        params = {"pageSize": args.limit}
        if args.health:
            params["healthStatus"] = args.health
        if args.etype:
            params["type"] = args.etype
        if args.search:
            params["search"] = args.search
        if args.isolation:
            params["isolationStatus"] = args.isolation
        if args.group:
            params["groupId"] = args.group
        data = client.endpoints(**params)
        items = data.get("items", [])
        pages = data.get("pages", {})
        result = []
        for e in items:
            os_info = e.get("os", {})
            health = e.get("health", {})
            result.append({
                "id": e.get("id"), "hostname": e.get("hostname"), "type": e.get("type"),
                "os": f"{os_info.get('name', '')} {os_info.get('majorVersion', '')}".strip(),
                "health": health.get("overall"),
                "health_threats": health.get("threats", {}).get("status"),
                "ipv4": e.get("ipv4Addresses", []),
                "associated_person": e.get("associatedPerson", {}).get("viaLogin"),
                "group": e.get("group", {}).get("name"),
                "isolation_status": e.get("isolation", {}).get("status"),
                "tamper_enabled": e.get("lockdown", {}).get("status") == "on",
                "last_seen": e.get("lastSeenAt"),
            })
        out({"success": True, "total": pages.get("total", len(result)), "count": len(result), "endpoints": result})

    elif args.action == "detail":
        out({"success": True, "endpoint": client.endpoint(args.endpoint_id)})

    elif args.action == "scan":
        out({"success": True, "result": client.endpoint_scan(args.endpoint_id), "endpoint_id": args.endpoint_id})

    elif args.action == "isolate":
        out({"success": True, "result": client.endpoint_isolation(args.endpoint_id, True, args.comment), "action": "isolated"})

    elif args.action == "deisolate":
        out({"success": True, "result": client.endpoint_isolation(args.endpoint_id, False, args.comment), "action": "deisolated"})

    elif args.action == "tamper":
        if args.enable:
            out({"success": True, "result": client.endpoint_tamper_protection(args.endpoint_id, True), "tamper": "enabled"})
        elif args.disable:
            out({"success": True, "result": client.endpoint_tamper_protection(args.endpoint_id, False), "tamper": "disabled"})
        else:
            out({"success": True, "tamper_protection": client.endpoint_tamper_protection(args.endpoint_id)})

    elif args.action == "groups":
        data = client.endpoint_groups(pageSize=args.limit)
        items = data.get("items", [])
        result = [{"id": g.get("id"), "name": g.get("name"), "type": g.get("type"), "description": g.get("description", ""), "endpoints_total": g.get("endpoints", {}).get("total", 0)} for g in items]
        out({"success": True, "count": len(result), "groups": result})

    elif args.action == "group-members":
        data = client.endpoint_group_endpoints(args.group_id, pageSize=args.limit)
        items = data.get("items", [])
        result = [{"id": e.get("id"), "hostname": e.get("hostname"), "type": e.get("type"), "health": e.get("health", {}).get("overall"), "last_seen": e.get("lastSeenAt")} for e in items]
        out({"success": True, "count": len(result), "endpoints": result})


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def register_alerts(sub):
    p = sub.add_parser("alerts", help="Security alerts")
    s = p.add_subparsers(dest="action", required=True)
    ls = s.add_parser("list")
    ls.add_argument("--limit", type=int, default=50)
    ls.add_argument("--severity")
    ls.add_argument("--category")
    ls.add_argument("--product")
    ls.add_argument("--from", dest="from_date")
    ls.add_argument("--to", dest="to_date")
    det = s.add_parser("detail")
    det.add_argument("--id", required=True, dest="alert_id")
    ack = s.add_parser("acknowledge")
    ack.add_argument("--id", required=True, dest="alert_id")
    ack.add_argument("--message")
    clr = s.add_parser("clear")
    clr.add_argument("--ids")
    clr.add_argument("--severity")


def run_alerts(args, client):
    if args.action == "list":
        params = {"pageSize": args.limit}
        for attr, key in [("severity", "severity"), ("category", "category"), ("product", "product"), ("from_date", "from"), ("to_date", "to")]:
            v = getattr(args, attr, None)
            if v:
                params[key] = v
        data = client.alerts(**params)
        items = data.get("items", [])
        result = [{"id": a.get("id"), "severity": a.get("severity"), "category": a.get("category"), "type": a.get("type"), "description": a.get("description"), "product": a.get("product"), "endpoint_id": a.get("managedAgent", {}).get("id"), "raised_at": a.get("raisedAt"), "allowed_actions": a.get("allowedActions", [])} for a in items]
        out({"success": True, "count": len(result), "alerts": result})
    elif args.action == "detail":
        out({"success": True, "alert": client.alert(args.alert_id)})
    elif args.action == "acknowledge":
        out({"success": True, "result": client.alert_action(args.alert_id, "acknowledge", args.message)})
    elif args.action == "clear":
        if args.ids:
            out({"success": True, "result": client.alerts_action("acknowledge", alert_ids=[x.strip() for x in args.ids.split(",")])})
        elif args.severity:
            out({"success": True, "result": client.alerts_action("acknowledge", filters={"severity": args.severity})})
        else:
            die("Provide --ids or --severity.")


# ---------------------------------------------------------------------------
# Directory (Users & Groups from Azure AD sync)
# ---------------------------------------------------------------------------

def register_directory(sub):
    p = sub.add_parser("directory", help="Directory users and groups (Azure AD sync)")
    s = p.add_subparsers(dest="action", required=True)
    us = s.add_parser("users")
    us.add_argument("--limit", type=int, default=50)
    us.add_argument("--search", help="Search by name or email")
    us.add_argument("--group-id", dest="groupId")
    ud = s.add_parser("user")
    ud.add_argument("--id", required=True, dest="user_id")
    gs = s.add_parser("groups")
    gs.add_argument("--limit", type=int, default=50)
    gs.add_argument("--search", help="Search by group name")
    gd = s.add_parser("group")
    gd.add_argument("--id", required=True, dest="group_id")


def run_directory(args, client):
    if args.action == "users":
        params = {"pageSize": args.limit}
        if args.search:
            params["search"] = args.search
        if args.groupId:
            params["groupId"] = args.groupId
        data = client.directory_users(**params)
        items = data.get("items", [])
        result = [{"id": u.get("id"), "name": u.get("name"), "email": u.get("email"), "domain": u.get("domain"), "source": u.get("source", {}).get("type"), "groups_count": u.get("groups", {}).get("total", 0)} for u in items]
        out({"success": True, "count": len(result), "users": result})
    elif args.action == "user":
        out({"success": True, "user": client.directory_user(args.user_id)})
    elif args.action == "groups":
        params = {"pageSize": args.limit}
        if args.search:
            params["search"] = args.search
        data = client.directory_user_groups(**params)
        items = data.get("items", [])
        result = [{"id": g.get("id"), "name": g.get("name"), "description": g.get("description", ""), "domain": g.get("domain"), "source": g.get("source", {}).get("type"), "users_count": g.get("users", {}).get("total", 0)} for g in items]
        out({"success": True, "count": len(result), "groups": result})
    elif args.action == "group":
        out({"success": True, "group": client.directory_user_group(args.group_id)})


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

def register_policies(sub):
    p = sub.add_parser("policies", help="Endpoint policies")
    s = p.add_subparsers(dest="action", required=True)
    ls = s.add_parser("list")
    ls.add_argument("--limit", type=int, default=50)
    ls.add_argument("--type", dest="ptype", help="agent-updating, threat-protection, peripheral-control, application-control, data-loss-prevention, web-control, windows-firewall, server-threat-protection, server-peripheral-control, server-application-control, server-data-loss-prevention, server-web-control, server-windows-firewall, server-lockdown")
    det = s.add_parser("detail")
    det.add_argument("--id", required=True, dest="policy_id")


def run_policies(args, client):
    if args.action == "list":
        params = {"pageSize": args.limit}
        if args.ptype:
            params["policyType"] = args.ptype
        data = client.policies(**params)
        items = data.get("items", [])
        result = [{"id": p.get("id"), "name": p.get("name"), "type": p.get("type"), "enabled": p.get("enabled"), "priority": p.get("priority"), "locked": p.get("lockedByManagingAccount", False)} for p in items]
        out({"success": True, "count": len(result), "policies": result})
    elif args.action == "detail":
        out({"success": True, "policy": client.policy(args.policy_id)})


# ---------------------------------------------------------------------------
# Settings (allowed/blocked items, exclusions, web control)
# ---------------------------------------------------------------------------

def register_settings(sub):
    p = sub.add_parser("settings", help="Global security settings")
    s = p.add_subparsers(dest="action", required=True)

    s.add_parser("allowed-items")
    aa = s.add_parser("add-allowed")
    aa.add_argument("--type", required=True, dest="item_type", help="sha256, path, certificateSigner, process")
    aa.add_argument("--value", required=True, help="SHA256 hash, file path, or certificate signer")
    aa.add_argument("--comment")
    da = s.add_parser("delete-allowed")
    da.add_argument("--id", required=True, dest="item_id")

    s.add_parser("blocked-items")
    ab = s.add_parser("add-blocked")
    ab.add_argument("--type", required=True, dest="item_type", help="sha256, certificateSigner")
    ab.add_argument("--value", required=True, help="SHA256 hash or certificate signer")
    ab.add_argument("--comment")
    db = s.add_parser("delete-blocked")
    db.add_argument("--id", required=True, dest="item_id")

    s.add_parser("scanning-exclusions")
    ae = s.add_parser("add-exclusion")
    ae.add_argument("--type", required=True, dest="exc_type", help="path, process, web, pua, amsi, behavioral, exploitMitigation")
    ae.add_argument("--value", required=True)
    ae.add_argument("--scan-mode", default="onDemandAndOnAccess", help="onDemandAndOnAccess, onAccess, onDemand")
    ae.add_argument("--comment")
    de = s.add_parser("delete-exclusion")
    de.add_argument("--id", required=True, dest="exc_id")

    s.add_parser("exploit-mitigation")
    s.add_parser("web-control-sites")

    aw = s.add_parser("add-web-site")
    aw.add_argument("--url", required=True)
    aw.add_argument("--tags", help="Comma-separated tags")
    aw.add_argument("--comment")
    dw = s.add_parser("delete-web-site")
    dw.add_argument("--id", required=True, dest="site_id")

    s.add_parser("tamper-protection")
    s.add_parser("downloads")


def run_settings(args, client):
    if args.action == "allowed-items":
        data = client.allowed_items(pageSize=100)
        items = data.get("items", [])
        result = [{"id": i.get("id"), "type": i.get("type"), "properties": i.get("properties"), "comment": i.get("comment", ""), "created": i.get("createdAt")} for i in items]
        out({"success": True, "count": len(result), "allowed_items": result})

    elif args.action == "add-allowed":
        props = {}
        if args.item_type == "sha256":
            props["sha256"] = args.value
        elif args.item_type == "path":
            props["path"] = args.value
        elif args.item_type == "certificateSigner":
            props["certificateSigner"] = args.value
        out({"success": True, "result": client.add_allowed_item(args.item_type, props, args.comment)})

    elif args.action == "delete-allowed":
        out({"success": True, "result": client.delete_allowed_item(args.item_id)})

    elif args.action == "blocked-items":
        data = client.blocked_items(pageSize=100)
        items = data.get("items", [])
        result = [{"id": i.get("id"), "type": i.get("type"), "properties": i.get("properties"), "comment": i.get("comment", ""), "created": i.get("createdAt")} for i in items]
        out({"success": True, "count": len(result), "blocked_items": result})

    elif args.action == "add-blocked":
        props = {"sha256": args.value} if args.item_type == "sha256" else {"certificateSigner": args.value}
        out({"success": True, "result": client.add_blocked_item(args.item_type, props, args.comment)})

    elif args.action == "delete-blocked":
        out({"success": True, "result": client.delete_blocked_item(args.item_id)})

    elif args.action == "scanning-exclusions":
        data = client.scanning_exclusions(pageSize=100)
        items = data.get("items", [])
        result = [{"id": i.get("id"), "type": i.get("type"), "value": i.get("value"), "scan_mode": i.get("scanMode"), "comment": i.get("comment", "")} for i in items]
        out({"success": True, "count": len(result), "exclusions": result})

    elif args.action == "add-exclusion":
        out({"success": True, "result": client.add_scanning_exclusion(args.value, args.exc_type, args.scan_mode, args.comment)})

    elif args.action == "delete-exclusion":
        out({"success": True, "result": client.delete_scanning_exclusion(args.exc_id)})

    elif args.action == "exploit-mitigation":
        data = client.exploit_mitigation_apps(pageSize=100)
        items = data.get("items", [])
        result = [{"id": i.get("id"), "name": i.get("name"), "category": i.get("category"), "type": i.get("type"), "protected": i.get("modifications", {}).get("protected", True), "paths": i.get("paths", [])} for i in items]
        out({"success": True, "count": len(result), "applications": result})

    elif args.action == "web-control-sites":
        data = client.web_control_local_sites(pageSize=100)
        items = data.get("items", [])
        result = [{"id": i.get("id"), "url": i.get("url"), "tags": i.get("tags", []), "comment": i.get("comment", "")} for i in items]
        out({"success": True, "count": len(result), "sites": result})

    elif args.action == "add-web-site":
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        out({"success": True, "result": client.add_web_control_local_site(args.url, tags, args.comment)})

    elif args.action == "delete-web-site":
        out({"success": True, "result": client.delete_web_control_local_site(args.site_id)})

    elif args.action == "tamper-protection":
        out({"success": True, "tamper_protection": client.global_tamper_protection()})

    elif args.action == "downloads":
        data = client.installer_downloads()
        out({"success": True, "licensed_products": data.get("licensedProducts", []), "installers": data.get("installers", [])})


# ---------------------------------------------------------------------------
# Account Health
# ---------------------------------------------------------------------------

def register_health(sub):
    p = sub.add_parser("health", help="Account health check dashboard")
    s = p.add_subparsers(dest="action", required=True)
    s.add_parser("check")


def run_health(args, client):
    if args.action == "check":
        data = client.account_health_check()
        ep = data.get("endpoint", {})
        protection = ep.get("protection", {})
        tamper = ep.get("tamperProtection", {})
        out({
            "success": True,
            "protection": {
                "computers": {"score": protection.get("computer", {}).get("score"), "total": protection.get("computer", {}).get("total"), "not_protected": protection.get("computer", {}).get("notFullyProtected")},
                "servers": {"score": protection.get("server", {}).get("score"), "total": protection.get("server", {}).get("total"), "not_protected": protection.get("server", {}).get("notFullyProtected")},
            },
            "tamper_protection": {
                "global_enabled": tamper.get("global", False),
                "computers": {"score": tamper.get("computer", {}).get("score"), "total": tamper.get("computer", {}).get("total"), "disabled": tamper.get("computer", {}).get("disabled")},
                "servers": {"score": tamper.get("server", {}).get("score"), "total": tamper.get("server", {}).get("total"), "disabled": tamper.get("server", {}).get("disabled")},
            },
            "policy_compliance": ep.get("policy", {}),
            "exclusions": ep.get("exclusions", {}),
            "raw": data,
        })


# ---------------------------------------------------------------------------
# SIEM Events
# ---------------------------------------------------------------------------

def register_siem(sub):
    p = sub.add_parser("siem", help="SIEM event feed")
    s = p.add_subparsers(dest="action", required=True)
    ev = s.add_parser("events")
    ev.add_argument("--limit", type=int, default=200)
    ev.add_argument("--from", dest="from_date", help="ISO 8601 start date")
    al = s.add_parser("alerts")
    al.add_argument("--limit", type=int, default=200)
    al.add_argument("--from", dest="from_date", help="ISO 8601 start date")


def run_siem(args, client):
    if args.action == "events":
        data = client.siem_events(limit=args.limit, from_date=args.from_date)
        items = data.get("items", [])
        out({"success": True, "count": len(items), "has_more": data.get("has_more", False), "next_cursor": data.get("next_cursor"), "events": items})
    elif args.action == "alerts":
        data = client.siem_alerts(limit=args.limit, from_date=args.from_date)
        items = data.get("items", [])
        out({"success": True, "count": len(items), "has_more": data.get("has_more", False), "alerts": items})


# ---------------------------------------------------------------------------
# XDR / Data Lake
# ---------------------------------------------------------------------------

def register_xdr(sub):
    p = sub.add_parser("xdr", help="XDR Data Lake forensic queries")
    s = p.add_subparsers(dest="action", required=True)
    s.add_parser("queries")
    s.add_parser("categories")
    run = s.add_parser("run")
    run.add_argument("--sql", required=True)
    run.add_argument("--from", dest="from_date")
    run.add_argument("--to", dest="to_date")
    st = s.add_parser("status")
    st.add_argument("--run-id", required=True, dest="run_id")
    res = s.add_parser("results")
    res.add_argument("--run-id", required=True, dest="run_id")
    res.add_argument("--limit", type=int, default=100)


def run_xdr(args, client):
    if args.action == "queries":
        data = client.xdr_queries(pageSize=500)
        items = data.get("items", [])
        result = [{"id": q.get("id"), "name": q.get("name"), "description": q.get("description", ""), "category": q.get("category", {}).get("name", ""), "data_source": q.get("dataSource", "")} for q in items]
        out({"success": True, "count": len(result), "queries": result})
    elif args.action == "categories":
        data = client.xdr_query_categories()
        items = data.get("items", [])
        result = [{"id": c.get("id"), "name": c.get("name"), "code": c.get("code"), "description": c.get("description", ""), "query_count": c.get("queryCount", 0)} for c in items]
        out({"success": True, "count": len(result), "categories": result})
    elif args.action == "run":
        out({"success": True, "run": client.xdr_run(args.sql, args.from_date, args.to_date)})
    elif args.action == "status":
        out({"success": True, "run_status": client.xdr_run_status(args.run_id)})
    elif args.action == "results":
        data = client.xdr_run_results(args.run_id, args.limit)
        out({"success": True, "count": len(data.get("items", [])), "columns": data.get("columns", []), "items": data.get("items", [])})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

MODULES = {
    "endpoints": (register_endpoints, run_endpoints),
    "alerts": (register_alerts, run_alerts),
    "directory": (register_directory, run_directory),
    "policies": (register_policies, run_policies),
    "settings": (register_settings, run_settings),
    "health": (register_health, run_health),
    "siem": (register_siem, run_siem),
    "xdr": (register_xdr, run_xdr),
}


def main():
    parser = argparse.ArgumentParser(description="Sophos Central CLI", prog="sophos.py")
    sub = parser.add_subparsers(dest="module", required=True, help="Module")
    for register_fn, _ in MODULES.values():
        register_fn(sub)
    args = parser.parse_args()
    client = SophosClient()
    _, run_fn = MODULES[args.module]
    run_fn(args, client)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
