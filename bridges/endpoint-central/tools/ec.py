#!/usr/bin/env python3
"""Endpoint Central -- Unified CLI.

Reads EC_INSTANCE_URL, EC_AUTH_TOKEN from environment
(auto-injected by Tendril credential vault).

Usage:
    python3 ec.py <module> <action> [options]

Modules: server, inventory, patch, som
"""

import argparse
import json
import sys

from ec_client import ECClient


def out(obj):
    print(json.dumps(obj))


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def resp(data, *keys):
    """Navigate into message_response and optional sub-keys."""
    r = data.get("message_response", data)
    for k in keys:
        if isinstance(r, dict):
            r = r.get(k, r)
    return r


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def register_server(sub):
    p = sub.add_parser("server", help="Server info and properties")
    s = p.add_subparsers(dest="action", required=True)
    s.add_parser("discover")
    s.add_parser("properties")


def run_server(args, client):
    if args.action == "discover":
        data = client.discover()
        r = resp(data)
        out({"success": True, "server": r})

    elif args.action == "properties":
        data = client.server_properties()
        r = resp(data, "serverproperties")
        props = r if isinstance(r, dict) else {}
        out({"success": True, "domains": props.get("domains", []),
             "custom_groups": props.get("customgroups", []),
             "branch_offices": props.get("branchoffices", [])})


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def register_inventory(sub):
    p = sub.add_parser("inventory", help="Asset and software inventory")
    s = p.add_subparsers(dest="action", required=True)

    s.add_parser("summary")

    ls = s.add_parser("computers")
    ls.add_argument("--domain", dest="domainfilter")
    ls.add_argument("--branch-office", dest="branchofficefilter")
    ls.add_argument("--custom-group", dest="customgroupfilter")
    ls.add_argument("--limit", type=int, default=50)

    sw = s.add_parser("software")
    sw.add_argument("--search")
    sw.add_argument("--limit", type=int, default=50)

    hw = s.add_parser("hardware")
    hw.add_argument("--limit", type=int, default=50)

    cd = s.add_parser("computer-detail")
    cd.add_argument("--resource-id", required=True)

    isw = s.add_parser("installed-software")
    isw.add_argument("--resource-id", required=True)

    swc = s.add_parser("software-computers")
    swc.add_argument("--software-id", required=True)

    s.add_parser("metering")

    mu = s.add_parser("metering-usage")
    mu.add_argument("--rule-id", required=True)

    s.add_parser("licenses")

    sl = s.add_parser("software-licenses")
    sl.add_argument("--software-id", required=True)

    s.add_parser("scan-status")
    s.add_parser("scan-all")

    sc = s.add_parser("scan")
    sc.add_argument("--resource-ids", required=True, help="Comma-separated resource IDs")


