"""
VLAN Numbering Standard and Site Map -- Reference Module

Template/stub for organization-specific VLAN numbering scheme, site map,
IP addressing formula, and naming conventions. Operators should populate
VLAN_STANDARD and SITE_MAP with their own organizational data.

IP Addressing Formula:
    10.{site_id}.{vlan_third_octet}.0/24
    Gateway: 10.{site_id}.{vlan_third_octet}.254

VLAN ID typically encodes function; the examples below show the schema.
"""


# ── Standard VLAN Roles ────────────────────────────────────────────────
# Schema: {vlan_id: {"role": str, "description": str, "third_octet": int,
#                    "dhcp": str, "name_suffix": str, "common": bool}}
# Populate with your organization's VLAN standard.

VLAN_STANDARD = {
    14: {
        "role": "Clients",
        "description": "Employee workstations and DHCP clients",
        "third_octet": 14,
        "dhcp": "Run a DHCP server",
        "name_suffix": "Clients",
        "common": True,
    },
    20: {
        "role": "Public",
        "description": "Public / guest WiFi and public access networks",
        "third_octet": 20,
        "dhcp": "Run a DHCP server",
        "name_suffix": "Public",
        "common": True,
    },
    254: {
        "role": "MGT",
        "description": "Network management (switches, APs, appliance management)",
        "third_octet": 254,
        "dhcp": "Do not respond to DHCP requests",
        "name_suffix": "MGT",
        "common": True,
    },
}

# Acceptable name variants (lowercase) for each role -- used for matching
VLAN_NAME_ALIASES = {
    14: ["clients", "client"],
    20: ["public", "wifi", "guest"],
    254: ["mgt"],
}


# ── Site Map ───────────────────────────────────────────────────────────
# Schema: {site_id: {"name": str, "tier": str}}
# Populate with your organization's sites. Tiers determine expected VLANs.

SITE_MAP = {
    1: {"name": "Main Office", "tier": "full-stack"},
    2: {"name": "Branch Office", "tier": "medium"},
    3: {"name": "Remote Site", "tier": "z-series"},
}

# Network name prefix to site ID mapping (parsed from "NNN - Name" or "NNN_XX - Name")
NETWORK_PREFIX_MAP = {
    "000": None,
    "001": 1,
    "002": 2,
    "003": 3,
}

# Standard VLAN set for each tier
TIER_VLANS = {
    "full-stack": [14, 20, 254],
    "medium": [14, 20, 254],
    "z-series": [14, 20, 254],
    "special": [254],
}


# ── Helper Functions ───────────────────────────────────────────────────

def site_id_from_network_name(network_name: str) -> int | None:
    """
    Extract the site ID from a Meraki network name.
    e.g., "001 - Main Office" -> 1
          "003_SD - Remote Site" -> 3
    """
    prefix = network_name[:3]
    if prefix in NETWORK_PREFIX_MAP:
        return NETWORK_PREFIX_MAP[prefix]
    try:
        return int(prefix)
    except ValueError:
        return None


def site_id_from_vlan_name(vlan_name: str) -> int | None:
    """
    Extract the site ID from a VLAN name prefix.
    e.g., "01_Clients" -> 1
          "STATIC" -> None (no prefix)
    """
    parts = vlan_name.split("_", 1)
    if len(parts) == 2:
        try:
            return int(parts[0])
        except ValueError:
            return None
    return None


def expected_subnet(site_id: int, vlan_id: int) -> str:
    """
    Calculate the expected subnet for a site + VLAN combination.
    Formula: 10.{site_id}.{third_octet}.0/24
    """
    vlan_def = VLAN_STANDARD.get(vlan_id)
    if not vlan_def:
        return ""
    third = vlan_def["third_octet"]
    return f"10.{site_id}.{third}.0/24"


def expected_gateway(site_id: int, vlan_id: int) -> str:
    """
    Calculate the expected gateway for a site + VLAN combination.
    Formula: 10.{site_id}.{third_octet}.254
    """
    vlan_def = VLAN_STANDARD.get(vlan_id)
    if not vlan_def:
        return ""
    third = vlan_def["third_octet"]
    return f"10.{site_id}.{third}.254"


def expected_name(site_id: int, vlan_id: int) -> str:
    """
    Return the canonical VLAN name for a site.
    Format: {site_id:02d}_{Suffix}  e.g., "01_Clients"
    """
    vlan_def = VLAN_STANDARD.get(vlan_id)
    if not vlan_def:
        return ""
    return f"{site_id:02d}_{vlan_def['name_suffix']}"


