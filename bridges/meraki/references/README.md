# Meraki Bridge -- References Directory

This directory holds **institutional knowledge** documents that customize the
Meraki bridge for your organization. The Tendril agent references these files
when answering questions about your network infrastructure.

## What to put here

### VLAN Structure (`ik-vlan-structure.md`)

Document your organization's VLAN numbering standard, site map, and IP
addressing formula. A well-structured VLAN reference enables the agent to:

- Audit VLAN configurations across all networks
- Identify naming inconsistencies and missing VLANs
- Correlate IP addresses to sites and roles
- Answer "what VLAN is X on at site Y?" instantly

**Recommended sections:**

| Section | Description |
|---------|-------------|
| VLAN Roles | Standard VLAN IDs and their purpose (e.g., 14=Clients, 16=Phones) |
| Site Map | Site ID to name mapping with tier classification |
| IP Formula | How subnets are derived (e.g., `10.{site_id}.{vlan_id}.0/24`) |
| SSID Map | Wireless SSIDs, authentication type, and VLAN binding |
| Firewall Patterns | Standard inter-VLAN rules and site-to-site VPN policies |
| Group Policies | Named policies and their traffic shaping rules |

**Example VLAN table:**

```markdown
| VLAN ID | Role    | Description                | Third Octet | DHCP Mode        |
|---------|---------|----------------------------|-------------|------------------|
| 12      | Static  | Printers, servers, fixed   | 12          | DHCP reservation |
| 14      | Clients | Workstations               | 14          | DHCP pool        |
| 16      | Phones  | VoIP handsets              | 16          | DHCP pool        |
| 18      | DVRs    | Security cameras and NVRs  | 18          | DHCP reservation |
| 20      | Public  | Guest/public WiFi          | 20          | DHCP pool        |
| 254     | MGT     | Meraki management traffic  | 254         | DHCP reservation |
```

**Example site map:**

```markdown
| Site ID | Name          | Tier       | Notes              |
|---------|---------------|------------|--------------------|
| 1       | Main Office   | full-stack | Hub, all VLANs     |
| 2       | Branch Office | full-stack | Spoke, all VLANs   |
| 3       | Remote Site   | minimal    | Spoke, limited set |
```

### Other Reference Documents

You can add any Markdown files here that contain institutional knowledge:

- Network diagrams and topology notes
- Change management history
- Vendor contact information and support contracts
- Hardware lifecycle and replacement schedules
- Compliance requirements (PCI DSS scope, CJIS boundaries)

## How the agent uses references

The Tendril agent's SKILL.md file points to this directory. When answering
questions, the agent reads these reference documents as context. Keeping them
accurate and up-to-date improves the quality of network audits and
troubleshooting recommendations.

## Generating your VLAN reference

The `vlan_reference.py` tool in the `tools/` directory provides a framework
for encoding your VLAN standard programmatically. Populate the `VLAN_STANDARD`
and `SITE_MAP` dictionaries with your organization's data, then run:

```bash
python3 tools/vlan_reference.py roles    # Print VLAN role table
python3 tools/vlan_reference.py sites    # Print site map
python3 tools/vlan_reference.py formula  # Show IP addressing formula
```

You can also export the reference as Markdown and save it here.
