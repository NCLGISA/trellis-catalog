#!/bin/bash
# Azure bridge entrypoint wrapper
# Logs into Azure Government cloud before starting the Tendril agent

if [ -n "$ARM_CLIENT_ID" ] && [ -n "$ARM_CLIENT_SECRET" ] && [ -n "$AZURE_TENANT_ID" ]; then
    CLOUD_NAME="${AZURE_CLOUD:-usgovernment}"
    if [ "$CLOUD_NAME" = "usgovernment" ]; then
        az cloud set --name AzureUSGovernment 2>/dev/null
    fi
    az login --service-principal \
        -u "$ARM_CLIENT_ID" \
        -p "$ARM_CLIENT_SECRET" \
        --tenant "$AZURE_TENANT_ID" \
        --output none 2>/dev/null
    if [ -n "$AZURE_SUBSCRIPTION_ID" ]; then
        az account set --subscription "$AZURE_SUBSCRIPTION_ID" 2>/dev/null
    fi
    echo "[bridge-azure] Azure CLI authenticated (${CLOUD_NAME} cloud)"
fi

exec /opt/bridge/entrypoint.sh "$@"
