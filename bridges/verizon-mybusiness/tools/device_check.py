"""
Verizon MyBusiness Bridge -- Per-Line Device Detail

Retrieve IMEI, SIM ID, equipment model, SIM type, device lock status,
and upgrade eligibility for individual wireless lines.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from verizon_client import VerizonClient, require_credentials

CACHE_DIR = Path("/opt/bridge/data/cache")


def main():
    if len(sys.argv) < 2:
        print("Usage: device_check.py <command> [options]")
        print("Commands: info <mtn>, batch-imei [--type ODI|Tablet|MIFI], sim-status <mtn>")
        sys.exit(1)

    require_credentials()
    cmd = sys.argv[1]
    client = VerizonClient()

    if cmd == "info":
        if len(sys.argv) < 3:
            print("Usage: device_check.py info <mtn>")
            sys.exit(1)
        mtn = sys.argv[2]

        fleet = client.retrieve_entitled_mtn()
        mtn_digits = "".join(c for c in mtn if c.isdigit())
        line = None
        for r in fleet.get("mtnDetails", []):
            if "".join(c for c in r.get("mtn", "") if c.isdigit()) == mtn_digits:
                line = r
                break

        if not line:
            print(f"MTN {mtn} not found in fleet")
            sys.exit(1)

        account = line["accountNumber"]
        formatted_mtn = line["mtn"]

        print(f"Line: {formatted_mtn} ({line.get('userName', 'N/A')})")
        print(f"Account: {account}")
        print(f"Status: {line.get('status', '?')}")
        print(f"Device type: {line.get('deviceType', '?')}")
        print(f"Cost center: {line.get('costCenter', '?')}")
        print(f"Plan: {line.get('planName', 'N/A')}")

        print(f"\nFetching device detail...")
        try:
            device = client.retrieve_mtn_device_info(formatted_mtn, account)
            info = device.get("deviceInformation", {})
            imei = info.get("deviceId", "").strip()
            print(f"\nDevice Information:")
            print(f"  IMEI: {imei}")
            print(f"  SIM ID: {info.get('simId', 'N/A')}")
            print(f"  Model: {info.get('equipmentModel', 'N/A')}")
            print(f"  Short model: {info.get('modelName', 'N/A').strip()}")
            print(f"  SIM type: {info.get('simType4G5G', '?')} / {info.get('simTypeEsimPsim', '?')}")
            print(f"  Category: {info.get('category', '?')}")
            print(f"  5G FWA: {info.get('is5GFWADevice', False)}")
            print(f"  Upgrade date: {info.get('upgradeDate', 'N/A')}")
            print(f"  Balance: ${info.get('balanceDetails', 0):.2f}")

            if imei:
                print(f"\nFetching device lock status...")
                try:
                    lock = client.retrieve_device_lock(formatted_mtn, account, imei)
                    print(f"  Lock status: {lock.get('deviceLockInd', '?')}")
                    print(f"  Eligible unlock date: {lock.get('eligibleUnlockDate', 'N/A')}")
                except Exception as e:
                    print(f"  Lock check failed: {e}")

        except Exception as e:
            print(f"  Device detail failed: {e}")

    elif cmd == "batch-imei":
        device_filter = "ODI"
        if "--type" in sys.argv:
            idx = sys.argv.index("--type")
            if idx + 1 < len(sys.argv):
                device_filter = sys.argv[idx + 1].upper()

        fleet = client.retrieve_entitled_mtn()
        lines = fleet.get("mtnDetails", [])
        filtered = [l for l in lines if device_filter in l.get("deviceType", "").upper()]

        print(f"Fetching IMEI for {len(filtered)} {device_filter} devices...")
        print(f"{'MTN':<15} {'User':<25} {'IMEI':<18} {'Model'}")
        print("─" * 75)

        results = []
        for i, line in enumerate(filtered):
            mtn = line["mtn"]
            account = line["accountNumber"]
            try:
                device = client.retrieve_mtn_device_info(mtn, account)
                info = device.get("deviceInformation", {})
                imei = info.get("deviceId", "").strip()
                model = info.get("modelName", "").strip()
                print(f"{mtn:<15} {line.get('userName',''):<25} {imei:<18} {model}")
                results.append({
                    "mtn": mtn,
                    "userName": line.get("userName"),
                    "imei": imei,
                    "simId": info.get("simId"),
                    "model": model,
                    "costCenter": line.get("costCenter"),
                })
            except Exception as e:
                print(f"{mtn:<15} {line.get('userName',''):<25} ERROR: {e}")
            # Rate limit: ~200ms between calls
            if i < len(filtered) - 1:
                time.sleep(0.2)

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        outpath = CACHE_DIR / f"imei-{device_filter.lower()}.json"
        outpath.write_text(json.dumps(results, indent=2))
        print(f"\n{len(results)} results saved to {outpath}")

    elif cmd == "sim-status":
        if len(sys.argv) < 3:
            print("Usage: device_check.py sim-status <mtn>")
            sys.exit(1)
        mtn = sys.argv[2]

        fleet = client.retrieve_entitled_mtn()
        mtn_digits = "".join(c for c in mtn if c.isdigit())
        line = None
        for r in fleet.get("mtnDetails", []):
            if "".join(c for c in r.get("mtn", "") if c.isdigit()) == mtn_digits:
                line = r
                break

        if not line:
            print(f"MTN {mtn} not found")
            sys.exit(1)

        print(f"Line: {line['mtn']} ({line.get('userName', 'N/A')})")
        print(f"SIM freeze status: {line.get('simFreezeStatus', '?')}")
        print(f"SIMP blocked: {line.get('simpBlocked', '?')}")
        print(f"eSIM: {line.get('eSIMId', '?')}")
        print(f"Port status: {line.get('portStatus', '?')}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
