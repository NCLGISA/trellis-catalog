#!/bin/bash
# ============================================================================
# Purview Bridge Setup Script
# ============================================================================
# Automates Entra ID app registration, certificate generation,
# Compliance Administrator role assignment, and Exchange.ManageAsApp
# permission grant for the Purview bridge.
#
# Usage:
#   ./setup_purview_bridge.sh <tenant-onmicrosoft-domain>
#
# Example:
#   ./setup_purview_bridge.sh contoso.onmicrosoft.com
# ============================================================================
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <tenant-onmicrosoft-domain>"
    echo "Example: $0 contoso.onmicrosoft.com"
    exit 1
fi

ORGANIZATION="$1"
APP_NAME="Tendril Purview Bridge"
CERT_DIR="./certs"
CERT_PREFIX="purview-bridge"

echo "============================================"
echo "Purview Bridge Setup"
echo "Organization: $ORGANIZATION"
echo "============================================"
echo ""

echo "[1/7] Verifying Azure CLI login..."
TENANT_ID=$(az account show --query tenantId -o tsv 2>/dev/null)
if [ -z "$TENANT_ID" ]; then
    echo "ERROR: Not logged in to Azure CLI. Run 'az login' first."
    exit 1
fi
echo "  Tenant ID: $TENANT_ID"
echo ""

echo "[2/7] Creating app registration: $APP_NAME..."
APP_ID=$(az ad app create \
    --display-name "$APP_NAME" \
    --sign-in-audience AzureADMyOrg \
    --query appId -o tsv)
echo "  App ID: $APP_ID"
echo ""

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

echo "[4/7] Uploading certificate to app registration..."
az ad app credential reset \
    --id "$APP_ID" \
    --cert "@$CERT_DIR/$CERT_PREFIX.crt" \
    --append \
    -o none 2>/dev/null
echo "  Certificate uploaded"
echo ""

echo "[5/7] Creating service principal..."
SP_ID=$(az ad sp create --id "$APP_ID" --query id -o tsv)
echo "  Service Principal ID: $SP_ID"
echo ""

echo "[6/7] Assigning Compliance Administrator role..."
az rest --method POST \
    --url "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments" \
    --body "{
        \"principalId\": \"$SP_ID\",
        \"roleDefinitionId\": \"17315797-102d-40b4-93e0-432062caca18\",
        \"directoryScopeId\": \"/\"
    }" \
    -o none 2>/dev/null
echo "  Compliance Administrator role assigned"
echo ""

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

echo "============================================"
echo "Setup complete! Add these to your .env file:"
echo "============================================"
echo ""
echo "PURVIEW_TENANT_ID=$TENANT_ID"
echo "PURVIEW_APP_ID=$APP_ID"
echo "PURVIEW_CERT_THUMBPRINT=$THUMBPRINT"
echo "PURVIEW_ORGANIZATION=$ORGANIZATION"
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
