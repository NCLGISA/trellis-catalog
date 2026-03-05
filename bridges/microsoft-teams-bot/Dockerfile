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
# Tendril Bridge - Microsoft Teams Bot (Bot Framework + Cloudflare Tunnel)
# ============================================================================
# Dual-mode Teams bot: webhook mode runs a persistent aiohttp server behind
# a cloudflared tunnel for real-time Bot Framework messaging; polling mode
# uses Graph API for tenant-wide message reads without inbound connectivity.
#
# Base: python:3.11-slim-bookworm
# Auth: Entra ID App Registration with client secret (Bot Framework standard)
# Tunnel: cloudflared from Cloudflare official Debian repository
# ============================================================================

FROM python:3.11-slim-bookworm

# Install system deps and cloudflared
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates procps iputils-ping iproute2 dnsutils net-tools traceroute gnupg \
    && mkdir -p --mode=0755 /usr/share/keyrings \
    && curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
       -o /usr/share/keyrings/cloudflare-main.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main' \
       > /etc/apt/sources.list.d/cloudflared.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends cloudflared \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Create directory structure
RUN mkdir -p /opt/tendril /opt/bridge/_seed /opt/bridge/data/tools /opt/bridge/data/skills

# Copy tools and skills into seed directory
COPY tools/ /opt/bridge/_seed/tools/
COPY skills/ /opt/bridge/_seed/skills/

# Copy entrypoint
COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

# Bot server port
EXPOSE 3978

# Persistent volumes
VOLUME ["/opt/tendril", "/opt/bridge/data"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
