#!/usr/bin/env python3
"""
Global Secure Access (GSA) Investigation Tool

Discover and audit user access to internal resources through Microsoft Entra
Private Access enterprise applications.  Uses a cached catalog of all Private
Access apps (identified by the IsAccessibleViaZTNAClient service principal tag)
for fast, natural-language queries.

Catalog commands (run 'refresh' first to seed the catalog):
    python3 gsa_check.py refresh                            # Rebuild catalog from live Graph data
    python3 gsa_check.py list-apps                          # Show all Private Access apps
    python3 gsa_check.py check <user> <resource>            # Quick yes/no access check
    python3 gsa_check.py audit <user-email>                 # Full GSA access audit for a user

Discovery commands:
    python3 gsa_check.py discover                           # Find GSA enterprise apps (generic + per-app)
    python3 gsa_check.py assignments <sp-id>                # List users/groups assigned to an app
    python3 gsa_check.py access-chain <sp-id>               # Expand group membership for an app
    python3 gsa_check.py ca-policies                        # CA policies targeting GSA apps

Network access commands (beta API, requires NetworkAccess.Read.All):
    python3 gsa_check.py profiles                           # Forwarding profiles
    python3 gsa_check.py app-segments                       # Private Access app segments
    python3 gsa_check.py find-resource <fqdn>               # Search app segments for an FQDN
"""

import sys
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from graph_client import GraphClient

CATALOG_PATH = Path(__file__).resolve().parent / "gsa_catalog.json"

ZTNA_TAG = "IsAccessibleViaZTNAClient"

GSA_KEYWORDS = [
    "Global Secure Access",
    "Microsoft Entra Private Access",
    "Microsoft Entra Internet Access",
    "Entra Private Access",
    "Entra Internet Access",
    "Private Access",
]


# ── Catalog helpers ───────────────────────────────────────────────────


def _generate_aliases(display_name: str) -> list:
    """Generate search aliases from an enterprise app display name.

    Examples:
        "Tyler - EERP Reports Server"  -> ["tyler", "eerp", "eerp reports", "reports server", "munis reports"]
        "CentralSquare - OneSolution CAD" -> ["centralsquare", "onesolution", "onesolution cad", "cad"]
        "Print Server - az01s084"      -> ["print server", "az01s084"]
    """
    aliases = set()
    name_lower = display_name.lower().strip()
    aliases.add(name_lower)

    # Split on " - " vendor prefix pattern
    parts = re.split(r"\s*-\s*", name_lower, maxsplit=1)
    if len(parts) == 2:
        vendor, resource = parts
        aliases.add(vendor.strip())
        aliases.add(resource.strip())
        # Individual words of resource part (if multi-word)
        resource_words = resource.strip().split()
        if len(resource_words) > 1:
            for w in resource_words:
                if len(w) > 2:
                    aliases.add(w)

    # Known synonyms
    synonym_map = {
        "eerp reports server": ["munis reports", "eerp reports", "ssrs reports", "ssrs"],
        "eerp database": ["munis database", "eerp db", "munis db"],
        "eerp": ["munis", "tyler munis"],
        "onesolution cad": ["cad", "dispatch"],
        "onesolution rms": ["rms", "records management"],
        "guard1": ["timekeeping", "guard1 plus"],
        "resolution iii": ["cott", "register of deeds", "rod"],
        "proqa": ["priority dispatch", "proqa aqua"],
        "wasteworks": ["solid waste", "waste"],
        "chameleon": ["hlp", "animal control", "animal services"],
        "arcsde": ["esri", "gis", "arcgis"],
        "compass": ["northwoods", "dss"],
        "raptor": ["raptormed", "veterinary"],
        "crossroads": ["nc crossroads"],
        "domain controllers": ["ad", "active directory", "dc"],
        "vcenter": ["vmware", "vsphere"],
        "synology": ["nas", "file share"],
        "netscaler": ["citrix", "citrix gateway", "xendesktop"],
        "umbrella": ["cisco umbrella", "dns security"],
    }
    for keyword, synonyms in synonym_map.items():
        if keyword in name_lower:
            aliases.update(synonyms)

    # Hostnames embedded in names (e.g., "az01s084")
    hostname_match = re.findall(r'\b([a-z]{2}\d{2}s\d{3})\b', name_lower)
    aliases.update(hostname_match)

    # Remove the full name from aliases (it's stored as 'name')
    aliases.discard(name_lower)
    # Remove very short aliases
    aliases = {a for a in aliases if len(a) > 1}

    return sorted(aliases)


def _load_catalog() -> dict:
    """Load the GSA app catalog from disk. Returns None if missing."""
    if not CATALOG_PATH.exists():
        return None
    try:
        with open(CATALOG_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def _save_catalog(catalog: dict):
    """Write the catalog to disk."""
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)


