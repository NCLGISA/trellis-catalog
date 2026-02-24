#!/usr/bin/env python3
"""
BeyondTrust Remote Support -- Unified CLI

Provides access to Command, Reporting, and Configuration APIs via subcommands:

  health     - Appliance health and failover status
  reps       - Logged-in representatives and status management
  teams      - Support teams and issue queues
  sessions   - Session key generation, management, and attributes
  clients    - Connected clients (reps, customers, Jumpoints)
  report     - Session reporting and license usage
  jump-items - Jump Item inventory (Shell Jump, RDP, VNC, etc.)
  users      - User and representative configuration
  jumpoints  - Jumpoint configuration
  vault      - Vault accounts and endpoints
  backup     - Software configuration backup
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from bt_client import (
    BTClient,
    BTAuthError,
    BTAPIError,
    strip_ns,
    xml_to_dict,
    print_json,
)


def get_client():
    try:
        return BTClient()
    except BTAuthError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ======================================================================
# health
# ======================================================================

def cmd_health(args):
    """Check appliance health and failover status."""
    client = get_client()
    root = client.command("check_health")
    print_json(xml_to_dict(strip_ns(root)))


def cmd_health_appliances(args):
    """List all appliances in the cluster/failover relationship."""
    client = get_client()
    root = client.command("get_appliances")
    print_json(xml_to_dict(strip_ns(root)))


def cmd_health_api_info(args):
    """Get API version and account permissions."""
    client = get_client()
    root = client.command("get_api_info")
    print_json(xml_to_dict(strip_ns(root)))


# ======================================================================
# reps
# ======================================================================

def cmd_reps_list(args):
    """List logged-in representatives."""
    client = get_client()
    root = client.command("get_logged_in_reps")
    print_json(xml_to_dict(strip_ns(root)))


def cmd_reps_status(args):
    """Set a representative's availability status."""
    client = get_client()
    params = {"user_id": args.user_id, "status": args.status}
    root = client.command_post("set_rep_status", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_reps_logout(args):
    """Log out a representative."""
    client = get_client()
    root = client.command_post("logout_rep", user_id=args.user_id)
    print_json(xml_to_dict(strip_ns(root)))


# ======================================================================
# teams
# ======================================================================

def cmd_teams_list(args):
    """List support teams and their issues."""
    client = get_client()
    root = client.command("get_support_teams")
    print_json(xml_to_dict(strip_ns(root)))


# ======================================================================
# sessions
# ======================================================================

def cmd_sessions_generate_key(args):
    """Generate a session key for starting support sessions."""
    client = get_client()
    params = {"type": "support", "queue_id": args.queue_id}
    if args.ttl:
        params["ttl"] = args.ttl
    if args.external_key:
        params["session.custom.external_key"] = args.external_key
    if args.priority:
        params["session.priority"] = args.priority
    if args.skills:
        params["session.skills"] = args.skills
    root = client.command("generate_session_key", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_sessions_set_attributes(args):
    """Set custom attributes on an active session."""
    client = get_client()
    params = {"lsid": args.lsid}
    if args.external_key:
        params["session.custom.external_key"] = args.external_key
    for kv in (args.custom or []):
        key, val = kv.split("=", 1)
        params[f"session.custom.{key}"] = val
    root = client.command_post("set_session_attributes", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_sessions_get_attributes(args):
    """Get custom attributes for an active session."""
    client = get_client()
    root = client.command("get_session_attributes", lsid=args.lsid)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_sessions_transfer(args):
    """Transfer an active session to a different queue."""
    client = get_client()
    params = {"lsid": args.lsid, "queue_id": args.queue_id}
    root = client.command_post("transfer_session", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_sessions_terminate(args):
    """Terminate an active session."""
    client = get_client()
    root = client.command_post("terminate_session", lsid=args.lsid)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_sessions_join(args):
    """Join a representative to an active session."""
    client = get_client()
    params = {"lsid": args.lsid, "user_id": args.user_id}
    root = client.command_post("join_session", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_sessions_leave(args):
    """Remove a representative from an active session."""
    client = get_client()
    params = {"lsid": args.lsid, "user_id": args.user_id}
    root = client.command_post("leave_session", **params)
    print_json(xml_to_dict(strip_ns(root)))


# ======================================================================
# clients
# ======================================================================

def cmd_clients_list(args):
    """List connected clients (summary)."""
    client = get_client()
    params = {}
    if args.type:
        params["type"] = args.type
    if args.summary:
        params["summary_only"] = "1"
    root = client.command("get_connected_client_list", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_clients_detail(args):
    """Get detailed info on connected clients."""
    client = get_client()
    params = {}
    if args.type:
        params["type"] = args.type
    if args.id:
        params["id"] = args.id
    if args.connections:
        params["include_connections"] = "1"
    root = client.command("get_connected_clients", **params)
    print_json(xml_to_dict(strip_ns(root)))


# ======================================================================
# report
# ======================================================================

def cmd_report_sessions(args):
    """Pull support session reports."""
    client = get_client()
    params = {}
    if args.start:
        params["start_date"] = args.start
    if args.end:
        params["end_date"] = args.end
    if args.duration:
        params["duration"] = args.duration
    if args.lsid:
        params["lsid"] = args.lsid
    report_type = "SupportSessionListing" if args.listing else "SupportSession"
    root = client.report(report_type, **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_report_license(args):
    """Pull license usage report."""
    client = get_client()
    params = {}
    if args.start:
        params["start_date"] = args.start
    if args.end:
        params["end_date"] = args.end
    if args.duration:
        params["duration"] = args.duration
    root = client.report("LicenseUsage", **params)
    print_json(xml_to_dict(strip_ns(root)))


def cmd_report_team(args):
    """Pull support team activity report."""
    client = get_client()
    params = {}
    if args.start:
        params["start_date"] = args.start
    if args.end:
        params["end_date"] = args.end
    if args.duration:
        params["duration"] = args.duration
    root = client.report("SupportTeam", **params)
    print_json(xml_to_dict(strip_ns(root)))


# ======================================================================
# jump-items  (Configuration API)
# ======================================================================

def cmd_jump_items_list(args):
    """List Jump Items of a given type."""
    client = get_client()
    jtype = args.type or "shell-jump"
    params = {}
    if args.name:
        params["name"] = args.name
    if args.tag:
        params["tag"] = args.tag
    if args.jumpoint_id:
        params["jumpoint_id"] = args.jumpoint_id
    if args.jump_group_id:
        params["jump_group_id"] = args.jump_group_id
    items = client.config_get_paginated(f"jump-item/{jtype}", **params)
    print_json(items)


def cmd_jump_items_get(args):
    """Get a specific Jump Item by ID."""
    client = get_client()
    jtype = args.type or "shell-jump"
    item = client.config_get(f"jump-item/{jtype}/{args.id}")
    print_json(item)


def cmd_jump_items_create(args):
    """Create a new Jump Item."""
    client = get_client()
    jtype = args.type or "shell-jump"
    data = json.loads(args.json)
    result = client.config_post(f"jump-item/{jtype}", data)
    print_json(result)


def cmd_jump_items_update(args):
    """Update an existing Jump Item."""
    client = get_client()
    jtype = args.type or "shell-jump"
    data = json.loads(args.json)
    result = client.config_patch(f"jump-item/{jtype}/{args.id}", data)
    print_json(result)


def cmd_jump_items_delete(args):
    """Delete a Jump Item."""
    client = get_client()
    jtype = args.type or "shell-jump"
    client.config_delete(f"jump-item/{jtype}/{args.id}")
    print(f"Deleted {jtype} {args.id}")


# ======================================================================
# users  (Configuration API)
# ======================================================================

def cmd_users_list(args):
    """List users/representatives."""
    client = get_client()
    items = client.config_get_paginated("user")
    print_json(items)


def cmd_users_get(args):
    """Get a specific user by ID."""
    client = get_client()
    item = client.config_get(f"user/{args.id}")
    print_json(item)


# ======================================================================
# jumpoints  (Configuration API)
# ======================================================================

def cmd_jumpoints_list(args):
    """List Jumpoints."""
    client = get_client()
    items = client.config_get_paginated("jumpoint")
    print_json(items)


def cmd_jumpoints_get(args):
    """Get a specific Jumpoint by ID."""
    client = get_client()
    item = client.config_get(f"jumpoint/{args.id}")
    print_json(item)


# ======================================================================
# jump-groups  (Configuration API)
# ======================================================================

def cmd_jump_groups_list(args):
    """List Jump Groups."""
    client = get_client()
    items = client.config_get_paginated("jump-group")
    print_json(items)


def cmd_jump_groups_get(args):
    """Get a specific Jump Group by ID."""
    client = get_client()
    item = client.config_get(f"jump-group/{args.id}")
    print_json(item)


# ======================================================================
# vault  (Configuration API)
# ======================================================================

def cmd_vault_accounts(args):
    """List Vault accounts."""
    client = get_client()
    items = client.config_get_paginated("vault/account")
    print_json(items)


def cmd_vault_endpoints(args):
    """List Vault endpoints."""
    client = get_client()
    items = client.config_get_paginated("vault/endpoint")
    print_json(items)


# ======================================================================
# group-policy  (Configuration API)
# ======================================================================

def cmd_group_policy_list(args):
    """List group policies."""
    client = get_client()
    items = client.config_get_paginated("group-policy")
    print_json(items)


def cmd_group_policy_get(args):
    """Get a specific group policy by ID."""
    client = get_client()
    item = client.config_get(f"group-policy/{args.id}")
    print_json(item)


# ======================================================================
# backup
# ======================================================================

def cmd_backup(args):
    """Download a software configuration backup."""
    client = get_client()
    client._ensure_token()
    resp = client.session.get(
        f"{client.base_url}/api/backup",
        headers=client._auth_headers(),
        timeout=120,
    )
    if resp.status_code != 200:
        print(f"Backup failed: {resp.status_code}", file=sys.stderr)
        sys.exit(1)

    outfile = args.output or "beyondtrust-backup.zip"
    with open(outfile, "wb") as f:
        f.write(resp.content)
    print(f"Backup saved to {outfile} ({len(resp.content)} bytes)")


# ======================================================================
# Argument parser
# ======================================================================

def build_parser():
    parser = argparse.ArgumentParser(
        prog="bt",
        description="BeyondTrust Remote Support CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- health --
    p_health = sub.add_parser("health", help="Appliance health")
    health_sub = p_health.add_subparsers(dest="subcommand")
    health_sub.add_parser("check", help="Check appliance health").set_defaults(func=cmd_health)
    health_sub.add_parser("appliances", help="List cluster appliances").set_defaults(func=cmd_health_appliances)
    health_sub.add_parser("api-info", help="API version and permissions").set_defaults(func=cmd_health_api_info)
    p_health.set_defaults(func=cmd_health)

    # -- reps --
    p_reps = sub.add_parser("reps", help="Representatives")
    reps_sub = p_reps.add_subparsers(dest="subcommand")
    reps_sub.add_parser("list", help="List logged-in reps").set_defaults(func=cmd_reps_list)
    p_rs = reps_sub.add_parser("set-status", help="Set rep status")
    p_rs.add_argument("--user-id", required=True, help="Representative user ID")
    p_rs.add_argument("--status", required=True, choices=["available", "busy", "do_not_disturb"],
                       help="New status")
    p_rs.set_defaults(func=cmd_reps_status)
    p_rl = reps_sub.add_parser("logout", help="Log out a rep")
    p_rl.add_argument("--user-id", required=True, help="Representative user ID")
    p_rl.set_defaults(func=cmd_reps_logout)
    p_reps.set_defaults(func=cmd_reps_list)

    # -- teams --
    p_teams = sub.add_parser("teams", help="Support teams")
    teams_sub = p_teams.add_subparsers(dest="subcommand")
    teams_sub.add_parser("list", help="List teams").set_defaults(func=cmd_teams_list)
    p_teams.set_defaults(func=cmd_teams_list)

    # -- sessions --
    p_sess = sub.add_parser("sessions", help="Session management")
    sess_sub = p_sess.add_subparsers(dest="subcommand", required=True)

    p_gk = sess_sub.add_parser("generate-key", help="Generate session key")
    p_gk.add_argument("--queue-id", required=True,
                       help="Queue: general, rep:<id>, team:<id>, rep_username:<name>, issue:<code>")
    p_gk.add_argument("--ttl", type=int, help="Key validity in seconds")
    p_gk.add_argument("--external-key", help="External ticket ID")
    p_gk.add_argument("--priority", type=int, choices=[1, 2, 3], help="1=high, 2=medium, 3=low")
    p_gk.add_argument("--skills", help="Comma-separated skill code names")
    p_gk.set_defaults(func=cmd_sessions_generate_key)

    p_sa = sess_sub.add_parser("set-attributes", help="Set session attributes")
    p_sa.add_argument("--lsid", required=True, help="Session LSID")
    p_sa.add_argument("--external-key", help="External key value")
    p_sa.add_argument("--custom", nargs="*", help="key=value pairs for custom fields")
    p_sa.set_defaults(func=cmd_sessions_set_attributes)

    p_ga = sess_sub.add_parser("get-attributes", help="Get session attributes")
    p_ga.add_argument("--lsid", required=True, help="Session LSID")
    p_ga.set_defaults(func=cmd_sessions_get_attributes)

    p_tr = sess_sub.add_parser("transfer", help="Transfer session")
    p_tr.add_argument("--lsid", required=True, help="Session LSID")
    p_tr.add_argument("--queue-id", required=True, help="Target queue")
    p_tr.set_defaults(func=cmd_sessions_transfer)

    p_te = sess_sub.add_parser("terminate", help="Terminate session")
    p_te.add_argument("--lsid", required=True, help="Session LSID")
    p_te.set_defaults(func=cmd_sessions_terminate)

    p_jo = sess_sub.add_parser("join", help="Join rep to session")
    p_jo.add_argument("--lsid", required=True, help="Session LSID")
    p_jo.add_argument("--user-id", required=True, help="Representative user ID")
    p_jo.set_defaults(func=cmd_sessions_join)

    p_le = sess_sub.add_parser("leave", help="Remove rep from session")
    p_le.add_argument("--lsid", required=True, help="Session LSID")
    p_le.add_argument("--user-id", required=True, help="Representative user ID")
    p_le.set_defaults(func=cmd_sessions_leave)

    # -- clients --
    p_clients = sub.add_parser("clients", help="Connected clients")
    clients_sub = p_clients.add_subparsers(dest="subcommand")
    p_cl = clients_sub.add_parser("list", help="List connected clients")
    p_cl.add_argument("--type", help="Filter: all, representative, support_customer, push_agent")
    p_cl.add_argument("--summary", action="store_true", help="Summary only")
    p_cl.set_defaults(func=cmd_clients_list)
    p_cd = clients_sub.add_parser("detail", help="Detailed client info")
    p_cd.add_argument("--type", help="Filter: all, representative, support_customer, push_agent")
    p_cd.add_argument("--id", help="Comma-separated client IDs (max 100)")
    p_cd.add_argument("--connections", action="store_true", help="Include connection details")
    p_cd.set_defaults(func=cmd_clients_detail)
    p_clients.set_defaults(func=cmd_clients_list)

    # -- report --
    p_report = sub.add_parser("report", help="Reporting")
    report_sub = p_report.add_subparsers(dest="subcommand", required=True)

    p_rptsess = report_sub.add_parser("sessions", help="Session report")
    p_rptsess.add_argument("--start", help="Start date (YYYY-MM-DDTHH:MM:SS)")
    p_rptsess.add_argument("--end", help="End date")
    p_rptsess.add_argument("--duration", help="Duration (e.g. P1D, PT1H)")
    p_rptsess.add_argument("--lsid", help="Specific session LSID")
    p_rptsess.add_argument("--listing", action="store_true", help="Listing format (summary)")
    p_rptsess.set_defaults(func=cmd_report_sessions)

    p_rptlic = report_sub.add_parser("license", help="License usage report")
    p_rptlic.add_argument("--start", help="Start date")
    p_rptlic.add_argument("--end", help="End date")
    p_rptlic.add_argument("--duration", help="Duration")
    p_rptlic.set_defaults(func=cmd_report_license)

    p_rptteam = report_sub.add_parser("teams", help="Team activity report")
    p_rptteam.add_argument("--start", help="Start date")
    p_rptteam.add_argument("--end", help="End date")
    p_rptteam.add_argument("--duration", help="Duration")
    p_rptteam.set_defaults(func=cmd_report_team)

    # -- jump-items --
    p_ji = sub.add_parser("jump-items", help="Jump Item management")
    ji_sub = p_ji.add_subparsers(dest="subcommand", required=True)

    p_jil = ji_sub.add_parser("list", help="List Jump Items")
    p_jil.add_argument("--type", default="shell-jump",
                        help="Jump type: shell-jump, remote-rdp, remote-vnc, local-jump, "
                             "protocol-tunnel-jump, web-jump (default: shell-jump)")
    p_jil.add_argument("--name", help="Filter by name")
    p_jil.add_argument("--tag", help="Filter by tag")
    p_jil.add_argument("--jumpoint-id", help="Filter by Jumpoint ID")
    p_jil.add_argument("--jump-group-id", help="Filter by Jump Group ID")
    p_jil.set_defaults(func=cmd_jump_items_list)

    p_jig = ji_sub.add_parser("get", help="Get Jump Item by ID")
    p_jig.add_argument("--id", required=True, help="Jump Item ID")
    p_jig.add_argument("--type", default="shell-jump", help="Jump type")
    p_jig.set_defaults(func=cmd_jump_items_get)

    p_jic = ji_sub.add_parser("create", help="Create Jump Item")
    p_jic.add_argument("--type", default="shell-jump", help="Jump type")
    p_jic.add_argument("--json", required=True, help="JSON body with Jump Item fields")
    p_jic.set_defaults(func=cmd_jump_items_create)

    p_jiu = ji_sub.add_parser("update", help="Update Jump Item")
    p_jiu.add_argument("--id", required=True, help="Jump Item ID")
    p_jiu.add_argument("--type", default="shell-jump", help="Jump type")
    p_jiu.add_argument("--json", required=True, help="JSON body with fields to update")
    p_jiu.set_defaults(func=cmd_jump_items_update)

    p_jid = ji_sub.add_parser("delete", help="Delete Jump Item")
    p_jid.add_argument("--id", required=True, help="Jump Item ID")
    p_jid.add_argument("--type", default="shell-jump", help="Jump type")
    p_jid.set_defaults(func=cmd_jump_items_delete)

    # -- users --
    p_users = sub.add_parser("users", help="User configuration")
    users_sub = p_users.add_subparsers(dest="subcommand")
    users_sub.add_parser("list", help="List users").set_defaults(func=cmd_users_list)
    p_ug = users_sub.add_parser("get", help="Get user by ID")
    p_ug.add_argument("--id", required=True, help="User ID")
    p_ug.set_defaults(func=cmd_users_get)
    p_users.set_defaults(func=cmd_users_list)

    # -- jumpoints --
    p_jp = sub.add_parser("jumpoints", help="Jumpoint configuration")
    jp_sub = p_jp.add_subparsers(dest="subcommand")
    jp_sub.add_parser("list", help="List Jumpoints").set_defaults(func=cmd_jumpoints_list)
    p_jpg = jp_sub.add_parser("get", help="Get Jumpoint by ID")
    p_jpg.add_argument("--id", required=True, help="Jumpoint ID")
    p_jpg.set_defaults(func=cmd_jumpoints_get)
    p_jp.set_defaults(func=cmd_jumpoints_list)

    # -- jump-groups --
    p_jg = sub.add_parser("jump-groups", help="Jump Group configuration")
    jg_sub = p_jg.add_subparsers(dest="subcommand")
    jg_sub.add_parser("list", help="List Jump Groups").set_defaults(func=cmd_jump_groups_list)
    p_jgg = jg_sub.add_parser("get", help="Get Jump Group by ID")
    p_jgg.add_argument("--id", required=True, help="Jump Group ID")
    p_jgg.set_defaults(func=cmd_jump_groups_get)
    p_jg.set_defaults(func=cmd_jump_groups_list)

    # -- vault --
    p_vault = sub.add_parser("vault", help="Vault management")
    vault_sub = p_vault.add_subparsers(dest="subcommand")
    vault_sub.add_parser("accounts", help="List Vault accounts").set_defaults(func=cmd_vault_accounts)
    vault_sub.add_parser("endpoints", help="List Vault endpoints").set_defaults(func=cmd_vault_endpoints)
    p_vault.set_defaults(func=cmd_vault_accounts)

    # -- group-policy --
    p_gp = sub.add_parser("group-policy", help="Group policy configuration")
    gp_sub = p_gp.add_subparsers(dest="subcommand")
    gp_sub.add_parser("list", help="List group policies").set_defaults(func=cmd_group_policy_list)
    p_gpg = gp_sub.add_parser("get", help="Get group policy by ID")
    p_gpg.add_argument("--id", required=True, help="Group Policy ID")
    p_gpg.set_defaults(func=cmd_group_policy_get)
    p_gp.set_defaults(func=cmd_group_policy_list)

    # -- backup --
    p_bk = sub.add_parser("backup", help="Download configuration backup")
    p_bk.add_argument("--output", help="Output filename (default: beyondtrust-backup.zip)")
    p_bk.set_defaults(func=cmd_backup)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except BTAPIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        if e.response_body:
            print(f"Response: {e.response_body}", file=sys.stderr)
        sys.exit(1)
    except BTAuthError as e:
        print(f"Auth Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
