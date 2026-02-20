"""
Server Documentation Generator

Auto-generates docs/servers/HOSTNAME.md files from collected Tendril
baseline data. Fills in the standard template with system overview,
CMDB manifest skeleton, and raw discovery data.

This closes the documentation gap:
  Tendril agents -> collect -> .collected-assets.json -> server docs
                                                         -> CMDB manifests
                                                         -> Freshservice sync

Usage:
  python server_doc_gen.py --all                  # Generate for all collected servers
  python server_doc_gen.py --host IS01S064        # Generate for one server
  python server_doc_gen.py --all --overwrite       # Regenerate existing docs
  python server_doc_gen.py --all --dry-run         # Preview without writing
"""

import json
from datetime import datetime
from pathlib import Path

COLLECTED_ASSETS_FILE = Path(__file__).parent / ".collected-assets.json"
TEMPLATE_FILE = Path(__file__).resolve().parents[3] / "docs" / "templates" / "server-documentation-template.md"
OUTPUT_DIR = Path(__file__).resolve().parents[3] / "docs" / "servers"


def load_collected_assets() -> dict:
    if COLLECTED_ASSETS_FILE.exists():
        return json.loads(COLLECTED_ASSETS_FILE.read_text())
    return {}


def _format_disk_table(data: dict) -> str:
    """Generate disk table rows from collected data."""
    disk_gb = data.get("disk_gb")
    if not disk_gb:
        return "| C: | - | - | - | Primary OS disk |"

    return f"| C: | - | - | {disk_gb} GB | Primary OS disk |"


def _format_os(data: dict) -> str:
    """Format OS string from collected data."""
    caption = data.get("os_caption", "")
    version = data.get("os_version", "")
    if caption and version:
        return f"{caption} ({version})"
    return caption or version or "Unknown"


def _classify_for_doc(data: dict) -> str:
    """Classify server for documentation purposes."""
    if data.get("is_azure"):
        return "Azure VM"
    if data.get("is_vmware_guest"):
        return "VMware VM (On-Prem)"
    if data.get("is_esxi_host"):
        return "ESXi Hypervisor"
    ip = data.get("ip_address", "")
    if ip.startswith("10.200.") or ip.startswith("10.216."):
        return "On-Prem Server"
    if ip.startswith("10.215."):
        return "Azure VM"
    return "Server"


def _build_manifest_skeleton(hostname: str, data: dict) -> str:
    """Build a CMDB manifest section with placeholder guidance."""
    server_type = _classify_for_doc(data)
    app = data.get("tag_application", "")
    vendor = data.get("tag_vendor", "")
    dept = data.get("tag_department", "IT")

    lines = []
    lines.append("## CMDB Manifest\n")
    lines.append("<!-- This section is machine-parsed by scripts/freshservice/cmdb_parser.py.")
    lines.append("     Keep the exact table headers and ### headings below. -->")
    lines.append("")

    # Business Services
    lines.append("### Business Services\n")
    if app and app != "N/A":
        impact = "Medium"
        lines.append("| Service | Type | Impact | Department |")
        lines.append("|---------|------|--------|------------|")
        lines.append(f"| {app} | Business Service | {impact} | {dept or 'IT'} |")
    else:
        lines.append("<!-- No business service identified from Azure tags.")
        lines.append("     Add manually after exploration: -->")
        lines.append("")
        lines.append("| Service | Type | Impact | Department |")
        lines.append("|---------|------|--------|------------|")
        lines.append(f"| (needs discovery) | Business Service | Medium | {dept or 'IT'} |")
    lines.append("")

    # IT Services
    lines.append("### IT Services\n")
    lines.append("<!-- Populate after running baseline-collect.ps1 and reviewing services. -->")
    lines.append("")
    lines.append("| Service | Version | Vendor | Installed On |")
    lines.append("|---------|---------|--------|--------------|")
    if vendor and vendor != "N/A":
        lines.append(f"| (review services) | - | {vendor} | {hostname} |")
    else:
        lines.append(f"| (review services) | - | - | {hostname} |")
    lines.append("")

    # Databases
    lines.append("### Databases\n")
    lines.append("<!-- Populate after SQL discovery. Only production databases. -->")
    lines.append("")
    lines.append("| Database | Type | Size | Instance | Environment |")
    lines.append("|----------|------|------|----------|-------------|")
    lines.append("| (run SQL discovery) | MSSQL | - | - | Production |")
    lines.append("")

    # Relationships
    lines.append("### Relationships\n")
    lines.append("| Source | Relationship | Target |")
    lines.append("|--------|-------------|--------|")
    if app and app != "N/A":
        lines.append(f"| {app} | Hosted On | {hostname} |")
    lines.append(f"| (services) | Runs on | {hostname} |")
    lines.append("")
    lines.append(f"<!-- Server type: {server_type}")
    if data.get("resource_group"):
        lines.append(f"     Resource group: {data['resource_group']}")
    if data.get("vm_size"):
        lines.append(f"     VM size: {data['vm_size']}")
    lines.append("     Run baseline-collect.ps1 for full service/SQL discovery. -->")

    return "\n".join(lines)