def _fuzzy_match_app(catalog: dict, query: str) -> list:
    """Find catalog apps matching a search query (fuzzy, case-insensitive).

    Returns list of matching app entries, best matches first.
    """
    q = query.lower().strip()
    exact = []
    partial = []

    for app in catalog.get("apps", []):
        name_lower = app["name"].lower()

        # Exact name match
        if q == name_lower:
            exact.append(app)
            continue

        # Alias exact match
        if q in app.get("aliases", []):
            exact.append(app)
            continue

        # Substring match in name
        if q in name_lower:
            partial.append(app)
            continue

        # Substring match in any alias
        if any(q in alias for alias in app.get("aliases", [])):
            partial.append(app)
            continue

        # Query word appears in name or aliases
        q_words = q.split()
        all_text = name_lower + " " + " ".join(app.get("aliases", []))
        if all(w in all_text for w in q_words):
            partial.append(app)

    return exact + partial


# ── Catalog commands ──────────────────────────────────────────────────


def refresh_catalog(client: GraphClient):
    """Rebuild the GSA app catalog from live Graph data."""
    print("Refreshing GSA Private Access app catalog...")
    print(f"  Discovering service principals tagged with '{ZTNA_TAG}'...\n")

    sps = client.list_service_principals(top=999)
    private_apps = [sp for sp in sps if ZTNA_TAG in sp.get("tags", [])]

    if not private_apps:
        print("No Private Access enterprise apps found (no IsAccessibleViaZTNAClient tags).")
        return

    print(f"  Found {len(private_apps)} Private Access apps. Resolving assignments...\n")

    apps = []
    for i, sp in enumerate(private_apps, 1):
        sp_id = sp["id"]
        name = sp.get("displayName", "?")
        print(f"  [{i:2d}/{len(private_apps)}] {name}...", end="", flush=True)

        assignments = client.list_app_role_assignments(sp_id)
        groups = [
            {"id": a["principalId"], "name": a.get("principalDisplayName", "")}
            for a in assignments
            if a.get("principalType", "").lower() == "group"
        ]
        direct_users = [
            {"id": a["principalId"], "name": a.get("principalDisplayName", "")}
            for a in assignments
            if a.get("principalType", "").lower() == "user"
        ]

        aliases = _generate_aliases(name)

        app_entry = {
            "name": name,
            "sp_id": sp_id,
            "app_id": sp.get("appId", ""),
            "groups": groups,
            "direct_users": direct_users,
            "aliases": aliases,
        }
        apps.append(app_entry)

        assign_summary = []
        if groups:
            assign_summary.append(f"{len(groups)} group(s)")
        if direct_users:
            assign_summary.append(f"{len(direct_users)} direct user(s)")
        print(f" {', '.join(assign_summary) or 'no assignments'}")

    catalog = {
        "_meta": {
            "last_refreshed": datetime.now(timezone.utc).isoformat(),
            "app_count": len(apps),
            "connector_host": "is01s114",
            "ztna_tag": ZTNA_TAG,
        },
        "apps": apps,
    }

    _save_catalog(catalog)
    print(f"\nCatalog saved: {CATALOG_PATH}")
    print(f"  {len(apps)} Private Access apps indexed")
    print(f"\nUse 'gsa_check.py list-apps' to view, 'gsa_check.py check <user> <resource>' to query.")


def list_apps(catalog: dict):
    """Show all Private Access apps from the cached catalog."""
    apps = catalog.get("apps", [])
    meta = catalog.get("_meta", {})

    print(f"GSA Private Access App Catalog ({len(apps)} apps)")
    print(f"  Last refreshed: {meta.get('last_refreshed', '?')}")
    print(f"  Connector host: {meta.get('connector_host', '?')}")
    print()

    print(f"  {'Application':<45} {'Assignment':<20} {'Groups / Users'}")
    print("  " + "-" * 100)

    for app in sorted(apps, key=lambda a: a["name"]):
        name = app["name"][:44]
        groups = app.get("groups", [])
        direct = app.get("direct_users", [])

        if groups and direct:
            assign_type = "group + direct"
        elif groups:
            assign_type = "group"
        elif direct:
            assign_type = "direct"
        else:
            assign_type = "none"

        details = []
        for g in groups:
            details.append(g["name"])
        for u in direct:
            details.append(f"{u['name']} (direct)")

        detail_str = ", ".join(details[:3])
        if len(details) > 3:
            detail_str += f" +{len(details) - 3} more"

        print(f"  {name:<45} {assign_type:<20} {detail_str}")

    print(f"\n  Aliases are searchable -- e.g., 'munis' matches 'Tyler - EERP Reports Server'")


