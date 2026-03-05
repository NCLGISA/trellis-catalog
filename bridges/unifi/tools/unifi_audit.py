#!/usr/bin/env python3
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
UniFi Configuration Compliance Audit Tool

Checks UniFi controller and device configuration against best-practice
standards. Reports compliance issues as structured findings.

Usage:
    python3 unifi_audit.py full [--site SITE]
    python3 unifi_audit.py firmware [--site SITE]
    python3 unifi_audit.py wlans [--site SITE]
    python3 unifi_audit.py networks [--site SITE]
    python3 unifi_audit.py security [--site SITE]

All operations are read-only.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient


class Finding:
    def __init__(self, category, severity, title, detail, remediation=""):
        self.category = category
        self.severity = severity
        self.title = title
        self.detail = detail
        self.remediation = remediation

    def to_dict(self):
        d = {
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
        }
        if self.remediation:
            d["remediation"] = self.remediation
        return d


findings = []


def add_finding(category, severity, title, detail, remediation=""):
    findings.append(Finding(category, severity, title, detail, remediation))


def audit_firmware(client, site):
    """Check firmware currency across all devices."""
    devices = client.list_devices(site=site)

    upgradable = [d for d in devices if d.get("upgradable")]
    offline = [d for d in devices if d.get("state", 0) != 1]

    if upgradable:
        names = [d.get("name", d.get("mac", "?")) for d in upgradable]
        add_finding(
            "Firmware", "WARNING",
            f"{len(upgradable)} device(s) have firmware updates available",
            f"Devices: {', '.join(names[:10)}",
            "Run: python3 unifi_devices.py upgrade <mac> for each device"
        )

    if offline:
        names = [d.get("name", d.get("mac", "?")) for d in offline]
        add_finding(
            "Firmware", "CRITICAL",
            f"{len(offline)} device(s) are offline",
            f"Devices: {', '.join(names[:10)}",
            "Check physical connectivity, PoE power, and device health"
        )

    firmware_versions = {}
    for d in devices:
        model = d.get("model", "?")
        ver = d.get("version", "?")
        firmware_versions.setdefault(model, set()).add(ver)

    for model, versions in firmware_versions.items():
        if len(versions) > 1:
            add_finding(
                "Firmware", "INFO",
                f"Mixed firmware versions for model {model}",
                f"Versions in use: {', '.join(sorted(versions))}",
                "Consider upgrading all devices of the same model to the latest version"
            )

    if not upgradable and not offline:
        add_finding("Firmware", "PASS", "All devices online and up to date", "")


def audit_wlans(client, site):
    """Check WLAN security configuration."""
    wlans = client.list_wlans(site=site)

    for w in wlans:
        name = w.get("name", "?")
        security = w.get("security", "open")
        wpa_mode = w.get("wpa_mode", "")
        enabled = w.get("enabled", True)

        if not enabled:
            continue

        if security == "open" and not w.get("is_guest", False):
            add_finding(
                "WLAN Security", "CRITICAL",
                f"WLAN '{name}' is open (no encryption)",
                "Non-guest networks should use WPA2 or WPA3 encryption",
                f"Enable WPA2/WPA3 on WLAN '{name}'"
            )

        if security == "wpapsk" and wpa_mode == "wpa1":
            add_finding(
                "WLAN Security", "WARNING",
                f"WLAN '{name}' uses legacy WPA1",
                "WPA1 has known vulnerabilities; WPA2 or WPA3 is recommended",
                f"Upgrade WLAN '{name}' to WPA2 or WPA3"
            )

        passphrase = w.get("x_passphrase", "")
        if passphrase and len(passphrase) < 12:
            add_finding(
                "WLAN Security", "WARNING",
                f"WLAN '{name}' has a short passphrase ({len(passphrase)} chars)",
                "NIST recommends passphrases of 12+ characters",
                f"Set a longer passphrase for WLAN '{name}'"
            )

        if w.get("hide_ssid"):
            add_finding(
                "WLAN Security", "INFO",
                f"WLAN '{name}' has hidden SSID",
                "Hidden SSIDs do not improve security and can cause client connectivity issues",
            )

    if not any(f.category == "WLAN Security" for f in findings):
        add_finding("WLAN Security", "PASS", "All WLANs pass security checks", "")


