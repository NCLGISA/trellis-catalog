"""
Extended Intune Management Tool

Query Intune managed devices, apps, configuration profiles, compliance policies,
RBAC roles, and device overview statistics.

Usage:
    python3 intune_check.py overview                  # Device overview (counts by OS, compliance)
    python3 intune_check.py devices [--os windows]     # List managed devices
    python3 intune_check.py device <name>              # Detailed device info
    python3 intune_check.py apps                       # Deployed Intune apps
    python3 intune_check.py configs                    # Device configuration profiles
    python3 intune_check.py compliance                 # Compliance policies
    python3 intune_check.py roles                      # Intune RBAC roles
    python3 intune_check.py stale [days]               # Devices not synced in N days (default 30)
    python3 intune_check.py noncompliant               # Noncompliant devices
"""

import sys
import json
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from graph_client import GraphClient


def show_overview(client: GraphClient):
    """Show Intune managed device overview."""
    print("Intune Managed Device Overview")
    print("=" * 60)

    try:
        overview = client.get_managed_device_overview()
        print(f"  Total enrolled: {overview.get('enrolledDeviceCount', '?')}")
        print(f"  MDM authority:  {overview.get('mdmAuthority', '?')}")

        dt = overview.get("deviceOperatingSystemSummary", {})
        if dt:
            print(f"\n  By OS:")
            print(f"    Windows:   {dt.get('windowsCount', 0)}")
            print(f"    iOS:       {dt.get('iosCount', 0)}")
            print(f"    macOS:     {dt.get('macOSCount', 0)}")
            print(f"    Android:   {dt.get('androidCount', 0)}")
            print(f"    Unknown:   {dt.get('unknownCount', 0)}")

        compliance = overview.get("deviceExchangeAccessStateSummary", {})
        if compliance:
            print(f"\n  Exchange Access:")
            print(f"    Allowed:     {compliance.get('allowedDeviceCount', 0)}")
            print(f"    Blocked:     {compliance.get('blockedDeviceCount', 0)}")
            print(f"    Quarantined: {compliance.get('quarantinedDeviceCount', 0)}")
            print(f"    Unknown:     {compliance.get('unknownDeviceCount', 0)}")
    except Exception as e:
        print(f"  Error: {e}")

    # Supplement with device counts from actual list
    devices = client.list_managed_devices()
    os_counts = Counter(d.get("operatingSystem", "?") for d in devices)
    compliance_counts = Counter(d.get("complianceState", "?") for d in devices)

    print(f"\n  Actual enrolled devices: {len(devices)}")
    print(f"  By OS (actual): {', '.join(f'{c} {o}' for o, c in os_counts.most_common())}")
    print(f"  Compliance: {', '.join(f'{c} {s}' for s, c in compliance_counts.most_common())}")


def list_devices(client: GraphClient, os_filter: str = None):
    """List managed devices, optionally filtered by OS."""
    devices = client.list_managed_devices()

    if os_filter:
        devices = [d for d in devices if os_filter.lower() in (d.get("operatingSystem") or "").lower()]

    print(f"Intune Managed Devices: {len(devices)}")
    print()
    print(f"{'Device':<22} {'OS':<10} {'Version':<16} {'Compliance':<14} {'Last Sync'}")
    print("-" * 82)

    for d in sorted(devices, key=lambda x: (x.get("deviceName") or "").lower()):
        name = (d.get("deviceName") or "?")[:21]
        os = (d.get("operatingSystem") or "?")[:9]
        version = (d.get("osVersion") or "?")[:15]
        compliance = (d.get("complianceState") or "?")[:13]
        last_sync = (d.get("lastSyncDateTime") or "?")[:19]
        print(f"{name:<22} {os:<10} {version:<16} {compliance:<14} {last_sync}")


