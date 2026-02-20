"""
CMDB Relationship Sync

Creates non-server CIs (Business Services, IT Services, MSSQL Databases)
and relationships between all CIs in Freshservice, based on CMDB Manifest
sections parsed from server documentation.

Workflow:
  1. Parse all docs/servers/*.md for CMDB Manifest sections
  2. Aggregate unique CIs and relationships
  3. Resolve existing assets (servers already synced via asset_sync)
  4. Create or update Business Service, IT Service, MSSQL CIs
  5. Create relationships between CIs

CI type mapping:
  - Business Services  -> Freshservice "Business Service" (no product required)
  - IT Services        -> Freshservice "IT Service" (no product required)
  - Databases          -> Freshservice "MSSQL" (requires product_7001129941)

Sync state is tracked in .sync-state.json under a "cmdb" key.
"""

import json
from pathlib import Path

import os

try:
    from freshservice_client import FreshserviceClient
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from freshservice_client import FreshserviceClient

from cmdb_parser import parse_all_manifests, collect_all_cis


# ── Freshservice IDs ────────────────────────────────────────────────────

DEFAULT_AGENT_ID = int(os.environ.get("FRESHSERVICE_AGENT_ID", "7000348606"))
IT_DEPARTMENT_ID = int(os.environ.get("FRESHSERVICE_DEPARTMENT_ID", "7000161748"))

# CI Type IDs
BUSINESS_SERVICE_TYPE_ID = 7001129963
IT_SERVICE_TYPE_ID = 7001129964
MSSQL_TYPE_ID = 7001129975

# Product IDs (required for MSSQL type)
SQL_SERVER_2016_PRODUCT_ID = 7001008979  # "SQL Server 2016" (only DB product available)

# Relationship Type IDs
REL_DEPENDS_ON = 7000455383        # Depends On / Used By
REL_SENDS_DATA_TO = 7000455385     # Sends Data To / Receives Data From
REL_RUNS_ON = 7000455386           # Runs on / Runs
REL_HOSTED_ON = 7000455393         # Hosted On / Hosts

RELATIONSHIP_TYPE_MAP = {
    "depends on": REL_DEPENDS_ON,
    "used by": REL_DEPENDS_ON,
    "sends data to": REL_SENDS_DATA_TO,
    "receives data from": REL_SENDS_DATA_TO,
    "runs on": REL_RUNS_ON,
    "runs": REL_RUNS_ON,
    "hosted on": REL_HOSTED_ON,
    "hosts": REL_HOSTED_ON,
}

# Valid Freshservice impact values (strings)
VALID_IMPACTS = {"low", "medium", "high"}

SYNC_STATE_FILE = Path(__file__).parent / ".sync-state.json"


# ── Sync state ──────────────────────────────────────────────────────────

def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text())
    return {"changes": {}, "assets": {}, "cmdb": {}}


def save_sync_state(state: dict):
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))


def _get_cmdb_state(state: dict) -> dict:
    """Get or initialize the cmdb subsection of sync state."""
    if "cmdb" not in state:
        state["cmdb"] = {}
    cmdb = state["cmdb"]
    cmdb.setdefault("services", {})      # name -> display_id
    cmdb.setdefault("it_services", {})   # name -> display_id
    cmdb.setdefault("databases", {})     # name -> display_id
    cmdb.setdefault("relationships", []) # [(source_id, rel_type_id, target_id)]
    return cmdb


# ── CI resolution ───────────────────────────────────────────────────────

def _resolve_ci_id(name: str, state: dict) -> int | None:
    """
    Look up a CI's Freshservice display_id by name.
    Checks assets (servers), then cmdb services, apps, databases.
    """
    # Check server assets (hostname -> display_id)
    name_lower = name.lower()
    assets = state.get("assets", {})
    if name_lower in assets:
        return assets[name_lower]

    # Check CMDB CIs
    cmdb = _get_cmdb_state(state)
    for section in ["services", "it_services", "databases"]:
        if name in cmdb[section]:
            return cmdb[section][name]

    return None


