#!/bin/bash
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

# ============================================================================
# Automated setup for bridge-microsoft-defender
# ============================================================================
# Creates an Entra app registration with the correct API permissions for
# Defender XDR, MDE, and Sentinel, plus ARM RBAC role assignments.
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Global Administrator or Application Administrator role
#   - Subscription Contributor (for Sentinel RBAC)
#
# Usage:
#   chmod +x setup_defender_bridge.sh
#   ./setup_defender_bridge.sh
# ============================================================================

set -e

APP_NAME="Tendril Defender Bridge"

echo "============================================"
echo "  Tendril Defender Bridge -- Automated Setup"
echo "============================================"
echo ""

# Get tenant info
TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Tenant ID:       $TENANT_ID"
echo "Subscription ID: $SUBSCRIPTION_ID"
echo ""

# Step 1: Create app registration
echo "[1/5] Creating app registration: $APP_NAME"
APP_ID=$(az ad app create \
    --display-name "$APP_NAME" \
    --sign-in-audience AzureADMyOrg \
    --query appId -o tsv)
echo "  App ID: $APP_ID"

# Create service principal
SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
echo "  SP Object ID: $SP_ID"

# Step 2: Create client secret
echo ""
echo "[2/5] Creating client secret..."
SECRET=$(az ad app credential reset \
    --id "$APP_ID" \
    --display-name "tendril-bridge-secret" \
    --years 2 \
    --query password -o tsv)
echo "  Client Secret: $SECRET"
echo "  (save this -- it won't be shown again)"

# Step 3: Add API permissions
echo ""
echo "[3/5] Adding API permissions..."

# Microsoft Threat Protection (Defender XDR)
# Resource ID: 8ee8fdad-f234-4243-8f3b-15c294843740
echo "  Adding Microsoft Threat Protection permissions..."
az ad app permission add --id "$APP_ID" \
    --api 8ee8fdad-f234-4243-8f3b-15c294843740 \
    --api-permissions \
    dd98c7f5-2d42-42d8-a6d0-7b174f86eab5=Role \
    7734e8e5-8dde-42fc-b5ae-6eafea078693=Role \
    128ca929-1a19-45e6-a3b8-435ec44a36ba=Role \
    2>&1 | head -5

# WindowsDefenderATP (MDE)
# Resource ID: fc780465-2017-40d4-a0c5-307022471b92
echo "  Adding WindowsDefenderATP permissions..."
az ad app permission add --id "$APP_ID" \
    --api fc780465-2017-40d4-a0c5-307022471b92 \
    --api-permissions \
    ea8291d3-4b9a-44b5-bc3a-6cea3026dc79=Role \
    41269fc5-d04d-4bfd-bce7-43a51cea049a=Role \
    93489bf5-0fbc-4f2d-b901-33f2fe08ff05=Role \
    e60e5f01-acf4-4632-8861-33ada7e52726=Role \
    f8dcd971-5d83-4e1e-aa95-ef44611ad351=Role \
    37f71c98-d198-41ae-964d-f7571f1a1261=Role \
    6443965c-7dd2-4cfd-b38f-bb7772bee163=Role \
    2>&1 | head -5

echo ""
echo "[4/5] Granting admin consent..."
sleep 5
az ad app permission admin-consent --id "$APP_ID" 2>&1 | head -3

# If admin-consent fails with BadRequest/ConsentValidationFailed, grant
# roles individually via appRoleAssignment.  Look up the resource SP object
# IDs for Microsoft Threat Protection and WindowsDefenderATP, then POST to:
#
#   az rest --method POST \
#     --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_ID/appRoleAssignments" \
#     --body '{"principalId":"'$SP_ID'","resourceId":"<resource-sp-object-id>","appRoleId":"<guid>"}'
#
# To find <resource-sp-object-id>:
#   az ad sp list --filter "appId eq '8ee8fdad-f234-4243-8f3b-15c294843740'" --query "[0].id" -o tsv   # Threat Protection
#   az ad sp list --filter "appId eq 'fc780465-2017-40d4-a0c5-307022471b92'" --query "[0].id" -o tsv   # WindowsDefenderATP
#
# Repeat the POST for each appRoleId listed at the bottom of this script.