def check_access(client: GraphClient, catalog: dict, user_query: str, resource_query: str):
    """Quick yes/no access check: does a user have access to a resource via GSA?"""
    # Step 1: Match resource in catalog
    matches = _fuzzy_match_app(catalog, resource_query)

    if not matches:
        print(f"NO MATCH: No Private Access app found matching '{resource_query}'.")
        print(f"\nAvailable apps ({len(catalog.get('apps', []))}):")
        for app in sorted(catalog.get("apps", []), key=lambda a: a["name"]):
            print(f"  - {app['name']}")
        print(f"\nRun 'gsa_check.py refresh' if a new app was recently added.")
        return

    if len(matches) > 1:
        print(f"Multiple apps match '{resource_query}':\n")
        for i, m in enumerate(matches, 1):
            print(f"  {i}. {m['name']}")
        print(f"\nUsing first match: {matches[0]['name']}")
        print()

    app = matches[0]
    app_name = app["name"]
    app_groups = {g["id"]: g["name"] for g in app.get("groups", [])}
    app_direct_ids = {u["id"] for u in app.get("direct_users", [])}
    app_direct_names = {u["id"]: u["name"] for u in app.get("direct_users", [])}

    # Step 2: Resolve user (1 API call)
    try:
        users = client.search_users(
            user_query,
            select="id,displayName,mail,userPrincipalName,accountEnabled",
        )
        if not users:
            # Try as exact UPN/email
            try:
                u = client.get_user(
                    user_query,
                    select="id,displayName,mail,userPrincipalName,accountEnabled",
                )
                users = [u]
            except Exception:
                pass

        if not users:
            print(f"NO USER FOUND: Could not find user matching '{user_query}'.")
            return

        user = users[0]
    except Exception as e:
        print(f"ERROR resolving user: {e}")
        return

    user_id = user["id"]
    user_name = user.get("displayName", "?")
    user_upn = user.get("userPrincipalName", "?")
    user_enabled = user.get("accountEnabled", False)

    # Step 3: Check direct assignment (no API call needed -- from catalog)
    if user_id in app_direct_ids:
        print(f"YES -- {user_name} HAS access to {app_name}")
        print(f"\n  User:     {user_name} ({user_upn})")
        print(f"  Resource: {app_name}")
        print(f"  Access:   DIRECT assignment to enterprise app")
        print(f"  Account:  {'Enabled' if user_enabled else 'DISABLED'}")
        return

    # Step 4: Get user's group memberships (1 API call)
    try:
        resp = client.get(f"users/{user_id}/memberOf")
        resp.raise_for_status()
        memberships = resp.json().get("value", [])
    except Exception as e:
        print(f"ERROR fetching group memberships: {e}")
        return

    user_group_ids = {
        m["id"] for m in memberships
        if m.get("@odata.type") == "#microsoft.graph.group"
    }

    # Step 5: Compare groups
    matching_groups = user_group_ids & set(app_groups.keys())

    if matching_groups:
        group_names = [app_groups[gid] for gid in matching_groups]
        print(f"YES -- {user_name} HAS access to {app_name}")
        print(f"\n  User:     {user_name} ({user_upn})")
        print(f"  Resource: {app_name}")
        print(f"  Access:   Via group membership")
        for gname in group_names:
            print(f"            -> {gname}")
        print(f"  Account:  {'Enabled' if user_enabled else 'DISABLED'}")
    else:
        print(f"NO -- {user_name} does NOT have access to {app_name}")
        print(f"\n  User:     {user_name} ({user_upn})")
        print(f"  Resource: {app_name}")
        print(f"  Account:  {'Enabled' if user_enabled else 'DISABLED'}")
        if app_groups:
            print(f"\n  To grant access, add user to one of these groups:")
            for gid, gname in app_groups.items():
                print(f"    - {gname} ({gid})")
        elif app_direct_ids:
            print(f"\n  This app uses direct assignment. Assign user in:")
            print(f"    Entra admin center > Enterprise applications > {app_name} > Users and groups")
        else:
            print(f"\n  This app has no assignments configured.")


# ── Discovery commands ────────────────────────────────────────────────


