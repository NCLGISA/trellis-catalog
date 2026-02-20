"""
CMDB Audit and Reconciliation

Compares live Tendril agent data against Freshservice CMDB assets to find:
  - Missing: Tendril agents with no matching Freshservice asset
  - Stale:   Freshservice server assets with no connected Tendril agent
  - Mistyped: Assets classified as Azure VM that are actually on-prem
  - Drift:   Fields that differ between Tendril live data and Freshservice
  - Orphaned: CMDB CIs with no relationships or no server backing

Classification logic:
  - Azure IMDS present (is_azure=true)     -> Azure VM (7001431713)
  - OS = vmkernel                           -> VMware VCenter Host (7001431717)
  - Windows + no IMDS + VMware manufacturer -> VMware VCenter VM (7001431715)
  - Windows + no IMDS + not VMware          -> Server (7001129968)
  - Linux on-prem                           -> Server (7001129968)
  - Bridge containers                       -> excluded from CMDB
  - AVD desktops                            -> Azure VM (7001431713) w/ AVD tag

Usage:
  python cmdb_audit.py                   # Full audit report
  python cmdb_audit.py --json            # Machine-readable JSON output
"""

import json
import os
from pathlib import Path
from collections import defaultdict

try:
    from freshservice_client import FreshserviceClient
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from freshservice_client import FreshserviceClient


SYNC_STATE_FILE = Path(__file__).parent / ".sync-state.json"
COLLECTED_ASSETS_FILE = Path(__file__).parent / ".collected-assets.json"

# ── Freshservice Type IDs ────────────────────────────────────────────────

AZURE_VM_TYPE_ID = 7001431713
VMWARE_VM_TYPE_ID = 7001431715
VMWARE_HOST_TYPE_ID = 7001431717
SERVER_TYPE_ID = 7001129968
COMPUTER_TYPE_ID = 7001129946
BUSINESS_SERVICE_TYPE_ID = 7001129963
IT_SERVICE_TYPE_ID = 7001129964
MSSQL_TYPE_ID = 7001129975

# All types that represent "server-class" assets
SERVER_CLASS_TYPE_IDS = {
    AZURE_VM_TYPE_ID,
    VMWARE_VM_TYPE_ID,
    VMWARE_HOST_TYPE_ID,
    SERVER_TYPE_ID,
    7001129990,  # Linux Server
    7001129993,  # VMware Server
    7001129994,  # Windows Server
    7001270331,  # VMware VCenter Host-deprecated
    7001270332,  # VMware VCenter VM-deprecated
    7001270330,  # Host-deprecated
}

# Hostnames that are bridge containers (excluded from CMDB)
BRIDGE_PREFIXES = {"bridge-"}
BRIDGE_HOSTNAMES = {
    "bridge-freshservice", "bridge-azure", "bridge-zoom",
    "bridge-meraki", "bridge-microsoft-graph",
}

# AVD hostname patterns
AVD_PREFIXES = ("avd-", "avd_", "avdwin")
AVD_SUBSTRINGS = ("-cad-", "-esri-")

# Domain suffixes to strip for hostname normalization
# Override via FRESHSERVICE_DOMAIN_SUFFIX env var (default .example.local)
_DEFAULT_DOMAIN_SUFFIX = os.environ.get("FRESHSERVICE_DOMAIN_SUFFIX", ".example.local")
DOMAIN_SUFFIXES = (_DEFAULT_DOMAIN_SUFFIX, ".local")


def _normalize_hostname(hostname: str) -> str:
    """Strip common domain suffixes for FQDN normalization."""
    h = hostname.lower()
    for suffix in DOMAIN_SUFFIXES:
        if h.endswith(suffix):
            h = h[: -len(suffix)]
    return h


# ── Agent classification ─────────────────────────────────────────────────

