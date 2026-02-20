#!/usr/bin/env python3
"""
Meraki Bridge Battery Test

Comprehensive read-only test covering all API areas to verify the bridge
has proper access to the Meraki Dashboard API.

Usage:
  python3 meraki_bridge_tests.py
"""

import sys
import json
import time

# Track results
results = []


def test(category, name, fn):
    """Run a test and record the result."""
    try:
        result = fn()
        count = ""
        if isinstance(result, list):
            count = f" ({len(result)} items)"
        elif isinstance(result, dict):
            count = " (ok)"
        results.append(("PASS", category, name, count))
        print(f"  PASS  {name}{count}")
        return result
    except Exception as e:
        results.append(("FAIL", category, name, str(e)))
        print(f"  FAIL  {name}: {e}")
        return None


def main():
    print("=" * 70)
    print("Meraki Bridge Battery Test")
    print("=" * 70)

    from meraki_client import MerakiClient
    client = MerakiClient()

    # ── Category 1: Organization ──────────────────────────────────────
    print("\n[1/8] Organization")
    org = test("Organization", "Get organization", lambda: client.get_org())
    test("Organization", "List admins", lambda: client.list_admins())
    test("Organization", "License overview", lambda: client.get_license_overview())

    # ── Category 2: Networks ──────────────────────────────────────────
    print("\n[2/8] Networks")
    networks = test("Networks", "List networks", lambda: client.list_networks())

    sample_net = None
    appliance_net = None
    wireless_net = None
    switch_net = None
    if networks:
        for n in networks:
            types = n.get("productTypes", [])
            if "appliance" in types and "wireless" in types and "switch" in types:
                sample_net = n
                appliance_net = n
                wireless_net = n
                switch_net = n
                break
        if not sample_net:
            sample_net = networks[0]
        if not appliance_net:
            appliance_net = next((n for n in networks if "appliance" in n.get("productTypes", [])), None)
        if not wireless_net:
            wireless_net = next((n for n in networks if "wireless" in n.get("productTypes", [])), None)
        if not switch_net:
            switch_net = next((n for n in networks if "switch" in n.get("productTypes", [])), None)

    if sample_net:
        test("Networks", f"Get network ({sample_net['name'][:30]})",
             lambda: client.get_network(sample_net["id"]))
        test("Networks", f"List network devices",
             lambda: client.list_network_devices(sample_net["id"]))

    # ── Category 3: Devices ───────────────────────────────────────────
    print("\n[3/8] Devices")
    devices = test("Devices", "List devices", lambda: client.list_devices())
    test("Devices", "Device status overview", lambda: client.get_device_status_overview())
    statuses = test("Devices", "List device statuses", lambda: client.list_device_statuses())

    sample_device = None
    if devices:
        sample_device = devices[0]
        test("Devices", f"Get device ({sample_device.get('name', sample_device['serial'])})",
             lambda: client.get_device(sample_device["serial"]))

    test("Devices", "List inventory", lambda: client.list_inventory())

    # ── Category 4: Uplinks ───────────────────────────────────────────
    print("\n[4/8] Uplinks")
    test("Uplinks", "List uplink statuses", lambda: client.list_uplink_statuses())

    # ── Category 5: Wireless ──────────────────────────────────────────
    print("\n[5/8] Wireless")
    if wireless_net:
        ssids = test("Wireless", f"Get SSIDs ({wireless_net['name'][:30]})",
                     lambda: client.get_ssids(wireless_net["id"]))
        if ssids:
            test("Wireless", f"Get SSID 0 detail",
                 lambda: client.get_ssid(wireless_net["id"], 0))
    else:
        print("  SKIP  No wireless network available")

    # ── Category 6: Appliance (VLANs + Firewall) ─────────────────────
    print("\n[6/8] Appliance (VLANs + Firewall)")
    if appliance_net:
        test("Appliance", f"Get VLANs ({appliance_net['name'][:30]})",
             lambda: client.get_vlans(appliance_net["id"]))
        test("Appliance", f"Get L3 firewall rules",
             lambda: client.get_l3_firewall_rules(appliance_net["id"]))
        test("Appliance", f"Get L7 firewall rules",
             lambda: client.get_l7_firewall_rules(appliance_net["id"]))
        test("Appliance", f"Get site-to-site VPN config",
             lambda: client.get_site_to_site_vpn(appliance_net["id"]))
        test("Appliance", f"Get firmware upgrades",
             lambda: client.get_firmware_upgrades(appliance_net["id"]))
    else:
        print("  SKIP  No appliance network available")

    # ── Category 7: VPN ───────────────────────────────────────────────
    print("\n[7/8] VPN")
    test("VPN", "List VPN statuses", lambda: client.list_vpn_statuses())
    test("VPN", "List firmware upgrade history", lambda: client.list_firmware_upgrades())

    # ── Category 8: Switch ────────────────────────────────────────────
    print("\n[8/8] Switch")
    switch_device = None
    if devices:
        switch_device = next((d for d in devices if d.get("productType") == "switch"), None)
    if switch_device:
        serial = switch_device["serial"]
        test("Switch", f"Get switch ports ({switch_device.get('name', serial)})",
             lambda: client.get_switch_ports(serial))
        test("Switch", f"Get switch port statuses",
             lambda: client.get_switch_port_statuses(serial))
    else:
        print("  SKIP  No switch device available")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    total = len(results)
    print(f"Results: {passed}/{total} passed, {failed} failed")

    if failed:
        print(f"\nFailed tests:")
        for status, cat, name, detail in results:
            if status == "FAIL":
                print(f"  [{cat}] {name}: {detail}")

    print("=" * 70)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
