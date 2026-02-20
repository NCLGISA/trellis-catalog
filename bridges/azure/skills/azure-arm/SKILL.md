---
name: azure-arm
description: Access Azure Resource Manager -- VMs, NSGs, storage, AVD, Arc, Key Vault, Recovery Services, SQL, monitoring, and all resource types across your Azure subscription via az CLI and Python REST helpers.
compatibility:
  - platform: linux
    arch: amd64
    min_version: "2026.02.16"
metadata:
  author: tendril-project
  version: "2.1.0"
  tendril-bridge: "true"
  skill_scope: "bridge"
  tags:
    - azure
    - arm
    - compute
    - networking
    - avd
    - storage
    - keyvault
    - recovery
    - sql
    - arc
    - monitoring
---

# Azure Resource Manager Bridge

Access your Azure subscription via Azure CLI and ARM REST API. Covers VMs, NSGs, disks, Key Vaults, Recovery Services, AVD, Arc machines, SQL servers, monitoring, and cost data.

This bridge supplements (does not replace) hardware Tendril agents deployed on Azure VMs. Hardware agents provide OS-level depth (services, logs, registry); this bridge provides ARM-level breadth (all Azure resource types, power state, cost data).

## Authentication

Two authentication methods are available -- both use the same service principal:

1. **az CLI** (primary): Service principal login at container startup via `az login --service-principal`. Pre-authenticated and ready for any `az` command.
2. **Python MSAL** (helpers): `client_credentials` flow for compound workflows requiring custom logic.

**App Registration:** Configure via AZURE_CLIENT_ID
**Tenant:** Configured via AZURE_TENANT_ID environment variable
**Subscription:** Configured via az CLI login or service principal

**RBAC roles assigned:**
- `Contributor` on subscription -- full read/write access to all ARM resources
- `Desktop Virtualization Contributor` on subscription -- full read/write access to AVD resources

## Quick Start (az CLI)

The `az` CLI is pre-authenticated. Use it directly for any Azure query.

```bash
# List all VMs with power state
az vm list -d --query "[].{name:name, rg:resourceGroup, powerState:powerState, size:hardwareProfile.vmSize}" -o json

# List all resource groups
az group list --query "[].{name:name, location:location}" -o json

# Count all resources by type (tsv + pipe for shell aggregation)
az resource list --query "[].type" -o tsv | sort | uniq -c | sort -rn | head -20

# Get a specific VM
az vm show -g rg-name -n vm-name -d -o json

# List NSG rules
az network nsg rule list -g rg-name --nsg-name nsg-name -o json

# Key Vault secrets (names only -- values require access policy)
az keyvault secret list --vault-name vault-name --query "[].name" -o json

# Recovery Services vault list
az backup vault list --query "[].{name:name, rg:resourceGroup}" -o json

# SQL databases
az sql db list -g rg-name -s server-name --query "[].{name:name, status:status, sku:currentSku.name}" -o json

# Arc connected machines
az resource list --resource-type Microsoft.HybridCompute/machines --query "[].{name:name, rg:resourceGroup}" -o json

# Cost for current month (replace SUBSCRIPTION_ID with your subscription ID)
az costmanagement query --type ActualCost --scope "/subscriptions/SUBSCRIPTION_ID" --timeframe MonthToDate --query "properties.rows[:10]" -o json
```

## Tools (Python Helpers)

For compound workflows requiring custom logic, use the Python helpers:

| Script | Location | Purpose |
|--------|----------|---------|
| `arm_client.py` | `/opt/bridge/data/tools/` | REST API client with MSAL auth, pagination, rate limiting |
| `arm_check.py` | `/opt/bridge/data/tools/` | Health check: validates env vars and API access |
| `vm_inventory.py` | `/opt/bridge/data/tools/` | VM listing, power state, detailed views |
| `nsg_query.py` | `/opt/bridge/data/tools/` | NSG rules, port search, segmentation analysis |
| `avd_status.py` | `/opt/bridge/data/tools/` | AVD host pools, session hosts, user sessions |

```bash
# Verify bridge connectivity
python3 /opt/bridge/data/tools/arm_check.py

# Python helper examples
python3 /opt/bridge/data/tools/vm_inventory.py list
python3 /opt/bridge/data/tools/nsg_query.py list
python3 /opt/bridge/data/tools/avd_status.py overview
```

## az CLI Patterns by Category

