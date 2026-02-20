#!/usr/bin/env python3
"""
Freshservice Integration CLI

Syncs IT infrastructure data into Freshservice:
  - Multi-type server assets from Tendril agent discovery
  - Change Requests from docs/cr/cr-*.md markdown files
  - CMDB CIs and relationships from docs/servers/*.md manifests
  - CMDB audit and reconciliation against live Tendril fleet

Usage:
    cd scripts/freshservice
    source .venv/bin/activate

    python cli.py status                     # Show what's synced
    python cli.py discover                   # Read-only Freshservice discovery

    python cli.py audit                      # Full CMDB audit report
    python cli.py audit --json               # Machine-readable JSON
    python cli.py audit --fix-types          # Show type reclassification plan
    python cli.py audit --mark-stale         # Mark stale assets as Missing
    python cli.py audit --mark-stale --no-dry-run  # Actually mark stale

    python cli.py sync-changes               # Sync all CR docs to Freshservice
    python cli.py sync-changes --dry-run     # Preview without pushing
    python cli.py sync-changes --file FILE   # Sync a single CR file

    python cli.py sync-assets                # Push collected assets to CMDB
    python cli.py sync-assets --dry-run      # Preview without pushing
    python cli.py sync-assets --host HOST    # Sync a single host

    python cli.py collect-assets             # Re-collect data from Tendril
                                             # (requires MCP -- use from Cursor)
"""

import sys
import json
import argparse
from pathlib import Path
from freshservice_client import FreshserviceClient


# ── status ──────────────────────────────────────────────────────────────

def cmd_status(args):
    """Show current sync state for both changes and assets."""
    from change_sync import load_sync_state

    state = load_sync_state()
    changes = state.get("changes", {})
    assets = state.get("assets", {})

    print("=" * 70)
    print("FRESHSERVICE SYNC STATUS")
    print("=" * 70)

    print(f"\n-- Changes: {len(changes)} synced --")
    for cr_num, fs_id in sorted(changes.items()):
        print(f"  {cr_num:50s} -> Change #{fs_id}")

    print(f"\n-- Assets: {len(assets)} synced --")
    for hostname, fs_id in sorted(assets.items()):
        print(f"  {hostname:20s} -> Asset #{fs_id}")

    # Check for unsynced CR files in docs/cr/
    cr_dir = Path(__file__).resolve().parents[2] / "docs" / "cr"
    cr_files = sorted(cr_dir.glob("cr-*.md"))
    from cr_parser import parse_cr_file
    pending = []
    for f in cr_files:
        cr = parse_cr_file(str(f))
        if cr.get("cr_number") not in changes:
            pending.append((f.name, cr.get("cr_number", "?")))
    if pending:
        print(f"\n-- Pending CRs in docs/cr/ ({len(pending)}) --")
        for fname, cr_num in pending:
            print(f"  {fname:55s} ({cr_num})")
    else:
        print(f"\n  No pending CR files in docs/cr/")

    # Show processed CR count
    processed_dir = cr_dir / "processed"
    if processed_dir.exists():
        processed_files = sorted(processed_dir.glob("cr-*.md"))
        print(f"\n-- Processed CRs in docs/cr/processed/ ({len(processed_files)}) --")
        for f in processed_files:
            print(f"  {f.name}")
    else:
        print(f"\n  No processed/ folder yet.")

    # Check for collected but unsynced assets
    collected_file = Path(__file__).parent / ".collected-assets.json"
    if collected_file.exists():
        collected = json.loads(collected_file.read_text())
        unsynced = [h for h in collected if h.lower() not in assets]
        print(f"\n-- Collected assets: {len(collected)} total, {len(unsynced)} unsynced --")
        if unsynced:
            for h in sorted(unsynced)[:10]:
                print(f"  {h}")
            if len(unsynced) > 10:
                print(f"  ... and {len(unsynced) - 10} more")
    else:
        print(f"\n  No .collected-assets.json found. Run collect-assets first.")

    # CMDB CIs (business services, IT services, databases)
    cmdb = state.get("cmdb", {})
    svc_count = len(cmdb.get("services", {}))
    it_svc_count = len(cmdb.get("it_services", {}))
    db_count = len(cmdb.get("databases", {}))
    rel_count = len(cmdb.get("relationships", []))
    total_cis = svc_count + it_svc_count + db_count
    if total_cis > 0:
        print(f"\n-- CMDB CIs: {total_cis} synced ({svc_count} business services, "
              f"{it_svc_count} IT services, {db_count} databases) --")
        print(f"  Relationships tracked: {rel_count}")
    else:
        print(f"\n  No CMDB CIs synced yet. Run sync-cmdb to populate.")


