FROM python:3.11-slim-bookworm

LABEL maintainer="tendril-project"
LABEL description="Tendril bridge for Verizon MyBusiness wireless fleet management"
LABEL tendril.bridge="verizon-mybusiness"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    httpx[http2]==0.28.*

RUN mkdir -p /opt/bridge/_seed/tools \
             /opt/bridge/_seed/skills \
             /opt/bridge/_seed/references \
             /opt/bridge/data/tools \
             /opt/bridge/data/references \
             /opt/bridge/data/session \
             /opt/bridge/data/cache \
             /opt/tendril/skills

COPY tools/ /opt/bridge/_seed/tools/
COPY skills/ /opt/bridge/_seed/skills/
COPY references/ /opt/bridge/_seed/references/
COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

VOLUME ["/opt/bridge/data", "/opt/tendril"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