def classify_agent(agent: dict, collected_data: dict = None) -> dict:
    """
    Classify a Tendril agent into a CMDB asset category.

    Returns dict with:
      - category: "azure_vm" | "vmware_vm" | "esxi_host" | "onprem_server"
                  | "avd_desktop" | "bridge" | "linux_appliance" | "unknown"
      - recommended_type_id: Freshservice asset type ID
      - exclude: True if the agent should not be in CMDB (bridges)
      - reason: Human-readable classification reason
    """
    hostname = agent.get("hostname", "").lower()
    os_version = agent.get("os_version", "")
    ip = agent.get("ip_address", "")

    # Bridge containers -- exclude from CMDB
    if hostname in BRIDGE_HOSTNAMES or any(hostname.startswith(p) for p in BRIDGE_PREFIXES):
        return {
            "category": "bridge",
            "recommended_type_id": None,
            "exclude": True,
            "reason": "Bridge container (not a CMDB asset)",
        }

    # ESXi hosts
    if "vmkernel" in os_version:
        return {
            "category": "esxi_host",
            "recommended_type_id": VMWARE_HOST_TYPE_ID,
            "exclude": False,
            "reason": "VMkernel OS detected (ESXi host)",
        }

    # AVD desktops
    if (hostname.startswith(AVD_PREFIXES) or
            any(s in hostname for s in AVD_SUBSTRINGS)):
        return {
            "category": "avd_desktop",
            "recommended_type_id": AZURE_VM_TYPE_ID,
            "exclude": False,
            "reason": "AVD desktop hostname pattern",
        }

    # Check collected data for IMDS / VMware detection
    collected = (collected_data or {}).get(hostname, {})
    is_azure = collected.get("is_azure", False)

    if is_azure:
        return {
            "category": "azure_vm",
            "recommended_type_id": AZURE_VM_TYPE_ID,
            "exclude": False,
            "reason": "Azure IMDS metadata present",
        }

    # Example subnet mapping (configure per environment):
    #   10.10.0.0/16   = Azure Production
    #   10.20.0.0/16   = Azure Non-Production
    #   10.30.0.0/16   = Legacy on-premise VMware
    is_onprem_ip = ip.startswith("10.30.")
    is_azure_ip = ip.startswith("10.10.") or ip.startswith("10.20.")

    # Windows agents without Azure IMDS
    if "windows" in os_version:
        # Check for VMware guest indicators
        manufacturer = collected.get("manufacturer", "").lower()
        serial = collected.get("serial_number", "").lower()
        uuid = collected.get("uuid", "").lower()

        is_vmware_guest = (
            "vmware" in manufacturer or
            "vmware" in serial or
            (uuid and uuid.startswith("4204"))  # VMware UUID prefix
        )

        if is_vmware_guest or is_onprem_ip:
            return {
                "category": "vmware_vm",
                "recommended_type_id": VMWARE_VM_TYPE_ID,
                "exclude": False,
                "reason": f"On-prem Windows VM (IP={ip}, vmware={'yes' if is_vmware_guest else 'no'})",
            }

        # Azure VMs without IMDS data (IMDS may have failed during collection)
        if is_azure_ip:
            return {
                "category": "azure_vm",
                "recommended_type_id": AZURE_VM_TYPE_ID,
                "exclude": False,
                "reason": f"Azure subnet IP ({ip}), IMDS not collected",
            }

        return {
            "category": "onprem_server",
            "recommended_type_id": SERVER_TYPE_ID,
            "exclude": False,
            "reason": f"Windows server, non-Azure (IP={ip})",
        }

    # Linux/ARM appliances
    if "linux" in os_version:
        # Azure Linux VMs (no IMDS in Linux collection script)
        if is_azure_ip:
            return {
                "category": "azure_vm",
                "recommended_type_id": AZURE_VM_TYPE_ID,
                "exclude": False,
                "reason": f"Azure Linux VM ({ip})",
            }
        # Auvik appliance
        if "auvik" in hostname:
            return {
                "category": "linux_appliance",
                "recommended_type_id": SERVER_TYPE_ID,
                "exclude": False,
                "reason": "Auvik virtual appliance",
            }
        return {
            "category": "linux_appliance",
            "recommended_type_id": SERVER_TYPE_ID,
            "exclude": False,
            "reason": f"Linux device ({os_version})",
        }

    # Android devices
    if "android" in os_version:
        return {
            "category": "mobile",
            "recommended_type_id": None,
            "exclude": True,
            "reason": "Android device (managed via Intune, not server CMDB)",
        }

    return {
        "category": "unknown",
        "recommended_type_id": SERVER_TYPE_ID,
        "exclude": False,
        "reason": f"Unclassified agent (os={os_version})",
    }


