"""
LAPS (Local Administrator Password Solution) Lookup Tool

Query Windows LAPS passwords backed up to Entra ID via Microsoft Graph.
Supports lookup by hostname, coverage auditing, and random sampling.

Usage:
    python3 laps_lookup.py <hostname>            # Get LAPS password for a device
    python3 laps_lookup.py search <query>         # Search devices by partial name
    python3 laps_lookup.py audit                  # LAPS coverage report
    python3 laps_lookup.py sample [N]             # Random sample of N devices (default 5)
    python3 laps_lookup.py stale [days]           # Devices with LAPS older than N days (default 30)
"""

import sys
import json
import base64
import random
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, "/opt/bridge/data/tools")
from graph_client import GraphClient


def decode_laps_password(pw_b64: str) -> str:
    """Decode a base64-encoded LAPS password."""
    if not pw_b64:
        return "(empty)"
    try:
        return base64.b64decode(pw_b64).decode("utf-8")
    except Exception:
        try:
            return base64.b64decode(pw_b64).decode("utf-16-le")
        except Exception:
            return pw_b64


def format_laps_entry(device_name: str, cred_data: dict, verbose: bool = False) -> str:
    """Format a single LAPS credential entry for display."""
    creds = cred_data.get("credentials", [])
    if not creds:
        return f"  {device_name}: (no credentials stored)"

    latest = creds[0]
    account = latest.get("accountName", "?")
    password = decode_laps_password(latest.get("passwordBase64", ""))
    backed_up = (latest.get("backupDateTime") or "?")[:19]
    refresh = (cred_data.get("refreshDateTime") or "?")[:19]
    history = len(creds) - 1

    lines = [
        f"  Device:     {device_name}",
        f"  Account:    {account}",
        f"  Password:   {password}",
        f"  Backed up:  {backed_up}",
        f"  Next rotate: {refresh}",
        f"  History:    {history} older password(s)",
    ]

    if verbose and history > 0:
        lines.append("  Password history:")
        for i, c in enumerate(creds[1:], 1):
            old_pw = decode_laps_password(c.get("passwordBase64", ""))
            old_date = (c.get("backupDateTime") or "?")[:19]
            lines.append(f"    [{i}] {old_pw}  (backed up: {old_date})")

    return "\n".join(lines)


def lookup_by_hostname(client: GraphClient, hostname: str):
    """Look up LAPS password for a specific device by hostname."""
    # Find the device in Intune to get its Entra device ID
    devices = client.list_managed_devices()
    matches = [d for d in devices
               if (d.get("deviceName") or "").lower() == hostname.lower()]

    if not matches:
        # Try partial match
        matches = [d for d in devices
                   if hostname.lower() in (d.get("deviceName") or "").lower()]

    if not matches:
        print(f"Device '{hostname}' not found in Intune ({len(devices)} devices searched)")
        sys.exit(1)

    if len(matches) > 1:
        print(f"Multiple matches for '{hostname}':")
        for d in matches:
            print(f"  {d.get('deviceName'):<20} OS={d.get('operatingSystem')} AAD={d.get('azureADDeviceId')}")
        print(f"\nUsing first match: {matches[0].get('deviceName')}")

    device = matches[0]
    name = device.get("deviceName", hostname)
    aad_id = device.get("azureADDeviceId", "")

    if not aad_id:
        print(f"Device '{name}' has no Entra device ID (not Azure AD joined)")
        sys.exit(1)

    try:
        data = client.get_device_laps(aad_id)
        print(f"LAPS credential for {name} (Entra ID: {aad_id})")
        print()
        print(format_laps_entry(name, data, verbose=True))
    except Exception as e:
        if "404" in str(e):
            print(f"Device '{name}' ({aad_id}) does not have LAPS credentials backed up")
        else:
            print(f"Error retrieving LAPS for '{name}': {e}")
        sys.exit(1)


def search_devices(client: GraphClient, query: str):
    """Search for devices by partial hostname and show LAPS status."""
    devices = client.list_managed_devices()
    matches = [d for d in devices
               if query.lower() in (d.get("deviceName") or "").lower()
               and d.get("operatingSystem") == "Windows"]

    if not matches:
        print(f"No Windows devices matching '{query}' (searched {len(devices)})")
        sys.exit(1)

    print(f"Windows devices matching '{query}': {len(matches)}")
    print()
    print(f"{'Device':<20} {'OS Version':<20} {'LAPS Account':<16} {'Password':<22} {'Backed Up'}")
    print("-" * 100)

    for d in matches[:20]:
        name = (d.get("deviceName") or "?")[:19]
        build = (d.get("osVersion") or "?")[:19]
        aad_id = d.get("azureADDeviceId", "")

        if not aad_id:
            print(f"{name:<20} {build:<20} {'(no AAD ID)':<16}")
            continue

        try:
            data = client.get_device_laps(aad_id)
            creds = data.get("credentials", [])
            if creds:
                latest = creds[0]
                account = latest.get("accountName", "?")
                password = decode_laps_password(latest.get("passwordBase64", ""))
                backed_up = (latest.get("backupDateTime") or "?")[:19]
                print(f"{name:<20} {build:<20} {account:<16} {password[:21]:<22} {backed_up}")
            else:
                print(f"{name:<20} {build:<20} {'(no creds)':<16}")
        except Exception:
            print(f"{name:<20} {build:<20} {'(not enrolled)':<16}")

    if len(matches) > 20:
        print(f"\n... {len(matches) - 20} more devices not shown")