### Compute

```bash
az vm list --query "length(@)" -o tsv                     # VM count (scalar -- tsv)
az vm list -d --query "[].{name:name, rg:resourceGroup, powerState:powerState, size:hardwareProfile.vmSize}" -o json
az resource list --resource-type Microsoft.Compute/disks --query "length(@)" -o tsv  # Disk count (scalar -- tsv)
az snapshot list --query "[].{name:name, size:diskSizeGb}" -o json
az sql vm list --query "[].{name:name, rg:resourceGroup, sqlImage:sqlImageSku}" -o json
```

### Networking

```bash
az network nsg list --query "[].{name:name, rg:resourceGroup}" -o json
az network nic list --query "length(@)" -o tsv             # NIC count (scalar -- tsv)
az network vnet list --query "[].{name:name, rg:resourceGroup, addressSpace:addressSpace.addressPrefixes[0]}" -o json
az network public-ip list --query "[].{name:name, ip:ipAddress, method:publicIpAllocationMethod}" -o json
az resource list --resource-type Microsoft.Network/virtualNetworkGateways --query "[].{name:name, rg:resourceGroup}" -o json
az resource list --resource-type Microsoft.Network/localNetworkGateways --query "length(@)" -o tsv  # Count (scalar -- tsv)
az network nat gateway list --query "[].{name:name, rg:resourceGroup}" -o json
az network bastion list --query "[].{name:name, rg:resourceGroup}" -o json
```

### Storage

```bash
az storage account list --query "[].{name:name, rg:resourceGroup, sku:sku.name, kind:kind}" -o json
```

### Security and Recovery

```bash
az keyvault list --query "[].{name:name, rg:resourceGroup, sku:properties.sku.name}" -o json
az backup vault list --query "[].{name:name, rg:resourceGroup}" -o json
```

### Azure Virtual Desktop (AVD)

```bash
az desktopvirtualization hostpool list --query "[].{name:name, rg:resourceGroup, type:hostPoolType}" -o json
az desktopvirtualization applicationgroup list --query "[].{name:name, rg:resourceGroup}" -o json
```

### SQL and Data

```bash
az sql server list --query "[].{name:name, rg:resourceGroup, fqdn:fullyQualifiedDomainName}" -o json
az sql db list -g RG_NAME -s SERVER_NAME --query "[].{name:name, status:status}" -o json
az postgres flexible-server list --query "[].{name:name, rg:resourceGroup, version:version}" -o json
```

### Hybrid and Arc

```bash
az resource list --resource-type Microsoft.HybridCompute/machines --query "[].{name:name, rg:resourceGroup}" -o json
az sql vm list --query "[].{name:name, sqlImage:sqlImageSku}" -o json
```

### Monitoring and Automation

```bash
az monitor log-analytics workspace list --query "[].{name:name, rg:resourceGroup, sku:sku.name}" -o json
az resource list --resource-type Microsoft.Automation/automationAccounts --query "[].{name:name, rg:resourceGroup}" -o json
az monitor metrics alert list --query "length(@)" -o tsv   # Count (scalar -- tsv)
```

### Web and App Services

```bash
az webapp list --query "[].{name:name, rg:resourceGroup, state:state}" -o json
az appservice plan list --query "[].{name:name, rg:resourceGroup, sku:sku.name}" -o json
```

### Resource Discovery (any type)

```bash
# Generic pattern for any resource type
az resource list --resource-type PROVIDER/TYPE --query "[].{name:name, rg:resourceGroup}" -o json

# Find all resource types in the subscription (tsv + pipe for shell aggregation)
az resource list --query "[].type" -o tsv | sort | uniq -c | sort -rn
```

## Python API Coverage (Compound Workflows)

```python
from arm_client import ArmClient
client = ArmClient()

# Resource Groups
client.list_resource_groups()

# Virtual Machines
client.list_vms()
client.get_vm("rg", "vm", instance_view=True)
client.list_vm_statuses()
client.vm_power_action("rg", "vm", "start")  # start|deallocate|restart|powerOff

# NSGs
client.list_nsgs()
client.get_nsg("rg", "nsg")
client.list_nsg_rules("rg", "nsg")

# VNets and Storage
client.list_vnets()
client.list_storage_accounts()

# AVD
client.list_host_pools()
client.list_session_hosts("rg", "pool")
client.list_user_sessions("rg", "pool", "host")
client.list_app_groups()

# Monitor and Cost
client.get_metrics(resource_id="...", metric_names="Percentage CPU", timespan="PT1H")
client.get_cost_summary(timeframe="MonthToDate")
```