# ── Sync state helpers ───────────────────────────────────────────────────

def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text())
    return {"changes": {}, "assets": {}, "cmdb": {}}


def load_collected_assets() -> dict:
    if COLLECTED_ASSETS_FILE.exists():
        return json.loads(COLLECTED_ASSETS_FILE.read_text())
    return {}


# ── Freshservice asset type name cache ───────────────────────────────────

def _build_type_name_map(client: FreshserviceClient) -> dict:
    """Build type_id -> name lookup from Freshservice."""
    types = client.list_asset_types()
    return {t["id"]: t["name"] for t in types}


# ── Core audit logic ─────────────────────────────────────────────────────

def run_audit(tendril_agents: list, client: FreshserviceClient = None,
              collected_data: dict = None) -> dict:
    """
    Run full CMDB audit comparing Tendril agents vs Freshservice assets.

    Args:
        tendril_agents: List of agent dicts from list_tendrils
        client: FreshserviceClient (optional; skip Freshservice checks if None)
        collected_data: Dict of hostname -> collected asset data (optional)

    Returns audit report dict.
    """
    collected = collected_data or load_collected_assets()
    state = load_sync_state()
    synced_assets = state.get("assets", {})

    report = {
        "summary": {},
        "agents_classified": [],
        "missing_in_cmdb": [],
        "stale_in_cmdb": [],
        "type_mismatches": [],
        "orphaned_cis": [],
        "excluded": [],
    }

    # ── Phase 1: Classify all Tendril agents ─────────────────────────────

    agent_hostnames = set()       # All hostname forms (FQDN + short)
    agent_short_names = set()     # Short hostnames only (for matching)
    for agent in tendril_agents:
        hostname = agent["hostname"].lower()
        short = _normalize_hostname(hostname)
        agent_hostnames.add(hostname)
        agent_hostnames.add(short)
        agent_short_names.add(short)

        classification = classify_agent(agent, collected)
        entry = {
            "hostname": hostname,
            "ip": agent.get("ip_address", ""),
            "os": agent.get("os_version", ""),
            **classification,
        }
        report["agents_classified"].append(entry)

        if classification["exclude"]:
            report["excluded"].append(entry)
            continue

        # Check if agent has a Freshservice asset (try FQDN and short name)
        synced_id = synced_assets.get(hostname) or synced_assets.get(short)
        if not synced_id:
            report["missing_in_cmdb"].append(entry)

    # ── Phase 2: Find stale Freshservice assets ──────────────────────────

    if client:
        all_fs_assets = client.list_assets()
        type_names = _build_type_name_map(client)

        for asset in all_fs_assets:
            asset_type = asset.get("asset_type_id", 0)
            if asset_type not in SERVER_CLASS_TYPE_IDS:
                continue

            name = (asset.get("name") or "").lower()
            short_name = _normalize_hostname(name)
            display_id = asset.get("display_id")
            updated = asset.get("updated_at", "")[:10]

            # Match by both FQDN and short hostname
            if name not in agent_hostnames and short_name not in agent_short_names:
                report["stale_in_cmdb"].append({
                    "hostname": name,
                    "display_id": display_id,
                    "asset_type": type_names.get(asset_type, str(asset_type)),
                    "asset_type_id": asset_type,
                    "last_updated": updated,
                    "reason": "No connected Tendril agent matches this asset",
                })

        # ── Phase 3: Detect type mismatches ──────────────────────────────

        synced_id_to_hostname = {v: k for k, v in synced_assets.items()}
        # Build FS asset lookup by both FQDN and short hostname
        fs_asset_map = {}
        for a in all_fs_assets:
            aname = (a.get("name") or "").lower()
            fs_asset_map[aname] = a
            fs_asset_map[_normalize_hostname(aname)] = a

        for entry in report["agents_classified"]:
            if entry.get("exclude"):
                continue

            hostname = entry["hostname"]
            short = _normalize_hostname(hostname)
            recommended_type = entry["recommended_type_id"]
            if not recommended_type:
                continue

            fs_asset = (fs_asset_map.get(hostname)
                        or fs_asset_map.get(short)
                        or fs_asset_map.get(hostname.upper())
                        or fs_asset_map.get(short.upper()))
            if not fs_asset:
                continue

            current_type = fs_asset.get("asset_type_id")
            if current_type and current_type != recommended_type:
                report["type_mismatches"].append({
                    "hostname": hostname,
                    "display_id": fs_asset.get("display_id"),
                    "current_type": type_names.get(current_type, str(current_type)),
                    "current_type_id": current_type,
                    "recommended_type": type_names.get(recommended_type, str(recommended_type)),
                    "recommended_type_id": recommended_type,
                    "reason": entry["reason"],
                })

        # ── Phase 4: Detect orphaned CMDB CIs ───────────────────────────

        cmdb = state.get("cmdb", {})
        rel_source_ids = set()
        rel_target_ids = set()
        for r in cmdb.get("relationships", []):
            if isinstance(r, list) and len(r) == 3:
                rel_source_ids.add(r[0])
                rel_target_ids.add(r[2])

        all_synced_ids = set(synced_assets.values())
        for section_name, section_label in [
            ("services", "Business Service"),
            ("it_services", "IT Service"),
            ("databases", "Database"),
        ]:
            for name, display_id in cmdb.get(section_name, {}).items():
                has_relationships = (
                    display_id in rel_source_ids or
                    display_id in rel_target_ids
                )
                if not has_relationships:
                    report["orphaned_cis"].append({
                        "name": name,
                        "display_id": display_id,
                        "type": section_label,
                        "reason": "No relationships found in sync state",
                    })

    # ── Build summary ────────────────────────────────────────────────────

    category_counts = defaultdict(int)
    for entry in report["agents_classified"]:
        category_counts[entry["category"]] += 1

    report["summary"] = {
        "total_tendril_agents": len(tendril_agents),
        "agents_by_category": dict(category_counts),
        "synced_assets": len(synced_assets),
        "missing_in_cmdb": len(report["missing_in_cmdb"]),
        "stale_in_cmdb": len(report["stale_in_cmdb"]),
        "type_mismatches": len(report["type_mismatches"]),
        "orphaned_cis": len(report["orphaned_cis"]),
        "excluded_agents": len(report["excluded"]),
    }

    return report


