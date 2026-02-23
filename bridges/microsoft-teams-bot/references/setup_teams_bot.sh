#!/bin/bash
# ============================================================================
# Teams Bot Bridge Setup Script
# ============================================================================
# Automates Entra ID app registration, client secret creation, Azure Bot
# Service resource, Teams channel, Graph API permissions, and admin consent
# for the Teams Bot bridge.
#
# Usage:
#   ./setup_teams_bot.sh <tenant-onmicrosoft-domain> [bot-display-name]
#
# Example:
#   ./setup_teams_bot.sh contoso.onmicrosoft.com "Tendril Bot"
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - Global Administrator or Application Administrator + Teams Administrator
#   - An active Azure subscription (for Bot Service resource)
# ============================================================================
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <tenant-onmicrosoft-domain> [bot-display-name]"
    echo "Example: $0 contoso.onmicrosoft.com \"Tendril Bot\""
    exit 1
fi

ORGANIZATION="$1"
BOT_NAME="${2:-Tendril Bot}"
APP_NAME="Tendril Teams Bot Bridge"
RESOURCE_GROUP="${TEAMS_BOT_RESOURCE_GROUP:-}"

echo "============================================"
echo "Teams Bot Bridge Setup"
echo "Organization: $ORGANIZATION"
echo "Bot Name: $BOT_NAME"
echo "============================================"
echo ""

# Step 1: Verify Azure CLI login
echo "[1/8] Verifying Azure CLI login..."
TENANT_ID=$(az account show --query tenantId -o tsv 2>/dev/null)
SUBSCRIPTION_ID=$(az account show --query id -o tsv 2>/dev/null)
if [ -z "$TENANT_ID" ]; then
    echo "ERROR: Not logged in to Azure CLI. Run 'az login' first."
    exit 1
fi
echo "  Tenant ID: $TENANT_ID"
echo "  Subscription: $SUBSCRIPTION_ID"
echo ""

# Step 2: Create app registration (single-tenant)
echo "[2/8] Creating app registration: $APP_NAME..."
APP_ID=$(az ad app create \
    --display-name "$APP_NAME" \
    --sign-in-audience AzureADMyOrg \
    --query appId -o tsv)
echo "  App ID: $APP_ID"

OBJECT_ID=$(az ad app show --id "$APP_ID" --query id -o tsv)
echo "  Object ID: $OBJECT_ID"
echo ""

# Step 3: Create client secret
echo "[3/8] Creating client secret..."
SECRET_RESULT=$(az ad app credential reset \
    --id "$APP_ID" \
    --display-name "Teams Bot Bridge Secret" \
    --years 2 \
    --query password -o tsv)
echo "  Client secret created (save this -- shown only once)"
echo "  TEAMS_BOT_APP_SECRET=$SECRET_RESULT"
echo ""

# Step 4: Create service principal
echo "[4/8] Creating service principal..."
SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv 2>/dev/null || \
    az ad sp show --id "$APP_ID" --query id -o tsv)
echo "  Service Principal ID: $SP_ID"
echo ""

# Step 5: Add Graph API permissions
echo "[5/8] Adding Graph API permissions..."
GRAPH_API="00000003-0000-0000-c000-000000000000"

# ChatMessage.Read.All
az ad app permission add --id "$APP_ID" \
    --api "$GRAPH_API" \
    --api-permissions b9bb2381-47a4-46cd-aafb-00cb12f68504=Role \
    -o none 2>/dev/null
echo "  + ChatMessage.Read.All (application)"

# Chat.Read.All
az ad app permission add --id "$APP_ID" \
    --api "$GRAPH_API" \
    --api-permissions 6b7d71aa-70aa-4810-a8d9-5d9fb2830017=Role \
    -o none 2>/dev/null
echo "  + Chat.Read.All (application)"

# ChannelMessage.Read.All
az ad app permission add --id "$APP_ID" \
    --api "$GRAPH_API" \
    --api-permissions 7b2449af-6ccd-4f4d-9f78-e550c193f0d1=Role \
    -o none 2>/dev/null
echo "  + ChannelMessage.Read.All (application)"

