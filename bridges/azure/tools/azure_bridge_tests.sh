#!/usr/bin/env bash
# Azure Bridge Battery Test
# Tests az CLI + ARM REST API across all resource types in the configured Azure subscription
# Tests: ~35 across 12 categories
# Runtime: ~2-3 minutes

set -uo pipefail

PASS=0
FAIL=0
SKIP=0
TOTAL=0

pass() { PASS=$((PASS+1)); TOTAL=$((TOTAL+1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL+1)); TOTAL=$((TOTAL+1)); echo "  FAIL: $1 -- $2"; }
skip() { SKIP=$((SKIP+1)); TOTAL=$((TOTAL+1)); echo "  SKIP: $1 -- $2"; }

TOOLS_DIR="/opt/bridge/data/tools"

# ============================================================
# Category 1: Bridge Health
# ============================================================
echo ""
echo "=== Category 1: Bridge Health ==="

# Test 1: az CLI installed
echo "Test 1: az CLI installed"
AZ_VER=$(az --version 2>&1 | head -1)
if echo "$AZ_VER" | grep -q "azure-cli"; then
    pass "az CLI installed ($AZ_VER)"
else
    fail "az CLI not found" "$AZ_VER"
fi

# Test 2: Service principal login valid
echo "Test 2: Service principal login"
ACCT=$(az account show --query 'name' -o tsv 2>&1)
if [ -n "$ACCT" ] && [ "$ACCT" != "" ]; then
    pass "Logged in to $ACCT"
else
    fail "Not logged in" "$ACCT"
fi

# Test 3: Subscription accessible
echo "Test 3: Subscription accessible"
SUB_ID=$(az account show --query 'id' -o tsv 2>&1)
EXPECTED_SUB_ID="${AZURE_SUBSCRIPTION_ID:-}"
if [ -n "$EXPECTED_SUB_ID" ]; then
    if [ "$SUB_ID" = "$EXPECTED_SUB_ID" ]; then
        pass "Subscription ID matches"
    else
        fail "Subscription ID mismatch" "expected=$EXPECTED_SUB_ID got=$SUB_ID"
    fi
else
    if [ -n "$SUB_ID" ] && [ "${#SUB_ID}" -eq 36 ] 2>/dev/null; then
        pass "Subscription ID present (UUID format)"
    else
        fail "No valid subscription ID" "$SUB_ID"
    fi
fi