def _find_existing_ci(client: FreshserviceClient, name: str) -> dict | None:
    """Search Freshservice for an existing asset by display name."""
    resp = client.get("assets", params={"query": f"\"name:'{name}'\""})
    if resp.status_code == 200:
        assets = resp.json().get("assets", [])
        if assets:
            return assets[0]
    return None


# ── CI creation ─────────────────────────────────────────────────────────

def _create_or_update_ci(client: FreshserviceClient, name: str,
                          asset_type_id: int, type_fields: dict,
                          description: str = "",
                          impact: str = "medium",
                          state: dict = None,
                          state_section: str = "",
                          dry_run: bool = False) -> int | None:
    """
    Create or update a CI in Freshservice.
    Returns the display_id on success.
    """
    cmdb = _get_cmdb_state(state)
    existing_id = cmdb.get(state_section, {}).get(name)

    payload = {
        "name": name,
        "asset_type_id": asset_type_id,
        "description": description,
        "impact": impact.lower() if impact.lower() in VALID_IMPACTS else "medium",
        "agent_id": DEFAULT_AGENT_ID,
        "department_id": IT_DEPARTMENT_ID,
        "type_fields": type_fields,
    }

    if dry_run:
        action = f"UPDATE #{existing_id}" if existing_id else "CREATE"
        print(f"    DRY RUN [{action}]: {name} (type_id={asset_type_id})")
        return existing_id

    if existing_id:
        # Update existing
        print(f"    Updating #{existing_id}: {name}...")
        update_payload = dict(payload)
        update_payload.pop("asset_type_id", None)
        result = client.update_asset(existing_id, update_payload)
        asset = result.get("asset", result)
        print(f"    Updated: #{asset.get('display_id', existing_id)}")
        return existing_id
    else:
        # Check if it exists in Freshservice but not in our state
        existing = _find_existing_ci(client, name)
        if existing:
            display_id = existing["display_id"]
            print(f"    Found existing #{display_id}: {name}, updating...")
            update_payload = dict(payload)
            update_payload.pop("asset_type_id", None)
            client.update_asset(display_id, update_payload)
            cmdb[state_section][name] = display_id
            save_sync_state(state)
            return display_id

        # Create new
        print(f"    Creating: {name}...")
        result = client.create_asset(payload)
        asset = result.get("asset", {})
        display_id = asset.get("display_id")
        if display_id:
            print(f"    Created: #{display_id}")
            cmdb[state_section][name] = display_id
            save_sync_state(state)
            return display_id
        else:
            print(f"    ERROR: {result}")
            return None


# ── Sync orchestration ──────────────────────────────────────────────────

def sync_business_services(client: FreshserviceClient, all_cis: dict,
                            state: dict, dry_run: bool = False):
    """Create/update Business Service CIs."""
    services = all_cis["business_services"]
    if not services:
        return

    print(f"\n-- Business Services ({len(services)}) --")
    for name, info in sorted(services.items()):
        type_fields = {
            "health_7001129938": "Operational",
        }

        _create_or_update_ci(
            client, name, BUSINESS_SERVICE_TYPE_ID, type_fields,
            description=f"<p><strong>Department:</strong> {info.get('department', 'IT')}</p>"
                        f"<p><em>Auto-synced from CMDB Manifest</em></p>",
            impact=info.get("impact", "medium"),
            state=state,
            state_section="services",
            dry_run=dry_run,
        )


def sync_it_services(client: FreshserviceClient, all_cis: dict,
                      state: dict, dry_run: bool = False):
    """Create/update IT Service CIs (no product required)."""
    it_services = all_cis.get("it_services", {})
    if not it_services:
        return

    # Filter out items that are also Business Services (avoid dupes)
    svc_names = set(all_cis["business_services"].keys())
    to_sync = {k: v for k, v in it_services.items() if k not in svc_names}

    if not to_sync:
        return

    print(f"\n-- IT Services ({len(to_sync)}) --")
    for name, info in sorted(to_sync.items()):
        type_fields = {
            "health_7001129938": "Operational",
        }

        desc_parts = []
        if info.get("vendor"):
            desc_parts.append(f"<p><strong>Vendor:</strong> {info['vendor']}</p>")
        if info.get("version") and info["version"] != "-":
            desc_parts.append(
                f"<p><strong>Version:</strong> {info['version']}</p>")
        if info.get("installed_on"):
            desc_parts.append(
                f"<p><strong>Installed On:</strong> {info['installed_on']}</p>")
        desc_parts.append("<p><em>Auto-synced from CMDB Manifest</em></p>")

        _create_or_update_ci(
            client, name, IT_SERVICE_TYPE_ID, type_fields,
            description="\n".join(desc_parts),
            impact="medium",
            state=state,
            state_section="it_services",
            dry_run=dry_run,
        )


