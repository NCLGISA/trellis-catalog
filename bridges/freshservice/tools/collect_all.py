#!/usr/bin/env python3
"""
Batch collector: runs the asset collection PowerShell script on all
connected Tendril agents via the Tendril server HTTP API.

Outputs a JSON file with hostname -> collected data for use by asset_sync.py.

Usage:
  python collect_all.py                  # Collect from all agents
  python collect_all.py --resume         # Resume (skip already collected)
  python collect_all.py --host az01s009  # Collect from one host
"""

import json
import subprocess
import sys
import time
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

TENDRIL_API = os.getenv("TENDRIL_API", "http://localhost:3000")
OUTPUT_FILE = Path(__file__).parent / ".collected-assets.json"

# Compact version of the collection script
COLLECT_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$info = @{}
$os  = Get-CimInstance Win32_OperatingSystem
$cs  = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$bios = Get-CimInstance Win32_BIOS
$csp = Get-CimInstance Win32_ComputerSystemProduct
$info.hostname       = $env:COMPUTERNAME
$info.domain         = $cs.Domain
$info.os_caption     = $os.Caption
$info.os_version     = $os.Version
$info.memory_gb      = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
$info.cpu_cores      = $cpu.NumberOfCores
$info.cpu_speed_ghz  = [math]::Round($cpu.MaxClockSpeed / 1000, 2)
$info.serial_number  = $bios.SerialNumber
$info.uuid           = $csp.UUID
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$info.disk_gb = [math]::Round($disk.Size / 1GB, 0)
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169' } | Select-Object -First 1).IPAddress
$info.ip_address = $ip
try {
    $headers = @{ "Metadata" = "true" }
    $imds = Invoke-RestMethod -Uri "http://169.254.169.254/metadata/instance?api-version=2021-12-13" -Headers $headers -TimeoutSec 3
    $info.is_azure = $true; $info.subscription_id = $imds.compute.subscriptionId; $info.resource_group = $imds.compute.resourceGroupName
    $info.resource_uri = $imds.compute.resourceId; $info.azure_vm_name = $imds.compute.name; $info.vm_size = $imds.compute.vmSize
    $info.location = $imds.compute.location; $info.publisher = $imds.compute.storageProfile.imageReference.publisher
    $info.offer = $imds.compute.storageProfile.imageReference.offer; $info.sku = $imds.compute.storageProfile.imageReference.sku
    $info.os_disk_name = $imds.compute.storageProfile.osDisk.name
} catch { $info.is_azure = $false }
$tagPath = 'HKLM:\SOFTWARE\Tendril\ServerInfo'
if (Test-Path $tagPath) { $tags = Get-ItemProperty $tagPath; $info.tag_application = $tags.Application; $info.tag_department = $tags.Department; $info.tag_lifecycle = $tags.Lifecycle; $info.tag_server_type = $tags.ServerType; $info.tag_vendor = $tags.Vendor }
$info | ConvertTo-Json -Depth 3
"""

SKIP_HOSTNAMES = {"avd-esri-0", "avd-0", "avd-1", "avdwin11-0", "avdwin11-1"}


def get_connected_agents():
    """Get list of connected Tendril agents."""
    proc = subprocess.run(
        ["curl", "-s", f"{TENDRIL_API}/api/v1/agents"],
        capture_output=True, text=True, timeout=10
    )
    data = json.loads(proc.stdout)
    agents = data.get("agents", [])
    return [a["hostname"].lower() for a in agents
            if a.get("status") == "connected"
            and a["hostname"].lower() not in SKIP_HOSTNAMES]


def collect_one(hostname: str) -> tuple:
    """Collect from a single agent. Returns (hostname, data_dict or None)."""
    try:
        proc = subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"{TENDRIL_API}/api/v1/execute",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({
                 "agent": hostname,
                 "script": COLLECT_SCRIPT,
                 "timeout": 30
             })],
            capture_output=True, text=True, timeout=45
        )
        resp = json.loads(proc.stdout)
        if resp.get("success") and resp.get("stdout"):
            data = json.loads(resp["stdout"])
            return (hostname, data)
        else:
            err = resp.get("stderr", "")[:100]
            print(f"  WARN: {hostname} -- no data (exit={resp.get('exit_code')}, err={err})")
            return (hostname, None)
    except Exception as e:
        print(f"  ERROR: {hostname} -- {e}")
        return (hostname, None)


def main():
    resume = "--resume" in sys.argv
    single_host = None
    if "--host" in sys.argv:
        idx = sys.argv.index("--host") + 1
        single_host = sys.argv[idx].lower()

    # Load existing data if resuming
    existing = {}
    if resume and OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text())
        print(f"Resuming: {len(existing)} agents already collected")

    if single_host:
        hostnames = [single_host]
    else:
        hostnames = get_connected_agents()

    # Filter out already collected if resuming
    if resume:
        hostnames = [h for h in hostnames if h not in existing]

    print(f"Collecting from {len(hostnames)} agents (max 5 parallel)...")
    collected = dict(existing)
    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(collect_one, h): h for h in hostnames}
        for i, future in enumerate(as_completed(futures)):
            hostname, data = future.result()
            if data:
                collected[hostname] = data
                success += 1
                app = data.get("tag_application", "?")
                print(f"  [{success + failed}/{len(hostnames)}] {hostname}: OK "
                      f"({data.get('os_caption', '?')[:30]}, {app})")
            else:
                failed += 1
                print(f"  [{success + failed}/{len(hostnames)}] {hostname}: FAILED")

            # Save progress every 10 agents
            if (success + failed) % 10 == 0:
                OUTPUT_FILE.write_text(json.dumps(collected, indent=2))

    # Final save
    OUTPUT_FILE.write_text(json.dumps(collected, indent=2))
    print(f"\nDone: {success} collected, {failed} failed, {len(collected)} total")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
