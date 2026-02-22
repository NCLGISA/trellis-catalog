#!/usr/bin/env python3
"""
Sierra AirLink Device Telemetry & Data Tool

Retrieves last-known device management data from AirVantage for a system.

Subcommands:
    signal <uid>       RSSI, RSRP, RSRQ, signal bars, network type
    location <uid>     GPS latitude/longitude
    cellular <uid>     APN, cell ID, roaming, bytes sent/received
    firmware <uid>     Firmware version and components
    summary <uid>      Combined overview of all data points

Usage:
    python3 data_check.py signal abc123def456
    python3 data_check.py summary abc123def456
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from airlink_client import AirLinkClient


SIGNAL_IDS = "_RSSI,_RSSI_LEVEL,_RSRP,_RSRP_LEVEL,_RSRQ,_RSRQ_LEVEL,_ECIO,_ECIO_LEVEL,_SIGNAL_BARS,_SIGNAL_STRENGTH,_NETWORK_SERVICE_TYPE"
LOCATION_IDS = "_LATITUDE,_LONGITUDE"
CELLULAR_IDS = "_APN,_CELL_ID,_ROAMING_STATUS,_OPERATOR,_BYTES_SENT,_BYTES_RECEIVED,_PACKETS_SENT,_PACKETS_RECEIVED"
FIRMWARE_IDS = "_FIRMWARE_VERSION"


def ts_to_str(ts) -> str:
    if not ts:
        return "n/a"
    try:
        dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OSError):
        return str(ts)


def format_bytes(b) -> str:
    """Human-readable byte count."""
    try:
        b = int(b)
    except (ValueError, TypeError):
        return str(b)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def get_val(data: dict, key: str):
    """Extract the value from AirVantage data response format."""
    entry = data.get(key, [])
    if isinstance(entry, list) and entry:
        return entry[0].get("value")
    return None


def get_ts(data: dict, key: str):
    """Extract the timestamp from AirVantage data response format."""
    entry = data.get(key, [])
    if isinstance(entry, list) and entry:
        return entry[0].get("timestamp")
    return None


def cmd_signal(client: AirLinkClient, uid: str):
    try:
        data = client.get_system_data(uid, ids=SIGNAL_IDS)
    except Exception as e:
        print(f"ERROR: Failed to retrieve signal data for {uid}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Signal Quality for system {uid}:\n")
    rssi = get_val(data, "_RSSI")
    rssi_level = get_val(data, "_RSSI_LEVEL")
    rsrp = get_val(data, "_RSRP")
    rsrp_level = get_val(data, "_RSRP_LEVEL")
    rsrq = get_val(data, "_RSRQ")
    rsrq_level = get_val(data, "_RSRQ_LEVEL")
    ecio = get_val(data, "_ECIO")
    ecio_level = get_val(data, "_ECIO_LEVEL")
    bars = get_val(data, "_SIGNAL_BARS")
    strength = get_val(data, "_SIGNAL_STRENGTH")
    net_type = get_val(data, "_NETWORK_SERVICE_TYPE")

    print(f"  Signal Bars:    {bars or 'n/a'} ({strength or 'n/a'})")
    print(f"  Network Type:   {net_type or 'n/a'}")
    print(f"  RSSI:           {rssi or 'n/a'} dBm ({rssi_level or 'n/a'})")
    print(f"  RSRP:           {rsrp or 'n/a'} dBm ({rsrp_level or 'n/a'})")
    print(f"  RSRQ:           {rsrq or 'n/a'} dB ({rsrq_level or 'n/a'})")
    print(f"  Ec/Io:          {ecio or 'n/a'} dB ({ecio_level or 'n/a'})")

    ts = get_ts(data, "_RSSI") or get_ts(data, "_SIGNAL_BARS")
    if ts:
        print(f"\n  Last updated:   {ts_to_str(ts)}")


def cmd_location(client: AirLinkClient, uid: str):
    try:
        data = client.get_system_data(uid, ids=LOCATION_IDS)
    except Exception as e:
        print(f"ERROR: Failed to retrieve location data for {uid}: {e}", file=sys.stderr)
        sys.exit(1)

    lat = get_val(data, "_LATITUDE")
    lon = get_val(data, "_LONGITUDE")

    print(f"GPS Location for system {uid}:\n")
    print(f"  Latitude:       {lat or 'n/a'}")
    print(f"  Longitude:      {lon or 'n/a'}")

    if lat and lon and str(lat) != "0.0" and str(lon) != "0.0":
        print(f"\n  Google Maps:    https://www.google.com/maps?q={lat},{lon}")

    ts = get_ts(data, "_LATITUDE")
    if ts:
        print(f"  Last updated:   {ts_to_str(ts)}")


def cmd_cellular(client: AirLinkClient, uid: str):
    try:
        data = client.get_system_data(uid, ids=CELLULAR_IDS)
    except Exception as e:
        print(f"ERROR: Failed to retrieve cellular data for {uid}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Cellular Details for system {uid}:\n")
    print(f"  APN:            {get_val(data, '_APN') or 'n/a'}")
    print(f"  Cell ID:        {get_val(data, '_CELL_ID') or 'n/a'}")
    print(f"  Operator:       {get_val(data, '_OPERATOR') or 'n/a'}")
    print(f"  Roaming:        {get_val(data, '_ROAMING_STATUS') or 'n/a'}")

    sent = get_val(data, "_BYTES_SENT")
    recv = get_val(data, "_BYTES_RECEIVED")

    print(f"\n  Bytes Sent:     {format_bytes(sent) if sent else 'n/a'}")
    print(f"  Bytes Received: {format_bytes(recv) if recv else 'n/a'}")

    pkt_sent = get_val(data, "_PACKETS_SENT")
    pkt_recv = get_val(data, "_PACKETS_RECEIVED")
    if pkt_sent or pkt_recv:
        print(f"  Packets Sent:   {pkt_sent or 'n/a'}")
        print(f"  Packets Recv:   {pkt_recv or 'n/a'}")


def cmd_firmware(client: AirLinkClient, uid: str):
    try:
        data = client.get_system_data(uid, ids=FIRMWARE_IDS)
    except Exception as e:
        print(f"ERROR: Failed to retrieve firmware data for {uid}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Firmware for system {uid}:\n")
    version = get_val(data, "_FIRMWARE_VERSION")

    print(f"  Version:        {version or 'n/a'}")

    ts = get_ts(data, "_FIRMWARE_VERSION")
    if ts:
        print(f"\n  Last reported:  {ts_to_str(ts)}")


def cmd_summary(client: AirLinkClient, uid: str):
    all_ids = ",".join([SIGNAL_IDS, LOCATION_IDS, CELLULAR_IDS, FIRMWARE_IDS,
                        "_BOARD_TEMP,_RADIO_MODULE_TEMP,_NUMBER_OF_RESETS,_VOLTAGE"])
    try:
        data = client.get_system_data(uid, ids=all_ids)
    except Exception as e:
        print(f"ERROR: Failed to retrieve telemetry for {uid}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        sys_info = client.get_system(uid)
        name = sys_info.get("name", uid)
        comm = sys_info.get("commStatus", "?")
    except Exception:
        name = uid
        comm = "?"

    print(f"System Summary: {name}")
    print(f"  Comm Status:    {comm}")
    print()

    # Signal
    bars = get_val(data, "_SIGNAL_BARS")
    strength = get_val(data, "_SIGNAL_STRENGTH")
    net_type = get_val(data, "_NETWORK_SERVICE_TYPE")
    rssi = get_val(data, "_RSSI")
    rsrp = get_val(data, "_RSRP")
    print(f"  Signal:         {bars or '?'} bars ({strength or '?'})  |  {net_type or '?'}")
    if rssi:
        print(f"                  RSSI={rssi} dBm  RSRP={rsrp or 'n/a'} dBm")

    # Location
    lat = get_val(data, "_LATITUDE")
    lon = get_val(data, "_LONGITUDE")
    if lat and lon and str(lat) != "0.0" and str(lon) != "0.0":
        print(f"  Location:       {lat}, {lon}")
    else:
        print(f"  Location:       n/a (GPS not reporting)")

    # Cellular
    apn = get_val(data, "_APN")
    operator = get_val(data, "_OPERATOR")
    roaming = get_val(data, "_ROAMING_STATUS")
    print(f"  Cellular:       APN={apn or 'n/a'}  operator={operator or 'n/a'}  roaming={roaming or 'n/a'}")

    sent = get_val(data, "_BYTES_SENT")
    recv = get_val(data, "_BYTES_RECEIVED")
    if sent or recv:
        print(f"  Data Usage:     sent={format_bytes(sent)}  recv={format_bytes(recv)}")

    # Firmware
    fw = get_val(data, "_FIRMWARE_VERSION")
    print(f"  Firmware:       {fw or 'n/a'}")

    # Hardware
    board_temp = get_val(data, "_BOARD_TEMP")
    radio_temp = get_val(data, "_RADIO_MODULE_TEMP")
    resets = get_val(data, "_NUMBER_OF_RESETS")
    voltage = get_val(data, "_VOLTAGE")
    if board_temp or radio_temp:
        print(f"  Temperature:    board={board_temp or '?'}C  radio={radio_temp or '?'}C")
    if voltage:
        print(f"  Voltage:        {voltage}V")
    if resets is not None:
        print(f"  Resets:         {resets}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 data_check.py <signal|location|cellular|firmware|summary> <system_uid>")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    uid = sys.argv[2]
    client = AirLinkClient()

    if cmd == "signal":
        cmd_signal(client, uid)
    elif cmd == "location":
        cmd_location(client, uid)
    elif cmd == "cellular":
        cmd_cellular(client, uid)
    elif cmd == "firmware":
        cmd_firmware(client, uid)
    elif cmd == "summary":
        cmd_summary(client, uid)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: signal, location, cellular, firmware, summary")
        sys.exit(1)


if __name__ == "__main__":
    main()
