FROM python:3.11-slim

RUN pip install --no-cache-dir requests

COPY tools/ /opt/bridge/data/tools/
RUN chmod +x /opt/bridge/data/tools/*.py

COPY skills/ /opt/tendril/skills/

ENTRYPOINT ["/opt/tendril/tendril", "run"]