def audit_networks(client, site):
    """Check network/VLAN configuration."""
    nets = client.list_networks(site=site)

    vlans_used = set()
    for n in nets:
        vlan = n.get("vlan")
        if vlan is not None and isinstance(vlan, int):
            if vlan in vlans_used:
                add_finding(
                    "Networks", "WARNING",
                    f"Duplicate VLAN ID {vlan}",
                    f"Multiple networks use VLAN {vlan}",
                    "Ensure each network segment has a unique VLAN ID"
                )
            vlans_used.add(vlan)

    for n in nets:
        name = n.get("name", "?")
        if n.get("dhcpd_enabled") and not n.get("dhcpd_dns_1"):
            add_finding(
                "Networks", "INFO",
                f"Network '{name}' has DHCP enabled but no DNS server configured",
                "Clients may use the gateway as DNS; explicit DNS is recommended",
            )

    if not any(f.category == "Networks" for f in findings):
        add_finding("Networks", "PASS", "Network configuration looks good", "")


def audit_security(client, site):
    """Check overall security posture."""
    rogues = client.list_rogue_aps(site=site)
    high_signal_rogues = [r for r in rogues if (r.get("rssi") or -100) > -60]

    if high_signal_rogues:
        essids = set(r.get("essid", "?") for r in high_signal_rogues)
        add_finding(
            "Security", "WARNING",
            f"{len(high_signal_rogues)} strong-signal rogue AP(s) detected",
            f"SSIDs: {', '.join(list(essids)[:10])}",
            "Investigate whether these are legitimate neighbor APs or security threats"
        )

    clients = client.list_clients(site=site)
    blocked = [c for c in clients if c.get("blocked")]
    if blocked:
        add_finding(
            "Security", "INFO",
            f"{len(blocked)} blocked client(s) currently connected",
            "These clients are flagged as blocked but may still appear in the client list",
        )

    port_forwards = client.list_port_forwards(site=site)
    enabled_forwards = [f for f in port_forwards if f.get("enabled", True)]
    if len(enabled_forwards) > 10:
        add_finding(
            "Security", "WARNING",
            f"{len(enabled_forwards)} active port forwards",
            "A high number of port forwards increases attack surface",
            "Review and remove unnecessary port forwards"
        )

    if not any(f.category == "Security" for f in findings):
        add_finding("Security", "PASS", "Security posture looks good", "")


def print_report(audit_type):
    """Print structured audit report."""
    critical = sum(1 for f in findings if f.severity == "CRITICAL")
    warnings = sum(1 for f in findings if f.severity == "WARNING")
    info = sum(1 for f in findings if f.severity == "INFO")
    passed = sum(1 for f in findings if f.severity == "PASS")

    report = {
        "audit_type": audit_type,
        "summary": {
            "total_findings": len(findings),
            "critical": critical,
            "warnings": warnings,
            "info": info,
            "passed": passed,
        },
        "findings": [f.to_dict() for f in findings],
    }
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description="UniFi Configuration Compliance Audit")
    parser.add_argument("command", choices=["full", "firmware", "wlans", "networks", "security"])
    parser.add_argument("--site", default=None, help="Site name")
    args = parser.parse_args()

    client = UniFiClient()
    try:
        if args.command == "full":
            audit_firmware(client, args.site)
            audit_wlans(client, args.site)
            audit_networks(client, args.site)
            audit_security(client, args.site)
        elif args.command == "firmware":
            audit_firmware(client, args.site)
        elif args.command == "wlans":
            audit_wlans(client, args.site)
        elif args.command == "networks":
            audit_networks(client, args.site)
        elif args.command == "security":
            audit_security(client, args.site)

        print_report(args.command)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    main()