## Common IT Service Provider Patterns

### Segmentation Analysis
1. `az network nsg list -o json` -- enumerate all NSGs
2. `python3 nsg_query.py find-port 3389` -- find RDP exposure
3. Cross-reference with Tendril segmentation tests for live validation

### VM Power State Audit
1. `az vm list -d --query "[?powerState!='VM running']" -o json` -- find deallocated VMs
2. Check cost impact via `client.get_cost_summary()`

### AVD Session Monitoring
1. `python3 avd_status.py overview` -- full AVD summary
2. `az desktopvirtualization hostpool list -o json` -- host pool health

### Cost Review
Use `client.get_cost_summary(timeframe="MonthToDate")` for cost by resource group.

## Output Format Guidance

Use `-o json` as the default for all az CLI queries. JSON preserves full response fidelity -- nested objects, arrays, nulls, and data types -- enabling the AI to reason about, chain, and transform results in multi-step workflows.

| Format | When to Use | Example |
|--------|-------------|---------|
| `-o json` | **Default.** All queries where the AI will process, chain, or reason about the result. | `az vm list -d --query "[].{name:name, powerState:powerState}" -o json` |
| `-o tsv` | Scalar values from `length(@)` or flat string lists piped into shell tools (`sort`, `wc`, `uniq`). | `az vm list --query "length(@)" -o tsv` |
| `-o table` | Only when the operator explicitly asks for human-readable display. Never as a default. | `az vm list -d -o table` (operator requested) |

**Why not tsv for lists?** TSV strips keys, discards nesting, and silently corrupts multi-value fields (e.g., an array of IP addresses on a NIC becomes a single cell). A field that is `null` vs `""` is indistinguishable. JSON avoids all of these issues.

**Why not table?** Table truncates long values to fit column widths, is unparseable by downstream tools, and discards all type information. It exists purely for terminal readability.

## API Quirks and Known Issues

- **az CLI is primary:** Use `az` commands for all standard queries. Use Python helpers only for compound workflows.
- **Always use -o json** unless extracting a scalar count (`length(@)` with `-o tsv`) or piping a flat list into shell tools.
- **Some commands require -g:** `az disk list`, `az network local-gateway list`, `az connectedmachine list` require resource group. Use `az resource list --resource-type` instead for subscription-wide queries.
- **Extension warnings:** Some commands (AVD, Arc, Automation) trigger extension auto-install on first use. Redirect stderr with `2>/dev/null` for clean output.
- **Instance view for power state:** `az vm list` does not include power state; use `az vm list -d` or `--show-details` flag.
- **Rate limits:** ARM has per-subscription rate limits (~12,000 reads/hour). The Python client handles 429s with `Retry-After` backoff.
- **Cost Management queries:** Can be slow for large subscriptions. Use `MonthToDate` for quick results.

## Hybrid Coverage Model

| Data Type | Hardware Agent (Tendril on VM) | This Bridge (ARM API) |
|-----------|-------------------------------|----------------------|
| OS services, logs, registry | Yes | No |
| VM power state | Partial (agent uptime) | Full (`az vm list -d`) |
| NSG rules and network topology | No | Yes |
| Resource group inventory | No | Yes |
| Disks, snapshots, NICs | No | Yes |
| Key Vaults | No | Yes |
| Recovery Services vaults | No | Yes |
| SQL servers and databases | No | Yes |
| Arc connected machines | No | Yes |
| AVD host pools and sessions | No | Yes |
| Storage accounts | No | Yes |
| Azure Monitor metrics and alerts | No | Yes |
| Automation accounts | No | Yes |
| Web Apps and App Service plans | No | Yes |
| Cost and billing | No | Yes |
| Entra ID (users, groups) | No | No (use bridge-microsoft-graph) |

## Tenant Context

Discover your subscription's resource inventory with:

```bash
az resource list --query "[].type" -o json | python3 -c "
import json, sys, collections
types = json.load(sys.stdin)
for t, c in sorted(collections.Counter(types).items(), key=lambda x: -x[1]):
    print(f'  {c:>4}  {t}')
print(f'Total: {len(types)} resources across {len(set(types))} types')
"
```
