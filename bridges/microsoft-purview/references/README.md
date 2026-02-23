# Microsoft Purview Bridge -- References

This directory contains reference materials for the Purview bridge.

## Setup

- **`setup_purview_bridge.sh`** -- Automated setup script that creates the Entra ID app registration, generates a self-signed certificate, assigns the Compliance Administrator role, and grants the Exchange.ManageAsApp permission. Run with your tenant's onmicrosoft.com domain as the argument.

## Adding Institutional Knowledge

After deploying the bridge, you can add organization-specific reference documents here:

- DLP policy naming conventions and change management procedures
- Retention schedule documentation
- Sensitivity label taxonomy and classification guidelines
- eDiscovery procedures and legal hold workflows
- Compliance review cadence and audit procedures

Reference documents are seeded into the container at `/opt/bridge/data/references/` and are available to the AI for operational context.
