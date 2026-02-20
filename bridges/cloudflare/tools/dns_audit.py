#!/usr/bin/env python3
"""
Cloudflare DNS Audit

Exports all DNS records for a zone and classifies them:
  - Tunnel-backed (CNAME to *.cfargotunnel.com)
  - Proxied vs DNS-only
  - Record type distribution
  - Orphaned records (pointing to stale IPs or CNAMEs)

Output modes:
  --json       Machine-readable JSON (default)
  --table      Human-readable table
  --csv        CSV for spreadsheet import

Usage:
    python3 dns_audit.py                     # JSON output for default zone
    python3 dns_audit.py --table             # Human-readable table
    python3 dns_audit.py --csv               # CSV export
    python3 dns_audit.py --zone <zone_id>    # Target specific zone by ID
    python3 dns_audit.py --type CNAME        # Filter by record type
"""

import sys
import os
import json
import csv
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudflare_client import CloudflareClient


def classify_record(record: dict) -> str:
    """Classify a DNS record as tunnel-backed, proxied, or DNS-only."""
    rtype = record.get("type", "")
    content = record.get("content", "")
    proxied = record.get("proxied", False)

    if rtype == "CNAME" and ".cfargotunnel.com" in content:
        return "tunnel"
    elif proxied:
        return "proxied"
    else:
        return "dns-only"


def audit_dns(client: CloudflareClient, zone_id: str, record_type: str = None) -> dict:
    """
    Audit all DNS records for a zone.

    Returns a structured report with:
      - records: Full list of classified records
      - summary: Counts by type, classification, and proxy status
      - tunnel_records: Records backed by Cloudflare Tunnels
      - potential_issues: Records that may need attention
    """
    records = client.list_dns_records(zone_id, record_type=record_type)

    classified = []
    for r in records:
        classification = classify_record(r)
        classified.append({
            "name": r.get("name", ""),
            "type": r.get("type", ""),
            "content": r.get("content", ""),
            "proxied": r.get("proxied", False),
            "ttl": r.get("ttl", 0),
            "classification": classification,
            "id": r.get("id", ""),
            "created_on": r.get("created_on", ""),
            "modified_on": r.get("modified_on", ""),
            "comment": r.get("comment", ""),
        })

    # Sort by name then type
    classified.sort(key=lambda r: (r["name"], r["type"]))

    # Build summary
    from collections import Counter
    by_type = Counter(r["type"] for r in classified)
    by_class = Counter(r["classification"] for r in classified)
    proxied_count = sum(1 for r in classified if r["proxied"])

    # Identify tunnel-backed records
    tunnel_records = [r for r in classified if r["classification"] == "tunnel"]

    # Identify potential issues
    issues = []

    # DNS-only A records pointing to private IPs (should be tunnel-backed)
    for r in classified:
        if r["type"] == "A" and r["classification"] == "dns-only":
            content = r["content"]
            if (content.startswith("10.") or
                content.startswith("192.168.") or
                content.startswith("172.16.") or
                content.startswith("172.17.") or
                content.startswith("172.18.") or
                content.startswith("172.19.") or
                content.startswith("172.2") or
                content.startswith("172.3")):
                issues.append({
                    "record": r["name"],
                    "type": r["type"],
                    "content": r["content"],
                    "issue": "DNS-only A record pointing to private IP",
                    "suggestion": "Consider using a Cloudflare Tunnel instead",
                })

    # CNAME records pointing to non-existent tunnel UUIDs
    for r in classified:
        if r["classification"] == "tunnel":
            tunnel_uuid = r["content"].replace(".cfargotunnel.com", "")
            if len(tunnel_uuid) != 36:
                issues.append({
                    "record": r["name"],
                    "type": r["type"],
                    "content": r["content"],
                    "issue": "Tunnel CNAME with unusual UUID format",
                    "suggestion": "Verify tunnel exists and is active",
                })

    # MX records that might conflict with email routing
    mx_records = [r for r in classified if r["type"] == "MX"]
    if mx_records:
        for mx in mx_records:
            if "route" in mx["content"].lower() or "cloudflare" not in mx["content"].lower():
                pass  # Normal MX records

    return {
        "zone_id": zone_id,
        "total_records": len(classified),
        "summary": {
            "by_type": dict(by_type.most_common()),
            "by_classification": dict(by_class),
            "proxied": proxied_count,
            "dns_only": len(classified) - proxied_count,
        },
        "tunnel_records": tunnel_records,
        "potential_issues": issues,
        "records": classified,
    }