def device_detail(client: GraphClient, name: str):
    """Show detailed info for a specific device."""
    devices = client.list_managed_devices()
    matches = [d for d in devices if name.lower() in (d.get("deviceName") or "").lower()]

    if not matches:
        print(f"No device matching '{name}' found ({len(devices)} searched)")
        sys.exit(1)

    d = matches[0]
    print(f"Device: {d.get('deviceName')}")
    print(f"  ID:             {d.get('id')}")
    print(f"  Entra ID:       {d.get('azureADDeviceId')}")
    print(f"  OS:             {d.get('operatingSystem')} {d.get('osVersion')}")
    print(f"  Compliance:     {d.get('complianceState')}")
    print(f"  Management:     {d.get('managementAgent')}")
    print(f"  Ownership:      {d.get('managedDeviceOwnerType')}")
    print(f"  Encrypted:      {d.get('isEncrypted')}")
    print(f"  Supervised:     {d.get('isSupervised')}")
    print(f"  Enrolled:       {(d.get('enrolledDateTime') or '?')[:19]}")
    print(f"  Last Sync:      {(d.get('lastSyncDateTime') or '?')[:19]}")
    print(f"  User:           {d.get('userDisplayName')} ({d.get('userPrincipalName')})")
    print(f"  Serial:         {d.get('serialNumber')}")
    print(f"  Model:          {d.get('model')}")
    print(f"  Manufacturer:   {d.get('manufacturer')}")
    print(f"  Total Storage:  {d.get('totalStorageSpaceInBytes', 0) / (1024**3):.1f} GB")
    print(f"  Free Storage:   {d.get('freeStorageSpaceInBytes', 0) / (1024**3):.1f} GB")
    print(f"  WiFi MAC:       {d.get('wiFiMacAddress')}")
    print(f"  EthernetMAC:    {d.get('ethernetMacAddress')}")

    if len(matches) > 1:
        print(f"\nNote: {len(matches)} devices matched '{name}', showing first")


def show_apps(client: GraphClient):
    """Show deployed Intune apps."""
    apps = client.list_intune_apps()
    app_types = Counter(a.get("@odata.type", "?").split(".")[-1] for a in apps)

    print(f"Intune Apps: {len(apps)}")
    print(f"Types: {', '.join(f'{c} {t}' for t, c in app_types.most_common())}")
    print()
    print(f"{'App Name':<50} {'Type':<25} {'Publisher'}")
    print("-" * 95)

    for a in sorted(apps, key=lambda x: (x.get("displayName") or "").lower()):
        name = (a.get("displayName") or "?")[:49]
        app_type = (a.get("@odata.type", "?").split(".")[-1])[:24]
        publisher = (a.get("publisher") or "")[:30]
        print(f"{name:<50} {app_type:<25} {publisher}")


def show_configs(client: GraphClient):
    """Show device configuration profiles."""
    configs = client.list_device_configurations()
    config_types = Counter(c.get("@odata.type", "?").split(".")[-1] for c in configs)

    print(f"Device Configuration Profiles: {len(configs)}")
    print(f"Types: {', '.join(f'{c} {t}' for t, c in config_types.most_common())}")
    print()
    print(f"{'Profile Name':<50} {'Type':<30} {'Created'}")
    print("-" * 95)

    for c in sorted(configs, key=lambda x: (x.get("displayName") or "").lower()):
        name = (c.get("displayName") or "?")[:49]
        cfg_type = (c.get("@odata.type", "?").split(".")[-1])[:29]
        created = (c.get("createdDateTime") or "?")[:19]
        print(f"{name:<50} {cfg_type:<30} {created}")


def show_compliance_policies(client: GraphClient):
    """Show compliance policies."""
    try:
        policies = client.list_compliance_policies()
        policy_types = Counter(p.get("@odata.type", "?").split(".")[-1] for p in policies)

        print(f"Compliance Policies: {len(policies)}")
        print(f"Types: {', '.join(f'{c} {t}' for t, c in policy_types.most_common())}")
        print()
        print(f"{'Policy Name':<50} {'Type':<30} {'Created'}")
        print("-" * 95)

        for p in sorted(policies, key=lambda x: (x.get("displayName") or "").lower()):
            name = (p.get("displayName") or "?")[:49]
            p_type = (p.get("@odata.type", "?").split(".")[-1])[:29]
            created = (p.get("createdDateTime") or "?")[:19]
            print(f"{name:<50} {p_type:<30} {created}")
    except Exception as e:
        print(f"Compliance policies: error ({e})")