def sync_databases(client: FreshserviceClient, all_cis: dict,
                    state: dict, dry_run: bool = False):
    """Create/update MSSQL Database CIs (requires product_7001129941)."""
    databases = all_cis["databases"]
    if not databases:
        return

    print(f"\n-- Databases ({len(databases)}) --")
    for name, info in sorted(databases.items()):
        type_fields = {
            "product_7001129941": SQL_SERVER_2016_PRODUCT_ID,
            "database_type_7001129960": info.get("type", "MSSQL"),
        }

        desc_parts = []
        if info.get("instance"):
            desc_parts.append(
                f"<p><strong>Instance:</strong> {info['instance']}</p>")
        if info.get("size") and info["size"] != "-":
            desc_parts.append(f"<p><strong>Size:</strong> {info['size']}</p>")
        if info.get("environment"):
            desc_parts.append(
                f"<p><strong>Environment:</strong> {info['environment']}</p>")
        desc_parts.append("<p><em>Auto-synced from CMDB Manifest</em></p>")

        _create_or_update_ci(
            client, name, MSSQL_TYPE_ID, type_fields,
            description="\n".join(desc_parts),
            impact="medium",
            state=state,
            state_section="databases",
            dry_run=dry_run,
        )


def sync_relationships(client: FreshserviceClient, all_cis: dict,
                        state: dict, dry_run: bool = False):
    """Create relationships between CIs."""
    relationships = all_cis["relationships"]
    if not relationships:
        return

    cmdb = _get_cmdb_state(state)
    existing_rels = set()
    for r in cmdb.get("relationships", []):
        if isinstance(r, list) and len(r) == 3:
            existing_rels.add(tuple(r))

    print(f"\n-- Relationships ({len(relationships)}) --")
    created = 0
    skipped = 0
    failed = 0
    pending = []

    for source_name, rel_type_str, target_name in relationships:
        rel_type_id = RELATIONSHIP_TYPE_MAP.get(rel_type_str.lower())
        if not rel_type_id:
            print(f"    SKIP: Unknown relationship type '{rel_type_str}'")
            skipped += 1
            continue

        source_id = _resolve_ci_id(source_name, state)
        target_id = _resolve_ci_id(target_name, state)

        if not source_id:
            print(f"    SKIP: Source '{source_name}' not found in CMDB")
            skipped += 1
            continue
        if not target_id:
            print(f"    SKIP: Target '{target_name}' not found in CMDB")
            skipped += 1
            continue

        # Check if already created
        rel_key = (source_id, rel_type_id, target_id)
        if rel_key in existing_rels:
            skipped += 1
            continue

        if dry_run:
            print(f"    DRY RUN: #{source_id} ({source_name}) "
                  f"--[{rel_type_str}]--> #{target_id} ({target_name})")
            continue

        pending.append({
            "rel_key": rel_key,
            "source_name": source_name,
            "target_name": target_name,
            "rel_type_str": rel_type_str,
            "data": {
                "relationship_type_id": rel_type_id,
                "primary_id": source_id,
                "primary_type": "asset",
                "secondary_id": target_id,
                "secondary_type": "asset",
            },
        })

    # Submit pending relationships via bulk-create in batches of 10
    BATCH_SIZE = 10
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        batch_payloads = [p["data"] for p in batch]
        for p in batch:
            print(f"    Linking: #{p['data']['primary_id']} ({p['source_name']}) "
                  f"--[{p['rel_type_str']}]--> #{p['data']['secondary_id']} ({p['target_name']})...")

        result = client.create_relationships_bulk(batch_payloads)
        if "error" in result and not result.get("relationships"):
            error_text = str(result.get("error", ""))[:300]
            print(f"    BATCH ERROR: {error_text}")
            failed += len(batch)
            continue

        # Process individual results
        rel_results = result.get("relationships", [])
        for idx, p in enumerate(batch):
            if idx < len(rel_results):
                r = rel_results[idx]
                if r.get("success"):
                    created += 1
                    cmdb.setdefault("relationships", []).append(list(p["rel_key"]))
                else:
                    err = str(r.get("errors", r.get("error", "unknown")))[:150]
                    if "already exists" in err.lower() or "duplicate" in err.lower():
                        skipped += 1
                        cmdb.setdefault("relationships", []).append(list(p["rel_key"]))
                    else:
                        print(f"    ERROR ({p['source_name']} -> {p['target_name']}): {err}")
                        failed += 1
            else:
                # No result for this item
                created += 1
                cmdb.setdefault("relationships", []).append(list(p["rel_key"]))
        save_sync_state(state)

    print(f"\n  Relationships: {created} created, {skipped} skipped, {failed} failed")