def expected_vlans_for_site(site_id: int) -> list[int]:
    """Return the list of expected VLAN IDs for a site based on its tier."""
    site_info = SITE_MAP.get(site_id)
    if not site_info:
        return []
    tier = site_info.get("tier", "medium")
    return list(TIER_VLANS.get(tier, []))


def vlan_role(vlan_id: int) -> str:
    """Return the functional role name for a VLAN ID, or 'Unknown'."""
    vlan_def = VLAN_STANDARD.get(vlan_id)
    return vlan_def["role"] if vlan_def else "Unknown"


def matches_role_name(actual_name: str, vlan_id: int) -> bool:
    """
    Check if a VLAN name matches the expected role (ignoring site prefix
    and case). Returns True if the name contains a recognized alias.
    """
    aliases = VLAN_NAME_ALIASES.get(vlan_id, [])
    if not aliases:
        return False

    clean = actual_name
    parts = actual_name.split("_", 1)
    if len(parts) == 2:
        try:
            int(parts[0])
            clean = parts[1]
        except ValueError:
            pass

    return clean.lower().strip() in aliases


def identify_vlan_role(vlan_id: int, vlan_name: str, subnet: str) -> dict:
    """
    Given a VLAN's ID, name, and subnet, identify which standard role it
    matches and extract the site ID from the subnet.

    Returns a dict with:
        role, site_id, standard_vlan_id, expected_name, issues
    """
    result = {
        "role": "Unknown",
        "site_id": None,
        "standard_vlan_id": None,
        "expected_name": "",
        "issues": [],
    }

    if subnet and subnet.startswith("10."):
        parts = subnet.split(".")
        if len(parts) >= 2:
            try:
                result["site_id"] = int(parts[1])
            except ValueError:
                pass

    octet_match = None
    if subnet and subnet.startswith("10."):
        parts = subnet.split(".")
        if len(parts) >= 3:
            try:
                third = int(parts[2])
                for std_id, std_def in VLAN_STANDARD.items():
                    if std_def["third_octet"] == third:
                        octet_match = std_id
                        break
            except ValueError:
                pass

    id_match = vlan_id if vlan_id in VLAN_STANDARD else None
    matched_standard = octet_match or id_match

    if matched_standard:
        std = VLAN_STANDARD[matched_standard]
        result["role"] = std["role"]
        result["standard_vlan_id"] = matched_standard

        if result["site_id"]:
            result["expected_name"] = expected_name(result["site_id"], matched_standard)

        if not matches_role_name(vlan_name, matched_standard):
            result["issues"].append(
                f"Name '{vlan_name}' doesn't match standard "
                f"(expected suffix: {std['name_suffix']})"
            )

    return result


# ── CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    action = sys.argv[1] if len(sys.argv) > 1 else "roles"

    if action == "roles":
        print("VLAN Numbering Standard (example schema)")
        print("=" * 60)
        print(f"{'VLAN':>6}  {'Role':<14}  {'3rd Oct':>7}  {'DHCP':<10}  Description")
        print("-" * 60)
        for vid in sorted(VLAN_STANDARD.keys()):
            v = VLAN_STANDARD[vid]
            dhcp_short = "Yes" if "Run" in v["dhcp"] else "No"
            print(
                f"{vid:>6}  {v['role']:<14}  .{v['third_octet']:<6}  "
                f"{dhcp_short:<10}  {v['description']}"
            )

    elif action == "sites":
        print("Site Map (example schema)")
        print("=" * 60)
        for sid in sorted(SITE_MAP.keys()):
            s = SITE_MAP[sid]
            print(f"  {sid:>3}  {s['name']:<35}  {s['tier']:<12}")

    elif action == "formula":
        site = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        print(f"Expected VLANs for site {site} ({SITE_MAP.get(site, {}).get('name', '?')}):")
        for vid in expected_vlans_for_site(site):
            v = VLAN_STANDARD.get(vid, {})
            if v:
                print(
                    f"  VLAN {vid:>4}  {v.get('role', '?'):<14}  "
                    f"{expected_subnet(site, vid):<20}  gw {expected_gateway(site, vid)}"
                )

    else:
        print("Usage: python3 vlan_reference.py [roles|sites|formula [site_id]]")
        sys.exit(1)
