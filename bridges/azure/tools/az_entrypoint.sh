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
