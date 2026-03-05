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

"""HYCU bridge battery tests — validates the core triad for introspection.

Run: python3 hycu_bridge_tests.py [--json]

Tests three layers:
  1. Client — can HYCUClient initialize and reach the controller?
  2. CLI    — does hycu.py dispatch correctly and return structured JSON?
  3. Check  — does hycu_check.py pass all endpoint probes?
"""

import json
import os
import subprocess
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def run_cmd(args, timeout=60):
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, cwd=TOOLS_DIR
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


def test_client_init():
    """Client can initialize and resolve server."""
    sys.path.insert(0, TOOLS_DIR)
    from hycu_client import HYCUClient

    try:
        c = HYCUClient()
        return {
            "name": "client_init",
            "pass": True,
            "detail": f"{c.server}:{c.port}",
        }
    except SystemExit:
        return {
            "name": "client_init",
            "pass": False,
            "detail": "HYCU_SERVER or HYCU_API_KEY not set",
        }


def test_client_controller():
    """Client can reach the HYCU controller API."""
    sys.path.insert(0, TOOLS_DIR)
    from hycu_client import HYCUClient

    try:
        c = HYCUClient()
        sw = c.get_software_version()
        entities = sw.get("entities", [])
        ver = entities[0].get("version", "?") if entities else "?"
        return {
            "name": "client_controller",
            "pass": True,
            "detail": f"HYCU {ver}",
        }
    except SystemExit:
        return {"name": "client_controller", "pass": False, "detail": "no credentials"}
    except Exception as e:
        return {"name": "client_controller", "pass": False, "detail": str(e)}


def test_cli_admin_version():
    """CLI returns structured JSON from 'admin version'."""
    code, out, err = run_cmd([PYTHON, "hycu.py", "admin", "version"])
    if code != 0:
        return {"name": "cli_admin_version", "pass": False, "detail": err or out}
    try:
        data = json.loads(out)
        ok = data.get("success", False)
        return {"name": "cli_admin_version", "pass": ok, "detail": "structured JSON"}
    except json.JSONDecodeError:
        return {"name": "cli_admin_version", "pass": False, "detail": "invalid JSON"}


def test_cli_vms_list():
    """CLI returns VM list with count."""
    code, out, err = run_cmd([PYTHON, "hycu.py", "vms", "list", "--limit", "5"])
    if code != 0:
        return {"name": "cli_vms_list", "pass": False, "detail": err or out}
    try:
        data = json.loads(out)
        count = data.get("count", 0)
        return {
            "name": "cli_vms_list",
            "pass": data.get("success", False),
            "detail": f"{count} VMs returned",
        }
    except json.JSONDecodeError:
        return {"name": "cli_vms_list", "pass": False, "detail": "invalid JSON"}


def test_cli_jobs_list():
    """CLI returns job list."""
    code, out, err = run_cmd([PYTHON, "hycu.py", "jobs", "list", "--limit", "5"])
    if code != 0:
        return {"name": "cli_jobs_list", "pass": False, "detail": err or out}
    try:
        data = json.loads(out)
        return {
            "name": "cli_jobs_list",
            "pass": data.get("success", False),
            "detail": f"{data.get('count', 0)} jobs",
        }
    except json.JSONDecodeError:
        return {"name": "cli_jobs_list", "pass": False, "detail": "invalid JSON"}


def test_cli_targets_list():
    """CLI returns target list."""
    code, out, err = run_cmd([PYTHON, "hycu.py", "targets", "list"])
    if code != 0:
        return {"name": "cli_targets_list", "pass": False, "detail": err or out}
    try:
        data = json.loads(out)
        return {
            "name": "cli_targets_list",
            "pass": data.get("success", False),
            "detail": f"{data.get('count', 0)} targets",
        }
    except json.JSONDecodeError:
        return {"name": "cli_targets_list", "pass": False, "detail": "invalid JSON"}


def test_cli_policies_list():
    """CLI returns policy list."""
    code, out, err = run_cmd([PYTHON, "hycu.py", "policies", "list"])
    if code != 0:
        return {"name": "cli_policies_list", "pass": False, "detail": err or out}
    try:
        data = json.loads(out)
        return {
            "name": "cli_policies_list",
            "pass": data.get("success", False),
            "detail": f"{data.get('count', 0)} policies",
        }
    except json.JSONDecodeError:
        return {"name": "cli_policies_list", "pass": False, "detail": "invalid JSON"}


def test_health_check():
    """Full health check (hycu_check.py) passes."""
    code, out, err = run_cmd([PYTHON, "hycu_check.py", "--json"], timeout=120)
    if code == 0:
        return {"name": "health_check", "pass": True, "detail": "all probes passed"}
    lines = out.strip().split("\n")
    last = lines[-1] if lines else ""
    try:
        data = json.loads(last)
        return {
            "name": "health_check",
            "pass": False,
            "detail": f"{data.get('passed', '?')}/{data.get('total', '?')} passed",
        }
    except json.JSONDecodeError:
        return {"name": "health_check", "pass": False, "detail": err or out[-200:]}


ALL_TESTS = [
    test_client_init,
    test_client_controller,
    test_cli_admin_version,
    test_cli_vms_list,
    test_cli_jobs_list,
    test_cli_targets_list,
    test_cli_policies_list,
    test_health_check,
]


def main():
    json_mode = "--json" in sys.argv
    results = []
    t0 = time.time()

    for fn in ALL_TESTS:
        r = fn()
        results.append(r)
        if not json_mode:
            status = "PASS" if r["pass"] else "FAIL"
            print(f"  {status}: {r['name']}" + (f" ({r['detail']})" if r.get("detail") else ""))

    elapsed = round(time.time() - t0, 1)
    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    if json_mode:
        print(json.dumps({
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "elapsed_s": elapsed,
            "tests": results,
        }))
    else:
        print()
        print(f"Results: {passed}/{total} passed in {elapsed}s")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
