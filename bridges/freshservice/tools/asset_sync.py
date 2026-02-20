r"""
Multi-Type Asset Sync

Collects system info from Tendril agents via PowerShell/Azure IMDS,
then upserts assets into Freshservice CMDB with automatic type
classification:

  - Azure VMs:       IMDS present -> Azure VM type (7001431713)
  - VMware VMs:      On-prem Windows + VMware manufacturer -> VMware VCenter VM (7001431715)
  - ESXi Hosts:      vmkernel OS -> VMware VCenter Host (7001431717)
  - On-prem Servers: Windows with no IMDS and no VMware -> Server (7001129968)
  - AVD Desktops:    Azure VM with AVD hostname pattern

Data sources per agent:
  - WMI/CIM: hostname, domain, OS, memory, CPU, disk, serial, UUID,
    manufacturer (Win32_ComputerSystemProduct)
  - Azure IMDS (169.254.169.254): subscription, resource URI, VM size,
    location, publisher, offer, SKU, OS disk, tags
  - Tendril Registry (HKLM:\SOFTWARE\Tendril\ServerInfo): Azure tags
    cached locally (Application, Department, Lifecycle, ServerType, Vendor)

Features:
  - Multi-type: auto-classifies agents into the correct Freshservice type
  - Upsert: search by hostname, update if exists, create if new
  - Always-update strategy on re-runs (keeps CMDB current)
  - Sync-state tracking in .sync-state.json
  - Dry-run mode for previewing payloads
  - Single-host mode for testing
  - Retirement marking for decommissioned assets
"""

import json
import os
import subprocess
import time
from pathlib import Path

# These are imported by the caller -- we use them when invoked from cli.py
# or __main__. Import here to keep the module self-contained.
try:
    from freshservice_client import FreshserviceClient
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from freshservice_client import FreshserviceClient


SYNC_STATE_FILE = Path(__file__).parent / ".sync-state.json"

# Freshservice IDs (override via environment variables)
DEFAULT_AGENT_ID = int(os.environ.get("FRESHSERVICE_AGENT_ID", "7000348606"))
IT_DEPARTMENT_ID = int(os.environ.get("FRESHSERVICE_DEPARTMENT_ID", "7000161748"))

# Asset Type IDs
AZURE_VM_TYPE_ID = 7001431713
VMWARE_VM_TYPE_ID = 7001431715
VMWARE_HOST_TYPE_ID = 7001431717
SERVER_TYPE_ID = 7001129968

# Hostnames to skip (bridge containers, mobile devices)
SKIP_HOSTNAMES = set()
BRIDGE_HOSTNAMES = {
    "bridge-freshservice", "bridge-azure", "bridge-zoom",
    "bridge-meraki", "bridge-microsoft-graph",
}

# Freshservice Product and Vendor IDs (looked up from existing data)
PRODUCT_AZURE_VM_ID = 7001020143       # "Azure VM" product
PRODUCT_VIRTUAL_MACHINE_ID = 7000979028  # "Virtual Machine" product (on-prem)
PRODUCT_VMWARE_VM_ID = 7001024437      # "VMware VCenter VM" product
PRODUCT_VMWARE_HOST_ID = 7001024438    # "VMware VCenter Host" product
VENDOR_MICROSOFT_ID = 7000417454       # "Microsoft" vendor
VENDOR_TYLER_ID = 7000640786           # "Tyler Technologies" vendor

# Vendor name -> Freshservice vendor ID mapping
VENDOR_MAP = {
    "microsoft": VENDOR_MICROSOFT_ID,
    "microsoft corporation": VENDOR_MICROSOFT_ID,
    "tyler technologies": VENDOR_TYLER_ID,
    "tyler": VENDOR_TYLER_ID,
}

# AVD hostname patterns
AVD_PREFIXES = ("avd-", "avd_", "avdwin")
AVD_SUBSTRINGS = ("-cad-", "-esri-")

# ── PowerShell collection script ────────────────────────────────────────
# Runs on each Tendril agent to gather all VM info in one call.
COLLECT_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
$info = @{}

