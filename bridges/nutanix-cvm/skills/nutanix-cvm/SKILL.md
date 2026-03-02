---
name: nutanix-cvm
description: "Nutanix Controller VM (CVM) operations skill for AHV-based hyper-converged infrastructure. Provides cluster health monitoring, VM management, storage capacity tracking, alert triage, protection domain status, Nutanix Files monitoring, and hypervisor-level access via the CVM built-in tools (ncli, acli) and passwordless SSH to the local AHV host."
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.03.01"
metadata:
  author: tendril-project
  version: "1.0.0"
  skill_scope: "local"
  tags:
    - nutanix
    - cvm
    - ahv
    - hypervisor
    - hci
    - virtualization
    - storage
    - cluster
    - ncli
    - acli
---

# Nutanix CVM Operations

This skill describes the operational capabilities available on a Nutanix Controller VM
(CVM) running the Tendril agent. CVMs are the recommended installation target for Tendril
on Nutanix clusters — they provide access to all Nutanix management tools, survive AOS
upgrades (unlike AHV hypervisor hosts which are re-imaged), and have passwordless SSH
to both the local hypervisor and peer CVMs.

## Environment Setup

Nutanix CLI tools are installed under the `nutanix` user's home directory and are NOT
in the system PATH by default. **Every command must include:**

```bash
export PATH=$PATH:/usr/local/nutanix/bin:/home/nutanix/prism/cli
```

### Available CLI Tools

| Tool | Path | Purpose |
|------|------|---------|
| `ncli` | `/home/nutanix/prism/cli/ncli` | Cluster, storage, host, disk, alert, protection domain management |
| `acli` | `/usr/local/nutanix/bin/acli` | AHV VM lifecycle, networking, and snapshot operations |
| `ncc` | Varies by AOS version | Nutanix Cluster Check — health diagnostics framework |

## Cluster Health

### Quick Health Check

```bash
export PATH=$PATH:/usr/local/nutanix/bin:/home/nutanix/prism/cli
ncli cluster info
ncli host ls | grep -E "Name|Host Status|Under Maintenance"
```

**Healthy state:** All hosts `NORMAL`, none under maintenance.

### Alerts

```bash
ncli alerts ls                         # All unresolved alerts
ncli alerts ls max-alerts=10           # Limit results
ncli alerts acknowledge id=<uuid>      # Acknowledge after review
ncli alerts resolve id=<uuid>          # Mark resolved
```

**Severity levels:** `kCritical` (action required), `kWarning` (investigate), `kInfo` (advisory).

### SSL Certificate Status

A common critical alert. To regenerate self-signed certs:

```bash
ncli cluster regenerate-ssl-certificate
```

For CA-signed certs, renewal requires the Prism UI or v3 API.

## VM Management

### Listing and Inspecting VMs

```bash
acli vm.list                           # All VMs (name + UUID)
acli vm.get <vm_name>                  # Full VM details (CPU, RAM, disks, NICs, host placement)
acli vm.get <vm_name> | grep host_name # Which physical host runs this VM
```

### Power Operations

These are mutating operations — follow your organization's change management process.

```bash
acli vm.on <vm_name>                   # Power on
acli vm.shutdown <vm_name>             # Graceful guest OS shutdown (requires NGT)
acli vm.off <vm_name>                  # Hard power off (use if shutdown hangs)
acli vm.reset <vm_name>               # Hard reboot
```

### Snapshots

```bash
acli vm.snapshot_create <vm_name> snapshot_name_list=<snap_name>
acli vm.snapshot_list <vm_name>
acli vm.snapshot_delete <vm_name> snapshot_name_list=<snap_name>
```

## Storage

### Capacity Overview

```bash
ncli sp ls                             # Storage pool (physical capacity)
ncli ctr ls                            # Container breakdown (logical usage)
```

**Key fields:**
- `Capacity (Physical)` / `Used (Physical)` / `Free (Physical)` — Raw disk totals
- `Replication Factor` — RF2 means data is written twice (usable ≈ raw / 2)
- `Compression` / `Erasure Code` / `On-Disk Dedup` — Data reduction features

### Disk Health

```bash
ncli disk ls                           # All physical disks
ncli disk ls | grep -E "Id |Serial|Tier|Online|Location|Host|Status"
```

All disks should show `Online: true`. Mixed SSD and HDD tiers are normal (tiered storage).

## Networking

```bash
acli net.list                          # All virtual networks (name, VLAN, vswitch)
acli net.get <network_name>            # Network details including IP pools
```

## Protection Domains & DR

```bash
ncli pd ls                             # List protection domains
ncli pd list-snapshots name=<pd_name>  # Snapshots for a specific PD
```

**Healthy state:** All PDs `Active: true` with `Next Snapshot Time` in the near future.

## Nutanix Files

If the cluster runs Nutanix Files:

```bash
ncli fs ls                             # File server status, capacity, AD domain, VMs
```

## Cross-Node Operations

### Accessing the Local Hypervisor (AHV)

Each CVM has passwordless SSH to its local AHV host via the internal backplane:

```bash
ssh root@<ahv-host-ip> "virsh list --all"          # List VMs at hypervisor level
ssh root@<ahv-host-ip> "ovs-vsctl show"            # OVS bridge configuration
ssh root@<ahv-host-ip> "uptime && uname -r"        # Host uptime and kernel
ssh root@<ahv-host-ip> "free -h"                    # Host memory
ssh root@<ahv-host-ip> "cat /proc/cpuinfo | grep 'model name' | head -1"  # CPU model
```

### Running Commands Across All CVMs

CVMs within a cluster have passwordless SSH to each other:

```bash
for cvm in <CVM_IP_1> <CVM_IP_2> ... <CVM_IP_N>; do
  echo "=== $cvm ==="
  ssh -o ConnectTimeout=5 nutanix@$cvm "<COMMAND>" 2>&1
done
```

Alternatively, use Tendril's parallel execution by targeting each CVM agent individually.

## Pre-Maintenance Checklist

Run before AOS upgrades, LCM updates, or hardware maintenance:

```bash
export PATH=$PATH:/usr/local/nutanix/bin:/home/nutanix/prism/cli
echo "=== Cluster ==="
ncli cluster info | grep -E "Cluster Name|Version|Node Count"
echo "=== Host Status ==="
ncli host ls | grep -E "Name|Host Status|Under Maintenance"
echo "=== Critical Alerts ==="
ncli alerts ls | grep -B2 "kCritical"
echo "=== Storage ==="
ncli sp ls | grep -E "Capacity|Used|Free"
echo "=== Disks ==="
ncli disk ls | grep "Online" | sort | uniq -c
echo "=== Protection Domains ==="
ncli pd ls | grep -E "Protection Domain|Active"
```

**Go/No-Go:**
- All hosts NORMAL, none under maintenance
- No unaddressed critical alerts
- Storage pool below 80% used
- All disks online
- All protection domains active

## Deployment Notes

- **Install location:** `/opt/tendril/` on each CVM
- **Service:** systemd (`tendril.service`), auto-recovery enabled
- **Persistence:** CVM agents survive AOS rolling upgrades (CVMs are upgraded in-place).
  AHV hypervisor upgrades do NOT affect CVM-installed agents.
- **Upgrades:** During AOS rolling upgrades, expect brief agent disconnects as each CVM
  restarts sequentially. The agent will auto-reconnect.
- **Why CVM, not AHV:** AHV hypervisor hosts are re-imaged during upgrades, which would
  wipe the agent. CVMs are persistent and have all the management tools.
