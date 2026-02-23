# ============================================================================
# Tendril Bridge - Microsoft Exchange (Exchange Online PowerShell)
# ============================================================================
# Provides Exchange Online admin operations not available through Microsoft
# Graph REST API: quarantine management, message trace, full mailbox
# delegation, shared mailbox conversion, and transport rules.
#
# Base: mcr.microsoft.com/powershell (PowerShell 7 + .NET on Debian)
# Auth: Entra ID App Registration with certificate-based authentication
#       via Connect-ExchangeOnline (ExchangeOnlineManagement v3+ REST)
# ============================================================================

FROM mcr.microsoft.com/powershell:7.4-debian-bookworm

# Install Python 3, pip, and network utilities
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3 python3-pip python3-venv \
       curl ca-certificates procps iputils-ping iproute2 dnsutils net-tools traceroute \
    && rm -rf /var/lib/apt/lists/*

# Install ExchangeOnlineManagement module (preinstall to avoid runtime delay)
RUN pwsh -NoProfile -Command "Set-PSRepository -Name PSGallery -InstallationPolicy Trusted; Install-Module -Name ExchangeOnlineManagement -Scope AllUsers -Force -AcceptLicense"

# Install pip dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Create directory structure
RUN mkdir -p /opt/tendril /opt/bridge/_seed /opt/bridge/data/tools /opt/bridge/data/skills /opt/bridge/certs

# Copy tools into seed directory
COPY tools/ /opt/bridge/_seed/tools/

# Copy skills into seed directory
COPY skills/ /opt/bridge/_seed/skills/

# Copy entrypoint
COPY entrypoint.sh /opt/bridge/entrypoint.sh
RUN chmod +x /opt/bridge/entrypoint.sh

# Persistent volumes
VOLUME ["/opt/tendril", "/opt/bridge/data"]

ENTRYPOINT ["/opt/bridge/entrypoint.sh"]