# Test 4: Python helpers present
echo "Test 4: Python helpers"
HELPER_COUNT=$(ls "$TOOLS_DIR"/*.py 2>/dev/null | wc -l)
if [ "$HELPER_COUNT" -ge 4 ]; then
    pass "$HELPER_COUNT Python helpers in $TOOLS_DIR"
else
    fail "Too few Python helpers" "$HELPER_COUNT"
fi

# Test 5: ARM client health check
echo "Test 5: ARM client health check"
CHECK=$(python3 "$TOOLS_DIR/arm_check.py" 2>&1)
if [ $? -eq 0 ]; then
    pass "arm_check.py passed"
else
    fail "arm_check.py failed" "$CHECK"
fi

# ============================================================
# Category 2: Resource Enumeration
# ============================================================
echo ""
echo "=== Category 2: Resource Enumeration ==="

# Test 6: Total resource count
echo "Test 6: Total resource count"
TOTAL_RES=$(az resource list --query "length(@)" -o tsv 2>&1)
if [ "$TOTAL_RES" -gt 2000 ] 2>/dev/null; then
    pass "Total resources: $TOTAL_RES"
else
    fail "Too few resources" "$TOTAL_RES"
fi

# Test 7: Resource type count
echo "Test 7: Resource type diversity"
TYPE_COUNT=$(az resource list --query "[].type" -o tsv 2>&1 | sort -u | wc -l)
if [ "$TYPE_COUNT" -gt 50 ] 2>/dev/null; then
    pass "Distinct resource types: $TYPE_COUNT"
else
    fail "Too few types" "$TYPE_COUNT"
fi

# Test 8: Resource group count
echo "Test 8: Resource groups"
RG_COUNT=$(az group list --query "length(@)" -o tsv 2>&1)
if [ "$RG_COUNT" -gt 40 ] 2>/dev/null; then
    pass "Resource groups: $RG_COUNT"
else
    fail "Too few resource groups" "$RG_COUNT"
fi

# ============================================================
# Category 3: Compute
# ============================================================
echo ""
echo "=== Category 3: Compute ==="

# Test 9: Virtual Machines
echo "Test 9: Virtual Machines"
VM_COUNT=$(az vm list --query "length(@)" -o tsv 2>&1)
if [ "$VM_COUNT" -gt 80 ] 2>/dev/null; then
    pass "VMs: $VM_COUNT"
else
    fail "Too few VMs" "$VM_COUNT"
fi

# Test 10: Managed Disks
echo "Test 10: Managed Disks"
DISK_COUNT=$(az resource list --resource-type Microsoft.Compute/disks --query "length(@)" -o tsv 2>/dev/null)
if [ "$DISK_COUNT" -gt 100 ] 2>/dev/null; then
    pass "Managed disks: $DISK_COUNT"
else
    fail "Too few disks" "$DISK_COUNT"
fi

# Test 11: Snapshots
echo "Test 11: Snapshots"
SNAP_COUNT=$(az snapshot list --query "length(@)" -o tsv 2>&1)
if [ "$SNAP_COUNT" -ge 0 ] 2>/dev/null; then
    pass "Snapshots: $SNAP_COUNT"
else
    fail "Snapshot query failed" "$SNAP_COUNT"
fi

# ============================================================
# Category 4: Networking
# ============================================================
echo ""
echo "=== Category 4: Networking ==="

# Test 12: Network Security Groups
echo "Test 12: NSGs"
NSG_COUNT=$(az network nsg list --query "length(@)" -o tsv 2>&1)
if [ "$NSG_COUNT" -gt 50 ] 2>/dev/null; then
    pass "NSGs: $NSG_COUNT"
else
    fail "Too few NSGs" "$NSG_COUNT"
fi

# Test 13: Network Interfaces
echo "Test 13: NICs"
NIC_COUNT=$(az network nic list --query "length(@)" -o tsv 2>&1)
if [ "$NIC_COUNT" -gt 50 ] 2>/dev/null; then
    pass "NICs: $NIC_COUNT"
else
    fail "Too few NICs" "$NIC_COUNT"
fi

# Test 14: Virtual Networks
echo "Test 14: VNets"
VNET_COUNT=$(az network vnet list --query "length(@)" -o tsv 2>&1)
if [ "$VNET_COUNT" -ge 1 ] 2>/dev/null; then
    pass "VNets: $VNET_COUNT"
else
    fail "No VNets found" "$VNET_COUNT"
fi

# Test 15: Public IP Addresses
echo "Test 15: Public IPs"
PIP_COUNT=$(az network public-ip list --query "length(@)" -o tsv 2>&1)
if [ "$PIP_COUNT" -gt 10 ] 2>/dev/null; then
    pass "Public IPs: $PIP_COUNT"
else
    fail "Too few public IPs" "$PIP_COUNT"
fi

# Test 16: VPN Gateways
echo "Test 16: VPN Gateways"
VPN_COUNT=$(az resource list --resource-type Microsoft.Network/virtualNetworkGateways --query "length(@)" -o tsv 2>/dev/null)
if [ "$VPN_COUNT" -ge 1 ] 2>/dev/null; then
    pass "VPN gateways: $VPN_COUNT"
else
    skip "No VPN gateways" "may not be deployed"
fi

# Test 17: Local Network Gateways
echo "Test 17: Local Network Gateways"
LNG_COUNT=$(az resource list --resource-type Microsoft.Network/localNetworkGateways --query "length(@)" -o tsv 2>/dev/null)
if [ "$LNG_COUNT" -gt 10 ] 2>/dev/null; then
    pass "Local gateways: $LNG_COUNT"
else
    fail "Too few local gateways" "$LNG_COUNT"
fi

# Test 18: NAT Gateways
echo "Test 18: NAT Gateways"
NAT_COUNT=$(az network nat gateway list --query "length(@)" -o tsv 2>&1)
if [ "$NAT_COUNT" -ge 1 ] 2>/dev/null; then
    pass "NAT gateways: $NAT_COUNT"
else
    skip "No NAT gateways" "may not be deployed"
fi

# Test 19: Bastion Hosts
echo "Test 19: Bastion Hosts"
BASTION_COUNT=$(az network bastion list --query "length(@)" -o tsv 2>&1)
if [ "$BASTION_COUNT" -ge 1 ] 2>/dev/null; then
    pass "Bastion hosts: $BASTION_COUNT"
else
    skip "No Bastion hosts" "may not be deployed"
fi

# ============================================================
# Category 5: Storage
# ============================================================
echo ""
echo "=== Category 5: Storage ==="

# Test 20: Storage Accounts
echo "Test 20: Storage Accounts"
SA_COUNT=$(az storage account list --query "length(@)" -o tsv 2>&1)
if [ "$SA_COUNT" -gt 5 ] 2>/dev/null; then
    pass "Storage accounts: $SA_COUNT"
else
    fail "Too few storage accounts" "$SA_COUNT"
fi

# ============================================================
# Category 6: Security and Recovery
# ============================================================
echo ""
echo "=== Category 6: Security and Recovery ==="

# Test 21: Key Vaults
echo "Test 21: Key Vaults"
KV_COUNT=$(az keyvault list --query "length(@)" -o tsv 2>&1)
if [ "$KV_COUNT" -ge 1 ] 2>/dev/null; then
    pass "Key Vaults: $KV_COUNT"
else
    fail "No Key Vaults found" "$KV_COUNT"
fi

# Test 22: Recovery Services Vaults
echo "Test 22: Recovery Services Vaults"
RSV_COUNT=$(az backup vault list --query "length(@)" -o tsv 2>&1)
if [ "$RSV_COUNT" -gt 10 ] 2>/dev/null; then
    pass "Recovery Services vaults: $RSV_COUNT"
else
    fail "Too few Recovery vaults" "$RSV_COUNT"
fi

# ============================================================
# Category 7: AVD (Azure Virtual Desktop)
# ============================================================
echo ""
echo "=== Category 7: AVD ==="

# Test 23: Host Pools
echo "Test 23: AVD Host Pools"
HP_COUNT=$(az desktopvirtualization hostpool list --query "length(@)" -o tsv 2>/dev/null)
if [ "$HP_COUNT" -ge 1 ] 2>/dev/null; then
    pass "AVD host pools: $HP_COUNT"
else
    fail "No AVD host pools" "$HP_COUNT"
fi

# Test 24: Application Groups
echo "Test 24: AVD Application Groups"
AG_COUNT=$(az desktopvirtualization applicationgroup list --query "length(@)" -o tsv 2>/dev/null)
if [ "$AG_COUNT" -ge 1 ] 2>/dev/null; then
    pass "AVD app groups: $AG_COUNT"
else
    fail "No AVD app groups" "$AG_COUNT"
fi

# ============================================================
# Category 8: SQL and Data
# ============================================================
echo ""
echo "=== Category 8: SQL and Data ==="

# Test 25: SQL Servers
echo "Test 25: SQL Servers"
SQL_COUNT=$(az sql server list --query "length(@)" -o tsv 2>&1)
if [ "$SQL_COUNT" -ge 1 ] 2>/dev/null; then
    pass "SQL servers: $SQL_COUNT"
else
    fail "No SQL servers" "$SQL_COUNT"
fi

# Test 26: SQL Databases
echo "Test 26: SQL Databases"
if [ "$SQL_COUNT" -ge 1 ] 2>/dev/null; then
    FIRST_SQL_RG=$(az sql server list --query "[0].resourceGroup" -o tsv 2>&1)
    FIRST_SQL_NAME=$(az sql server list --query "[0].name" -o tsv 2>&1)
    DB_COUNT=$(az sql db list -g "$FIRST_SQL_RG" -s "$FIRST_SQL_NAME" --query "length(@)" -o tsv 2>&1)
    if [ "$DB_COUNT" -ge 1 ] 2>/dev/null; then
        pass "SQL databases on $FIRST_SQL_NAME: $DB_COUNT"
    else
        fail "No databases on $FIRST_SQL_NAME" "$DB_COUNT"
    fi
else
    skip "SQL databases" "no SQL servers to query"
fi

# Test 27: PostgreSQL Flexible Servers
echo "Test 27: PostgreSQL Flexible Servers"
PG_COUNT=$(az postgres flexible-server list --query "length(@)" -o tsv 2>&1)
if [ "$PG_COUNT" -ge 1 ] 2>/dev/null; then
    pass "PostgreSQL flexible servers: $PG_COUNT"
else
    skip "No PostgreSQL servers" "may not be deployed"
fi

# ============================================================
# Category 9: Hybrid and Arc
# ============================================================
echo ""
echo "=== Category 9: Hybrid and Arc ==="

# Test 28: Arc Connected Machines
echo "Test 28: Arc Connected Machines"
ARC_COUNT=$(az resource list --resource-type Microsoft.HybridCompute/machines --query "length(@)" -o tsv 2>/dev/null)
if [ "$ARC_COUNT" -gt 10 ] 2>/dev/null; then
    pass "Arc machines: $ARC_COUNT"
else
    fail "Too few Arc machines" "$ARC_COUNT"
fi

# Test 29: SQL Virtual Machines
echo "Test 29: SQL Virtual Machines"
SQLVM_COUNT=$(az sql vm list --query "length(@)" -o tsv 2>&1)
if [ "$SQLVM_COUNT" -gt 10 ] 2>/dev/null; then
    pass "SQL VMs: $SQLVM_COUNT"
else
    fail "Too few SQL VMs" "$SQLVM_COUNT"
fi

# ============================================================
# Category 10: Monitoring and Automation
# ============================================================
echo ""
echo "=== Category 10: Monitoring and Automation ==="

# Test 30: Log Analytics Workspaces
echo "Test 30: Log Analytics Workspaces"
LA_COUNT=$(az monitor log-analytics workspace list --query "length(@)" -o tsv 2>&1)
if [ "$LA_COUNT" -ge 1 ] 2>/dev/null; then
    pass "Log Analytics workspaces: $LA_COUNT"
else
    fail "No Log Analytics workspaces" "$LA_COUNT"
fi

# Test 31: Automation Accounts
echo "Test 31: Automation Accounts"
AUTO_COUNT=$(az resource list --resource-type Microsoft.Automation/automationAccounts --query "length(@)" -o tsv 2>/dev/null)
if [ "$AUTO_COUNT" -ge 1 ] 2>/dev/null; then
    pass "Automation accounts: $AUTO_COUNT"
else
    fail "No Automation accounts" "$AUTO_COUNT"
fi

# Test 32: Metric Alerts
echo "Test 32: Metric Alerts"
ALERT_COUNT=$(az monitor metrics alert list --query "length(@)" -o tsv 2>&1)
if [ "$ALERT_COUNT" -gt 100 ] 2>/dev/null; then
    pass "Metric alerts: $ALERT_COUNT"
else
    fail "Too few metric alerts" "$ALERT_COUNT"
fi

# ============================================================
# Category 11: Web and App Services
# ============================================================
echo ""
echo "=== Category 11: Web and App Services ==="

# Test 33: Web Apps
echo "Test 33: Web Apps"
WEBAPP_COUNT=$(az webapp list --query "length(@)" -o tsv 2>&1)
if [ "$WEBAPP_COUNT" -ge 1 ] 2>/dev/null; then
    pass "Web apps: $WEBAPP_COUNT"
else
    skip "No web apps" "may not be deployed"
fi

# Test 34: App Service Plans
echo "Test 34: App Service Plans"
ASP_COUNT=$(az appservice plan list --query "length(@)" -o tsv 2>&1)
if [ "$ASP_COUNT" -ge 1 ] 2>/dev/null; then
    pass "App Service plans: $ASP_COUNT"
else
    skip "No App Service plans" "may not be deployed"
fi

# ============================================================
# Category 12: Cross-Validation
# ============================================================
echo ""
echo "=== Category 12: Cross-Validation ==="

# Test 35: az CLI vs ARM client VM count
echo "Test 35: az CLI vs ARM REST API VM count"
AZ_VM_COUNT=$(az vm list --query "length(@)" -o tsv 2>&1)
ARM_VM_COUNT=$(python3 -c "
import sys; sys.path.insert(0, '$TOOLS_DIR')
from arm_client import ArmClient
c = ArmClient()
print(len(c.list_vms()))
" 2>&1)
if [ "$AZ_VM_COUNT" = "$ARM_VM_COUNT" ] 2>/dev/null; then
    pass "VM counts match: az=$AZ_VM_COUNT arm=$ARM_VM_COUNT"
else
    fail "VM count mismatch" "az=$AZ_VM_COUNT arm=$ARM_VM_COUNT"
fi

# ============================================================
# Summary
# ============================================================
echo ""
echo "============================================"
echo "  Azure Bridge Battery Test Summary"
echo "============================================"
echo "  PASS: $PASS"
echo "  FAIL: $FAIL"
echo "  SKIP: $SKIP"
echo "  TOTAL: $TOTAL"
echo "============================================"

if [ $FAIL -gt 0 ]; then
    echo "  STATUS: SOME TESTS FAILED"
    exit 1
else
    echo "  STATUS: ALL TESTS PASSED"
    exit 0
fi