def discover_gsa_apps(client: GraphClient):
    """Find all GSA-related enterprise applications (generic + per-app Private Access)."""
    print("Searching for Global Secure Access enterprise applications...\n")

    # 1. Find generic GSA apps by keyword
    generic = []
    seen_ids = set()

    for keyword in GSA_KEYWORDS:
        try:
            sps = client.list_service_principals(
                filter_expr=f"startswith(displayName, '{keyword}')",
                top=50,
            )
        except Exception:
            sps = []

        for sp in sps:
            sp_id = sp.get("id")
            if sp_id and sp_id not in seen_ids:
                seen_ids.add(sp_id)
                generic.append(sp)

    # 2. Find per-app Private Access apps by ZTNA tag
    all_sps = client.list_service_principals(top=999)
    per_app = []
    for sp in all_sps:
        sp_id = sp.get("id")
        if sp_id in seen_ids:
            continue
        if ZTNA_TAG in sp.get("tags", []):
            seen_ids.add(sp_id)
            per_app.append(sp)
        else:
            name = (sp.get("displayName") or "").lower()
            if any(kw.lower() in name for kw in GSA_KEYWORDS):
                if sp_id not in seen_ids:
                    seen_ids.add(sp_id)
                    generic.append(sp)

    if generic:
        print(f"Generic GSA Enterprise Apps ({len(generic)}):")
        print(f"  {'Display Name':<50} {'Object ID'}")
        print("  " + "-" * 90)
        for sp in generic:
            name = (sp.get("displayName") or "?")[:49]
            print(f"  {name:<50} {sp.get('id', '?')}")
        print()

    if per_app:
        print(f"Per-App Private Access Apps ({len(per_app)}) [tag: {ZTNA_TAG}]:")
        print(f"  {'Display Name':<50} {'Object ID'}")
        print("  " + "-" * 90)
        for sp in per_app:
            name = (sp.get("displayName") or "?")[:49]
            print(f"  {name:<50} {sp.get('id', '?')}")
        print()

    total = len(generic) + len(per_app)
    if not total:
        print("No GSA enterprise applications found.")
    else:
        print(f"Total: {total} ({len(generic)} generic, {len(per_app)} per-app)")
        print(f"\nRun 'gsa_check.py refresh' to build/update the searchable catalog.")


def show_assignments(client: GraphClient, sp_id: str):
    """List all users and groups assigned to a GSA enterprise app."""
    try:
        sp = client.get(f"servicePrincipals/{sp_id}")
        sp.raise_for_status()
        sp_data = sp.json()
        sp_name = sp_data.get("displayName", sp_id)
    except Exception:
        sp_name = sp_id

    assignments = client.list_app_role_assignments(sp_id)

    if not assignments:
        print(f"No assignments found for '{sp_name}'.")
        print("\nUsers/groups may be assigned via:")
        print("  Entra admin center > Enterprise applications > [app] > Users and groups")
        return

    groups = []
    users = []
    sps_assigned = []

    for a in assignments:
        principal_type = a.get("principalType", "").lower()
        if principal_type == "group":
            groups.append(a)
        elif principal_type == "user":
            users.append(a)
        else:
            sps_assigned.append(a)

    print(f"Assignments for '{sp_name}': {len(assignments)} total")
    print(f"  Groups: {len(groups)}  |  Users (direct): {len(users)}  |  Service Principals: {len(sps_assigned)}")
    print()

    if groups:
        print("Assigned Groups:")
        print(f"  {'Group Name':<45} {'Principal ID':<38} {'Role ID'}")
        print("  " + "-" * 120)
        for a in groups:
            name = (a.get("principalDisplayName") or "?")[:44]
            pid = a.get("principalId", "?")
            role = a.get("appRoleId", "?")
            print(f"  {name:<45} {pid:<38} {role}")
        print()

    if users:
        print("Directly Assigned Users:")
        print(f"  {'User Name':<45} {'Principal ID':<38} {'Role ID'}")
        print("  " + "-" * 120)
        for a in users:
            name = (a.get("principalDisplayName") or "?")[:44]
            pid = a.get("principalId", "?")
            role = a.get("appRoleId", "?")
            print(f"  {name:<45} {pid:<38} {role}")
        print()

    if sps_assigned:
        print("Assigned Service Principals:")
        for a in sps_assigned:
            print(f"  {a.get('principalDisplayName', '?'):45s}  {a.get('principalId', '?')}")
        print()

    if groups:
        print(f"Use 'gsa_check.py access-chain {sp_id}' to expand group memberships.")


