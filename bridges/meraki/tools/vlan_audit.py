#!/usr/bin/env python3
"""
Meraki VLAN Audit Tool

Audits VLAN configurations across all organization sites against the institutional
standard defined in vlan_reference.py. Reports naming inconsistencies,
missing VLANs, subnet deviations, and DHCP misconfigurations.

Commands:
    list <site>         Show VLANs for a site with role annotations
    audit <site>        Audit a single site against the standard
    audit-all           Audit all appliance networks org-wide
    matrix              Site-vs-VLAN matrix showing coverage
    inconsistencies     List all naming/config deviations
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from meraki_client import MerakiClient
from vlan_reference import (
    VLAN_STANDARD,
    SITE_MAP,
    VLAN_NAME_ALIASES,
    TIER_VLANS,
    site_id_from_network_name,
    site_id_from_vlan_name,
    expected_subnet,
    expected_gateway,
    expected_name,
    expected_vlans_for_site,
    vlan_role,
    matches_role_name,
    identify_vlan_role,
)


def get_appliance_networks(client: MerakiClient) -> list:
    """Return networks that have an appliance (and thus VLANs)."""
    networks = client.list_networks()
    return [
        n for n in sorted(networks, key=lambda x: x.get("name", ""))
        if "appliance" in n.get("productTypes", [])
    ]


def find_network(client: MerakiClient, search: str) -> dict | None:
    """Find a network by name substring (case-insensitive)."""
    networks = client.list_networks()
    search_lower = search.lower()
    for n in networks:
        if search_lower in n.get("name", "").lower():
            return n
    return None


def annotate_vlans(vlans: list, network_name: str) -> list:
    """Add role annotations to a list of raw VLAN dicts."""
    annotated = []
    for v in sorted(vlans, key=lambda x: x.get("id", 0)):
        vid = v.get("id", 0)
        name = v.get("name", "")
        subnet = v.get("subnet", "")
        gw = v.get("applianceIp", "")
        dhcp = v.get("dhcpHandling", "")

        info = identify_vlan_role(vid, name, subnet)

        annotated.append({
            "vlan_id": vid,
            "name": name,
            "subnet": subnet,
            "gateway": gw,
            "dhcp": dhcp,
            "role": info["role"],
            "site_id": info["site_id"],
            "expected_name": info["expected_name"],
            "issues": info["issues"],
        })
    return annotated


def audit_site(client: MerakiClient, network: dict) -> dict:
    """Audit a single network's VLANs against the standard."""
    net_name = network["name"]
    net_id = network["id"]
    primary_site = site_id_from_network_name(net_name)

    vlans = client.get_vlans(net_id)
    if not vlans:
        return {
            "network": net_name,
            "site_id": primary_site,
            "vlan_count": 0,
            "findings": ["No VLANs configured (may not be an appliance network)"],
            "vlans": [],
        }

    annotated = annotate_vlans(vlans, net_name)

    # Group VLANs by the site_id derived from their subnet
    sites_found = set()
    for v in annotated:
        if v["site_id"]:
            sites_found.add(v["site_id"])

    findings = []

    for site_id in sorted(sites_found):
        site_info = SITE_MAP.get(site_id)
        if not site_info:
            continue
        site_name = site_info.get("name", f"Site {site_id}")
        site_vlans = [v for v in annotated if v["site_id"] == site_id]
        site_vlan_roles = set()

        for v in site_vlans:
            # Check naming
            for issue in v["issues"]:
                findings.append(f"[Site {site_id:>3} {site_name}] VLAN {v['vlan_id']} ({v['role']}): {issue}")

            # Check subnet
            if v["role"] != "Unknown":
                std_id = None
                for sid, sdef in VLAN_STANDARD.items():
                    if sdef["role"] == v["role"]:
                        std_id = sid
                        break
                if std_id:
                    site_vlan_roles.add(std_id)
                    exp_sub = expected_subnet(site_id, std_id)
                    exp_gw = expected_gateway(site_id, std_id)
                    if exp_sub and v["subnet"] != exp_sub:
                        findings.append(
                            f"[Site {site_id:>3} {site_name}] VLAN {v['vlan_id']} ({v['role']}): "
                            f"Subnet {v['subnet']} != expected {exp_sub}"
                        )
                    if exp_gw and v["gateway"] != exp_gw:
                        findings.append(
                            f"[Site {site_id:>3} {site_name}] VLAN {v['vlan_id']} ({v['role']}): "
                            f"Gateway {v['gateway']} != expected {exp_gw}"
                        )

                    # Check DHCP mode
                    exp_dhcp = VLAN_STANDARD[std_id]["dhcp"]
                    if v["dhcp"] and v["dhcp"] != exp_dhcp:
                        findings.append(
                            f"[Site {site_id:>3} {site_name}] VLAN {v['vlan_id']} ({v['role']}): "
                            f"DHCP '{v['dhcp']}' != expected '{exp_dhcp}'"
                        )

        # Check for missing standard VLANs
        expected = expected_vlans_for_site(site_id)
        for evid in expected:
            if evid not in site_vlan_roles:
                role = vlan_role(evid)
                findings.append(
                    f"[Site {site_id:>3} {site_name}] Missing standard VLAN {evid} ({role})"
                )

    return {
        "network": net_name,
        "site_id": primary_site,
        "vlan_count": len(vlans),
        "sites_in_network": sorted(sites_found),
        "findings": findings,
        "vlans": annotated,
    }