def run_inventory(args, client):
    if args.action == "summary":
        data = client.inventory_summary()
        out({"success": True, "summary": resp(data)})

    elif args.action == "computers":
        filters = {}
        if args.domainfilter:
            filters["domainfilter"] = args.domainfilter
        if args.branchofficefilter:
            filters["branchofficefilter"] = args.branchofficefilter
        if args.customgroupfilter:
            filters["customgroupfilter"] = args.customgroupfilter
        filters["pagelimit"] = args.limit
        data = client.inventory_computers(**filters)
        r = resp(data)
        computers = r.get("computers", [])
        total = r.get("total", len(computers))
        result = []
        for c in computers:
            result.append({
                "resource_id": c.get("resource_id"),
                "name": c.get("resource_name", c.get("full_name")),
                "fqdn": c.get("fqdn_name"),
                "domain": c.get("domain_netbios_name"),
                "os": c.get("os_name", c.get("service_pack")),
                "ip": c.get("ip_address"),
                "mac": c.get("mac_address"),
                "agent_version": c.get("agent_version"),
                "live_status": c.get("computer_live_status"),
                "branch_office": c.get("branch_office_name"),
            })
        out({"success": True, "total": total, "count": len(result), "computers": result})

    elif args.action == "software":
        if args.search:
            items = client.search(
                "inventory/software", "software_name", "software_name", args.search, limit=args.limit
            )
            out({"success": True, "count": len(items), "software": items})
        else:
            data = client.inventory_software(pagelimit=args.limit)
            r = resp(data)
            sw = r.get("software", [])
            out({"success": True, "total": r.get("total", len(sw)), "count": len(sw), "software": sw})

    elif args.action == "hardware":
        data = client.inventory_hardware(pagelimit=args.limit)
        r = resp(data)
        hw = r.get("hardware", [])
        out({"success": True, "total": r.get("total", len(hw)), "count": len(hw), "hardware": hw})

    elif args.action == "computer-detail":
        data = client.computer_detail(args.resource_id)
        out({"success": True, "detail": resp(data)})

    elif args.action == "installed-software":
        data = client.installed_software(args.resource_id)
        r = resp(data)
        sw = r.get("installedsoftware", r.get("installed_software", []))
        if isinstance(sw, list):
            out({"success": True, "count": len(sw), "software": sw})
        else:
            out({"success": True, "software": r})

    elif args.action == "software-computers":
        data = client.software_computers(args.software_id)
        r = resp(data)
        comps = r.get("computers", [])
        out({"success": True, "count": len(comps), "computers": comps})

    elif args.action == "metering":
        data = client.metering_rules()
        r = resp(data)
        rules = r.get("swmeteringsummary", [])
        out({"success": True, "count": len(rules), "rules": rules})

    elif args.action == "metering-usage":
        data = client.metering_usage(args.rule_id)
        r = resp(data)
        out({"success": True, "usage": r})

    elif args.action == "licenses":
        data = client.licensed_software()
        r = resp(data)
        sw = r.get("licensesoftware", [])
        out({"success": True, "count": len(sw), "software": sw})

    elif args.action == "software-licenses":
        data = client.software_licenses(args.software_id)
        r = resp(data)
        lics = r.get("licenses", [])
        out({"success": True, "count": len(lics), "licenses": lics})

    elif args.action == "scan-status":
        data = client.scan_computers()
        r = resp(data)
        out({"success": True, "scan_status": r})

    elif args.action == "scan-all":
        data = client.trigger_scan_all()
        out({"success": True, "result": resp(data)})

    elif args.action == "scan":
        ids = [int(x.strip()) for x in args.resource_ids.split(",")]
        data = client.trigger_scan(ids)
        out({"success": True, "result": resp(data)})


# ---------------------------------------------------------------------------
# Patch Management
# ---------------------------------------------------------------------------

def register_patch(sub):
    p = sub.add_parser("patch", help="Patch management")
    s = p.add_subparsers(dest="action", required=True)

    pd = s.add_parser("details")
    pd.add_argument("--patch-id", required=True, type=int)
    pd.add_argument("--domain", dest="domainfilter")
    pd.add_argument("--severity", dest="severityfilter", type=int,
                     help="0=Unrated, 1=Low, 2=Moderate, 3=Important, 4=Critical")
    pd.add_argument("--status", dest="patchstatusfilter", type=int,
                     help="201=Installed, 202=Missing, 206=Failed")

    sy = s.add_parser("systems")
    sy.add_argument("--domain", dest="domainfilter")
    sy.add_argument("--branch-office", dest="branchofficefilter")
    sy.add_argument("--limit", type=int, default=50)

    ss = s.add_parser("scan-status")
    ss.add_argument("--domain", dest="domainfilter")
    ss.add_argument("--limit", type=int, default=50)

    ap = s.add_parser("approve")
    ap.add_argument("--patch-ids", required=True, help="Comma-separated patch IDs")

    dc = s.add_parser("decline")
    dc.add_argument("--patch-ids", required=True, help="Comma-separated patch IDs")

    s.add_parser("scan")