def show_access_chain(client: GraphClient, sp_id: str):
    """Expand group memberships to show the full User -> Group -> App chain."""
    try:
        sp = client.get(f"servicePrincipals/{sp_id}")
        sp.raise_for_status()
        sp_data = sp.json()
        sp_name = sp_data.get("displayName", sp_id)
    except Exception:
        sp_name = sp_id

    assignments = client.list_app_role_assignments(sp_id)

    if not assignments:
        print(f"No assignments found for '{sp_name}'.")
        return

    groups = [a for a in assignments if a.get("principalType", "").lower() == "group"]
    direct_users = [a for a in assignments if a.get("principalType", "").lower() == "user"]

    print(f"Access Chain for '{sp_name}'")
    print("=" * 80)

    total_users = set()

    if direct_users:
        print(f"\nDirect User Assignments ({len(direct_users)}):")
        for a in direct_users:
            name = a.get("principalDisplayName", "?")
            pid = a.get("principalId", "?")
            print(f"  {name} ({pid})")
            total_users.add(pid)

    if groups:
        print(f"\nGroup Assignments ({len(groups)}):")
        for a in groups:
            group_name = a.get("principalDisplayName", "?")
            group_id = a.get("principalId", "?")
            print(f"\n  Group: {group_name} ({group_id})")

            try:
                members = client.list_group_members(group_id)
                if not members:
                    print("    (no members)")
                    continue

                user_members = [m for m in members if m.get("@odata.type") == "#microsoft.graph.user"]
                group_members = [m for m in members if m.get("@odata.type") == "#microsoft.graph.group"]
                other_members = [m for m in members if m not in user_members and m not in group_members]

                if user_members:
                    print(f"    Users ({len(user_members)}):")
                    for m in sorted(user_members, key=lambda x: x.get("displayName", "")):
                        mail = m.get("mail") or m.get("userPrincipalName") or ""
                        print(f"      {m.get('displayName', '?'):40s}  {mail}")
                        total_users.add(m.get("id"))

                if group_members:
                    print(f"    Nested Groups ({len(group_members)}):")
                    for m in group_members:
                        print(f"      {m.get('displayName', '?')} (nested -- members not expanded)")

                if other_members:
                    print(f"    Other ({len(other_members)}):")
                    for m in other_members:
                        obj_type = m.get("@odata.type", "?").split(".")[-1]
                        print(f"      [{obj_type}] {m.get('displayName', '?')}")

            except Exception as e:
                print(f"    Error listing members: {e}")

    print(f"\n{'=' * 80}")
    print(f"Total unique users with access: {len(total_users)}")


def show_gsa_ca_policies(client: GraphClient):
    """Show Conditional Access policies that target GSA enterprise apps."""
    print("Searching for GSA enterprise apps...\n")

    gsa_app_ids = set()
    gsa_names = {}

    # Use catalog if available for fast app ID lookup
    catalog = _load_catalog()
    if catalog:
        for app in catalog.get("apps", []):
            aid = app.get("app_id")
            if aid:
                gsa_app_ids.add(aid)
                gsa_names[aid] = app["name"]

    # Also find generic GSA apps
    for keyword in GSA_KEYWORDS:
        try:
            sps = client.list_service_principals(
                filter_expr=f"startswith(displayName, '{keyword}')",
                top=50,
            )
        except Exception:
            sps = []
        for sp in sps:
            app_id = sp.get("appId")
            if app_id and app_id not in gsa_app_ids:
                gsa_app_ids.add(app_id)
                gsa_names[app_id] = sp.get("displayName", "?")

    if not gsa_app_ids:
        print("No GSA enterprise apps found. Cannot filter CA policies.")
        print("Showing all Conditional Access policies instead.\n")

    policies = client.list_conditional_access_policies()

    if not policies:
        print("No Conditional Access policies found.")
        return

    matching = []
    other = []

    for p in policies:
        conditions = p.get("conditions", {})
        apps = conditions.get("applications", {})
        include_apps = apps.get("includeApplications", [])
        exclude_apps = apps.get("excludeApplications", [])

        all_referenced = set(include_apps + exclude_apps)
        if gsa_app_ids and all_referenced & gsa_app_ids:
            matching.append(p)
        elif "All" in include_apps or "Office365" in include_apps:
            matching.append(p)
        else:
            other.append(p)

    if matching:
        print(f"Conditional Access Policies Targeting GSA ({len(matching)}):")
        print(f"  {'State':<12} {'Policy Name':<55} {'Target Apps'}")
        print("  " + "-" * 100)

        for p in sorted(matching, key=lambda x: x.get("state", "")):
            state = (p.get("state") or "?")[:11]
            name = (p.get("displayName") or "?")[:54]
            apps = p.get("conditions", {}).get("applications", {})
            include = apps.get("includeApplications", [])
            target = ", ".join(include[:3])
            if len(include) > 3:
                target += f" +{len(include) - 3} more"
            print(f"  {state:<12} {name:<55} {target}")

            grant = p.get("grantControls", {})
            if grant:
                built_in = grant.get("builtInControls", [])
                if built_in:
                    print(f"  {'':12} Grant: {', '.join(built_in)}")

            session = p.get("sessionControls", {})
            if session:
                parts = [k for k, v in session.items() if v and k != "@odata.type"]
                if parts:
                    print(f"  {'':12} Session: {', '.join(parts)}")
        print()

    if not gsa_app_ids:
        print(f"\nAll Conditional Access Policies ({len(policies)}):")
        print(f"  {'State':<12} {'Policy Name':<55} {'Created'}")
        print("  " + "-" * 85)
        for p in sorted(policies, key=lambda x: x.get("state", "")):
            state = (p.get("state") or "?")[:11]
            name = (p.get("displayName") or "?")[:54]
            created = (p.get("createdDateTime") or "?")[:19]
            print(f"  {state:<12} {name:<55} {created}")

    print(f"\nTotal CA policies: {len(policies)} ({len(matching)} GSA-related, {len(other)} other)")