# ── Main sync function ──────────────────────────────────────────────────

def sync_cmdb(client: FreshserviceClient, docs_dir: str = None,
               dry_run: bool = False):
    """
    Full CMDB sync: parse manifests, create CIs, create relationships.
    """
    if docs_dir is None:
        docs_dir = str(Path(__file__).resolve().parents[2] / "docs" / "servers")

    print(f"Parsing server docs from: {docs_dir}")
    manifests = parse_all_manifests(docs_dir)
    if not manifests:
        print("No CMDB Manifests found in server docs.")
        return

    print(f"Found {len(manifests)} manifests: "
          f"{', '.join(m['hostname'] for m in manifests)}")

    all_cis = collect_all_cis(manifests)
    print(f"\nAggregated: {len(all_cis['business_services'])} business services, "
          f"{len(all_cis['it_services'])} IT services, "
          f"{len(all_cis['databases'])} databases, "
          f"{len(all_cis['relationships'])} relationships")

    state = load_sync_state()

    # Phase 1: Create CIs (business services, IT services, databases)
    sync_business_services(client, all_cis, state, dry_run)
    sync_it_services(client, all_cis, state, dry_run)
    sync_databases(client, all_cis, state, dry_run)

    # Phase 2: Create relationships (after all CIs exist)
    sync_relationships(client, all_cis, state, dry_run)

    if not dry_run:
        cmdb = _get_cmdb_state(state)
        total = (len(cmdb["services"]) + len(cmdb["it_services"])
                 + len(cmdb["databases"]))
        print(f"\nCMDB sync complete: {total} CIs, "
              f"{len(cmdb['relationships'])} relationships tracked")


def show_cmdb_status():
    """Display current CMDB sync state."""
    state = load_sync_state()
    cmdb = _get_cmdb_state(state)

    print("\nCMDB Sync State:")
    print(f"  Business Services: {len(cmdb['services'])}")
    for name, fs_id in sorted(cmdb["services"].items()):
        print(f"    {name:40s} -> #{fs_id}")

    print(f"  IT Services: {len(cmdb['it_services'])}")
    for name, fs_id in sorted(cmdb["it_services"].items()):
        print(f"    {name:40s} -> #{fs_id}")

    print(f"  Databases: {len(cmdb['databases'])}")
    for name, fs_id in sorted(cmdb["databases"].items()):
        print(f"    {name:40s} -> #{fs_id}")

    print(f"  Relationships: {len(cmdb['relationships'])}")


# ── CLI entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--status" in sys.argv:
        show_cmdb_status()
    elif "--dry-run" in sys.argv:
        client = FreshserviceClient()
        sync_cmdb(client, dry_run=True)
    elif "--sync" in sys.argv:
        client = FreshserviceClient()
        sync_cmdb(client, dry_run=False)
    else:
        print("Usage:")
        print("  python cmdb_sync.py --dry-run   # Preview CIs and relationships")
        print("  python cmdb_sync.py --sync       # Create CIs and relationships")
        print("  python cmdb_sync.py --status     # Show sync state")
        print("  Use cli.py sync-cmdb for full orchestration")