# ── discover ────────────────────────────────────────────────────────────

def cmd_discover(args):
    """Read-only discovery of the Freshservice instance."""
    client = FreshserviceClient()

    print("=" * 70)
    print("FRESHSERVICE INSTANCE DISCOVERY")
    print(f"Domain: {client.domain}")
    print("=" * 70)

    print("\n-- Connection Test --")
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"  FAILED: {conn}")
        print("  Check FRESHSERVICE_API_KEY and FRESHSERVICE_DOMAIN in .env")
        return
    print(f"  Connected as: {conn['name']} ({conn['email']})")
    print(f"  Agent ID: {conn['agent_id']}")

    print("\n-- Departments --")
    for d in client.list_departments():
        print(f"  [{d['id']}] {d['name']}")

    print("\n-- Asset Types --")
    for at in client.list_asset_types():
        print(f"  [{at['id']}] {at['name']}")

    print("\n-- Existing Assets (first 30) --")
    resp = client.get("assets", params={"per_page": 30})
    if resp.status_code == 200:
        for a in resp.json().get("assets", []):
            print(f"  [{a['display_id']}] {a['name']} (type: {a.get('asset_type_id', '?')})")

    print("\n-- Existing Changes (first 20) --")
    resp = client.get("changes", params={"per_page": 20})
    if resp.status_code == 200:
        for c in resp.json().get("changes", []):
            print(f"  [#{c['id']}] {c.get('subject', '?')[:60]}")

    print("\n-- Change Field Reference --")
    print("  status:      1=Open 2=Planning 3=Awaiting Approval 4=Pending Release 5=Pending Review 6=Closed")
    print("  priority:    1=Low 2=Medium 3=High 4=Urgent")
    print("  impact:      1=Low 2=Medium 3=High")
    print("  risk:        1=Low 2=Medium 3=High 4=Very High")
    print("  change_type: 1=Minor 2=Standard 3=Major 4=Emergency")


# ── sync-changes ────────────────────────────────────────────────────────

def cmd_sync_changes(args):
    """Sync CR markdown files to Freshservice Change Requests."""
    from change_sync import sync_single_change, sync_all_changes, load_sync_state

    client = FreshserviceClient()
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"Connection failed: {conn}")
        return

    print(f"Connected as: {conn['name']}")

    if args.file:
        # Single file mode
        filepath = Path(args.file)
        if not filepath.exists():
            # Try relative to docs/cr/
            filepath = Path(__file__).resolve().parents[2] / "docs" / "cr" / args.file
        if not filepath.exists():
            print(f"File not found: {args.file}")
            return
        print(f"\nSyncing: {filepath.name}")
        sync_single_change(client, str(filepath), dry_run=args.dry_run)
    else:
        # All files
        cr_dir = str(Path(__file__).resolve().parents[2] / "docs" / "cr")
        sync_all_changes(client, docs_dir=cr_dir, dry_run=args.dry_run)

    if not args.dry_run:
        state = load_sync_state()
        print(f"\nTotal changes synced: {len(state.get('changes', {}))}")


# ── sync-assets ─────────────────────────────────────────────────────────