# Team.ReadBasic.All
az ad app permission add --id "$APP_ID" \
    --api "$GRAPH_API" \
    --api-permissions 2280dda6-0bfd-44ee-a2f4-cb867cfc4c1e=Role \
    -o none 2>/dev/null
echo "  + Team.ReadBasic.All (application)"

# Channel.ReadBasic.All
az ad app permission add --id "$APP_ID" \
    --api "$GRAPH_API" \
    --api-permissions 59a6b24b-4225-4393-8165-ebaec5f55d7a=Role \
    -o none 2>/dev/null
echo "  + Channel.ReadBasic.All (application)"

# User.Read.All (for user-scoped chat enumeration)
az ad app permission add --id "$APP_ID" \
    --api "$GRAPH_API" \
    --api-permissions df021288-bdef-4463-88db-98f22de89214=Role \
    -o none 2>/dev/null
echo "  + User.Read.All (application)"

echo ""

# Step 6: Grant admin consent
echo "[6/8] Granting admin consent (waiting for propagation)..."
sleep 10
az ad app permission admin-consent --id "$APP_ID" -o none 2>/dev/null
echo "  Admin consent granted"
echo ""

# Step 7: Create Azure Bot Service resource
echo "[7/8] Creating Azure Bot Service..."
if [ -z "$RESOURCE_GROUP" ]; then
    echo "  NOTE: Azure Bot Service requires a resource group."
    echo "  Set TEAMS_BOT_RESOURCE_GROUP env var or create manually:"
    echo ""
    echo "  az bot create \\"
    echo "    --resource-group <your-rg> \\"
    echo "    --name \"${BOT_NAME// /-}\" \\"
    echo "    --app-type SingleTenant \\"
    echo "    --appid $APP_ID \\"
    echo "    --tenant-id $TENANT_ID \\"
    echo "    --endpoint \"https://<your-tunnel-hostname>/api/messages\""
    echo ""
    echo "  Then enable Teams channel:"
    echo "  az bot msteams create --resource-group <your-rg> --name \"${BOT_NAME// /-}\""
    echo ""
else
    BOT_HANDLE="${BOT_NAME// /-}"
    az bot create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$BOT_HANDLE" \
        --app-type SingleTenant \
        --appid "$APP_ID" \
        --tenant-id "$TENANT_ID" \
        -o none 2>/dev/null
    echo "  Bot Service created: $BOT_HANDLE"

    # Step 8: Enable Teams channel
    echo "[8/8] Enabling Teams channel..."
    az bot msteams create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$BOT_HANDLE" \
        -o none 2>/dev/null
    echo "  Teams channel enabled"
    echo ""
    echo "  IMPORTANT: Set the messaging endpoint after creating your Cloudflare tunnel:"
    echo "  az bot update \\"
    echo "    --resource-group $RESOURCE_GROUP \\"
    echo "    --name $BOT_HANDLE \\"
    echo "    --endpoint \"https://<your-tunnel-hostname>/api/messages\""
fi
echo ""

# Output .env values
echo "============================================"
echo "Setup complete! Add these to your .env file:"
echo "============================================"
echo ""
echo "TEAMS_BOT_TENANT_ID=$TENANT_ID"
echo "TEAMS_BOT_APP_ID=$APP_ID"
echo "TEAMS_BOT_APP_SECRET=$SECRET_RESULT"
echo "TEAMS_BOT_NAME=$BOT_NAME"
echo "TEAMS_BOT_MODE=webhook"
echo ""
echo "# Create a Cloudflare tunnel and add the token:"
echo "CLOUDFLARE_TUNNEL_TOKEN=<your-tunnel-token>"
echo ""
echo "Next steps:"
echo "  1. Create a Cloudflare tunnel routing to http://localhost:3978"
echo "  2. Update the Azure Bot messaging endpoint with the tunnel URL + /api/messages"
echo "  3. cp .env.example .env and paste the values above"
echo "  4. Set TENDRIL_INSTALL_KEY in .env"
echo "  5. docker compose up -d --build"
echo "  6. Install the bot in Teams (Admin Center > Teams apps > Setup policies)"
echo ""
