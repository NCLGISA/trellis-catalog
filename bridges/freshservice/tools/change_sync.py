"""
Change Request Sync

Pushes parsed CR documents from docs/cr/cr-*.md into Freshservice as
Change Requests via the REST API v2.

Features:
  - Deduplication via local sync-state tracking
  - Adds planning sections as structured Change Notes
  - Links affected servers as CMDB assets
  - Auto-archives synced CRs to docs/cr/processed/
  - Dry-run mode for previewing payloads
"""

import json
import os
import shutil
from pathlib import Path
from freshservice_client import FreshserviceClient
from cr_parser import (parse_cr_file, parse_all_crs, to_freshservice_change,
                       _markdown_to_simple_html)
from asset_sync import load_sync_state as load_asset_state


SYNC_STATE_FILE = Path(__file__).parent / ".sync-state.json"

# Freshservice IDs (override via environment variables)
DEFAULT_AGENT_ID = int(os.environ.get("FRESHSERVICE_AGENT_ID", "7000348606"))
IT_DEPARTMENT_ID = int(os.environ.get("FRESHSERVICE_DEPARTMENT_ID", "7000161748"))


def load_sync_state() -> dict:
    """Load the mapping of CR numbers to Freshservice Change IDs."""
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text())
    return {"changes": {}, "assets": {}}


def save_sync_state(state: dict):
    """Persist the sync state."""
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))


def sync_single_change(client: FreshserviceClient, cr_file: str,
                        dry_run: bool = False) -> dict:
    """
    Parse a single CR file and create/update it in Freshservice.

    Returns the Freshservice change response or dry-run payload.
    """
    cr = parse_cr_file(cr_file)
    payload = to_freshservice_change(
        cr,
        requester_id=DEFAULT_AGENT_ID,
        department_id=IT_DEPARTMENT_ID,
    )

    # Add agent (assigned to default agent)
    payload["agent_id"] = DEFAULT_AGENT_ID

    state = load_sync_state()
    existing_id = state["changes"].get(cr["cr_number"])

    if dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN: {cr['cr_number']}")
        print(f"{'='*60}")
        print(f"  Title:    {cr['title']}")
        print(f"  Status:   {cr['status']} -> FS {payload['status']}")
        print(f"  Priority: {cr['priority']} -> FS {payload['priority']}")
        print(f"  Risk:     {cr['risk_level']} -> FS {payload['risk']}")
        print(f"  Type:     {cr['change_type']} -> FS {payload['change_type']}")
        print(f"  Dates:    {payload.get('planned_start_date', '-')} to {payload.get('planned_end_date', '-')}")
        print(f"  Servers:  {len(cr['affected_servers'])} affected")
        print(f"  Existing: {'#' + str(existing_id) if existing_id else 'NEW'}")
        print(f"\n  Payload (description truncated):")
        preview = dict(payload)
        desc = preview.pop("description", "")
        print(f"  {json.dumps(preview, indent=4)}")
        print(f"  description: ({len(desc)} chars HTML)")
        return {"dry_run": True, "cr": cr, "payload": payload}

    success = False

    if existing_id:
        print(f"  Updating existing change #{existing_id} for {cr['cr_number']}...")
        result = client.update_change(existing_id, payload)
        change = result.get("change", result)
        print(f"  Updated: #{change.get('id', existing_id)}")
        success = True
    else:
        print(f"  Creating new change for {cr['cr_number']}...")
        result = client.create_change(payload)
        change = result.get("change", {})
        change_id = change.get("id")
        if change_id:
            print(f"  Created: #{change_id}")
            # Save mapping
            state["changes"][cr["cr_number"]] = change_id
            save_sync_state(state)

            # Add planning section notes (since the API can't write
            # to the Planning fields directly)
            _add_planning_notes(client, change_id, cr)

            # Link affected servers as CMDB assets
            _link_affected_assets(client, change_id, cr)
            success = True
        else:
            print(f"  ERROR: {result}")

    # Archive the CR file to processed/ on success
    if success:
        _archive_cr_file(cr_file)

    return result