def cmd_sync_assets(args):
    """Push collected asset data to Freshservice CMDB."""
    from asset_sync import sync_single_asset, sync_all_assets, load_sync_state

    collected_file = Path(__file__).parent / ".collected-assets.json"
    if not collected_file.exists():
        print("No .collected-assets.json found.")
        print("Collect data first using Tendril MCP (collect-assets from Cursor),")
        print("or place a .collected-assets.json file manually.")
        return

    collected = json.loads(collected_file.read_text())
    print(f"Loaded {len(collected)} agents from .collected-assets.json")

    client = FreshserviceClient()
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"Connection failed: {conn}")
        return
    print(f"Connected as: {conn['name']}")

    if args.host:
        hostname = args.host.lower()
        if hostname not in collected:
            print(f"Host '{args.host}' not found in collected data.")
            print(f"Available: {', '.join(sorted(collected.keys())[:10])}...")
            return
        data = collected[hostname]
        print(f"\nSyncing: {hostname}")
        sync_single_asset(client, data, dry_run=args.dry_run)
    else:
        sync_all_assets(client, collected, dry_run=args.dry_run)

    if not args.dry_run:
        state = load_sync_state()
        print(f"\nTotal assets synced: {len(state.get('assets', {}))}")


# ── sync-cmdb ───────────────────────────────────────────────────────────

def cmd_sync_cmdb(args):
    """Sync CMDB CIs and relationships from server doc manifests."""
    from cmdb_sync import sync_cmdb, show_cmdb_status

    if args.status_only:
        show_cmdb_status()
        return

    client = FreshserviceClient()
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"Connection failed: {conn}")
        return
    print(f"Connected as: {conn['name']}")

    docs_dir = str(Path(__file__).resolve().parents[2] / "docs" / "servers")
    sync_cmdb(client, docs_dir=docs_dir, dry_run=args.dry_run)


# ── audit ────────────────────────────────────────────────────────────────

def cmd_audit(args):
    """Run CMDB audit comparing Tendril agents vs Freshservice assets."""
    from cmdb_audit import (
        run_audit, print_report, fix_type_mismatches, mark_stale_assets,
        load_collected_assets,
    )

    # Load Tendril agent data from .collected-assets.json to get
    # classification hints (is_azure, is_vmware_guest, etc.)
    collected_data = load_collected_assets()

    # Load Tendril agent list from a cached file or require --agents-file
    agents_file = Path(__file__).parent / ".tendril-agents.json"
    if args.agents_file:
        agents_file = Path(args.agents_file)

    if not agents_file.exists():
        print("No Tendril agent data available.")
        print("")
        print("The audit command needs a .tendril-agents.json file with the")
        print("output of list_tendrils. Generate it from Cursor by asking:")
        print("  'Save the Tendril agent list to")
        print("   scripts/freshservice/.tendril-agents.json'")
        print("")
        print("Or provide a file: python cli.py audit --agents-file FILE")
        return

    agents = json.loads(agents_file.read_text())
    if isinstance(agents, dict) and "agents" in agents:
        agents = agents["agents"]
    print(f"Loaded {len(agents)} Tendril agents from {agents_file.name}")

    # Connect to Freshservice
    client = FreshserviceClient()
    conn = client.test_connection()
    if not conn.get("ok"):
        print(f"Connection failed: {conn}")
        return
    print(f"Connected as: {conn['name']}")

    # Run audit
    report = run_audit(agents, client=client, collected_data=collected_data)

    # Output
    if args.json_output:
        print(json.dumps(report, indent=2, default=str))
        return

    print_report(report)

    # Action modes
    if args.fix_types:
        print(f"\n{'─' * 72}")
        print("TYPE RECLASSIFICATION PLAN")
        print(f"{'─' * 72}")
        fix_type_mismatches(client, report, dry_run=True)

    if args.mark_stale:
        print(f"\n{'─' * 72}")
        print("STALE ASSET MARKING")
        print(f"{'─' * 72}")
        is_dry = not args.no_dry_run
        if is_dry:
            print("  (dry-run mode -- add --no-dry-run to actually mark assets)")
        mark_stale_assets(client, report, dry_run=is_dry)


# ── collect-assets ──────────────────────────────────────────────────────

