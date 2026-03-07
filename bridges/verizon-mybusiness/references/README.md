# References -- Verizon MyBusiness Bridge

This directory holds institutional knowledge documents that give the AI context about your organization's Verizon wireless fleet.

## Included Templates

- **`ik-verizon-fleet.md`** -- Template for documenting your fleet's account structure, device type breakdown, cost center to department mappings, and cross-bridge correlation strategy.

## Customization

After deploying the bridge, fill in `ik-verizon-fleet.md` with your organization's specifics:

1. **Account numbers** -- Your Verizon MyBusiness billing account numbers and names
2. **Fleet summary** -- Total lines, device counts by type (run `fleet_check.py summary` and `fleet_check.py by-device-type`)
3. **Cost center mappings** -- Map your cost center prefixes to department names (also update `DEPT_LABELS` in `fleet_check.py`)
4. **Correlation strategy** -- Document which device types map to Sierra AirLink gateways (by IMEI) and Intune iPads (by phone number)

## Adding More References

Add any organization-specific documents that help operators understand the fleet:

- Network diagrams showing how cellular gateways connect to vehicles
- Verizon plan structures and rate plans
- Procurement and upgrade procedures
- SIM management policies
- Cost allocation and chargeback rules
