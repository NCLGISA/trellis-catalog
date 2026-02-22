# ============================================================================
# Tendril Bridge - Sierra AirLink (AirVantage)
# ============================================================================
# Provides API access to Sierra Wireless AirVantage for managing AirLink
# cellular gateways: system inventory, gateway status, alerts, signal
# quality, location, and firmware across the fleet.
#
# Auth: OAuth2 Client Credentials flow against na.airvantage.net
# See: https://source.sierrawireless.com/airvantage/almsc/reference/cloud/API/
# ============================================================================

FROM python:3.11-slim

ARG BRIDGE_SEED_VERSION=1
ENV BRIDGE_SEED_VERSION=${BRIDGE_SEED_VERSION}

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates procps iputils-ping iproute2 dnsutils net-tools traceroute \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/tendril /opt/bridge/_seed/tools /opt/bridge/_seed/skills /opt/bridge/data/tools

COPY tools/ /opt/bridge/_seed/tools/
COPY skills/ /opt/bridge/_seed/skills/

COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

VOLUME ["/opt/tendril", "/opt/bridge/data"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