def run_patch(args, client):
    if args.action == "details":
        filters = {}
        if args.domainfilter:
            filters["domainfilter"] = args.domainfilter
        if args.severityfilter is not None:
            filters["severityfilter"] = args.severityfilter
        if args.patchstatusfilter is not None:
            filters["patchstatusfilter"] = args.patchstatusfilter
        data = client.patch_alldetails(args.patch_id, **filters)
        r = resp(data)
        details = r.get("allpatchdetails", [])
        out({"success": True, "patch_id": args.patch_id, "total": r.get("total", len(details)),
             "count": len(details), "details": details})

    elif args.action == "systems":
        filters = {"pagelimit": args.limit}
        if args.domainfilter:
            filters["domainfilter"] = args.domainfilter
        if args.branchofficefilter:
            filters["branchofficefilter"] = args.branchofficefilter
        data = client.patch_systems(**filters)
        r = resp(data)
        systems = r.get("allsystems", r.get("systems", []))
        out({"success": True, "total": r.get("total", len(systems)),
             "count": len(systems), "systems": systems})

    elif args.action == "scan-status":
        filters = {"pagelimit": args.limit}
        if args.domainfilter:
            filters["domainfilter"] = args.domainfilter
        data = client.patch_scan_status(**filters)
        r = resp(data)
        out({"success": True, "scan_status": r})

    elif args.action == "approve":
        ids = [int(x.strip()) for x in args.patch_ids.split(",")]
        data = client.patch_approve(ids)
        out({"success": True, "result": resp(data), "patch_ids": ids})

    elif args.action == "decline":
        ids = [int(x.strip()) for x in args.patch_ids.split(",")]
        data = client.patch_decline(ids)
        out({"success": True, "result": resp(data), "patch_ids": ids})

    elif args.action == "scan":
        data = client.patch_scan()
        out({"success": True, "result": resp(data)})


# ---------------------------------------------------------------------------
# SoM (Scope of Management)
# ---------------------------------------------------------------------------

def register_som(sub):
    p = sub.add_parser("som", help="Scope of Management -- agents and offices")
    s = p.add_subparsers(dest="action", required=True)

    c = s.add_parser("computers")
    c.add_argument("--domain", dest="domainfilter")
    c.add_argument("--limit", type=int, default=50)

    s.add_parser("remote-offices")

    ia = s.add_parser("install-agent")
    ia.add_argument("--resource-ids", required=True, help="Comma-separated resource IDs")

    ua = s.add_parser("uninstall-agent")
    ua.add_argument("--resource-ids", required=True, help="Comma-separated resource IDs")


def run_som(args, client):
    if args.action == "computers":
        filters = {"pagelimit": args.limit}
        if args.domainfilter:
            filters["domainfilter"] = args.domainfilter
        data = client.som_computers(**filters)
        r = resp(data)
        comps = r.get("computers", [])
        out({"success": True, "total": r.get("total", len(comps)),
             "count": len(comps), "computers": comps})

    elif args.action == "remote-offices":
        data = client.som_remote_offices()
        r = resp(data)
        offices = r.get("remoteoffice", r.get("remote_offices", []))
        if isinstance(offices, list):
            out({"success": True, "count": len(offices), "offices": offices})
        else:
            out({"success": True, "offices": r})

    elif args.action == "install-agent":
        ids = [int(x.strip()) for x in args.resource_ids.split(",")]
        data = client.som_install_agent(ids)
        out({"success": True, "result": resp(data), "resource_ids": ids})

    elif args.action == "uninstall-agent":
        ids = [int(x.strip()) for x in args.resource_ids.split(",")]
        data = client.som_uninstall_agent(ids)
        out({"success": True, "result": resp(data), "resource_ids": ids})


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

MODULES = {
    "server": (register_server, run_server),
    "inventory": (register_inventory, run_inventory),
    "patch": (register_patch, run_patch),
    "som": (register_som, run_som),
}


def main():
    parser = argparse.ArgumentParser(description="Endpoint Central CLI", prog="ec.py")
    sub = parser.add_subparsers(dest="module", required=True, help="EC module")

    for register_fn, _ in MODULES.values():
        register_fn(sub)

    args = parser.parse_args()
    client = ECClient()
    _, run_fn = MODULES[args.module]
    run_fn(args, client)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
