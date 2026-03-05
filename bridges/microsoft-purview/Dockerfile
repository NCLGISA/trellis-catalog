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
# Tendril Bridge - Microsoft Purview (Security & Compliance PowerShell)
# ============================================================================
# Provides Microsoft Purview admin operations: DLP policies, retention
# policies/labels, sensitivity labels, alert policies, eDiscovery (read),
# and information barrier management.
#
# Base: mcr.microsoft.com/powershell (PowerShell 7 + .NET on Debian)
# Auth: Entra ID App Registration with certificate-based authentication
#       via Connect-IPPSSession (ExchangeOnlineManagement v3+ REST)
# ============================================================================

FROM mcr.microsoft.com/powershell:7.4-debian-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip python3-venv \
       curl ca-certificates procps iputils-ping iproute2 dnsutils net-tools traceroute \
    && rm -rf /var/lib/apt/lists/*

RUN pwsh -NoProfile -Command "Set-PSRepository -Name PSGallery -InstallationPolicy Trusted; Install-Module -Name ExchangeOnlineManagement -Scope AllUsers -Force -AcceptLicense"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN mkdir -p /opt/tendril /opt/bridge/_seed /opt/bridge/data/tools /opt/bridge/data/skills /opt/bridge/certs

COPY tools/ /opt/bridge/_seed/tools/
COPY skills/ /opt/bridge/_seed/skills/

COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

VOLUME ["/opt/tendril", "/opt/bridge/data"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
