# ============================================================================
# Tendril Bridge - Adobe Acrobat Sign
# ============================================================================
# Provides API-level access to Adobe Sign via REST API v6 for:
#   - Agreement lifecycle (send, track, download, cancel)
#   - Library document / template management
#   - User listing and search
#   - Web form (widget) management
#   - Webhook configuration
#   - Audit trail and form data extraction
#
# Auth: Integration Key (permanent Bearer token)
# Generated from bridge.yaml -- regenerate with: trellis build adobe-sign
# ============================================================================

FROM python:3.11-slim

ARG BRIDGE_SEED_VERSION=1
ENV BRIDGE_SEED_VERSION=${BRIDGE_SEED_VERSION}

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates procps iputils-ping iproute2 dnsutils net-tools traceroute \
       tesseract-ocr tesseract-ocr-eng poppler-utils libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/tendril /opt/bridge/_seed/tools /opt/bridge/_seed/skills /opt/bridge/data/tools

COPY tools/ /opt/bridge/_seed/tools/
COPY skills/ /opt/bridge/_seed/skills/

COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

VOLUME ["/opt/tendril", "/opt/bridge/data"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