def _archive_cr_file(cr_file: str):
    """Move a synced CR file to the processed/ subfolder."""
    src = Path(cr_file)
    if not src.exists():
        return
    archive_dir = src.parent / "processed"
    archive_dir.mkdir(exist_ok=True)
    dest = archive_dir / src.name
    shutil.move(str(src), str(dest))
    print(f"  Archived -> processed/{dest.name}")


def _add_planning_notes(client: FreshserviceClient, change_id: int, cr: dict):
    """
    Add structured notes for each Planning section area.
    Since the Freshservice Change API doesn't support writing to the
    Planning fields (Reason, Impact, Rollout, Backout) directly, we
    create dedicated notes that map to each planning area.
    """
    planning_sections = [
        ("Reason for Change", cr.get("reason_for_change", "")),
        ("Impact Analysis", cr.get("impact_analysis", "")),
        ("Rollout Plan", cr.get("implementation_plan", "")),
        ("Backout Plan", cr.get("rollback_procedure", "")),
    ]

    for title, content in planning_sections:
        if not content:
            continue
        # Convert the markdown content to HTML
        html_content = _markdown_to_simple_html(content)
        note_body = (
            f'<h2 style="color:#2c5282; border-bottom:2px solid #2c5282; '
            f'padding-bottom:4px;">{title}</h2>\n{html_content}'
        )
        print(f"  Adding note: {title} ({len(content)} chars)...")
        client.create_change_note(change_id, note_body)


def _link_affected_assets(client: FreshserviceClient, change_id: int, cr: dict):
    """
    Link affected servers from the CR to the Freshservice change as assets.
    Uses the sync-state to resolve hostnames to Freshservice display_ids.
    """
    servers = cr.get("affected_servers", [])
    if not servers:
        return

    asset_state = load_asset_state()
    asset_map = asset_state.get("assets", {})

    asset_list = []
    missing = []
    for hostname in servers:
        display_id = asset_map.get(hostname.lower())
        if display_id:
            asset_list.append({"display_id": display_id})
        else:
            missing.append(hostname)

    if not asset_list:
        print(f"  No CMDB assets found for {len(servers)} servers")
        return

    print(f"  Linking {len(asset_list)} assets (of {len(servers)} affected servers)...")
    resp = client.put(f"changes/{change_id}", json={"assets": asset_list})
    if resp.status_code == 200:
        linked = resp.json().get("change", {}).get("assets", [])
        print(f"  Linked {len(linked)} assets")
    else:
        print(f"  Error linking assets: {resp.status_code} {resp.text[:200]}")

    if missing:
        print(f"  Missing from CMDB: {missing}")


def sync_all_changes(client: FreshserviceClient, docs_dir: str = None,
                      dry_run: bool = False) -> list:
    """Sync all CR documents to Freshservice."""
    if docs_dir is None:
        docs_dir = str(Path(__file__).resolve().parents[2] / "docs" / "cr")

    cr_files = sorted(Path(docs_dir).glob("cr-*.md"))
    results = []
    for f in cr_files:
        print(f"\n── {f.name} ──")
        result = sync_single_change(client, str(f), dry_run=dry_run)
        results.append(result)
    return results


def show_sync_status():
    """Display current sync state."""
    state = load_sync_state()
    changes = state.get("changes", {})
    assets = state.get("assets", {})
    print(f"\nSync State ({SYNC_STATE_FILE}):")
    print(f"  Changes synced: {len(changes)}")
    for cr_num, fs_id in sorted(changes.items()):
        print(f"    {cr_num} -> Freshservice #{fs_id}")
    print(f"  Assets synced: {len(assets)}")
    for hostname, fs_id in sorted(list(assets.items())[:10]):
        print(f"    {hostname} -> Freshservice #{fs_id}")
    if len(assets) > 10:
        print(f"    ... and {len(assets) - 10} more")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        client = FreshserviceClient()
        sync_all_changes(client, dry_run=True)
    elif len(sys.argv) > 1 and sys.argv[1] == "--status":
        show_sync_status()
    else:
        print("Usage:")
        print("  python change_sync.py --dry-run   # Preview all changes")
        print("  python change_sync.py --status    # Show sync status")
        print("  Use cli.py sync-changes for actual sync")
