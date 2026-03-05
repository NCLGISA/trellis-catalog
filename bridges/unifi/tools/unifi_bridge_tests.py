#!/usr/bin/env python3
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
UniFi Bridge Read-Only Test Battery

Third leg of the core triad. Exercises every read-only API capability
against the live UniFi controller and produces a structured pass/fail report.
No mutations, no side effects.

Usage:
    python3 unifi_bridge_tests.py          # Text output
    python3 unifi_bridge_tests.py --json   # Machine-readable output

Exit codes:
    0 = all tests passed
    1 = one or more tests failed
"""

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unifi_client import UniFiClient

# ── Test Framework ─────────────────────────────────────────────────────

class TestResult:
    def __init__(self, num, category, name, status, detail=""):
        self.num = num
        self.category = category
        self.name = name
        self.status = status
        self.detail = detail


results = []
test_counter = 0


def run_test(category, name, fn):
    """Run a single test function, catch exceptions, record result."""
    global test_counter
    test_counter += 1
    num = test_counter
    start = time.time()
    try:
        detail = fn()
        elapsed_ms = int((time.time() - start) * 1000)
        if detail and str(detail).startswith("SKIP:"):
            results.append(TestResult(num, category, name, "SKIP", str(detail)))
        else:
            results.append(TestResult(num, category, name, "PASS",
                                      f"{detail or ''} ({elapsed_ms}ms)"))
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        results.append(TestResult(num, category, name, "FAIL",
                                  f"{str(e)[:120]} ({elapsed_ms}ms)"))


def print_report(elapsed, as_json=False):
    """Print the final structured report."""
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    total = len(results)

    if as_json:
        print(json.dumps({
            "bridge": "unifi",
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "elapsed_seconds": round(elapsed, 2),
            "tests": [
                {
                    "num": r.num,
                    "category": r.category,
                    "name": r.name,
                    "status": r.status,
                    "detail": r.detail,
                }
                for r in results
            ],
        }))
        return

    today_str = date.today().isoformat()
    print(f"\n{'=' * 100}")
    print("  UniFi Bridge Test Battery")
    print(f"  Date: {today_str}")
    print(f"{'=' * 100}")
    print(f"{'#':>3}  {'Category':<24} {'Test':<42} {'Status':<7} Detail")
    print(f"{'-' * 100}")

    for r in results:
        print(f"{r.num:>3}  {r.category:<24} {r.name:<42} {r.status:<7} {r.detail[:60]}")

    print(f"{'-' * 100}")
    print(f"RESULT: {passed}/{total} PASSED  |  {failed} FAILED  |  "
          f"{skipped} SKIPPED  |  Runtime: {elapsed:.1f}s")
    print(f"{'=' * 100}\n")


# ── Shared State ───────────────────────────────────────────────────────

shared = {}

# ── Category 1: Bridge Health ──────────────────────────────────────────

def test_connection_check(client):
    def fn():
        info = client.test_connection()
        assert info.get("ok"), f"Connection failed: {info.get('error')}"
        shared["controller_type"] = info.get("controller_type", "?")
        shared["site_count"] = info.get("sites", 0)
        return f"type={shared['controller_type']}, sites={shared['site_count']}"
    run_test("Bridge Health", "Connection check", fn)


def test_server_status(client):
    def fn():
        status = client.server_status()
        assert "error" not in status, status.get("error")
        return f"up={status.get('meta', {}).get('up', '?')}"
    run_test("Bridge Health", "Server status (no auth)", fn)


# ── Category 2: Site Discovery ─────────────────────────────────────────

def test_list_sites(client):
    def fn():
        sites = client.list_sites()
        assert len(sites) > 0, "No sites found"
        shared["sites"] = sites
        names = [s.get("desc", s.get("name", "?")) for s in sites]
        return f"{len(sites)} sites: {', '.join(names[:5])}"
    run_test("Sites", "List sites", fn)


def test_site_health(client):
    def fn():
        health = client.site_health()
        assert isinstance(health, list), f"Expected list, got {type(health)}"
        subsystems = [h.get("subsystem", "?") for h in health]
        return f"{len(health)} subsystems: {', '.join(subsystems[:5])}"
    run_test("Sites", "Site health", fn)


# ── Category 3: Devices ───────────────────────────────────────────────

def test_list_devices(client):
    def fn():
        devices = client.list_devices()
        shared["devices"] = devices
        shared["device_count"] = len(devices)
        if not devices:
            return "SKIP: No devices adopted"
        types = {}
        for d in devices:
            t = d.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        type_str = ", ".join(f"{k}={v}" for k, v in sorted(types.items()))
        return f"{len(devices)} devices ({type_str})"
    run_test("Devices", "List devices", fn)


def test_device_detail(client):
    def fn():
        devices = shared.get("devices", [])
        if not devices:
            return "SKIP: No devices to inspect"
        mac = devices[0].get("mac", "")
        dev = client.get_device(mac)
        assert dev, f"No device returned for MAC {mac}"
        name = dev.get("name", dev.get("hostname", mac))
        model = dev.get("model", "?")
        version = dev.get("version", "?")
        return f"{name} ({model}, fw {version})"
    run_test("Devices", "Device detail (first device)", fn)


def test_sysinfo(client):
    def fn():
        info = client.sysinfo()
        assert isinstance(info, list), f"Expected list, got {type(info)}"
        if info:
            version = info[0].get("version", "?")
            return f"controller version={version}"
        return "sysinfo returned empty"
    run_test("Devices", "Controller sysinfo", fn)


# ── Category 4: Clients ───────────────────────────────────────────────

def test_list_clients(client):
    def fn():
        clients = client.list_clients()
        shared["client_count"] = len(clients)
        wired = sum(1 for c in clients if c.get("is_wired", False))
        wireless = len(clients) - wired
        return f"{len(clients)} clients ({wired} wired, {wireless} wireless)"
    run_test("Clients", "List connected clients", fn)


def test_list_all_users(client):
    def fn():
        users = client.list_all_users()
        return f"{len(users)} known users (historical)"
    run_test("Clients", "List all known users", fn)


# ── Category 5: WLANs ─────────────────────────────────────────────────

def test_list_wlans(client):
    def fn():
        wlans = client.list_wlans()
        shared["wlan_count"] = len(wlans)
        if not wlans:
            return "SKIP: No WLANs configured"
        names = [w.get("name", "?") for w in wlans]
        return f"{len(wlans)} WLANs: {', '.join(names[:5])}"
    run_test("WLANs", "List wireless networks", fn)


# ── Category 6: Networks ──────────────────────────────────────────────

def test_list_networks(client):
    def fn():
        nets = client.list_networks()
        shared["network_count"] = len(nets)
        if not nets:
            return "SKIP: No networks configured"
        summaries = []
        for n in nets[:5]:
            name = n.get("name", "?")
            vlan = n.get("vlan", "-")
            purpose = n.get("purpose", "?")
            summaries.append(f"{name}(vlan={vlan},{purpose})")
        return f"{len(nets)} networks: {', '.join(summaries)}"
    run_test("Networks", "List network configurations", fn)


# ── Category 7: Firewall / Routing ─────────────────────────────────────

def test_list_firewall_rules(client):
    def fn():
        rules = client.list_firewall_rules()
        return f"{len(rules)} firewall rules"
    run_test("Firewall", "List firewall rules", fn)


def test_list_port_forwards(client):
    def fn():
        fwds = client.list_port_forwards()
        return f"{len(fwds)} port forwards"
    run_test("Firewall", "List port forwards", fn)


def test_list_routes(client):
    def fn():
        routes = client.list_routes()
        return f"{len(routes)} static routes"
    run_test("Firewall", "List static routes", fn)


# ── Category 8: Statistics ─────────────────────────────────────────────

def test_dpi_stats(client):
    def fn():
        stats = client.get_dpi_stats()
        if not stats:
            return "SKIP: DPI not enabled or no data"
        return f"{len(stats)} DPI stat entries"
    run_test("Statistics", "DPI statistics", fn)


# ── Category 9: Events / Alarms ───────────────────────────────────────

def test_list_events(client):
    def fn():
        events = client.list_events(limit=10)
        if not events:
            return "0 events (controller may be freshly deployed)"
        latest = events[0].get("msg", events[0].get("key", "?"))[:60]
        return f"{len(events)} events (latest: {latest})"
    run_test("Events", "List recent events", fn)


def test_list_alarms(client):
    def fn():
        alarms = client.list_alarms()
        return f"{len(alarms)} active alarms"
    run_test("Events", "List active alarms", fn)


def test_list_rogue_aps(client):
    def fn():
        rogues = client.list_rogue_aps()
        return f"{len(rogues)} rogue APs detected"
    run_test("Events", "List rogue APs", fn)


# ── Main ───────────────────────────────────────────────────────────────

def main():
    start = time.time()
    client = UniFiClient()

    test_connection_check(client)
    test_server_status(client)

    test_list_sites(client)
    test_site_health(client)

    test_list_devices(client)
    test_device_detail(client)
    test_sysinfo(client)

    test_list_clients(client)
    test_list_all_users(client)

    test_list_wlans(client)

    test_list_networks(client)

    test_list_firewall_rules(client)
    test_list_port_forwards(client)
    test_list_routes(client)

    test_dpi_stats(client)

    test_list_events(client)
    test_list_alarms(client)
    test_list_rogue_aps(client)

    client.logout()

    elapsed = time.time() - start
    print_report(elapsed, as_json="--json" in sys.argv)

    failed = sum(1 for r in results if r.status == "FAIL")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