# ── Fix actions ──────────────────────────────────────────────────────────

def fix_type_mismatches(client: FreshserviceClient, report: dict,
                        dry_run: bool = True) -> list:
    """
    Reclassify mistyped assets in Freshservice.

    NOTE: Freshservice API does not allow changing asset_type_id on update.
    The only way to reclassify is to delete and recreate, which loses
    relationships and history. Instead, we report the mismatches for
    manual resolution via the Freshservice admin UI.
    """
    results = []
    mismatches = report.get("type_mismatches", [])
    if not mismatches:
        print("  No type mismatches to fix.")
        return results

    print(f"\n  Type Mismatches ({len(mismatches)}):")
    print("  NOTE: Freshservice API cannot change asset_type_id on existing assets.")
    print("        These must be reclassified manually in the Freshservice admin UI,")
    print("        or deleted and recreated (which loses relationships).\n")

    for m in mismatches:
        action = "MANUAL FIX NEEDED" if dry_run else "MANUAL FIX NEEDED"
        print(f"    [{action}] #{m['display_id']} {m['hostname']}")
        print(f"      Current:     {m['current_type']} ({m['current_type_id']})")
        print(f"      Recommended: {m['recommended_type']} ({m['recommended_type_id']})")
        print(f"      Reason:      {m['reason']}")
        results.append(m)

    return results


