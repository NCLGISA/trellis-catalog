# ============================================================================
# Tendril Bridge - Microsoft Defender (Unified Security Operations)
# ============================================================================
# Unified security bridge spanning Defender XDR, MDE, and Microsoft Sentinel.
# Three API surfaces from one container: advanced hunting, incident management,
# machine actions, vulnerability management, IoC management, Sentinel rules,
# watchlists, and Log Analytics KQL queries.
#
# Base: python:3.11-slim-bookworm
# Auth: Entra ID App Registration with client secret (client_credentials)
# ============================================================================

FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates procps iputils-ping iproute2 dnsutils net-tools traceroute \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN mkdir -p /opt/tendril /opt/bridge/_seed /opt/bridge/data/tools /opt/bridge/data/skills

COPY tools/ /opt/bridge/_seed/tools/
COPY skills/ /opt/bridge/_seed/skills/

COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

VOLUME ["/opt/tendril", "/opt/bridge/data"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
