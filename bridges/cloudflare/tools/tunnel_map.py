#!/usr/bin/env python3
"""
Cloudflare Tunnel Map

Maps every Cloudflare Tunnel to its configured public hostnames and origin
services, producing a complete FQDN-to-internal-resource mapping.

This is the key tool for understanding the linkage between public FQDNs
(e.g., app.example.com) and internal origin servers
(e.g., https://10.0.0.10:443).

Output modes:
  --json       Machine-readable JSON (default)
  --table      Human-readable table
  --csv        CSV for spreadsheet import

Usage:
    python3 tunnel_map.py                    # JSON output
    python3 tunnel_map.py --table            # Human-readable table
    python3 tunnel_map.py --csv              # CSV export
    python3 tunnel_map.py --tunnel <name>    # Filter to specific tunnel
"""

import sys
import json
import csv
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cloudflare_client import CloudflareClient


def get_tunnel_mappings(client: CloudflareClient, tunnel_filter: str = None) -> list:
    """
    Build a list of FQDN -> origin mappings from all active tunnels.

    Each mapping includes:
      - tunnel_name: Tunnel name
      - tunnel_id: Tunnel UUID
      - tunnel_status: healthy/inactive/etc.
      - public_hostname: The public FQDN (e.g., app.example.com)
      - origin_service: Where traffic is routed (e.g., https://localhost:443)
      - origin_path: Optional path prefix
      - protocol: http, https, ssh, rdp, etc.
      - no_tls_verify: Whether TLS verification is disabled for origin
      - connections: Number of active connector connections
    """
    tunnels = client.list_tunnels()

    if tunnel_filter:
        tunnels = [
            t for t in tunnels
            if tunnel_filter.lower() in t.get("name", "").lower()
        ]

    mappings = []

    for tunnel in tunnels:
        tunnel_id = tunnel.get("id", "")
        tunnel_name = tunnel.get("name", "unknown")
        tunnel_status = tunnel.get("status", "unknown")

        # Get active connections count
        connections = client.list_tunnel_connections(tunnel_id)
        conn_count = len(connections)

        # Get tunnel configuration (ingress rules)
        try:
            config = client.get_tunnel_configurations(tunnel_id)
        except Exception:
            config = {}

        ingress_rules = []
        tunnel_config = config.get("config", {})
        if isinstance(tunnel_config, dict):
            ingress_rules = tunnel_config.get("ingress", [])

        if not ingress_rules:
            mappings.append({
                "tunnel_name": tunnel_name,
                "tunnel_id": tunnel_id[:12],
                "tunnel_status": tunnel_status,
                "public_hostname": "(no ingress rules)",
                "origin_service": "",
                "origin_path": "",
                "protocol": "",
                "no_tls_verify": False,
                "connections": conn_count,
            })
            continue

        for rule in ingress_rules:
            hostname = rule.get("hostname", "")
            service = rule.get("service", "")
            path = rule.get("path", "")

            # Determine protocol from origin service URL
            protocol = ""
            if service.startswith("https://"):
                protocol = "https"
            elif service.startswith("http://"):
                protocol = "http"
            elif service.startswith("ssh://"):
                protocol = "ssh"
            elif service.startswith("rdp://"):
                protocol = "rdp"
            elif service.startswith("tcp://"):
                protocol = "tcp"
            elif service == "http_status:404":
                protocol = "catch-all"

            # Check origin TLS settings
            origin_request = rule.get("originRequest", {})
            no_tls_verify = origin_request.get("noTLSVerify", False)

            mappings.append({
                "tunnel_name": tunnel_name,
                "tunnel_id": tunnel_id[:12],
                "tunnel_status": tunnel_status,
                "public_hostname": hostname or "(catch-all)",
                "origin_service": service,
                "origin_path": path,
                "protocol": protocol,
                "no_tls_verify": no_tls_verify,
                "connections": conn_count,
            })

    # Sort by public hostname
    mappings.sort(key=lambda m: m.get("public_hostname", ""))
    return mappings


def format_table(mappings: list) -> str:
    """Format mappings as a human-readable table."""
    if not mappings:
        return "No tunnel mappings found."

    lines = []
    lines.append("=" * 120)
    lines.append("Cloudflare Tunnel Map -- FQDN to Origin Service")
    lines.append("=" * 120)
    lines.append("")

    header = f"{'Public FQDN':<45s}  {'Origin Service':<40s}  {'Tunnel':<20s}  {'Status':<10s}  {'Conns'}"
    lines.append(header)
    lines.append("-" * 120)

    for m in mappings:
        hostname = m["public_hostname"]
        origin = m["origin_service"]
        tunnel = m["tunnel_name"]
        status = m["tunnel_status"]
        conns = m["connections"]
        tls_note = " [noTLSVerify]" if m["no_tls_verify"] else ""

        lines.append(
            f"{hostname:<45s}  {origin + tls_note:<40s}  {tunnel:<20s}  {status:<10s}  {conns}"
        )

    lines.append("")
    lines.append(f"Total mappings: {len(mappings)}")
    active = [m for m in mappings if m["tunnel_status"] == "healthy"]
    lines.append(f"Healthy tunnels: {len(set(m['tunnel_id'] for m in active))}")

    return "\n".join(lines)


def format_csv(mappings: list) -> str:
    """Format mappings as CSV."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "public_hostname", "origin_service", "protocol",
            "tunnel_name", "tunnel_id", "tunnel_status",
            "connections", "no_tls_verify", "origin_path",
        ],
    )
    writer.writeheader()
    writer.writerows(mappings)
    return output.getvalue()


def format_summary(mappings: list) -> dict:
    """Generate a summary of the tunnel map."""
    unique_tunnels = set(m["tunnel_id"] for m in mappings)
    healthy = set(
        m["tunnel_id"] for m in mappings if m["tunnel_status"] == "healthy"
    )
    hostnames = [m["public_hostname"] for m in mappings if m["public_hostname"] not in ("(catch-all)", "(no ingress rules)")]
    protocols = {}
    for m in mappings:
        p = m.get("protocol", "other")
        if p:
            protocols[p] = protocols.get(p, 0) + 1

    return {
        "total_mappings": len(mappings),
        "total_tunnels": len(unique_tunnels),
        "healthy_tunnels": len(healthy),
        "public_hostnames": len(hostnames),
        "protocols": protocols,
        "no_tls_verify_count": sum(1 for m in mappings if m["no_tls_verify"]),
    }


def main():
    output_format = "json"
    tunnel_filter = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--table":
            output_format = "table"
        elif args[i] == "--csv":
            output_format = "csv"
        elif args[i] == "--json":
            output_format = "json"
        elif args[i] == "--tunnel" and i + 1 < len(args):
            i += 1
            tunnel_filter = args[i]
        i += 1

    client = CloudflareClient()
    mappings = get_tunnel_mappings(client, tunnel_filter=tunnel_filter)

    if output_format == "table":
        print(format_table(mappings))
    elif output_format == "csv":
        print(format_csv(mappings))
    else:
        output = {
            "summary": format_summary(mappings),
            "mappings": mappings,
        }
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
