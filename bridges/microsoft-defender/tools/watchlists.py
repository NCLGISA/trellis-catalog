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
Sentinel watchlist management.

Watchlists allow you to maintain curated lists (IoCs, VIP users, exception
lists, asset inventories) that can be referenced in KQL analytics rules
and hunting queries using the _GetWatchlist('name') function.

Usage:
    python3 watchlists.py list                              # All watchlists
    python3 watchlists.py detail <alias>                    # Watchlist detail
    python3 watchlists.py items <alias>                     # List items in a watchlist
    python3 watchlists.py add-item <alias> <json-object>    # Add item
    python3 watchlists.py delete-item <alias> <item-id>     # Remove item
    python3 watchlists.py create <alias> <display-name> <description> <search-key>
    python3 watchlists.py delete <alias>                    # Delete watchlist
"""

import sys
import json

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from defender_client import DefenderClient


def cmd_list(client: DefenderClient):
    watchlists = client.sentinel_get_all("watchlists")

    if not watchlists:
        print("No watchlists found.")
        return

    print(f"Sentinel Watchlists: {len(watchlists)}\n")
    print(f"  {'Alias':25s}  {'Display Name':30s}  {'Items':>6s}  {'Provider':15s}")
    print(f"  {'─'*25}  {'─'*30}  {'─'*6}  {'─'*15}")

    for w in watchlists:
        props = w.get("properties") or {}
        alias = (props.get("watchlistAlias") or "?")[:25]
        name = (props.get("displayName") or "?")[:30]
        items = str(props.get("numberOfLinesToSkip") or "?")
        provider = (props.get("provider") or "?")[:15]
        print(f"  {alias:25s}  {name:30s}  {items:>6s}  {provider:15s}")


def cmd_detail(client: DefenderClient, alias: str):
    resp = client.sentinel_get(f"watchlists/{alias}")
    if resp.status_code != 200:
        print(f"ERROR: {resp.status_code} {resp.text}")
        return

    w = resp.json()
    props = w.get("properties", {})
    print(f"Watchlist: {props.get('displayName', '?')}")
    print(f"  Alias:         {props.get('watchlistAlias', '?')}")
    print(f"  Description:   {props.get('description', '?')}")
    print(f"  Search Key:    {props.get('itemsSearchKey', '?')}")
    print(f"  Provider:      {props.get('provider', '?')}")
    print(f"  Source:        {props.get('source', '?')}")
    print(f"  Created:       {props.get('created', '?')}")
    print(f"  Updated:       {props.get('updated', '?')}")
    print(f"  Created By:    {props.get('createdBy', {}).get('name', '?')}")

    print(f"\n  KQL Usage: _GetWatchlist('{props.get('watchlistAlias', alias)}')")


def cmd_items(client: DefenderClient, alias: str):
    items = client.sentinel_get_all(f"watchlists/{alias}/watchlistItems")

    if not items:
        print(f"No items in watchlist '{alias}'.")
        return

    print(f"Items in '{alias}': {len(items)}\n")

    for item in items[:50]:
        props = item.get("properties", {})
        item_id = item.get("name", "?")
        kv = props.get("itemsKeyValue", {})
        print(f"  [{item_id}] {json.dumps(kv, indent=None)}")

    if len(items) > 50:
        print(f"\n  ... and {len(items) - 50} more items")


def cmd_add_item(client: DefenderClient, alias: str, item_json: str):
    try:
        item_data = json.loads(item_json)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON: {item_json}")
        sys.exit(1)

    body = {
        "properties": {
            "itemsKeyValue": item_data,
        }
    }
    resp = client.sentinel_put(
        f"watchlists/{alias}/watchlistItems/{item_data.get('id', 'new-item')}",
        body,
    )
    if resp.status_code in (200, 201):
        print(f"Item added to watchlist '{alias}'")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_delete_item(client: DefenderClient, alias: str, item_id: str):
    resp = client.sentinel_delete(f"watchlists/{alias}/watchlistItems/{item_id}")
    if resp.status_code in (200, 204):
        print(f"Item '{item_id}' deleted from watchlist '{alias}'")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_create(client: DefenderClient, alias: str, display_name: str, description: str, search_key: str):
    body = {
        "properties": {
            "watchlistAlias": alias,
            "displayName": display_name,
            "description": description,
            "provider": "Tendril Bridge",
            "source": "Local",
            "itemsSearchKey": search_key,
        }
    }
    resp = client.sentinel_put(f"watchlists/{alias}", body)
    if resp.status_code in (200, 201):
        print(f"Watchlist '{alias}' created.")
        print(f"  KQL Usage: _GetWatchlist('{alias}')")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


def cmd_delete(client: DefenderClient, alias: str):
    resp = client.sentinel_delete(f"watchlists/{alias}")
    if resp.status_code in (200, 204):
        print(f"Watchlist '{alias}' deleted.")
    else:
        print(f"ERROR: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    client = DefenderClient()
    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "list":
        cmd_list(client)
    elif cmd == "detail" and args:
        cmd_detail(client, args[0])
    elif cmd == "items" and args:
        cmd_items(client, args[0])
    elif cmd == "add-item" and len(args) >= 2:
        cmd_add_item(client, args[0], " ".join(args[1:]))
    elif cmd == "delete-item" and len(args) >= 2:
        cmd_delete_item(client, args[0], args[1])
    elif cmd == "create" and len(args) >= 4:
        cmd_create(client, args[0], args[1], args[2], args[3])
    elif cmd == "delete" and args:
        cmd_delete(client, args[0])
    else:
        print(__doc__.strip())
        sys.exit(1)
