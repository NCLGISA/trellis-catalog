#!/usr/bin/env python3
"""
MDE Threat Indicator (IoC) management.

Create, list, and delete indicators to block or alert on IPs, URLs,
domains, file hashes, and certificates across the MDE fleet.

Usage:
    python3 indicators.py list                          # All indicators
    python3 indicators.py list --type IpAddress         # Filter by type
    python3 indicators.py list --action block           # Filter by action
    python3 indicators.py detail <indicator-id>         # Indicator detail
    python3 indicators.py block-ip <ip> <title> <desc>  # Block an IP
    python3 indicators.py block-url <url> <title> <desc>
    python3 indicators.py block-domain <domain> <title> <desc>
    python3 indicators.py block-hash <sha256> <title> <desc>
    python3 indicators.py alert-ip <ip> <title> <desc>  # Alert-only
    python3 indicators.py delete <indicator-id>         # Remove indicator
    python3 indicators.py summary                       # Indicator stats
"""

import sys
import json
from datetime import datetime, timezone

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient

IOC_TYPES = {
    "IpAddress": "IP address",
    "Url": "URL",
    "DomainName": "Domain",
    "FileSha256": "SHA-256 file hash",
    "FileSha1": "SHA-1 file hash",
    "CertificateThumbprint": "Certificate thumbprint",
}


def cmd_list(client: DefenderClient, ioc_type: str = None, action: str = None):
    indicators = client.mde_get_all("/api/indicators")

    if ioc_type:
        indicators = [i for i in indicators if i.get("indicatorType") == ioc_type]
    if action:
        action_map = {"block": "Block", "alert": "Alert", "allow": "Allowed", "warn": "Warn"}
        mapped = action_map.get(action.lower(), action)
        indicators = [i for i in indicators if i.get("action") == mapped]

    if not indicators:
        print("No indicators found.")
        return

    print(f"Threat Indicators: {len(indicators)}\n")
    print(f"  {'Type':15s}  {'Action':8s}  {'Value':40s}  {'Title':30s}  {'Severity'}")
    print(f"  {'─'*15}  {'─'*8}  {'─'*40}  {'─'*30}  {'─'*12}")

    for ind in indicators:
        itype = (ind.get("indicatorType") or "?")[:15]
        action = (ind.get("action") or "?")[:8]
        value = (ind.get("indicatorValue") or "?")[:40]
        title = (ind.get("title") or "?")[:30]
        sev = ind.get("severity") or "?"
        print(f"  {itype:15s}  {action:8s}  {value:40s}  {title:30s}  {sev}")


def cmd_detail(client: DefenderClient, indicator_id: str):
    resp = client.mde_get(f"/api/indicators/{indicator_id}")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    ind = resp.json()
    print(f"Indicator: {ind.get('indicatorValue', '?')}")
    print(f"  ID:            {ind.get('id', '?')}")
    print(f"  Type:          {ind.get('indicatorType', '?')}")
    print(f"  Action:        {ind.get('action', '?')}")
    print(f"  Severity:      {ind.get('severity', '?')}")
    print(f"  Title:         {ind.get('title', '?')}")
    print(f"  Description:   {ind.get('description', '?')}")
    print(f"  Created:       {ind.get('creationTimeDateTimeUtc', '?')}")
    print(f"  Expiration:    {ind.get('expirationTime', 'None')}")
    print(f"  Created By:    {ind.get('createdByDisplayName', '?')}")
    print(f"  Generate Alert: {ind.get('generateAlert', False)}")
    print(f"  Active:        {ind.get('active', True)}")


def _create_indicator(
    client: DefenderClient,
    indicator_type: str,
    value: str,
    action: str,
    title: str,
    description: str,
    severity: str = "High",
):
    body = {
        "indicatorValue": value,
        "indicatorType": indicator_type,
        "action": action,
        "title": title,
        "description": description,
        "severity": severity,
        "generateAlert": True,
        "recommendedActions": f"Indicator created via Tendril bridge",
    }

    resp = client.mde_post("/api/indicators", body)
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"Indicator created: {data.get('id', '?')}")
        print(f"  Type:    {data.get('indicatorType')}")
        print(f"  Value:   {data.get('indicatorValue')}")
        print(f"  Action:  {data.get('action')}")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_block_ip(client, ip, title, desc):
    _create_indicator(client, "IpAddress", ip, "Block", title, desc)

def cmd_block_url(client, url, title, desc):
    _create_indicator(client, "Url", url, "Block", title, desc)

def cmd_block_domain(client, domain, title, desc):
    _create_indicator(client, "DomainName", domain, "Block", title, desc)

def cmd_block_hash(client, sha256, title, desc):
    _create_indicator(client, "FileSha256", sha256, "Block", title, desc)

def cmd_alert_ip(client, ip, title, desc):
    _create_indicator(client, "IpAddress", ip, "Alert", title, desc, severity="Medium")


def cmd_delete(client: DefenderClient, indicator_id: str):
    resp = client.mde_delete(f"/api/indicators/{indicator_id}")
    if resp.status_code in (200, 204):
        print(f"Indicator {indicator_id} deleted.")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_summary(client: DefenderClient):
    indicators = client.mde_get_all("/api/indicators")

    by_type = {}
    by_action = {}
    for ind in indicators:
        itype = ind.get("indicatorType", "Unknown")
        by_type[itype] = by_type.get(itype, 0) + 1
        action = ind.get("action", "Unknown")
        by_action[action] = by_action.get(action, 0) + 1

    print(f"Indicator Summary: {len(indicators)} total\n")

    print("  By Type:")
    for itype, count in sorted(by_type.items(), key=lambda x: -x[1]):
        label = IOC_TYPES.get(itype, itype)
        print(f"    {label:30s}  {count}")

    print("\n  By Action:")
    for action, count in sorted(by_action.items(), key=lambda x: -x[1]):
        print(f"    {action:30s}  {count}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]

    ioc_type = None
    action = None
    args = sys.argv[2:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--type" and i + 1 < len(args):
            ioc_type = args[i + 1]
            i += 2
        elif args[i] == "--action" and i + 1 < len(args):
            action = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    if cmd == "list":
        cmd_list(client, ioc_type=ioc_type, action=action)
    elif cmd == "detail" and filtered_args:
        cmd_detail(client, filtered_args[0])
    elif cmd == "block-ip" and len(filtered_args) >= 3:
        cmd_block_ip(client, filtered_args[0], filtered_args[1], " ".join(filtered_args[2:]))
    elif cmd == "block-url" and len(filtered_args) >= 3:
        cmd_block_url(client, filtered_args[0], filtered_args[1], " ".join(filtered_args[2:]))
    elif cmd == "block-domain" and len(filtered_args) >= 3:
        cmd_block_domain(client, filtered_args[0], filtered_args[1], " ".join(filtered_args[2:]))
    elif cmd == "block-hash" and len(filtered_args) >= 3:
        cmd_block_hash(client, filtered_args[0], filtered_args[1], " ".join(filtered_args[2:]))
    elif cmd == "alert-ip" and len(filtered_args) >= 3:
        cmd_alert_ip(client, filtered_args[0], filtered_args[1], " ".join(filtered_args[2:]))
    elif cmd == "delete" and filtered_args:
        cmd_delete(client, filtered_args[0])
    elif cmd == "summary":
        cmd_summary(client)
    else:
        print(__doc__.strip())
        sys.exit(1)
