---
name: hycu
description: "HYCU Backup & Recovery — VM, application, and file share protection with backup job management, policy configuration, target storage, event monitoring, restore operations, and reporting via REST API v1.0"
category: backup
metadata:
  skill_scope: bridge
  version: "2026.02.26.1"
credentials:
  - key: HYCU_API_KEY
    env: HYCU_API_KEY
    description: "Per-operator API key generated in HYCU UI"
  - key: HYCU_SERVER
    env: HYCU_SERVER
    description: "HYCU controller IP or hostname"
  - key: HYCU_PORT
    env: HYCU_PORT
    description: "HYCU API port (default 8443)"
---

# HYCU Backup & Recovery Bridge

Gateway to an on-premises HYCU Backup & Recovery controller via REST API v1.0.
Provides full visibility into VM, application, and file share protection — backup
jobs, policies, storage targets, events, snapshots, restore operations, and reporting.

## Credential Setup

Each operator must generate an API key in the HYCU UI:

1. Log in to HYCU at `https://<server>:8443`
2. Go to **Administration > API Keys**
3. Click **Create** and set an expiration period
4. Copy the API key
5. Store via Tendril: `bridge_credentials(action="set", bridge="hycu", key="HYCU_API_KEY", value="<key>")`
6. Also set: `bridge_credentials(action="set", bridge="hycu", key="HYCU_SERVER", value="<ip-or-hostname>")`

## CLI Reference

All commands run on `bridge-hycu` at `/opt/bridge/data/tools/`.

### Administration

```
python3 hycu.py admin status          # Full controller status (version, license, scheduler, timezone)
python3 hycu.py admin version         # Software version
python3 hycu.py admin license         # License details
python3 hycu.py admin clusters        # Hypervisor sources (Nutanix, VMware, etc.)
python3 hycu.py admin encryption      # Encryption keys
python3 hycu.py admin worker          # Worker status
python3 hycu.py admin physical-machines # Physical machine list
python3 hycu.py admin logging         # Log configuration
python3 hycu.py admin purge           # DB purge settings
python3 hycu.py admin suspend-scheduler  # Suspend all scheduled tasks
python3 hycu.py admin start-scheduler    # Resume scheduled tasks
```

### Virtual Machines

```
python3 hycu.py vms list                           # All protected VMs
python3 hycu.py vms list --limit 50                # Paginated
python3 hycu.py vms detail --id <uuid>             # VM details
python3 hycu.py vms backups                        # All VM backups across fleet
python3 hycu.py vms backups --id <vm-uuid>         # Backups for specific VM
python3 hycu.py vms snapshots                      # All snapshots
python3 hycu.py vms snapshots --id <vm-uuid>       # Snapshots for specific VM
python3 hycu.py vms disks --id <vm-uuid>           # VM disk list
python3 hycu.py vms restore-locations --id <uuid>  # Possible restore destinations
python3 hycu.py vms backup-metadata --backup-id <uuid>  # Backup metadata
python3 hycu.py vms backup --id <vm-uuid>          # Trigger ad-hoc VM backup
python3 hycu.py vms mount-backup --id <vm-uuid> --backup-id <uuid>    # Mount for FLR
python3 hycu.py vms unmount-backup --id <vm-uuid> --backup-id <uuid>  # Unmount
```

### Jobs

```
python3 hycu.py jobs list              # All jobs (backup, restore, archive, etc.)
python3 hycu.py jobs list --limit 20   # Recent jobs
python3 hycu.py jobs detail --id <uuid>  # Job details
python3 hycu.py jobs report --id <uuid>  # Job report
python3 hycu.py jobs kill --id <uuid>    # Kill running job
python3 hycu.py jobs rerun --id <uuid>   # Rerun failed job
```

### Policies

```
python3 hycu.py policies list                      # All backup policies
python3 hycu.py policies detail --id <uuid>        # Policy details (schedule, retention, targets)
python3 hycu.py policies backupable-count --id <uuid>  # How many VMs/apps assigned
python3 hycu.py policies retention-limit           # Max retention limit
```

### Targets (Backup Storage)

```
python3 hycu.py targets list                # All backup targets
python3 hycu.py targets detail --id <uuid>  # Target details (type, capacity, status)
python3 hycu.py targets test --id <uuid>    # Test target connectivity
python3 hycu.py targets benchmark --id <uuid>  # Benchmark target performance
python3 hycu.py targets activate --id <uuid>   # Activate target
python3 hycu.py targets deactivate --id <uuid> # Deactivate target
python3 hycu.py targets sync-catalog        # Synchronize target catalog
```

### Events

```
python3 hycu.py events list              # All events
python3 hycu.py events list --limit 50   # Recent events
python3 hycu.py events detail --id <uuid>  # Event details
python3 hycu.py events categories        # Event category definitions
```