def show_roles(client: GraphClient):
    """Show Intune RBAC roles."""
    roles = client.list_intune_role_definitions()

    built_in = [r for r in roles if r.get("isBuiltIn")]
    custom = [r for r in roles if not r.get("isBuiltIn")]

    print(f"Intune RBAC Roles: {len(roles)} ({len(built_in)} built-in, {len(custom)} custom)")
    print()

    if custom:
        print("Custom Roles:")
        for r in custom:
            name = r.get("displayName", "?")
            desc = (r.get("description") or "")[:60]
            print(f"  {name}")
            if desc:
                print(f"    {desc}")
        print()

    print("Built-in Roles:")
    for r in built_in:
        name = r.get("displayName", "?")
        print(f"  {name}")


def stale_devices(client: GraphClient, days: int = 30):
    """Find devices that haven't synced in N days."""
    devices = client.list_managed_devices()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

    stale = [d for d in devices
             if (d.get("lastSyncDateTime") or "") < cutoff
             and d.get("lastSyncDateTime")]
    stale.sort(key=lambda x: x.get("lastSyncDateTime", ""))

    print(f"Devices not synced in {days}+ days: {len(stale)} of {len(devices)} total")
    print()
    print(f"{'Device':<22} {'OS':<10} {'Compliance':<14} {'Last Sync':<22} {'Days'}")
    print("-" * 78)

    for d in stale[:30]:
        name = (d.get("deviceName") or "?")[:21]
        os_name = (d.get("operatingSystem") or "?")[:9]
        compliance = (d.get("complianceState") or "?")[:13]
        last_sync = (d.get("lastSyncDateTime") or "?")[:19]
        try:
            age = (datetime.utcnow() - datetime.fromisoformat(d["lastSyncDateTime"].replace("Z", ""))).days
        except Exception:
            age = "?"
        print(f"{name:<22} {os_name:<10} {compliance:<14} {last_sync:<22} {str(age):>4}")

    if len(stale) > 30:
        print(f"\n... +{len(stale) - 30} more")


def noncompliant_devices(client: GraphClient):
    """Show noncompliant devices."""
    devices = client.list_managed_devices()
    nc = [d for d in devices if d.get("complianceState") == "noncompliant"]

    print(f"Noncompliant Devices: {len(nc)} of {len(devices)} total")
    print()
    print(f"{'Device':<22} {'OS':<10} {'Version':<16} {'User':<25} {'Last Sync'}")
    print("-" * 95)

    for d in sorted(nc, key=lambda x: (x.get("deviceName") or "").lower()):
        name = (d.get("deviceName") or "?")[:21]
        os_name = (d.get("operatingSystem") or "?")[:9]
        version = (d.get("osVersion") or "?")[:15]
        user = (d.get("userDisplayName") or "?")[:24]
        last_sync = (d.get("lastSyncDateTime") or "?")[:19]
        print(f"{name:<22} {os_name:<10} {version:<16} {user:<25} {last_sync}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1].lower()

    if command == "overview":
        show_overview(client)
    elif command == "devices":
        os_filter = None
        if "--os" in sys.argv:
            idx = sys.argv.index("--os")
            os_filter = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        list_devices(client, os_filter)
    elif command == "device":
        if len(sys.argv) < 3:
            print("Usage: intune_check.py device <name>")
            sys.exit(1)
        device_detail(client, " ".join(sys.argv[2:]))
    elif command == "apps":
        show_apps(client)
    elif command == "configs":
        show_configs(client)
    elif command == "compliance":
        show_compliance_policies(client)
    elif command == "roles":
        show_roles(client)
    elif command == "stale":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        stale_devices(client, days)
    elif command == "noncompliant":
        noncompliant_devices(client)
    else:
        print(f"Unknown command: {command}")
        print("Commands: overview, devices, device, apps, configs, compliance, roles, stale, noncompliant")
        sys.exit(1)


if __name__ == "__main__":
    main()
