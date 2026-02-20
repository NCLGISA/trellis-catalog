"""
CMDB Manifest Parser

Parses the ## CMDB Manifest section from server documentation markdown
files (docs/servers/*.md) into structured dicts for Freshservice sync.

Expected manifest format:
    ## CMDB Manifest

    ### Business Services
    | Service | Type | Impact | Department |
    |---------|------|--------|------------|
    | Tyler Munis ERP | Business Service | High | Finance |

    ### IT Services
    | Service | Version | Vendor | Installed On |
    |---------|---------|--------|--------------|
    | SSRS | 15.0.7961 | Microsoft | IS01S064 |

    ### Databases
    | Database | Type | Size | Instance | Environment |
    ...

    ### Relationships
    | Source | Relationship | Target |
    ...
"""

import re
from pathlib import Path


def _parse_table(lines: list[str], expected_headers: list[str]) -> list[dict]:
    """
    Parse a markdown table into a list of dicts.
    Skips the separator row (|---|---|).
    Keys are lowercased and stripped header names.
    """
    if len(lines) < 2:
        return []

    # First line is header
    header_line = lines[0]
    headers = [h.strip() for h in header_line.strip().strip("|").split("|")]
    headers = [h.lower() for h in headers]

    rows = []
    for line in lines[1:]:
        stripped = line.strip().strip("|")
        # Skip separator rows
        if re.match(r'^[\s\-:|]+$', stripped):
            continue
        cells = [c.strip() for c in stripped.split("|")]
        row = {}
        for i, h in enumerate(headers):
            row[h] = cells[i] if i < len(cells) else ""
        rows.append(row)

    return rows


def _extract_manifest_section(text: str, section_name: str) -> list[str]:
    """
    Extract lines belonging to a ### subsection within ## CMDB Manifest.
    Returns the table lines (header + separator + data rows).
    """
    lines = text.split("\n")
    in_manifest = False
    in_section = False
    table_lines = []

    for line in lines:
        # Detect start of CMDB Manifest
        if re.match(r'^##\s+CMDB Manifest\s*$', line):
            in_manifest = True
            continue

        # If we hit another ## heading, we've left the manifest
        if in_manifest and re.match(r'^##\s+[^#]', line) and "CMDB Manifest" not in line:
            break

        if not in_manifest:
            continue

        # Detect the target ### subsection
        if re.match(rf'^###\s+{re.escape(section_name)}\s*$', line):
            in_section = True
            continue

        # If we hit another ### heading, we've left this subsection
        if in_section and re.match(r'^###\s+', line):
            break

        if in_section:
            stripped = line.strip()
            if stripped.startswith("|"):
                table_lines.append(stripped)
            elif stripped == "" and table_lines:
                # Blank line after table ends it
                continue
            elif stripped.startswith("<!--"):
                continue

    return table_lines


def parse_manifest(filepath: str) -> dict:
    """
    Parse a server documentation file and extract the CMDB Manifest.

    Returns:
        {
            "hostname": "IS01S064",
            "filepath": "/path/to/IS01S064.md",
            "business_services": [
                {"service": "Tyler Munis ERP", "type": "Business Service",
                 "impact": "High", "department": "Finance"},
                ...
            ],
            "applications": [
                {"application": "SQL Server 2019", "version": "15.0.4455.2",
                 "vendor": "Microsoft", "installed on": "IS01S064"},
                ...
            ],
            "databases": [
                {"database": "munprod", "type": "MSSQL", "size": "178 GB",
                 "instance": "IS01S064\\TYLERCI", "environment": "Production"},
                ...
            ],
            "relationships": [
                {"source": "Tyler Munis ERP", "relationship": "Depends On",
                 "target": "munprod"},
                ...
            ],
        }
    """
    path = Path(filepath)
    text = path.read_text(encoding="utf-8")

    # Extract hostname from filename (e.g., IS01S064.md -> IS01S064)
    hostname = path.stem.upper()

    manifest = {
        "hostname": hostname,
        "filepath": str(path),
        "business_services": [],
        "it_services": [],
        "databases": [],
        "relationships": [],
    }

    # Parse each subsection
    svc_lines = _extract_manifest_section(text, "Business Services")
    if svc_lines:
        manifest["business_services"] = _parse_table(
            svc_lines, ["service", "type", "impact", "department"])

    # IT Services (formerly "Applications" -- uses Freshservice IT Service type)
    it_svc_lines = _extract_manifest_section(text, "IT Services")
    if it_svc_lines:
        manifest["it_services"] = _parse_table(
            it_svc_lines, ["service", "version", "vendor", "installed on"])

    db_lines = _extract_manifest_section(text, "Databases")
    if db_lines:
        manifest["databases"] = _parse_table(
            db_lines, ["database", "type", "size", "instance", "environment"])

    rel_lines = _extract_manifest_section(text, "Relationships")
    if rel_lines:
        manifest["relationships"] = _parse_table(
            rel_lines, ["source", "relationship", "target"])

    return manifest