# ── Commands ───────────────────────────────────────────────────────────

def cmd_list(client: MerakiClient, site_search: str):
    """Show VLANs for a site with role annotations."""
    network = find_network(client, site_search)
    if not network:
        print(f"No network found matching '{site_search}'")
        sys.exit(1)

    net_name = network["name"]
    net_id = network["id"]
    print(f"VLANs for: {net_name}")
    print("=" * 90)

    vlans = client.get_vlans(net_id)
    if not vlans:
        print("  No VLANs configured")
        return

    annotated = annotate_vlans(vlans, net_name)

    # Group by site_id
    by_site = {}
    for v in annotated:
        sid = v["site_id"] or 0
        if sid not in by_site:
            by_site[sid] = []
        by_site[sid].append(v)

    for sid in sorted(by_site.keys()):
        site_info = SITE_MAP.get(sid, {})
        site_label = site_info.get("name", f"Site {sid}") if sid else "Unknown Site"
        print(f"\n  Site {sid:>3} -- {site_label}")
        print(f"  {'VLAN':>6}  {'Name':<20}  {'Role':<14}  {'Subnet':<20}  {'Gateway':<18}  {'DHCP'}")
        print(f"  {'-' * 6}  {'-' * 20}  {'-' * 14}  {'-' * 20}  {'-' * 18}  {'-' * 10}")

        for v in by_site[sid]:
            dhcp_short = "DHCP" if "Run" in v["dhcp"] else "No DHCP" if v["dhcp"] else "?"
            flag = " *" if v["issues"] else ""
            print(
                f"  {v['vlan_id']:>6}  {v['name']:<20}  {v['role']:<14}  "
                f"{v['subnet']:<20}  {v['gateway']:<18}  {dhcp_short}{flag}"
            )
            for issue in v["issues"]:
                print(f"         >> {issue}")


def cmd_audit(client: MerakiClient, site_search: str):
    """Audit a single site against the standard."""
    network = find_network(client, site_search)
    if not network:
        print(f"No network found matching '{site_search}'")
        sys.exit(1)

    result = audit_site(client, network)

    print(f"VLAN Audit: {result['network']}")
    print(f"Primary Site ID: {result['site_id']}")
    print(f"Total VLANs: {result['vlan_count']}")
    if result.get("sites_in_network"):
        print(f"Sites in network: {result['sites_in_network']}")
    print("=" * 80)

    if result["findings"]:
        print(f"\nFindings ({len(result['findings'])}):")
        for f in result["findings"]:
            print(f"  - {f}")
    else:
        print("\n  All VLANs match the standard. No issues found.")


def cmd_audit_all(client: MerakiClient):
    """Audit all appliance networks org-wide."""
    networks = get_appliance_networks(client)
    print(f"Auditing {len(networks)} appliance networks...")
    print("=" * 80)

    total_findings = 0
    total_vlans = 0
    all_findings = []

    for net in networks:
        result = audit_site(client, net)
        total_vlans += result["vlan_count"]
        count = len(result["findings"])
        total_findings += count

        status = f"{count} finding(s)" if count else "OK"
        sites_str = ""
        if result.get("sites_in_network") and len(result["sites_in_network"]) > 1:
            sites_str = f"  [multi-site: {result['sites_in_network']}]"

        print(f"  {result['network']:<45}  {result['vlan_count']:>3} VLANs  {status}{sites_str}")

        for f in result["findings"]:
            all_findings.append(f)

    print("=" * 80)
    print(f"Total: {total_vlans} VLANs across {len(networks)} networks, {total_findings} findings")

    if all_findings:
        print(f"\nAll Findings ({total_findings}):")
        for f in sorted(all_findings):
            print(f"  - {f}")