def format_table(report: dict) -> str:
    """Format audit report as a human-readable table."""
    lines = []
    lines.append("=" * 120)
    lines.append("Cloudflare DNS Audit")
    lines.append("=" * 120)
    lines.append("")

    # Summary
    summary = report["summary"]
    lines.append(f"Total records: {report['total_records']}")
    lines.append(f"Proxied: {summary['proxied']}  |  DNS-only: {summary['dns_only']}")
    lines.append("")

    lines.append("Records by type:")
    for rtype, count in summary["by_type"].items():
        lines.append(f"  {rtype:10s}  {count}")
    lines.append("")

    lines.append("Records by classification:")
    for cls, count in summary["by_classification"].items():
        lines.append(f"  {cls:12s}  {count}")
    lines.append("")

    # Tunnel-backed records
    if report["tunnel_records"]:
        lines.append("-" * 120)
        lines.append("Tunnel-Backed Records")
        lines.append("-" * 120)
        header = f"{'FQDN':<45s}  {'Tunnel UUID':<38s}  {'Proxied'}"
        lines.append(header)
        for r in report["tunnel_records"]:
            tunnel_uuid = r["content"].replace(".cfargotunnel.com", "")
            proxied = "yes" if r["proxied"] else "no"
            lines.append(f"{r['name']:<45s}  {tunnel_uuid:<38s}  {proxied}")
        lines.append("")

    # Issues
    if report["potential_issues"]:
        lines.append("-" * 120)
        lines.append("Potential Issues")
        lines.append("-" * 120)
        for issue in report["potential_issues"]:
            lines.append(f"  [{issue['type']}] {issue['record']}")
            lines.append(f"    Content: {issue['content']}")
            lines.append(f"    Issue: {issue['issue']}")
            lines.append(f"    Suggestion: {issue['suggestion']}")
            lines.append("")

    # Full record list
    lines.append("-" * 120)
    lines.append("All Records")
    lines.append("-" * 120)
    header = f"{'Name':<45s}  {'Type':<8s}  {'Content':<45s}  {'Class':<10s}  {'Proxied'}"
    lines.append(header)
    lines.append("-" * 120)
    for r in report["records"]:
        content = r["content"][:45]
        proxied = "yes" if r["proxied"] else "no"
        lines.append(
            f"{r['name']:<45s}  {r['type']:<8s}  {content:<45s}  {r['classification']:<10s}  {proxied}"
        )

    return "\n".join(lines)


def format_csv(report: dict) -> str:
    """Format audit records as CSV."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "name", "type", "content", "proxied", "ttl",
            "classification", "comment", "created_on", "modified_on",
        ],
    )
    writer.writeheader()
    for r in report["records"]:
        writer.writerow({
            "name": r["name"],
            "type": r["type"],
            "content": r["content"],
            "proxied": r["proxied"],
            "ttl": r["ttl"],
            "classification": r["classification"],
            "comment": r["comment"],
            "created_on": r["created_on"],
            "modified_on": r["modified_on"],
        })
    return output.getvalue()


def main():
    output_format = "json"
    zone_id = None
    record_type = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--table":
            output_format = "table"
        elif args[i] == "--csv":
            output_format = "csv"
        elif args[i] == "--json":
            output_format = "json"
        elif args[i] == "--zone" and i + 1 < len(args):
            i += 1
            zone_id = args[i]
        elif args[i] == "--type" and i + 1 < len(args):
            i += 1
            record_type = args[i]
        i += 1

    client = CloudflareClient()

    # Resolve zone ID if not provided
    if not zone_id:
        default_domain = os.environ.get("CLOUDFLARE_DOMAIN", "example.com")
        zone_id = client.find_zone_id(default_domain)
        if not zone_id:
            print(f"ERROR: Could not find zone ID for {default_domain}", file=sys.stderr)
            print("Use --zone <zone_id> to specify explicitly", file=sys.stderr)
            sys.exit(1)

    report = audit_dns(client, zone_id, record_type=record_type)

    if output_format == "table":
        print(format_table(report))
    elif output_format == "csv":
        print(format_csv(report))
    else:
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
