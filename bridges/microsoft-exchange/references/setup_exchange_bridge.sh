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
# Exchange Bridge Setup Script
# ============================================================================
# Automates Entra ID app registration, certificate generation, role
# assignment, and permission grants for the Exchange Online bridge.
#
# Usage:
#   ./setup_exchange_bridge.sh <tenant-onmicrosoft-domain>
#
# Example:
#   ./setup_exchange_bridge.sh contoso.onmicrosoft.com
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - Global Administrator or Application Administrator + Exchange Administrator
#   - openssl installed
# ============================================================================
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <tenant-onmicrosoft-domain>"
    echo "Example: $0 contoso.onmicrosoft.com"
    exit 1
fi

ORGANIZATION="$1"
APP_NAME="Tendril Exchange Bridge"
CERT_DIR="./certs"
CERT_PREFIX="exchange-bridge"

echo "============================================"
echo "Exchange Bridge Setup"
echo "Organization: $ORGANIZATION"
echo "============================================"
echo ""

# Step 1: Verify Azure CLI login
echo "[1/7] Verifying Azure CLI login..."
TENANT_ID=$(az account show --query tenantId -o tsv 2>/dev/null)
if [ -z "$TENANT_ID" ]; then
    echo "ERROR: Not logged in to Azure CLI. Run 'az login' first."
    exit 1
fi
echo "  Tenant ID: $TENANT_ID"
echo ""

# Step 2: Create app registration
echo "[2/7] Creating app registration: $APP_NAME..."
APP_ID=$(az ad app create \
    --display-name "$APP_NAME" \
    --sign-in-audience AzureADMyOrg \
    --query appId -o tsv)
echo "  App ID: $APP_ID"
echo ""

# Step 3: Generate self-signed certificate
echo "[3/7] Generating self-signed certificate..."
mkdir -p "$CERT_DIR"
openssl req -x509 -newkey rsa:2048 \
    -keyout "$CERT_DIR/$CERT_PREFIX.key" \
    -out "$CERT_DIR/$CERT_PREFIX.crt" \
    -days 365 -nodes \
    -subj "/CN=$APP_NAME" 2>/dev/null

openssl pkcs12 -export \
    -out "$CERT_DIR/$CERT_PREFIX.pfx" \
    -inkey "$CERT_DIR/$CERT_PREFIX.key" \
    -in "$CERT_DIR/$CERT_PREFIX.crt" \
    -passout pass: 2>/dev/null

THUMBPRINT=$(openssl x509 -in "$CERT_DIR/$CERT_PREFIX.crt" -noout -fingerprint -sha1 \
    | sed 's/://g' | sed 's/sha1 Fingerprint=//i' | sed 's/SHA1 Fingerprint=//i')
echo "  Certificate thumbprint: $THUMBPRINT"
echo "  Files: $CERT_DIR/$CERT_PREFIX.{crt,key,pfx}"
echo ""

# Step 4: Upload certificate to app registration
echo "[4/7] Uploading certificate to app registration..."
az ad app credential reset \
    --id "$APP_ID" \
    --cert "@$CERT_DIR/$CERT_PREFIX.crt" \
    --append \
    -o none 2>/dev/null
echo "  Certificate uploaded"
echo ""

# Step 5: Create service principal
echo "[5/7] Creating service principal..."
SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
echo "  Service Principal ID: $SP_ID"
echo ""

# Step 6: Assign Exchange Administrator role
echo "[6/7] Assigning Exchange Administrator role..."
az rest --method POST \
    --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments" \
    --body "{
        \"principalId\": \"$SP_ID\",
        \"roleDefinitionId\": \"29232cdf-9323-42fd-ade2-1d097af3e4de\",
        \"directoryScopeId\": \"/\"
    }" \
    -o none 2>/dev/null
echo "  Exchange Administrator role assigned"
echo ""

# Step 7: Add Exchange.ManageAsApp permission and grant admin consent
echo "[7/7] Adding Exchange.ManageAsApp permission..."
az ad app permission add \
    --id "$APP_ID" \
    --api 00000002-0000-0ff1-ce00-000000000000 \
    --api-permissions dc50a0fb-09a3-484d-be87-e023b12c6440=Role \
    -o none 2>/dev/null

sleep 5

az ad app permission admin-consent --id "$APP_ID" -o none 2>/dev/null
echo "  Permission granted with admin consent"
echo ""

# Output .env values
echo "============================================"
echo "Setup complete! Add these to your .env file:"
echo "============================================"
echo ""
echo "EXO_TENANT_ID=$TENANT_ID"
echo "EXO_APP_ID=$APP_ID"
echo "EXO_CERT_THUMBPRINT=$THUMBPRINT"
echo "EXO_ORGANIZATION=$ORGANIZATION"
echo ""
echo "Certificate files are in: $CERT_DIR/"
echo "  - $CERT_PREFIX.pfx  (mount in Docker container)"
echo "  - $CERT_PREFIX.crt  (public certificate)"
echo "  - $CERT_PREFIX.key  (private key -- keep secure)"
echo ""
echo "Next steps:"
echo "  1. cp .env.example .env"
echo "  2. Paste the values above into .env"
echo "  3. Set TENDRIL_INSTALL_KEY in .env"
echo "  4. docker-compose up -d --build"
echo ""