def cmd_matrix(client: MerakiClient):
    """Show a site-vs-VLAN matrix."""
    networks = get_appliance_networks(client)

    # Standard VLAN IDs to check
    std_ids = sorted(VLAN_STANDARD.keys())
    header_roles = [VLAN_STANDARD[v]["role"][:6] for v in std_ids]

    print(f"{'Network':<40}  " + "  ".join(f"{r:>6}" for r in header_roles))
    print("-" * 40 + "  " + "  ".join("-" * 6 for _ in std_ids))

    for net in networks:
        vlans = client.get_vlans(net["id"])
        if not vlans:
            continue

        # Build a set of which standard roles are present (by third octet)
        present_roles = set()
        for v in vlans:
            subnet = v.get("subnet", "")
            parts = subnet.split(".")
            if len(parts) >= 3:
                try:
                    third = int(parts[2])
                    for sid, sdef in VLAN_STANDARD.items():
                        if sdef["third_octet"] == third:
                            present_roles.add(sid)
                except ValueError:
                    pass

        row = []
        for std_id in std_ids:
            if std_id in present_roles:
                row.append("  YES ")
            else:
                row.append("   -  ")

        print(f"{net['name']:<40}  " + "  ".join(row))


def cmd_inconsistencies(client: MerakiClient):
    """List all naming and configuration deviations."""
    networks = get_appliance_networks(client)
    print("VLAN Naming & Configuration Inconsistencies")
    print("=" * 80)

    naming_issues = []
    subnet_issues = []
    dhcp_issues = []
    missing_vlans = []

    for net in networks:
        result = audit_site(client, net)
        for finding in result["findings"]:
            if "Name " in finding and "doesn't match" in finding:
                naming_issues.append(finding)
            elif "Subnet" in finding:
                subnet_issues.append(finding)
            elif "DHCP" in finding:
                dhcp_issues.append(finding)
            elif "Missing" in finding:
                missing_vlans.append(finding)

    if naming_issues:
        print(f"\nNaming Inconsistencies ({len(naming_issues)}):")
        for f in sorted(naming_issues):
            print(f"  - {f}")

    if subnet_issues:
        print(f"\nSubnet Deviations ({len(subnet_issues)}):")
        for f in sorted(subnet_issues):
            print(f"  - {f}")

    if dhcp_issues:
        print(f"\nDHCP Mode Mismatches ({len(dhcp_issues)}):")
        for f in sorted(dhcp_issues):
            print(f"  - {f}")

    if missing_vlans:
        print(f"\nMissing Standard VLANs ({len(missing_vlans)}):")
        for f in sorted(missing_vlans):
            print(f"  - {f}")

    total = len(naming_issues) + len(subnet_issues) + len(dhcp_issues) + len(missing_vlans)
    if total == 0:
        print("\n  No inconsistencies found.")
    else:
        print(f"\nTotal: {total} issues across {len(networks)} networks")


# ── Main ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Meraki VLAN Audit Tool")
        print()
        print("Commands:")
        print("  list <site>         Show VLANs for a site with role annotations")
        print("  audit <site>        Audit a single site against the standard")
        print("  audit-all           Audit all appliance networks org-wide")
        print("  matrix              Site-vs-VLAN matrix showing coverage")
        print("  inconsistencies     List all naming/config deviations")
        print()
        print("Examples:")
        print('  python3 vlan_audit.py list "Main Office"')
        print('  python3 vlan_audit.py audit "Branch Office"')
        print("  python3 vlan_audit.py audit-all")
        print("  python3 vlan_audit.py matrix")
        print("  python3 vlan_audit.py inconsistencies")
        sys.exit(1)

    cmd = sys.argv[1]
    client = MerakiClient()

    if cmd == "list":
        if len(sys.argv) < 3:
            print("Usage: vlan_audit.py list <site_name>")
            sys.exit(1)
        cmd_list(client, sys.argv[2])

    elif cmd == "audit":
        if len(sys.argv) < 3:
            print("Usage: vlan_audit.py audit <site_name>")
            sys.exit(1)
        cmd_audit(client, sys.argv[2])

    elif cmd == "audit-all":
        cmd_audit_all(client)

    elif cmd == "matrix":
        cmd_matrix(client)

    elif cmd in ("inconsistencies", "inconsist"):
        cmd_inconsistencies(client)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
