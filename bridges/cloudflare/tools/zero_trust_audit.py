#!/usr/bin/env python3
"""
Cloudflare Zero Trust Audit

Inventories the complete Zero Trust configuration:
  - Access Applications and their policies (who can access what)
  - Service Tokens with expiry dates and last-used status
  - Identity Providers (IdP) configuration
  - Access Groups
  - Gateway rules (DNS/HTTP/Network filtering)
  - Gateway locations

Output modes:
  --json       Machine-readable JSON (default)
  --table      Human-readable table
  --section    Show only a specific section (apps, tokens, idps, groups, gateway)

Usage:
    python3 zero_trust_audit.py                     # Full audit (JSON)
    python3 zero_trust_audit.py --table              # Human-readable
    python3 zero_trust_audit.py --section apps       # Access apps only
    python3 zero_trust_audit.py --section tokens     # Service tokens only
    python3 zero_trust_audit.py --section gateway    # Gateway rules only
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudflare_client import CloudflareClient


def audit_access_apps(client: CloudflareClient) -> dict:
    """Audit all Access Applications and their policies."""
    apps = client.list_access_apps()
    app_details = []

    for app in apps:
        app_id = app.get("id", "")
        app_name = app.get("name", "unknown")
        app_type = app.get("type", "?")
        domain = app.get("domain", "")
        session_duration = app.get("session_duration", "")

        # Fetch policies for this app
        try:
            policies = client.list_access_policies(app_id)
        except Exception:
            policies = []

        policy_summaries = []
        for p in policies:
            includes = p.get("include", [])
            include_desc = []
            for inc in includes:
                if "email" in inc:
                    include_desc.append(f"email:{inc['email'].get('email', '?')}")
                elif "email_domain" in inc:
                    include_desc.append(f"domain:{inc['email_domain'].get('domain', '?')}")
                elif "everyone" in inc:
                    include_desc.append("everyone")
                elif "service_token" in inc:
                    include_desc.append("service_token")
                elif "group" in inc:
                    include_desc.append(f"group:{inc['group'].get('id', '?')[:8]}")
                elif "any_valid_service_token" in inc:
                    include_desc.append("any_service_token")
                elif "certificate" in inc:
                    include_desc.append("mtls_certificate")
                elif "ip" in inc:
                    include_desc.append(f"ip:{inc['ip'].get('ip', '?')}")
                else:
                    include_desc.append(str(list(inc.keys())))

            policy_summaries.append({
                "name": p.get("name", "?"),
                "decision": p.get("decision", "?"),
                "precedence": p.get("precedence", 0),
                "includes": include_desc,
            })

        app_details.append({
            "name": app_name,
            "id": app_id[:12],
            "type": app_type,
            "domain": domain,
            "session_duration": session_duration,
            "aud_tag": app.get("aud", "")[:12] if app.get("aud") else "",
            "auto_redirect_to_identity": app.get("auto_redirect_to_identity", False),
            "policies": policy_summaries,
            "policy_count": len(policy_summaries),
        })

    app_details.sort(key=lambda a: a["name"])
    return {
        "total_apps": len(app_details),
        "apps": app_details,
    }


def audit_service_tokens(client: CloudflareClient) -> dict:
    """Audit all Access Service Tokens with expiry analysis."""
    tokens = client.list_service_tokens()
    now = datetime.now(timezone.utc)

    token_details = []
    expiring_soon = []

    for t in tokens:
        name = t.get("name", "unknown")
        token_id = t.get("id", "")
        expires_at = t.get("expires_at", "")
        updated_at = t.get("updated_at", "")
        created_at = t.get("created_at", "")

        days_until_expiry = None
        status = "active"

        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                delta = exp_dt - now
                days_until_expiry = delta.days
                if days_until_expiry < 0:
                    status = "expired"
                elif days_until_expiry < 30:
                    status = "expiring_soon"
                    expiring_soon.append(name)
            except (ValueError, TypeError):
                pass

        token_details.append({
            "name": name,
            "id": token_id[:12],
            "status": status,
            "expires_at": expires_at or "never",
            "days_until_expiry": days_until_expiry,
            "created_at": created_at,
            "updated_at": updated_at,
        })

    token_details.sort(key=lambda t: t.get("days_until_expiry") or 99999)

    return {
        "total_tokens": len(token_details),
        "expired": sum(1 for t in token_details if t["status"] == "expired"),
        "expiring_soon": sum(1 for t in token_details if t["status"] == "expiring_soon"),
        "tokens": token_details,
    }


def audit_identity_providers(client: CloudflareClient) -> dict:
    """Audit configured identity providers."""
    idps = client.list_identity_providers()

    idp_details = []
    for idp in idps:
        idp_details.append({
            "name": idp.get("name", "unknown"),
            "id": idp.get("id", "")[:12],
            "type": idp.get("type", "?"),
        })

    return {
        "total_idps": len(idp_details),
        "idps": idp_details,
    }


def audit_access_groups(client: CloudflareClient) -> dict:
    """Audit Access Groups."""
    groups = client.list_access_groups()

    group_details = []
    for g in groups:
        includes = g.get("include", [])
        include_desc = []
        for inc in includes:
            if "email" in inc:
                include_desc.append(f"email:{inc['email'].get('email', '?')}")
            elif "email_domain" in inc:
                include_desc.append(f"domain:{inc['email_domain'].get('domain', '?')}")
            elif "everyone" in inc:
                include_desc.append("everyone")
            elif "ip" in inc:
                include_desc.append(f"ip:{inc['ip'].get('ip', '?')}")
            elif "group" in inc:
                include_desc.append(f"idp_group:{inc['group'].get('name', inc['group'].get('id', '?'))}")
            else:
                include_desc.append(str(list(inc.keys())))

        group_details.append({
            "name": g.get("name", "unknown"),
            "id": g.get("id", "")[:12],
            "includes": include_desc,
            "created_at": g.get("created_at", ""),
            "updated_at": g.get("updated_at", ""),
        })

    return {
        "total_groups": len(group_details),
        "groups": group_details,
    }


def audit_gateway(client: CloudflareClient) -> dict:
    """Audit Zero Trust Gateway rules and locations."""
    rules = client.list_gateway_rules()
    locations = client.list_gateway_locations()

    rule_details = []
    for r in rules:
        rule_details.append({
            "name": r.get("name", "unknown"),
            "action": r.get("action", "?"),
            "enabled": r.get("enabled", False),
            "filters": r.get("filters", []),
            "traffic": r.get("traffic", ""),
            "precedence": r.get("precedence", 0),
            "description": r.get("description", ""),
        })

    location_details = []
    for loc in locations:
        location_details.append({
            "name": loc.get("name", "unknown"),
            "id": loc.get("id", "")[:12],
            "networks": loc.get("networks", []),
            "client_default": loc.get("client_default", False),
        })

    return {
        "total_rules": len(rule_details),
        "enabled_rules": sum(1 for r in rule_details if r["enabled"]),
        "disabled_rules": sum(1 for r in rule_details if not r["enabled"]),
        "rules": rule_details,
        "total_locations": len(location_details),
        "locations": location_details,
    }


def format_table(report: dict) -> str:
    """Format audit report as a human-readable table."""
    lines = []
    lines.append("=" * 100)
    lines.append("Cloudflare Zero Trust Audit")
    lines.append("=" * 100)

    # Access Applications
    apps = report.get("access_apps", {})
    lines.append(f"\n{'─' * 100}")
    lines.append(f"ACCESS APPLICATIONS ({apps.get('total_apps', 0)})")
    lines.append(f"{'─' * 100}")
    for app in apps.get("apps", []):
        lines.append(f"\n  {app['name']}")
        lines.append(f"    Type: {app['type']}  |  Domain: {app['domain']}  |  Session: {app['session_duration']}")
        for p in app.get("policies", []):
            includes = ", ".join(p["includes"]) if p["includes"] else "none"
            lines.append(f"    Policy: {p['name']}  ({p['decision']})  includes=[{includes}]")

    # Service Tokens
    tokens = report.get("service_tokens", {})
    lines.append(f"\n{'─' * 100}")
    lines.append(f"SERVICE TOKENS ({tokens.get('total_tokens', 0)})")
    if tokens.get("expired"):
        lines.append(f"  !! {tokens['expired']} expired token(s)")
    if tokens.get("expiring_soon"):
        lines.append(f"  !! {tokens['expiring_soon']} token(s) expiring within 30 days")
    lines.append(f"{'─' * 100}")
    header = f"  {'Name':<35s}  {'Status':<15s}  {'Expires':<25s}  {'Days Left'}"
    lines.append(header)
    for t in tokens.get("tokens", []):
        days = str(t["days_until_expiry"]) if t["days_until_expiry"] is not None else "n/a"
        lines.append(
            f"  {t['name']:<35s}  {t['status']:<15s}  {t['expires_at']:<25s}  {days}"
        )

    # Identity Providers
    idps = report.get("identity_providers", {})
    lines.append(f"\n{'─' * 100}")
    lines.append(f"IDENTITY PROVIDERS ({idps.get('total_idps', 0)})")
    lines.append(f"{'─' * 100}")
    for idp in idps.get("idps", []):
        lines.append(f"  {idp['name']:<35s}  type={idp['type']}")

    # Access Groups
    groups = report.get("access_groups", {})
    lines.append(f"\n{'─' * 100}")
    lines.append(f"ACCESS GROUPS ({groups.get('total_groups', 0)})")
    lines.append(f"{'─' * 100}")
    for g in groups.get("groups", []):
        includes = ", ".join(g["includes"]) if g["includes"] else "none"
        lines.append(f"  {g['name']:<35s}  includes=[{includes}]")

    # Gateway
    gw = report.get("gateway", {})
    lines.append(f"\n{'─' * 100}")
    lines.append(f"GATEWAY RULES ({gw.get('total_rules', 0)} total, {gw.get('enabled_rules', 0)} enabled)")
    lines.append(f"{'─' * 100}")
    for r in gw.get("rules", []):
        status = "enabled" if r["enabled"] else "disabled"
        lines.append(f"  {r['name']:<45s}  action={r['action']:<12s}  {status}")

    if gw.get("locations"):
        lines.append(f"\n  Gateway Locations ({gw['total_locations']}):")
        for loc in gw["locations"]:
            default = " (default)" if loc["client_default"] else ""
            lines.append(f"    {loc['name']}{default}")

    lines.append("")
    return "\n".join(lines)


def main():
    output_format = "json"
    section = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--table":
            output_format = "table"
        elif args[i] == "--json":
            output_format = "json"
        elif args[i] == "--section" and i + 1 < len(args):
            i += 1
            section = args[i]
        i += 1

    client = CloudflareClient()

    report = {}

    sections_to_run = {
        "apps": ("access_apps", lambda: audit_access_apps(client)),
        "tokens": ("service_tokens", lambda: audit_service_tokens(client)),
        "idps": ("identity_providers", lambda: audit_identity_providers(client)),
        "groups": ("access_groups", lambda: audit_access_groups(client)),
        "gateway": ("gateway", lambda: audit_gateway(client)),
    }

    if section:
        if section not in sections_to_run:
            print(f"ERROR: Unknown section '{section}'", file=sys.stderr)
            print(f"Valid sections: {', '.join(sections_to_run.keys())}", file=sys.stderr)
            sys.exit(1)
        key, fn = sections_to_run[section]
        report[key] = fn()
    else:
        for key, fn in sections_to_run.values():
            try:
                report[key] = fn()
            except Exception as e:
                report[key] = {"error": str(e)}

    if output_format == "table":
        print(format_table(report))
    else:
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