def audit_user(client: GraphClient, user_email: str):
    """Full GSA access audit for a specific user.

    Uses the catalog for comprehensive coverage of all Private Access apps.
    Falls back to keyword-based discovery if catalog is missing.
    """
    print(f"GSA Access Audit for: {user_email}")
    print("=" * 80)

    # Resolve user
    try:
        user = client.get_user(
            user_email,
            select="id,displayName,mail,userPrincipalName,accountEnabled,"
                   "jobTitle,department",
        )
    except Exception as e:
        print(f"\nError: Could not find user '{user_email}': {e}")
        return

    user_id = user["id"]
    enabled = "Enabled" if user.get("accountEnabled") else "DISABLED"
    print(f"\n  Name:       {user.get('displayName', '?')}")
    print(f"  UPN:        {user.get('userPrincipalName', '?')}")
    print(f"  Department: {user.get('department', '?')}")
    print(f"  Title:      {user.get('jobTitle', '?')}")
    print(f"  Account:    {enabled}")
    print(f"  Object ID:  {user_id}")

    # Get user group memberships
    try:
        resp = client.get(f"users/{user_id}/memberOf")
        resp.raise_for_status()
        memberships = resp.json().get("value", [])
    except Exception as e:
        print(f"\nError fetching group memberships: {e}")
        memberships = []

    group_memberships = [
        m for m in memberships
        if m.get("@odata.type") == "#microsoft.graph.group"
    ]
    user_group_ids = {m["id"] for m in group_memberships}

    print(f"\n  Group Memberships: {len(group_memberships)} groups")

    # Load catalog for Private Access apps
    catalog = _load_catalog()
    if catalog and catalog.get("apps"):
        private_access_apps = catalog["apps"]
        print(f"  Private Access Apps (from catalog): {len(private_access_apps)}")
        print(f"  Catalog refreshed: {catalog.get('_meta', {}).get('last_refreshed', '?')}")
    else:
        print("\n  No catalog found. Run 'gsa_check.py refresh' for full coverage.")
        print("  Falling back to keyword-based discovery (limited)...\n")
        private_access_apps = None

    # Check each Private Access app
    print(f"\n{'─' * 80}")
    print("Private Access Application Analysis")
    print(f"{'─' * 80}")

    has_access = []
    no_access = []

    if private_access_apps:
        for app in private_access_apps:
            app_name = app["name"]
            app_group_ids = {g["id"] for g in app.get("groups", [])}
            app_direct_ids = {u["id"] for u in app.get("direct_users", [])}

            direct_match = user_id in app_direct_ids
            matching_groups = user_group_ids & app_group_ids
            group_names = [
                g["name"] for g in app.get("groups", []) if g["id"] in matching_groups
            ]

            if direct_match:
                has_access.append((app_name, "DIRECT", []))
            elif matching_groups:
                has_access.append((app_name, "GROUP", group_names))
            else:
                no_access.append(app_name)
    else:
        # Fallback: keyword-based discovery (old behavior)
        seen_ids = set()
        gsa_apps = []
        for keyword in GSA_KEYWORDS:
            try:
                sps = client.list_service_principals(
                    filter_expr=f"startswith(displayName, '{keyword}')",
                    top=50,
                )
            except Exception:
                sps = []
            for sp in sps:
                sp_id = sp.get("id")
                if sp_id and sp_id not in seen_ids:
                    seen_ids.add(sp_id)
                    gsa_apps.append(sp)

        for sp in gsa_apps:
            sp_id = sp["id"]
            sp_name = sp.get("displayName", "?")
            assignments = client.list_app_role_assignments(sp_id)

            direct_match = any(
                a.get("principalId") == user_id and a.get("principalType", "").lower() == "user"
                for a in assignments
            )
            matching_groups = [
                a.get("principalDisplayName", "?")
                for a in assignments
                if a.get("principalType", "").lower() == "group"
                and a.get("principalId") in user_group_ids
            ]

            if direct_match:
                has_access.append((sp_name, "DIRECT", []))
            elif matching_groups:
                has_access.append((sp_name, "GROUP", matching_groups))
            else:
                no_access.append(sp_name)

    if has_access:
        print(f"\n  ACCESS GRANTED ({len(has_access)} apps):")
        for app_name, access_type, groups in has_access:
            if access_type == "DIRECT":
                print(f"    [DIRECT]  {app_name}")
            else:
                group_str = ", ".join(groups)
                print(f"    [GROUP]   {app_name}  (via {group_str})")

    if no_access:
        print(f"\n  NO ACCESS ({len(no_access)} apps):")
        for app_name in no_access:
            print(f"    [ --- ]   {app_name}")

    print(f"\n{'=' * 80}")
    total = len(has_access) + len(no_access)
    print(f"Audit complete: {len(has_access)}/{total} apps accessible")