def generate_server_doc(hostname: str, data: dict) -> str:
    """Generate a server documentation markdown file from collected data."""
    hn = hostname.upper()
    date = datetime.now().strftime("%Y-%m-%d")
    ip = data.get("ip_address", "Unknown")

    lines = []
    lines.append(f"# Server Documentation: {hn}")
    lines.append("")
    lines.append(f"**Last Updated:** {date}  ")
    lines.append(f"**Server:** {hn} ({ip})  ")
    lines.append("**Documentation Generated By:** PSRemote Server Discovery via Tendril")
    lines.append("")
    lines.append(f"<!-- Discovery metadata:")
    lines.append(f"     Last baseline collection: {date}")
    lines.append(f"     Tendril agent: {hostname}")
    lines.append(f"     Last enrichment: (auto-generated, needs manual enrichment)")
    lines.append(f"-->")
    lines.append("")
    lines.append("---")
    lines.append("")

    # CMDB Manifest
    lines.append(_build_manifest_skeleton(hn, data))
    lines.append("")
    lines.append("---")
    lines.append("")

    # System Overview
    lines.append("## System Overview")
    lines.append("")
    lines.append("| Component | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| Hostname | {hn} |")
    lines.append(f"| IP Address | {ip} |")
    lines.append(f"| OS | {_format_os(data)} |")

    cpu = data.get("cpu_name", "Unknown")
    cores = data.get("cpu_cores", "-")
    lines.append(f"| CPU | {cpu} ({cores} cores) |")
    lines.append(f"| RAM | {data.get('memory_gb', '-')} GB |")
    lines.append(f"| Domain | {data.get('domain', '-')} |")
    lines.append(f"| Serial | {data.get('serial_number', '-')} |")
    lines.append(f"| UUID | {data.get('uuid', '-')} |")

    if data.get("is_azure"):
        lines.append(f"| Azure VM Size | {data.get('vm_size', '-')} |")
        lines.append(f"| Azure Location | {data.get('location', '-')} |")
        lines.append(f"| Resource Group | {data.get('resource_group', '-')} |")
        lines.append(f"| Subscription | {data.get('subscription_id', '-')} |")

    if data.get("tag_application"):
        lines.append(f"| Application Tag | {data.get('tag_application', '-')} |")
    if data.get("tag_vendor"):
        lines.append(f"| Vendor Tag | {data.get('tag_vendor', '-')} |")
    if data.get("tag_lifecycle"):
        lines.append(f"| Lifecycle | {data.get('tag_lifecycle', '-')} |")
    if data.get("tag_server_type"):
        lines.append(f"| Server Type Tag | {data.get('tag_server_type', '-')} |")

    lines.append("")

    # Disk
    lines.append("### Disk Configuration")
    lines.append("")
    lines.append("| Drive | Used | Free | Total | Notes |")
    lines.append("|-------|------|------|-------|-------|")
    lines.append(_format_disk_table(data))
    lines.append("")
    lines.append("---")
    lines.append("")

    # Placeholder sections
    lines.append("## Architecture Diagram")
    lines.append("")
    lines.append("```mermaid")
    lines.append("flowchart TB")
    lines.append(f"    subgraph server[\"{hn}\"]")
    if data.get("tag_application") and data["tag_application"] != "N/A":
        lines.append(f"        app[\"{data['tag_application']}\"]")
    else:
        lines.append(f"        app[\"Application\\n(needs discovery)\"]")
    lines.append("    end")
    lines.append("```")
    lines.append("")
    lines.append("<!-- Replace with actual architecture diagram after exploration. -->")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Services (placeholder)
    lines.append("## Services")
    lines.append("")
    lines.append("### Running Services (Application-Related)")
    lines.append("")
    lines.append("| Service Name | Display Name | Port | Start Type | Status |")
    lines.append("|--------------|--------------|------|------------|--------|")
    lines.append("| (run baseline-collect.ps1) | | | | |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Port Mapping (placeholder)
    lines.append("## Port Mapping")
    lines.append("")
    lines.append("| Port | Protocol | Process | Purpose |")
    lines.append("|------|----------|---------|---------|")
    lines.append("| (run baseline-collect.ps1) | | | |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Change History
    lines.append("## Change History")
    lines.append("")
    lines.append("| Date | Change | Author |")
    lines.append("|------|--------|--------|")
    lines.append(f"| {date} | Initial documentation auto-generated from Tendril baseline | PSRemote Discovery |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Raw Discovery Data
    lines.append("## Appendix: Raw Discovery Data")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Click to expand raw system information</summary>")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(data, indent=2, default=str))
    lines.append("```")
    lines.append("")
    lines.append("</details>")

    return "\n".join(lines)


def generate_all(overwrite: bool = False, dry_run: bool = False,
                  single_host: str = None) -> list:
    """
    Generate server docs for all collected assets.

    Returns list of generated filenames.
    """
    collected = load_collected_assets()
    if not collected:
        print("No .collected-assets.json found. Run collect-assets first.")
        return []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = []
    skipped = 0

    targets = collected.items()
    if single_host:
        hostname = single_host.lower()
        if hostname not in collected:
            print(f"Host '{single_host}' not found in collected data.")
            return []
        targets = [(hostname, collected[hostname])]

    for hostname, data in sorted(targets):
        hn_upper = hostname.upper()
        output_path = OUTPUT_DIR / f"{hn_upper}.md"

        if output_path.exists() and not overwrite:
            skipped += 1
            continue

        doc = generate_server_doc(hostname, data)

        if dry_run:
            print(f"  DRY RUN: Would write {output_path.name} "
                  f"({len(doc)} chars)")
            generated.append(output_path.name)
            continue

        output_path.write_text(doc)
        print(f"  Generated: {output_path.name}")
        generated.append(output_path.name)

    if skipped and not single_host:
        print(f"  Skipped {skipped} existing docs (use --overwrite to regenerate)")

    return generated


# ── CLI entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    overwrite = "--overwrite" in sys.argv
    dry_run = "--dry-run" in sys.argv
    single = None
    if "--host" in sys.argv:
        idx = sys.argv.index("--host") + 1
        single = sys.argv[idx]

    if "--all" in sys.argv or single:
        generated = generate_all(overwrite=overwrite, dry_run=dry_run,
                                  single_host=single)
        print(f"\nGenerated {len(generated)} server docs.")
    else:
        print(__doc__)