### Applications

```
python3 hycu.py apps list                  # All protected applications (SQL, Exchange, etc.)
python3 hycu.py apps detail --id <uuid>    # Application details
python3 hycu.py apps backups --id <uuid>   # Application backups
python3 hycu.py apps config --id <uuid>    # Application configuration
python3 hycu.py apps discover              # Run application discovery
python3 hycu.py apps clusters              # Application clusters
```

### File Shares

```
python3 hycu.py shares list                       # All protected shares
python3 hycu.py shares detail --id <uuid>          # Share details
python3 hycu.py shares backups                     # All share backups
python3 hycu.py shares backups --id <share-uuid>   # Backups for specific share
python3 hycu.py shares browse --backup-id <uuid>   # Browse share backup (FLR)
```

### Volume Groups

```
python3 hycu.py volumegroups list                     # All volume groups
python3 hycu.py volumegroups detail --id <uuid>       # VG details
python3 hycu.py volumegroups backups                  # All VG backups
python3 hycu.py volumegroups backups --id <vg-uuid>   # Backups for specific VG
```

### Users & Groups

```
python3 hycu.py users list              # All users
python3 hycu.py users detail --id <uuid>  # User details
python3 hycu.py users roles             # Available roles
python3 hycu.py users groups            # All user groups
python3 hycu.py users groups --id <uuid>  # Groups for specific user
python3 hycu.py users api-keys          # List API keys
```

### Archives

```
python3 hycu.py archives list                  # All archive configurations
python3 hycu.py archives detail --id <uuid>    # Archive details
python3 hycu.py archives policies --id <uuid>  # Policies using this archive
```

### Backup Windows

```
python3 hycu.py windows list                  # All backup windows
python3 hycu.py windows detail --id <uuid>    # Window schedule details
python3 hycu.py windows policies --id <uuid>  # Policies using this window
```

### Reports

```
python3 hycu.py reports list              # All report definitions
python3 hycu.py reports detail --id <uuid>  # Report details
python3 hycu.py reports generate --id <uuid>  # Generate report version
python3 hycu.py reports schedules         # Scheduled reports
```

### Credential Groups

```
python3 hycu.py credentials list   # All credential groups (for application-aware backups)
```

### Validation Policies

```
python3 hycu.py validation list                # All validation policies
python3 hycu.py validation detail --id <uuid>  # Validation policy details
```

### Webhooks

```
python3 hycu.py webhooks list                  # All webhooks
python3 hycu.py webhooks detail --id <uuid>    # Webhook details
python3 hycu.py webhooks ping --name <name>    # Ping a webhook
```

### Networks

```
python3 hycu.py networks list    # Network configurations
python3 hycu.py networks sites   # Network sites (throttling)
```

### Mounts (File-Level Restore)

```
python3 hycu.py mounts list              # Active mounts
python3 hycu.py mounts browse --id <uuid>  # Browse mounted backup
```

### Health Check

```
python3 hycu_check.py   # Run full health check (20 API endpoint tests)
```

## Common Workflows

### Daily Backup Review
1. `admin status` — controller health, scheduler running, license valid
2. `jobs list --limit 20` — check recent job status (completed/failed/running)
3. `events list --limit 50` — review warnings and errors
4. `targets list` — verify target storage capacity

### Investigate Failed Backup
1. `jobs detail --id <job-uuid>` — check job status and error
2. `jobs report --id <job-uuid>` — detailed sub-job report
3. `jobs rerun --id <job-uuid>` — retry the failed job
4. `events list` — correlated events

### Ad-hoc VM Backup
1. `vms list` — find the VM UUID
2. `vms backup --id <vm-uuid>` — trigger backup
3. `jobs list` — monitor the backup job

### File-Level Restore
1. `vms backups --id <vm-uuid>` — find the backup to restore from
2. `vms mount-backup --id <vm-uuid> --backup-id <backup-uuid>` — mount
3. `mounts browse --id <mount-uuid>` — browse files
4. `vms unmount-backup --id <vm-uuid> --backup-id <backup-uuid>` — cleanup

### Policy Audit
1. `policies list` — all policies with schedules and retention
2. `policies detail --id <uuid>` — specific policy configuration
3. `policies backupable-count --id <uuid>` — how many entities are assigned
4. `vms list` — cross-reference unprotected VMs

## API Surface

558 endpoints across 48 API groups covering: administration, VMs, jobs, policies,
targets, events, applications, shares, volume groups, users, API keys, archives,
backup windows, restore points, credential groups, validation policies, reporting,
webhooks, networks, mounts, certificates, SSH, upgrade/hotfixes, SMTP/notifications,
Active Directory, identity providers, cloud accounts (AWS, Azure, GCP), telemetry,
and HYCU instances.