def cmd_collect_assets(args):
    """Guidance for collecting asset data from Tendril agents."""
    collected_file = Path(__file__).parent / ".collected-assets.json"
    if collected_file.exists():
        collected = json.loads(collected_file.read_text())
        print(f"Existing .collected-assets.json has {len(collected)} agents.")
    else:
        print("No .collected-assets.json exists yet.")

    print("""
Asset collection uses Tendril MCP to run PowerShell on each agent.
This must be done from within Cursor using the Tendril MCP tools.

To collect, ask Cursor AI to:
  "Collect asset data from all Tendril agents and save to
   scripts/freshservice/.collected-assets.json"

The collection script gathers:
  - WMI/CIM: hostname, domain, OS, memory, CPU, disk, serial, UUID
  - Azure IMDS: subscription, resource group, VM size, location
  - Tendril Registry: Application, Department, Lifecycle, ServerType, Vendor

After collection, run:
  python cli.py sync-assets
""")


# ── main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Freshservice Integration CLI - IT department",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py status                       Show sync state
  python cli.py audit                        Full CMDB reconciliation report
  python cli.py audit --mark-stale           Preview stale asset retirement
  python cli.py audit --fix-types            Show type reclassification plan
  python cli.py sync-changes                 Push all CRs to Freshservice
  python cli.py sync-changes --dry-run       Preview without pushing
  python cli.py sync-changes --file cr-2026-0205-pwsh7-dev-servers.md
  python cli.py sync-assets                  Push all assets to CMDB
  python cli.py sync-assets --host is01s064  Push a single host
  python cli.py sync-cmdb                    Sync services/apps/DBs + relationships
  python cli.py sync-cmdb --dry-run          Preview CMDB sync
  python cli.py sync-cmdb --status           Show CMDB sync state
  python cli.py discover                     Read-only Freshservice discovery
""")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub_status = subparsers.add_parser("status", help="Show current sync state")
    sub_status.set_defaults(func=cmd_status)

    # audit
    sub_audit = subparsers.add_parser("audit",
        help="CMDB audit: reconcile Tendril agents vs Freshservice assets")
    sub_audit.add_argument("--json", dest="json_output", action="store_true",
        help="Output machine-readable JSON instead of text report")
    sub_audit.add_argument("--fix-types", action="store_true",
        help="Show type reclassification plan for mistyped assets")
    sub_audit.add_argument("--mark-stale", action="store_true",
        help="Mark stale Freshservice assets as Missing (dry-run by default)")
    sub_audit.add_argument("--no-dry-run", action="store_true",
        help="Actually apply changes (use with --mark-stale)")
    sub_audit.add_argument("--agents-file", type=str,
        help="Path to Tendril agents JSON file (default: .tendril-agents.json)")
    sub_audit.set_defaults(func=cmd_audit)

    # discover
    sub_discover = subparsers.add_parser("discover",
        help="Read-only discovery of Freshservice instance")
    sub_discover.set_defaults(func=cmd_discover)

    # sync-changes
    sub_changes = subparsers.add_parser("sync-changes",
        help="Sync CR docs to Freshservice Change Requests")
    sub_changes.add_argument("--dry-run", action="store_true",
        help="Preview payloads without creating/updating")
    sub_changes.add_argument("--file", type=str,
        help="Sync a single CR file (name or path)")
    sub_changes.set_defaults(func=cmd_sync_changes)

    # sync-assets
    sub_assets = subparsers.add_parser("sync-assets",
        help="Push collected assets to Freshservice CMDB")
    sub_assets.add_argument("--dry-run", action="store_true",
        help="Preview payloads without creating/updating")
    sub_assets.add_argument("--host", type=str,
        help="Sync a single host by hostname")
    sub_assets.set_defaults(func=cmd_sync_assets)

    # sync-cmdb
    sub_cmdb = subparsers.add_parser("sync-cmdb",
        help="Sync CMDB CIs and relationships from server doc manifests")
    sub_cmdb.add_argument("--dry-run", action="store_true",
        help="Preview CIs and relationships without creating/updating")
    sub_cmdb.add_argument("--status", dest="status_only", action="store_true",
        help="Show current CMDB sync state only")
    sub_cmdb.set_defaults(func=cmd_sync_cmdb)

    # collect-assets
    sub_collect = subparsers.add_parser("collect-assets",
        help="Info on collecting asset data from Tendril agents")
    sub_collect.set_defaults(func=cmd_collect_assets)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