def audit_coverage(client: GraphClient):
    """Audit LAPS coverage across all Windows devices."""
    print("Auditing LAPS coverage across all Windows Intune devices...")
    print()

    devices = client.list_managed_devices()
    windows = [d for d in devices if d.get("operatingSystem") == "Windows"]

    # Get all LAPS-backed-up devices
    laps_devices = client.list_laps_devices()
    laps_ids = {d.get("id", "").lower() for d in laps_devices}

    # Cross-reference
    with_laps = []
    without_laps = []
    no_aad_id = []

    for d in windows:
        aad_id = (d.get("azureADDeviceId") or "").lower()
        if not aad_id:
            no_aad_id.append(d)
        elif aad_id in laps_ids:
            with_laps.append(d)
        else:
            without_laps.append(d)

    total = len(windows)
    pct = (len(with_laps) / total * 100) if total else 0

    # OS breakdown
    os_with = Counter((d.get("osVersion") or "?")[:12] for d in with_laps)
    os_without = Counter((d.get("osVersion") or "?")[:12] for d in without_laps)

    print(f"Total Windows devices in Intune: {total}")
    print(f"  LAPS backed up:   {len(with_laps):>5} ({pct:.0f}%)")
    print(f"  No LAPS:          {len(without_laps):>5}")
    print(f"  No Entra ID:      {len(no_aad_id):>5}")
    print(f"  LAPS DB entries:  {len(laps_devices):>5}")
    print()

    if without_laps:
        print(f"Devices WITHOUT LAPS ({len(without_laps)}):")
        print(f"  {'Device':<20} {'OS Version':<20} {'Compliance':<15} {'Last Sync'}")
        print(f"  {'-' * 80}")
        for d in sorted(without_laps, key=lambda x: x.get("deviceName", ""))[:25]:
            name = (d.get("deviceName") or "?")[:19]
            build = (d.get("osVersion") or "?")[:19]
            compliance = (d.get("complianceState") or "?")[:14]
            last_sync = (d.get("lastSyncDateTime") or "?")[:19]
            print(f"  {name:<20} {build:<20} {compliance:<15} {last_sync}")
        if len(without_laps) > 25:
            print(f"  ... +{len(without_laps) - 25} more")

    print()
    print(json.dumps({
        "total_windows": total,
        "laps_backed_up": len(with_laps),
        "no_laps": len(without_laps),
        "no_entra_id": len(no_aad_id),
        "coverage_pct": round(pct, 1),
    }))


def random_sample(client: GraphClient, count: int = 5):
    """Show LAPS passwords for a random sample of Windows 11 devices."""
    devices = client.list_managed_devices()
    win11 = [d for d in devices
             if d.get("operatingSystem") == "Windows"
             and (d.get("osVersion") or "").startswith("10.0.2")
             and d.get("azureADDeviceId")]

    sample = random.sample(win11, min(count, len(win11)))

    print(f"LAPS random sample: {len(sample)} of {len(win11)} Windows 11 devices")
    print()
    print(f"{'Device':<18} {'OS Build':<18} {'Account':<16} {'Password':<22} {'Backed Up':<22} Hist")
    print("=" * 105)

    for d in sample:
        name = (d.get("deviceName") or "?")[:17]
        build = (d.get("osVersion") or "?")[:17]
        aad_id = d.get("azureADDeviceId", "")

        try:
            data = client.get_device_laps(aad_id)
            creds = data.get("credentials", [])
            if creds:
                latest = creds[0]
                account = latest.get("accountName", "?")
                password = decode_laps_password(latest.get("passwordBase64", ""))
                backed_up = (latest.get("backupDateTime") or "?")[:19]
                history = len(creds) - 1
                print(f"{name:<18} {build:<18} {account:<16} {password[:21]:<22} {backed_up:<22} +{history}")
            else:
                print(f"{name:<18} {build:<18} {'(no creds)':<16}")
        except Exception:
            print(f"{name:<18} {build:<18} {'(not enrolled)':<16}")

    print("=" * 105)


def stale_passwords(client: GraphClient, days: int = 30):
    """Find devices whose LAPS password hasn't rotated in N days."""
    print(f"Finding devices with LAPS passwords older than {days} days...")
    print()

    laps_devices = client.list_laps_devices()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

    stale = []
    for d in laps_devices:
        last_backup = d.get("lastBackupDateTime", "")
        if last_backup and last_backup < cutoff:
            stale.append(d)

    stale.sort(key=lambda x: x.get("lastBackupDateTime", ""))

    print(f"Total LAPS devices: {len(laps_devices)}")
    print(f"Stale (>{days} days): {len(stale)}")
    print()

    if stale:
        print(f"{'Device':<22} {'Last Backup':<22} {'Days Old':>10}")
        print("-" * 58)
        for d in stale[:30]:
            name = (d.get("deviceName") or "?")[:21]
            last = d.get("lastBackupDateTime", "?")
            last_display = last[:19] if last else "?"
            try:
                age = (datetime.utcnow() - datetime.fromisoformat(last.replace("Z", ""))).days
            except Exception:
                age = "?"
            print(f"{name:<22} {last_display:<22} {str(age):>10}")
        if len(stale) > 30:
            print(f"... +{len(stale) - 30} more")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = GraphClient()
    command = sys.argv[1].lower()

    if command == "audit":
        audit_coverage(client)
    elif command == "sample":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        random_sample(client, count)
    elif command == "stale":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        stale_passwords(client, days)
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: laps_lookup.py search <query>")
            sys.exit(1)
        search_devices(client, " ".join(sys.argv[2:]))
    else:
        # Treat as hostname lookup
        lookup_by_hostname(client, command)


if __name__ == "__main__":
    main()