# ── WMI / CIM system info ──
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
$info.cpu_name       = $cpu.Name
$info.cpu_cores      = $cpu.NumberOfCores
$info.cpu_speed_ghz  = [math]::Round($cpu.MaxClockSpeed / 1000, 2)
$info.serial_number  = $bios.SerialNumber
$info.uuid           = $csp.UUID
$info.manufacturer   = $csp.Vendor

# VMware guest detection
$info.is_vmware_guest = ($csp.Vendor -like '*VMware*') -or ($bios.SerialNumber -like '*VMware*')

# C: drive size
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
$info.disk_gb = [math]::Round($disk.Size / 1GB, 0)

# Primary IPv4
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and
                      $_.IPAddress -notmatch '^169' } |
       Select-Object -First 1).IPAddress
$info.ip_address = $ip

# ── Azure IMDS ──
try {
    $headers = @{ "Metadata" = "true" }
    $imds = Invoke-RestMethod -Uri "http://169.254.169.254/metadata/instance?api-version=2021-12-13" `
            -Headers $headers -TimeoutSec 3
    $info.is_azure         = $true
    $info.subscription_id  = $imds.compute.subscriptionId
    $info.resource_group   = $imds.compute.resourceGroupName
    $info.resource_uri     = $imds.compute.resourceId
    $info.azure_vm_name    = $imds.compute.name
    $info.vm_size          = $imds.compute.vmSize
    $info.location         = $imds.compute.location
    $info.publisher        = $imds.compute.storageProfile.imageReference.publisher
    $info.offer            = $imds.compute.storageProfile.imageReference.offer
    $info.sku              = $imds.compute.storageProfile.imageReference.sku
    $info.os_disk_name     = $imds.compute.storageProfile.osDisk.name
    $info.imds_tags        = $imds.compute.tags
} catch {
    $info.is_azure = $false
}

# ── Tendril registry tags ──
$tagPath = 'HKLM:\SOFTWARE\Tendril\ServerInfo'
if (Test-Path $tagPath) {
    $tags = Get-ItemProperty $tagPath
    $info.tag_application  = $tags.Application
    $info.tag_department   = $tags.Department
    $info.tag_lifecycle    = $tags.Lifecycle
    $info.tag_server_type  = $tags.ServerType
    $info.tag_vendor       = $tags.Vendor
}

$info | ConvertTo-Json -Depth 3
"""


# ── ESXi collection script ───────────────────────────────────────────────
# Runs on ESXi/vmkernel agents via ash/sh shell.
ESXI_COLLECT_SCRIPT = r"""
hostname=$(hostname)
cpu_model=$(esxcli hardware cpu global get 2>/dev/null | grep "Description" | sed 's/.*: //')
cpu_cores=$(esxcli hardware cpu global get 2>/dev/null | grep "CPU Cores" | sed 's/.*: //')
mem_bytes=$(esxcli hardware memory get 2>/dev/null | grep "Physical Memory" | sed 's/.*: //')
mem_gb=$((mem_bytes / 1073741824))
esxi_version=$(vmware -v 2>/dev/null || echo "unknown")
uuid=$(esxcli system uuid get 2>/dev/null || echo "")
serial=$(esxcli hardware platform get 2>/dev/null | grep "Serial Number" | sed 's/.*: //')
manufacturer=$(esxcli hardware platform get 2>/dev/null | grep "Vendor Name" | sed 's/.*: //')
model=$(esxcli hardware platform get 2>/dev/null | grep "Product Name" | sed 's/.*: //')
ip=$(esxcli network ip interface ipv4 get 2>/dev/null | grep vmk0 | awk '{print $2}')

cat <<ENDJSON
{
  "hostname": "$hostname",
  "os_caption": "$esxi_version",
  "os_version": "ESXi",
  "cpu_name": "$cpu_model",
  "cpu_cores": $cpu_cores,
  "memory_gb": $mem_gb,
  "serial_number": "$serial",
  "uuid": "$uuid",
  "manufacturer": "$manufacturer",
  "model": "$model",
  "ip_address": "$ip",
  "is_azure": false,
  "is_vmware_guest": false,
  "is_esxi_host": true
}
ENDJSON
"""

# ── Linux collection script ──────────────────────────────────────────────
# Runs on Linux agents via bash/sh shell.
LINUX_COLLECT_SCRIPT = r"""
hostname=$(hostname)
os_caption=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'"' -f2)
os_version=$(uname -r)
cpu_name=$(grep "model name" /proc/cpuinfo 2>/dev/null | head -1 | cut -d: -f2 | xargs)
cpu_cores=$(nproc 2>/dev/null || echo 1)
mem_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
mem_gb=$((mem_kb / 1048576))
disk_gb=$(df -BG / 2>/dev/null | tail -1 | awk '{print $2}' | tr -d 'G')
uuid=$(cat /sys/class/dmi/id/product_uuid 2>/dev/null || echo "")
serial=$(cat /sys/class/dmi/id/product_serial 2>/dev/null || echo "")
manufacturer=$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo "")
ip=$(hostname -I 2>/dev/null | awk '{print $1}')

cat <<ENDJSON
{
  "hostname": "$hostname",
  "os_caption": "$os_caption",
  "os_version": "$os_version",
  "cpu_name": "$cpu_name",
  "cpu_cores": $cpu_cores,
  "memory_gb": $mem_gb,
  "disk_gb": $disk_gb,
  "serial_number": "$serial",
  "uuid": "$uuid",
  "manufacturer": "$manufacturer",
  "ip_address": "$ip",
  "is_azure": false,
  "is_vmware_guest": false
}
ENDJSON
"""


# ── Sync state helpers ──────────────────────────────────────────────────

def load_sync_state() -> dict:
    if SYNC_STATE_FILE.exists():
        return json.loads(SYNC_STATE_FILE.read_text())
    return {"changes": {}, "assets": {}}


def save_sync_state(state: dict):
    SYNC_STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Tendril data collection ────────────────────────────────────────────

def collect_from_tendril(hostname: str, tendril_execute_fn=None,
                         os_hint: str = "windows") -> dict:
    """
    Run the collection script on a single Tendril agent.

    Uses the appropriate script based on os_hint:
      - "windows" -> PowerShell COLLECT_SCRIPT
      - "vmkernel" -> ESXI_COLLECT_SCRIPT
      - "linux" -> LINUX_COLLECT_SCRIPT

    If tendril_execute_fn is provided (MCP tool function), use it directly.
    Otherwise, fall back to calling the Tendril HTTP API via curl.
    """
    if "vmkernel" in os_hint:
        script = ESXI_COLLECT_SCRIPT
    elif "linux" in os_hint:
        script = LINUX_COLLECT_SCRIPT
    else:
        script = COLLECT_SCRIPT

    if tendril_execute_fn:
        result = tendril_execute_fn(agent=hostname, script=script, timeout=30)
        if isinstance(result, dict) and result.get("success"):
            try:
                return json.loads(result["stdout"])
            except json.JSONDecodeError:
                print(f"  WARNING: Could not parse JSON from {hostname}")
                print(f"  stdout: {result['stdout'][:300]}")
                return {}
        else:
            error = result.get("stderr", "") if isinstance(result, dict) else str(result)
            print(f"  ERROR collecting from {hostname}: {error[:200]}")
            return {}
    else:
        try:
            proc = subprocess.run(
                ["curl", "-s", "-X", "POST",
                 "http://localhost:3000/api/v1/execute",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({
                     "agent": hostname,
                     "script": script,
                     "timeout": 30
                 })],
                capture_output=True, text=True, timeout=45
            )
            resp = json.loads(proc.stdout)
            if resp.get("success"):
                return json.loads(resp["stdout"])
        except Exception as e:
            print(f"  ERROR collecting from {hostname} via curl: {e}")
        return {}


def collect_from_all_tendrils(tendril_list: list, tendril_execute_fn=None,
                               skip_avd: bool = False,
                               windows_only: bool = False) -> dict:
    """
    Collect data from all connected Tendril agents.
    Returns dict of hostname -> collected data.

    Uses the appropriate collection script based on agent OS:
      - Windows agents -> PowerShell COLLECT_SCRIPT
      - ESXi agents -> ESXI_COLLECT_SCRIPT
      - Linux agents -> LINUX_COLLECT_SCRIPT

    Skips bridge containers and mobile devices.
    """
    results = {}
    for i, agent in enumerate(tendril_list):
        hostname = agent["hostname"].lower()
        os_version = agent.get("os_version", "")

        # Skip bridge containers
        if hostname in BRIDGE_HOSTNAMES:
            print(f"  [{i+1}/{len(tendril_list)}] Skipping bridge: {hostname}")
            continue

        # Skip Android devices
        if "android" in os_version:
            print(f"  [{i+1}/{len(tendril_list)}] Skipping mobile: {hostname}")
            continue

        if skip_avd and (hostname.startswith(AVD_PREFIXES) or
                         any(s in hostname for s in AVD_SUBSTRINGS)):
            print(f"  [{i+1}/{len(tendril_list)}] Skipping AVD: {hostname}")
            continue

        # Determine OS hint for script selection
        if "windows" in os_version:
            os_hint = "windows"
        elif "vmkernel" in os_version:
            if windows_only:
                print(f"  [{i+1}/{len(tendril_list)}] Skipping ESXi: {hostname}")
                continue
            os_hint = "vmkernel"
        elif "linux" in os_version:
            if windows_only:
                print(f"  [{i+1}/{len(tendril_list)}] Skipping Linux: {hostname}")
                continue
            os_hint = "linux"
        else:
            print(f"  [{i+1}/{len(tendril_list)}] Skipping unknown OS: {hostname} ({os_version})")
            continue

        print(f"  [{i+1}/{len(tendril_list)}] Collecting from {hostname} ({os_hint})...")
        data = collect_from_tendril(hostname, tendril_execute_fn, os_hint=os_hint)
        if data:
            results[hostname] = data
        else:
            print(f"    (no data returned)")

    return results


# ── Freshservice payload mapping ────────────────────────────────────────

def _map_os_choice(os_caption: str) -> str:
    """Map WMI OS caption to a Freshservice OS dropdown value."""
    if not os_caption:
        return "Windows"
    cap = os_caption.lower()
    if "server" in cap:
        # Freshservice doesn't have a 'Windows Server' OS choice by default,
        # but the field accepts free text alongside choices
        return os_caption  # Use the full caption
    if "windows 11" in cap:
        if "enterprise" in cap:
            return "Microsoft Windows 11 Enterprise"
        return "Microsoft Windows 11 Pro"
    if "windows 10" in cap:
        if "enterprise" in cap:
            return "Microsoft Windows 10 Enterprise"
        return "Microsoft Windows 10 Pro"
    return os_caption


def _map_lifecycle_to_status(lifecycle: str) -> str:
    """Map Azure Lifecycle tag to Freshservice Server Status dropdown."""
    if not lifecycle:
        return "PROD"
    lc = lifecycle.lower()
    if "prod" in lc:
        return "PROD"
    if "dev" in lc:
        return "DEV"
    if "test" in lc or "staging" in lc:
        return "TEST"
    if "legacy" in lc or "decommission" in lc:
        return "LEGACY"
    return "PROD"


def _build_description(data: dict) -> str:
    """Build a rich HTML description from Azure tags and system info."""
    parts = []
    hostname = data.get("hostname", "Unknown")
    parts.append(f"<h3>{hostname}</h3>")

    tag_app = data.get("tag_application", "")
    tag_dept = data.get("tag_department", "")
    tag_vendor = data.get("tag_vendor", "")
    tag_type = data.get("tag_server_type", "")

    if tag_app or tag_vendor:
        parts.append("<p><strong>Application:</strong> " +
                      (tag_app or "N/A") + "</p>")
    if tag_vendor:
        parts.append("<p><strong>Vendor:</strong> " + tag_vendor + "</p>")
    if tag_dept:
        parts.append("<p><strong>Department:</strong> " + tag_dept + "</p>")
    if tag_type:
        parts.append("<p><strong>Server Type:</strong> " + tag_type + "</p>")

    rg = data.get("resource_group", "")
    if rg:
        parts.append(f"<p><strong>Resource Group:</strong> {rg}</p>")

    vm_size = data.get("vm_size", "")
    if vm_size:
        parts.append(f"<p><strong>VM Size:</strong> {vm_size}</p>")

    parts.append(f"<p><em>Auto-synced from Tendril agent data</em></p>")
    return "\n".join(parts)


def _classify_network(ip: str) -> str:
    """Classify IP into a network segment for the Freshservice Network dropdown.

    Example subnet mapping (configure per environment):
      10.10.10.0/24  = Production servers
      10.10.14.0/24  = Virtual servers
      10.10.20.0/16  = Non-production / Azure
    """
    if not ip:
        return ""
    if ip.startswith("10.10.10."):
        return "SERVERs"
    if ip.startswith("10.10.14."):
        return "VSERVERs"
    if ip.startswith("10.20."):
        return "SERVERs"
    return ""


# NOTE: The vendor field on an asset must match the product's manufacturer
# association. The "Azure VM" product's manufacturer is "Microsoft Corporation"
# but none of the Microsoft vendor IDs are associated with the product.
# We omit vendor_7001129940 and instead capture the application vendor
# (e.g. Tyler Technologies) in the description and server notes fields.


# ── Asset type auto-classification ──────────────────────────────────────

def classify_asset_type(data: dict) -> int:
    """
    Determine the correct Freshservice asset type ID based on collected data.

    Returns one of: AZURE_VM_TYPE_ID, VMWARE_VM_TYPE_ID, VMWARE_HOST_TYPE_ID,
                     SERVER_TYPE_ID.
    """
    hostname = (data.get("hostname") or "").lower()

    # ESXi hosts
    if data.get("is_esxi_host"):
        return VMWARE_HOST_TYPE_ID

    # AVD desktops are Azure VMs
    if (hostname.startswith(AVD_PREFIXES) or
            any(s in hostname for s in AVD_SUBSTRINGS)):
        return AZURE_VM_TYPE_ID

    # Azure IMDS detected
    if data.get("is_azure"):
        return AZURE_VM_TYPE_ID

    # VMware guest (explicit detection from collection script)
    if data.get("is_vmware_guest"):
        return VMWARE_VM_TYPE_ID

    # IP-subnet fallback (configure per environment):
    #
    #   10.10.0.0/16   = Azure Production
    #   10.20.0.0/16   = Azure Non-Production
    #   10.30.0.0/16   = Legacy on-premise VMware
    ip = data.get("ip_address", "")

    # Azure subnets: applies to any OS (Linux VMs don't have IMDS in collection)
    if ip.startswith("10.10.") or ip.startswith("10.20."):
        return AZURE_VM_TYPE_ID

    # Legacy on-prem VMware subnet: only for Windows machines.
    # Linux appliances on legacy subnet should be Server, not VMware VM.
    os_caption = (data.get("os_caption") or "").lower()
    is_windows = "windows" in os_caption or "server" in os_caption
    if is_windows and ip.startswith("10.30."):
        return VMWARE_VM_TYPE_ID

    return SERVER_TYPE_ID


def _type_id_label(type_id: int) -> str:
    """Human-readable label for an asset type ID."""
    labels = {
        AZURE_VM_TYPE_ID: "Azure VM",
        VMWARE_VM_TYPE_ID: "VMware VCenter VM",
        VMWARE_HOST_TYPE_ID: "VMware VCenter Host",
        SERVER_TYPE_ID: "Server",
    }
    return labels.get(type_id, str(type_id))


# Known Freshservice Instance Type dropdown values (for validation)
_KNOWN_INSTANCE_TYPES = {
    "Standard_D2s_v3", "Standard_B2ms", "Standard_D4s_v3", "Standard_B2s",
    "Standard_B4ms", "Standard_F4s_v2", "Standard_D8s_v3",
    "Standard_D2as_v4", "Standard_DS1_v2", "Standard_DS3_v2",
    "Standard_D2s_v5", "Standard_D4as_v4", "Standard_D4s_v5",
    "Standard_E2s_v3", "Standard_F8s_v2", "Standard_DS2_v2",
    "Standard_F2s_v2", "Standard_D4s_v4", "Standard_B8ms",
    "Standard_D4as_v5", "Standard_D2as_v5", "Standard_B1s",
    "Standard_D4ds_v5", "Standard_D2ds_v5",
    "Microsoft.Compute/virtualMachines",
}


def build_asset_payload(data: dict, force_type_id: int = None) -> dict:
    """
    Convert collected Tendril data into a Freshservice Asset API payload.

    Auto-classifies the asset type unless force_type_id is provided.
    Builds type_fields appropriate for the detected type.
    """
    hostname = (data.get("hostname") or "").upper()
    vm_size = data.get("vm_size", "")
    asset_type_id = force_type_id or classify_asset_type(data)

    # ── Common type_fields (shared across all server types) ──
    # Freshservice requires integer values for disk_space and memory
    disk_gb = data.get("disk_gb")
    if disk_gb is not None:
        disk_gb = int(disk_gb)
    memory_gb = data.get("memory_gb")
    if memory_gb is not None:
        memory_gb = int(memory_gb)

    type_fields = {
        # Hardware section
        "compute_type_7001129940": "Virtual",
        "domain_7001129940": data.get("domain", ""),
        "asset_state_7001129940": "In Use",
        "serial_number_7001129940": data.get("uuid") or data.get("serial_number") or data.get("hostname", ""),

        # Computer section
        "os_7001129946": _map_os_choice(data.get("os_caption", "")),
        "os_version_7001129946": data.get("os_version", ""),
        "memory_7001129946": memory_gb,
        "disk_space_7001129946": disk_gb if disk_gb is not None else 0,
        "cpu_speed_7001129946": data.get("cpu_speed_ghz") or 0,
        "cpu_core_count_7001129946": data.get("cpu_cores"),
        "uuid_7001129946": data.get("uuid", ""),
        "hostname_7001129946": hostname,
        "computer_ip_address_7001129946": data.get("ip_address", ""),
        "state_7001129946": "Running",

        # Server section
        "status_7001129968": _map_lifecycle_to_status(
            data.get("tag_lifecycle", "")),
        "datacenter_7001129968": "IT",
        "network_7001129968": _classify_network(
            data.get("ip_address", "")),
        "veeam_backup_7001129968": "!",
        "gfi_languard_agent_7001129968": "!",
        "cbdefense_agent_7001129968": "!",
        "unique_admin_password_7001129968": "N/A",
        "notes_7001129968": (
            f"Application: {data.get('tag_application', 'N/A')}\n"
            f"Vendor: {data.get('tag_vendor', 'N/A')}\n"
            f"Server Type: {data.get('tag_server_type', 'N/A')}\n"
            f"Resource Group: {data.get('resource_group', 'N/A')}"
        ),
    }

    # ── Type-specific fields ──
    if asset_type_id == AZURE_VM_TYPE_ID:
        type_fields.update({
            "virtual_subtype_7001129940": "Azure Cloud Service",
            "product_7001129940": PRODUCT_AZURE_VM_ID,
            "provider_type_7001129946": "AZURE",
            # Azure VM section
            "resource_uri_7001431713": data.get("resource_uri", ""),
            "subscription_id_7001431713": data.get("subscription_id", ""),
            "publisher_7001431713": data.get("publisher", ""),
            "offer_7001431713": data.get("offer", ""),
            "sku_7001431713": data.get("sku", ""),
            "os_disk_name_7001431713": data.get("os_disk_name", ""),
            "computer_name_7001431713": hostname,
        })
        if vm_size in _KNOWN_INSTANCE_TYPES:
            type_fields["cd_instance_type_7001129946"] = vm_size

    elif asset_type_id == VMWARE_VM_TYPE_ID:
        type_fields.update({
            "product_7001129940": PRODUCT_VMWARE_VM_ID,
            "virtual_subtype_7001129940": "Internal VM",
            "provider_type_7001129946": "VMWARE VCENTER",
        })

    elif asset_type_id == VMWARE_HOST_TYPE_ID:
        type_fields.update({
            "product_7001129940": PRODUCT_VMWARE_HOST_ID,
            "compute_type_7001129940": "Physical",
        })
        # VMware VCenter Host type does NOT have Server-section fields.
        # Remove any _7001129968 fields that were set in common section.
        keys_to_remove = [k for k in type_fields if k.endswith("_7001129968")]
        for k in keys_to_remove:
            del type_fields[k]

    elif asset_type_id == SERVER_TYPE_ID:
        type_fields.update({
            "product_7001129940": PRODUCT_VIRTUAL_MACHINE_ID,
            "provider_type_7001129946": "VMWARE VCENTER",
        })

    payload = {
        "name": hostname,
        "asset_type_id": asset_type_id,
        "description": _build_description(data),
        "impact": "medium",
        "usage_type": "permanent",
        "agent_id": DEFAULT_AGENT_ID,
        "department_id": IT_DEPARTMENT_ID,
        "type_fields": type_fields,
    }

    return payload


# ── Freshservice upsert logic ──────────────────────────────────────────

def _normalize_hostname(hostname: str) -> str:
    """Strip common domain suffixes for FQDN normalization."""
    domain_suffix = os.environ.get("FRESHSERVICE_DOMAIN_SUFFIX", ".example.local")
    h = hostname.lower()
    for suffix in (domain_suffix, ".local"):
        if h.endswith(suffix):
            h = h[: -len(suffix)]
    return h


def find_existing_asset(client: FreshserviceClient, hostname: str) -> dict | None:
    """Search for an existing asset by hostname (name field).

    Tries the exact name, upper/lower variants, and FQDN-stripped forms.
    """
    # Build list of name variants to try
    variants = [hostname, hostname.upper(), hostname.lower()]

    # Add FQDN-stripped variant if hostname contains a domain
    short = _normalize_hostname(hostname)
    if short != hostname.lower():
        variants.extend([short, short.upper()])

    # Add FQDN variant if hostname is short
    if "." not in hostname:
        domain_suffix = os.environ.get("FRESHSERVICE_DOMAIN_SUFFIX", ".example.local")
        variants.append(f"{hostname.lower()}{domain_suffix}")

    seen = set()
    for variant in variants:
        if variant in seen:
            continue
        seen.add(variant)
        resp = client.get("assets", params={
            "query": f"\"name:'{variant}'\"",
        })
        if resp.status_code == 200:
            assets = resp.json().get("assets", [])
            if assets:
                return assets[0]
    return None


def sync_single_asset(client: FreshserviceClient, data: dict,
                       dry_run: bool = False) -> dict:
    """
    Create or update a single asset in Freshservice.
    Returns the Freshservice asset response or dry-run summary.
    """
    payload = build_asset_payload(data)
    hostname = payload["name"]
    asset_type_id = payload["asset_type_id"]
    type_label = _type_id_label(asset_type_id)
    state = load_sync_state()

    # Check sync state first
    existing_display_id = state.get("assets", {}).get(hostname.lower())

    if dry_run:
        print(f"\n  DRY RUN: {hostname}")
        print(f"    Type:     {type_label}")
        print(f"    OS:       {data.get('os_caption', '?')}")
        print(f"    IP:       {data.get('ip_address', '?')}")
        print(f"    VM Size:  {data.get('vm_size', '?')}")
        print(f"    Memory:   {data.get('memory_gb', '?')} GB")
        print(f"    App:      {data.get('tag_application', '?')}")
        print(f"    VMware:   {data.get('is_vmware_guest', '?')}")
        print(f"    Existing: {'#' + str(existing_display_id) if existing_display_id else 'NEW'}")
        return {"dry_run": True, "hostname": hostname, "payload": payload}

    if existing_display_id:
        print(f"    Updating existing {type_label} #{existing_display_id}...")
        update_payload = dict(payload)
        update_payload.pop("asset_type_id", None)
        result = client.update_asset(existing_display_id, update_payload)
        asset = result.get("asset", result)
        print(f"    Updated: #{asset.get('display_id', existing_display_id)}")
    else:
        existing = find_existing_asset(client, hostname)
        if existing:
            display_id = existing["display_id"]
            print(f"    Found existing asset #{display_id}, updating as {type_label}...")
            update_payload = dict(payload)
            update_payload.pop("asset_type_id", None)
            result = client.update_asset(display_id, update_payload)
            asset = result.get("asset", result)
            state.setdefault("assets", {})[hostname.lower()] = display_id
            save_sync_state(state)
            print(f"    Updated: #{display_id}")
        else:
            print(f"    Creating new {type_label} asset...")
            result = client.create_asset(payload)
            asset = result.get("asset", {})
            display_id = asset.get("display_id")
            if display_id:
                print(f"    Created: #{display_id}")
                state.setdefault("assets", {})[hostname.lower()] = display_id
                save_sync_state(state)
            else:
                print(f"    ERROR: {result}")

    return result


def sync_all_assets(client: FreshserviceClient, collected_data: dict,
                     dry_run: bool = False) -> list:
    """
    Sync all collected agent data to Freshservice.
    collected_data: dict of hostname -> collected data from Tendril.
    """
    results = []
    total = len(collected_data)
    for i, (hostname, data) in enumerate(sorted(collected_data.items())):
        print(f"\n  [{i+1}/{total}] {hostname}")
        result = sync_single_asset(client, data, dry_run=dry_run)
        results.append(result)
    return results


def show_asset_sync_status():
    """Display current asset sync state."""
    state = load_sync_state()
    assets = state.get("assets", {})
    print(f"\nAsset Sync State:")
    print(f"  Assets synced: {len(assets)}")
    for hostname, fs_id in sorted(assets.items()):
        print(f"    {hostname:20s} -> Freshservice #{fs_id}")


# ── Retirement marking ──────────────────────────────────────────────────

def mark_asset_retired(client: FreshserviceClient, display_id: int,
                       hostname: str, dry_run: bool = False) -> bool:
    """Mark an asset as retired/missing in Freshservice."""
    if dry_run:
        print(f"    DRY RUN: Would mark #{display_id} ({hostname}) as Missing")
        return True

    print(f"    Marking #{display_id} ({hostname}) as Missing...")
    result = client.update_asset(display_id, {
        "type_fields": {
            "asset_state_7001129940": "Missing",
        },
    })
    if "error" in result:
        print(f"      ERROR: {str(result.get('error', ''))[:200]}")
        return False

    print(f"      Marked as Missing")
    return True


# ── CLI entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    usage = """
Usage:
  python asset_sync.py --dry-run              # Preview payloads for all agents
  python asset_sync.py --dry-run --host HOST  # Preview one host
  python asset_sync.py --sync --host HOST     # Sync one host to Freshservice
  python asset_sync.py --sync                 # Sync all agents
  python asset_sync.py --status               # Show sync state
  python asset_sync.py --collect --host HOST  # Collect & print data from one host
"""

    if "--status" in sys.argv:
        show_asset_sync_status()
        sys.exit(0)

    if "--collect" in sys.argv and "--host" in sys.argv:
        host_idx = sys.argv.index("--host") + 1
        hostname = sys.argv[host_idx]
        print(f"Collecting from {hostname}...")
        data = collect_from_tendril(hostname)
        print(json.dumps(data, indent=2))
        sys.exit(0)

    if "--dry-run" in sys.argv or "--sync" in sys.argv:
        is_dry = "--dry-run" in sys.argv

        if "--host" in sys.argv:
            host_idx = sys.argv.index("--host") + 1
            hostname = sys.argv[host_idx]
            print(f"{'DRY RUN' if is_dry else 'SYNCING'}: {hostname}")
            data = collect_from_tendril(hostname)
            if not data:
                print("ERROR: No data collected")
                sys.exit(1)
            client = FreshserviceClient()
            sync_single_asset(client, data, dry_run=is_dry)
        else:
            print("Full sync requires Tendril agent list.")
            print("Use cli.py sync-assets for full orchestration.")
        sys.exit(0)

    print(usage)