# ── Network access commands (beta API) ────────────────────────────────


def show_profiles(client: GraphClient):
    """List Global Secure Access forwarding profiles."""
    print("Global Secure Access Forwarding Profiles")
    print("(beta API -- requires NetworkAccess.Read.All)\n")

    try:
        profiles = client.list_forwarding_profiles()
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Authorization" in error_msg:
            print("ERROR: Access denied. The NetworkAccess.Read.All permission")
            print("is required but not currently granted to the app registration.")
            print()
            print("To enable:")
            print("  1. Open Entra admin center > App registrations")
            print("  2. Select your Tendril Graph Bridge app registration")
            print("  3. API permissions > Add > Microsoft Graph > Application")
            print("  4. Search for 'NetworkAccess.Read.All' and add it")
            print("  5. Grant admin consent")
        else:
            print(f"Error: {e}")
        return

    if not profiles:
        print("No forwarding profiles found.")
        return

    print(f"Found {len(profiles)} forwarding profile(s):\n")

    for p in profiles:
        name = p.get("name", "?")
        state = p.get("state", "?")
        traffic_type = p.get("trafficForwardingType", "?")
        profile_id = p.get("id", "?")

        print(f"  Profile: {name}")
        print(f"    State: {state}")
        print(f"    Traffic Type: {traffic_type}")
        print(f"    ID: {profile_id}")

        policies = p.get("policies", [])
        if policies:
            print(f"    Policies: {len(policies)}")
            for pol in policies:
                pol_name = pol.get("name", "?")
                print(f"      - {pol_name}")
        print()

    print("Use 'gsa_check.py app-segments' to see Private Access application segments.")


def show_app_segments(client: GraphClient):
    """List Private Access application segments from forwarding profiles."""
    print("Global Secure Access - Private Access Application Segments")
    print("(beta API -- requires NetworkAccess.Read.All)\n")

    try:
        profiles = client.list_forwarding_profiles()
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Authorization" in error_msg:
            print("ERROR: NetworkAccess.Read.All permission required.")
            print("See 'gsa_check.py profiles' for setup instructions.")
        else:
            print(f"Error: {e}")
        return

    private_profiles = [
        p for p in profiles
        if (p.get("trafficForwardingType") or "").lower() == "private"
        or "private" in (p.get("name") or "").lower()
    ]

    if not private_profiles:
        print("No Private Access forwarding profiles found.")
        print(f"Available profiles: {[p.get('name') for p in profiles]}")
        return

    all_segments = []

    for profile in private_profiles:
        profile_id = profile.get("id")
        profile_name = profile.get("name", "?")
        print(f"Profile: {profile_name} ({profile.get('state', '?')})")

        try:
            detail = client.get_forwarding_profile(profile_id)
            policies = detail.get("policies", [])

            for pol in policies:
                rules = pol.get("rules", [])
                for rule in rules:
                    destinations = rule.get("destinations", [])
                    for dest in destinations:
                        seg = {
                            "profile": profile_name,
                            "policy": pol.get("name", "?"),
                            "fqdn": dest.get("fqdn", ""),
                            "ip": dest.get("ip", ""),
                            "port": dest.get("port", ""),
                            "protocol": dest.get("protocol", ""),
                        }
                        all_segments.append(seg)
        except Exception as e:
            print(f"  Error expanding profile: {e}")

    if not all_segments:
        print("\nNo application segments found in Private Access profiles.")
        return

    print(f"\nApplication Segments ({len(all_segments)}):\n")
    print(f"  {'FQDN / IP':<45} {'Port':<10} {'Protocol':<10} {'Policy'}")
    print("  " + "-" * 100)

    for s in all_segments:
        target = s["fqdn"] or s["ip"] or "?"
        port = s["port"] or "*"
        proto = s["protocol"] or "*"
        policy = s["policy"][:30]
        print(f"  {target:<45} {str(port):<10} {proto:<10} {policy}")


