#!/bin/bash
# Azure bridge entrypoint wrapper
# Logs into Azure Government cloud before starting the Tendril agent

if [ -n "$AZURE_CLIENT_ID" ] && [ -n "$AZURE_CLIENT_SECRET" ] && [ -n "$AZURE_TENANT_ID" ]; then
    CLOUD_NAME="${AZURE_CLOUD:-commercial}"
    if [ "$CLOUD_NAME" = "usgovernment" ]; then
        az cloud set --name AzureUSGovernment 2>/dev/null
    fi
    az login --service-principal \
        -u "$AZURE_CLIENT_ID" \
        -p "$AZURE_CLIENT_SECRET" \
        --tenant "$AZURE_TENANT_ID" \
        --output none 2>/dev/null
    if [ -n "$AZURE_SUBSCRIPTION_ID" ]; then
        az account set --subscription "$AZURE_SUBSCRIPTION_ID" 2>/dev/null
    fi
    echo "[bridge-microsoft-arm] Azure CLI authenticated (${CLOUD_NAME} cloud)"
fi

exec /opt/bridge/entrypoint.sh "$@"