# Step 5: RBAC role assignments for Sentinel
echo ""
echo "[5/5] ARM RBAC role assignments..."
echo "  Enter the resource group containing your Sentinel workspace."
read -p "  Resource Group Name: " RG_NAME

if [ -n "$RG_NAME" ]; then
    echo "  Assigning 'Microsoft Sentinel Contributor'..."
    az role assignment create \
        --assignee "$SP_ID" \
        --role "Microsoft Sentinel Contributor" \
        --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME" \
        2>&1 | head -3

    echo "  Assigning 'Log Analytics Reader'..."
    az role assignment create \
        --assignee "$SP_ID" \
        --role "Log Analytics Reader" \
        --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME" \
        2>&1 | head -3

    # Get workspace details
    echo ""
    echo "  Looking up Log Analytics workspace..."
    WS_INFO=$(az monitor log-analytics workspace list \
        --resource-group "$RG_NAME" \
        --query "[0].{name:name,id:customerId}" -o json 2>/dev/null || echo "{}")
    WS_NAME=$(echo "$WS_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name',''))" 2>/dev/null || echo "")
    WS_ID=$(echo "$WS_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")

    if [ -n "$WS_NAME" ]; then
        echo "  Workspace Name: $WS_NAME"
        echo "  Workspace ID:   $WS_ID"
    fi
else
    echo "  Skipped RBAC (no resource group provided)"
    echo "  You can assign roles later with:"
    echo "    az role assignment create --assignee $SP_ID --role 'Microsoft Sentinel Contributor' --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/<rg>"
    echo "    az role assignment create --assignee $SP_ID --role 'Log Analytics Reader' --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/<rg>"
fi

# Summary
echo ""
echo "============================================"
echo "  Setup Complete"
echo "============================================"
echo ""
echo "Add these to your .env file:"
echo ""
echo "  AZURE_TENANT_ID=$TENANT_ID"
echo "  DEFENDER_CLIENT_ID=$APP_ID"
echo "  DEFENDER_CLIENT_SECRET=$SECRET"
if [ -n "$WS_NAME" ]; then
    echo "  SENTINEL_SUBSCRIPTION_ID=$SUBSCRIPTION_ID"
    echo "  SENTINEL_RESOURCE_GROUP=$RG_NAME"
    echo "  SENTINEL_WORKSPACE_NAME=$WS_NAME"
    echo "  SENTINEL_WORKSPACE_ID=$WS_ID"
fi
echo ""
echo "Next steps:"
echo "  1. Copy the above values to your .env file"
echo "  2. Wait 5-15 minutes for permission propagation"
echo "  3. Run health check: python3 defender_check.py"
echo "  4. Run battery test: python3 defender_bridge_tests.py"
echo "  5. Deploy via Docker Compose: docker compose up -d"
echo ""
echo "API permission GUIDs used:"
echo "  Microsoft Threat Protection:"
echo "    AdvancedHunting.Read.All  = dd98c7f5-2d42-42d8-a6d0-7b174f86eab5"
echo "    Incident.ReadWrite.All   = 7734e8e5-8dde-42fc-b5ae-6eafea078693"
echo "    Alert.ReadWrite.All      = 128ca929-1a19-45e6-a3b8-435ec44a36ba"
echo "  WindowsDefenderATP:"
echo "    Machine.ReadWrite.All              = ea8291d3-4b9a-44b5-bc3a-6cea3026dc79"
echo "    Vulnerability.Read.All             = 41269fc5-d04d-4bfd-bce7-43a51cea049a"
echo "    AdvancedQuery.Read.All             = 93489bf5-0fbc-4f2d-b901-33f2fe08ff05"
echo "    Ti.ReadWrite.All                   = e60e5f01-acf4-4632-8861-33ada7e52726"
echo "    Alert.ReadWrite.All                = f8dcd971-5d83-4e1e-aa95-ef44611ad351"
echo "    Software.Read.All                  = 37f71c98-d198-41ae-964d-f7571f1a1261"
echo "    SecurityRecommendation.Read.All    = 6443965c-7dd2-4cfd-b38f-bb7772bee163"