def parse_all_manifests(docs_dir: str = None) -> list[dict]:
    """Parse all server docs that contain CMDB Manifests."""
    if docs_dir is None:
        docs_dir = str(Path(__file__).resolve().parents[2] / "docs" / "servers")

    server_files = sorted(Path(docs_dir).glob("*.md"))
    results = []
    for f in server_files:
        text = f.read_text(encoding="utf-8")
        if "## CMDB Manifest" not in text:
            continue
        try:
            manifest = parse_manifest(str(f))
            results.append(manifest)
        except Exception as e:
            print(f"  Error parsing {f.name}: {e}")
    return results


def collect_all_cis(manifests: list[dict]) -> dict:
    """
    Aggregate all unique CIs and relationships across all manifests.

    Returns:
        {
            "business_services": {name: {type, impact, department}},
            "it_services": {name: {version, vendor, installed_on}},
            "databases": {name: {type, size, instance, environment}},
            "relationships": [(source, relationship_type, target), ...],
            "hostnames": set of hostnames referenced,
        }
    """
    services = {}
    it_services = {}
    databases = {}
    relationships = []
    hostnames = set()

    for m in manifests:
        hostnames.add(m["hostname"].upper())

        for svc in m["business_services"]:
            name = svc.get("service", "").strip()
            if name and not _is_template_var(name):
                services[name] = {
                    "type": svc.get("type", "Business Service"),
                    "impact": svc.get("impact", "Medium"),
                    "department": svc.get("department", ""),
                }

        for it_svc in m.get("it_services", []):
            name = it_svc.get("service", "").strip()
            if name and not _is_template_var(name):
                it_services[name] = {
                    "version": it_svc.get("version", ""),
                    "vendor": it_svc.get("vendor", ""),
                    "installed_on": it_svc.get("installed on", ""),
                }

        for db in m["databases"]:
            name = db.get("database", "").strip()
            if name and not _is_template_var(name):
                databases[name] = {
                    "type": db.get("type", "MSSQL"),
                    "size": db.get("size", ""),
                    "instance": db.get("instance", ""),
                    "environment": db.get("environment", ""),
                }

        for rel in m["relationships"]:
            src = rel.get("source", "").strip()
            rel_type = rel.get("relationship", "").strip()
            tgt = rel.get("target", "").strip()
            if src and rel_type and tgt and not _is_template_var(src):
                relationships.append((src, rel_type, tgt))

    return {
        "business_services": services,
        "it_services": it_services,
        "databases": databases,
        "relationships": relationships,
        "hostnames": hostnames,
    }


def _is_template_var(s: str) -> bool:
    """Check if a string is a template placeholder like {{FOO}}."""
    return s.startswith("{{") and s.endswith("}}")


# ── CLI test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    manifests = parse_all_manifests()
    print(f"Parsed {len(manifests)} server manifests:\n")

    for m in manifests:
        print(f"  {m['hostname']}:")
        print(f"    Business Svcs: {len(m['business_services'])}")
        print(f"    IT Services:   {len(m['it_services'])}")
        print(f"    Databases:     {len(m['databases'])}")
        print(f"    Relationships: {len(m['relationships'])}")
        print()

    all_cis = collect_all_cis(manifests)
    print(f"Aggregated CIs:")
    print(f"  Business Services: {list(all_cis['business_services'].keys())}")
    print(f"  IT Services:       {list(all_cis['it_services'].keys())}")
    print(f"  Databases:         {list(all_cis['databases'].keys())}")
    print(f"  Relationships:     {len(all_cis['relationships'])}")
    print(f"  Hostnames:         {all_cis['hostnames']}")
