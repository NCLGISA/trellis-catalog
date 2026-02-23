# Microsoft Exchange Bridge -- References

This directory contains reference materials for the Exchange Online bridge.

## Setup

- **`setup_exchange_bridge.sh`** -- Automated setup script that creates the Entra ID app registration, generates a self-signed certificate, assigns the Exchange Administrator role, and grants the Exchange.ManageAsApp permission. Run with your tenant's onmicrosoft.com domain as the argument.

## Adding Institutional Knowledge

After deploying the bridge, you can add organization-specific reference documents here:

- Email domain routing documentation
- Transport rule naming conventions and change management procedures
- Shared mailbox ownership and delegation policies
- Quarantine review and release workflows
- Offboarding mailbox conversion procedures

Reference documents are seeded into the container at `/opt/bridge/data/references/` and are available to the AI for operational context.