def find_resource(client: GraphClient, fqdn: str):
    """Search Private Access app segments for a specific FQDN."""
    print(f"Searching Global Secure Access for: {fqdn}")
    print("(beta API -- requires NetworkAccess.Read.All)\n")

    try:
        profiles = client.list_forwarding_profiles()
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg or "Authorization" in error_msg:
            print("ERROR: NetworkAccess.Read.All permission required.")
            print("See 'gsa_check.py profiles' for setup instructions.")
        else:
            print(f"Error: {e}")
        return

    fqdn_lower = fqdn.lower().rstrip("/").replace("https://", "").replace("http://", "")
    if "/" in fqdn_lower:
        fqdn_lower = fqdn_lower.split("/")[0]

    matches = []

    for profile in profiles:
        profile_id = profile.get("id")
        profile_name = profile.get("name", "?")

        try:
            detail = client.get_forwarding_profile(profile_id)
            policies = detail.get("policies", [])

            for pol in policies:
                rules = pol.get("rules", [])
                for rule in rules:
                    destinations = rule.get("destinations", [])
                    for dest in destinations:
                        dest_fqdn = (dest.get("fqdn") or "").lower()
                        dest_ip = (dest.get("ip") or "").lower()

                        if fqdn_lower in dest_fqdn or fqdn_lower in dest_ip or dest_fqdn in fqdn_lower:
                            matches.append({
                                "profile": profile_name,
                                "policy": pol.get("name", "?"),
                                "fqdn": dest.get("fqdn", ""),
                                "ip": dest.get("ip", ""),
                                "port": dest.get("port", ""),
                                "protocol": dest.get("protocol", ""),
                            })
        except Exception:
            pass

    if matches:
        print(f"Found {len(matches)} matching segment(s):\n")
        for m in matches:
            print(f"  Profile:  {m['profile']}")
            print(f"  Policy:   {m['policy']}")
            print(f"  FQDN:     {m['fqdn'] or '(none)'}")
            print(f"  IP:       {m['ip'] or '(none)'}")
            print(f"  Port:     {m['port'] or '*'}")
            print(f"  Protocol: {m['protocol'] or '*'}")
            print()
    else:
        print(f"No application segments found matching '{fqdn}'.")
        print()
        print("Possible reasons:")
        print("  - The resource may not be published through Private Access")
        print("  - The FQDN/IP may be in a different format in the segment definition")
        print("  - Access may be via IP range rather than FQDN")
        print(f"\nRun 'gsa_check.py app-segments' to see all defined segments.")


# ── CLI Entrypoint ─────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    command = sys.argv[1].lower()

    # Commands that need catalog only (no Graph client until needed)
    if command in ("list-apps", "listapps", "apps"):
        catalog = _load_catalog()
        if not catalog:
            print("No catalog found. Run 'gsa_check.py refresh' first.")
            sys.exit(1)
        list_apps(catalog)
        return

    # All other commands need a Graph client
    client = GraphClient()

    if command == "refresh":
        refresh_catalog(client)

    elif command == "check" and len(sys.argv) > 3:
        catalog = _load_catalog()
        if not catalog:
            print("No catalog found. Run 'gsa_check.py refresh' first.")
            sys.exit(1)
        check_access(client, catalog, sys.argv[2], " ".join(sys.argv[3:]))

    elif command == "discover":
        discover_gsa_apps(client)

    elif command == "assignments" and len(sys.argv) > 2:
        show_assignments(client, sys.argv[2])

    elif command in ("access-chain", "chain") and len(sys.argv) > 2:
        show_access_chain(client, sys.argv[2])

    elif command in ("ca-policies", "ca", "policies-ca"):
        show_gsa_ca_policies(client)

    elif command == "audit" and len(sys.argv) > 2:
        audit_user(client, sys.argv[2])

    elif command == "profiles":
        show_profiles(client)

    elif command in ("app-segments", "segments"):
        show_app_segments(client)

    elif command in ("find-resource", "find") and len(sys.argv) > 2:
        find_resource(client, sys.argv[2])

    else:
        print(f"Unknown command: {command}")
        print()
        print("Catalog commands (run 'refresh' first):")
        print("  refresh                         Rebuild app catalog from live Graph data")
        print("  list-apps                       Show all Private Access apps")
        print("  check <user> <resource>         Quick yes/no access check")
        print()
        print("Discovery commands:")
        print("  discover                        Find GSA enterprise apps (generic + per-app)")
        print("  assignments <sp-id>             List users/groups assigned to an app")
        print("  access-chain <sp-id>            Expand group membership for an app")
        print("  ca-policies                     CA policies targeting GSA apps")
        print("  audit <user-email>              Full GSA access audit for a user")
        print()
        print("Network access (beta API, requires NetworkAccess.Read.All):")
        print("  profiles                        Forwarding profiles")
        print("  app-segments                    Private Access app segments")
        print("  find-resource <fqdn>            Search segments for an FQDN")
        sys.exit(1)


if __name__ == "__main__":
    main()
