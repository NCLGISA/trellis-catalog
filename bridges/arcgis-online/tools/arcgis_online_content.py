#!/usr/bin/env python3
"""
ArcGIS Online - Content Management

Search items, view item details, list layers, and manage org content.

Usage:
    python3 arcgis_online_content.py search "water mains"
    python3 arcgis_online_content.py search "parcels" --type "Feature Service"
    python3 arcgis_online_content.py item <item_id>
    python3 arcgis_online_content.py item-data <item_id>
    python3 arcgis_online_content.py layers <service_url>
    python3 arcgis_online_content.py folders <username>
    python3 arcgis_online_content.py folder-items <username> <folder_id>
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arcgis_online_client import ArcGISOnlineClient


def cmd_search(client, args):
    result = client.search(args.query, item_type=args.type,
                           sort_field=args.sort, num=args.num, start=args.start)
    items = result.get("results", [])
    print(f"Total: {result.get('total', 0)} | Showing: {len(items)} (start={result.get('start', 1)})")
    print()
    for item in items:
        print(f"  {item['id']}  {item.get('type', '?'):25s}  {item['title']}")
        if item.get("snippet"):
            print(f"    {item['snippet'][:100]}")
    if result.get("nextStart", -1) != -1:
        print(f"\n  Next page: --start {result['nextStart']}")


def cmd_item(client, args):
    result = client.get(f"content/items/{args.item_id}")
    print(json.dumps(result, indent=2))


def cmd_item_data(client, args):
    result = client.get(f"content/items/{args.item_id}/data")
    print(json.dumps(result, indent=2))


def cmd_layers(client, args):
    result = client.get_url(args.service_url)
    layers = result.get("layers", [])
    tables = result.get("tables", [])
    print(f"Service: {result.get('serviceDescription', result.get('description', 'n/a'))}")
    print(f"Layers: {len(layers)}  Tables: {len(tables)}")
    print()
    for layer in layers:
        print(f"  [{layer['id']}] {layer['name']} ({layer.get('geometryType', 'n/a')})")
    for table in tables:
        print(f"  [{table['id']}] {table['name']} (table)")


def cmd_folders(client, args):
    result = client.get(f"content/users/{args.username}")
    folders = result.get("folders", [])
    items = result.get("items", [])
    print(f"Root items: {len(items)}")
    print(f"Folders: {len(folders)}")
    for f in folders:
        print(f"  {f['id']}  {f['title']}")


def cmd_folder_items(client, args):
    result = client.get(f"content/users/{args.username}/{args.folder_id}")
    items = result.get("items", [])
    print(f"Items in folder: {len(items)}")
    for item in items:
        print(f"  {item['id']}  {item.get('type', '?'):25s}  {item['title']}")


def main():
    parser = argparse.ArgumentParser(description="ArcGIS Online Content Management")
    sub = parser.add_subparsers(dest="command")

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--type", default=None)
    p_search.add_argument("--num", type=int, default=25)
    p_search.add_argument("--start", type=int, default=1)
    p_search.add_argument("--sort", default="modified")

    p_item = sub.add_parser("item")
    p_item.add_argument("item_id")

    p_data = sub.add_parser("item-data")
    p_data.add_argument("item_id")

    p_layers = sub.add_parser("layers")
    p_layers.add_argument("service_url")

    p_folders = sub.add_parser("folders")
    p_folders.add_argument("username")

    p_fitems = sub.add_parser("folder-items")
    p_fitems.add_argument("username")
    p_fitems.add_argument("folder_id")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = ArcGISOnlineClient()
    cmds = {
        "search": cmd_search, "item": cmd_item, "item-data": cmd_item_data,
        "layers": cmd_layers, "folders": cmd_folders, "folder-items": cmd_folder_items,
    }
    cmds[args.command](client, args)


if __name__ == "__main__":
    main()