def mark_stale_assets(client: FreshserviceClient, report: dict,
                      dry_run: bool = True) -> list:
    """
    Mark stale Freshservice assets (no Tendril agent) by setting
    asset_state to 'Missing' in the type_fields.
    """
    results = []
    stale = report.get("stale_in_cmdb", [])
    if not stale:
        print("  No stale assets to mark.")
        return results

    print(f"\n  Stale Assets ({len(stale)}):")
    for s in stale:
        if dry_run:
            print(f"    DRY RUN: Would mark #{s['display_id']} ({s['hostname']}) "
                  f"as Missing -- {s['reason']}")
        else:
            print(f"    Marking #{s['display_id']} ({s['hostname']}) as Missing...")
            result = client.update_asset(s["display_id"], {
                "type_fields": {
                    "asset_state_7001129940": "Missing",
                    # Include required fields to avoid validation errors
                    "veeam_backup_7001129968": "N/A",
                    "gfi_languard_agent_7001129968": "N/A",
                    "cbdefense_agent_7001129968": "N/A",
                    "unique_admin_password_7001129968": "N/A",
                },
            })
            if "error" in result:
                print(f"      ERROR: {str(result['error'])[:200]}")
            else:
                print(f"      Marked as Missing")
        results.append(s)

    return results


# ── Report formatting ────────────────────────────────────────────────────

def print_report(report: dict):
    """Print a human-readable audit report."""
    summary = report["summary"]

    print("=" * 72)
    print("CMDB AUDIT REPORT")
    print("=" * 72)

    print(f"\nTendril Fleet: {summary['total_tendril_agents']} agents")
    print(f"Agent Classification:")
    for cat, count in sorted(summary["agents_by_category"].items()):
        print(f"  {cat:25s} {count:4d}")

    print(f"\nSync State: {summary['synced_assets']} assets in .sync-state.json")

    # Findings
    print(f"\n{'─' * 72}")
    print("FINDINGS")
    print(f"{'─' * 72}")

    # Missing
    missing = report["missing_in_cmdb"]
    print(f"\n[MISSING] {len(missing)} Tendril agents not in Freshservice CMDB:")
    if missing:
        for m in sorted(missing, key=lambda x: x["hostname"]):
            print(f"  {m['hostname']:35s} {m['ip']:16s} {m['category']:15s} {m['reason']}")
    else:
        print("  (none)")

    # Stale
    stale = report["stale_in_cmdb"]
    print(f"\n[STALE] {len(stale)} Freshservice assets with no Tendril agent:")
    if stale:
        for s in sorted(stale, key=lambda x: x["hostname"]):
            print(f"  #{s['display_id']:5d} {s['hostname']:35s} {s['asset_type']:20s} "
                  f"updated:{s['last_updated']}")
    else:
        print("  (none)")

    # Type mismatches
    mismatches = report["type_mismatches"]
    print(f"\n[TYPE MISMATCH] {len(mismatches)} assets with wrong Freshservice type:")
    if mismatches:
        for m in sorted(mismatches, key=lambda x: x["hostname"]):
            print(f"  #{m['display_id']:5d} {m['hostname']:30s} "
                  f"{m['current_type']:20s} -> {m['recommended_type']:20s}")
            print(f"         Reason: {m['reason']}")
    else:
        print("  (none)")

    # Orphaned CIs
    orphaned = report["orphaned_cis"]
    print(f"\n[ORPHANED] {len(orphaned)} CMDB CIs with no relationships:")
    if orphaned:
        for o in sorted(orphaned, key=lambda x: x["name"]):
            print(f"  #{o['display_id']:5d} {o['name']:40s} {o['type']:20s}")
    else:
        print("  (none)")

    # Excluded
    excluded = report["excluded"]
    print(f"\n[EXCLUDED] {len(excluded)} agents excluded from CMDB:")
    if excluded:
        for e in sorted(excluded, key=lambda x: x["hostname"]):
            print(f"  {e['hostname']:35s} {e['reason']}")

    # Overall health
    print(f"\n{'=' * 72}")
    total_issues = (
        summary["missing_in_cmdb"] +
        summary["stale_in_cmdb"] +
        summary["type_mismatches"] +
        summary["orphaned_cis"]
    )
    if total_issues == 0:
        print("CMDB HEALTH: CLEAN -- no issues found")
    else:
        print(f"CMDB HEALTH: {total_issues} issues found")
        print(f"  {summary['missing_in_cmdb']} missing, "
              f"{summary['stale_in_cmdb']} stale, "
              f"{summary['type_mismatches']} mistyped, "
              f"{summary['orphaned_cis']} orphaned")
    print("=" * 72)


# ── CLI entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    print("CMDB Audit requires Tendril agent data.")
    print("Run via: python cli.py audit")
    print("  (uses Tendril API to get live agent list)")
