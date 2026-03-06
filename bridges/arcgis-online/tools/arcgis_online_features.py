#!/usr/bin/env python3
"""
ArcGIS Online - Feature Services

Query feature layers, get counts, inspect schemas, and export data.

Usage:
    python3 arcgis_online_features.py query <service_url> <layer_id> --where "1=1" --num 10
    python3 arcgis_online_features.py count <service_url> <layer_id> --where "1=1"
    python3 arcgis_online_features.py info <service_url> <layer_id>
    python3 arcgis_online_features.py export <service_url> <layer_id> --where "1=1" --format geojson
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arcgis_online_client import ArcGISOnlineClient


def _layer_url(service_url, layer_id):
    return f"{service_url.rstrip('/')}/{layer_id}"


def cmd_query(client, args):
    url = _layer_url(args.service_url, args.layer_id)
    params = {
        "where": args.where,
        "outFields": args.fields or "*",
        "returnGeometry": str(args.geometry).lower(),
        "resultRecordCount": args.num,
        "resultOffset": args.offset,
    }
    result = client.get_url(f"{url}/query", params=params)
    features = result.get("features", [])
    print(f"Features returned: {len(features)}")
    exceeded = result.get("exceededTransferLimit", False)
    if exceeded:
        print("(more results available -- increase --num or use --offset)")
    print()
    for feat in features:
        attrs = feat.get("attributes", {})
        print(json.dumps(attrs, indent=2, default=str))


def cmd_count(client, args):
    url = _layer_url(args.service_url, args.layer_id)
    result = client.get_url(f"{url}/query", params={
        "where": args.where, "returnCountOnly": "true",
    })
    print(f"Count: {result.get('count', 'unknown')}")


def cmd_info(client, args):
    url = _layer_url(args.service_url, args.layer_id)
    result = client.get_url(url)
    print(f"Name: {result.get('name')}")
    print(f"Type: {result.get('type')}")
    print(f"Geometry: {result.get('geometryType', 'n/a')}")
    print(f"Max Record Count: {result.get('maxRecordCount', 'n/a')}")
    print(f"Description: {result.get('description', 'n/a')}")
    print()
    fields = result.get("fields", [])
    print(f"Fields ({len(fields)}):")
    for f in fields:
        alias = f.get("alias", "")
        ftype = f.get("type", "?").replace("esriFieldType", "")
        nullable = "null" if f.get("nullable") else "not-null"
        print(f"  {f['name']:30s}  {ftype:15s}  {nullable:8s}  {alias}")


def cmd_export(client, args):
    url = _layer_url(args.service_url, args.layer_id)
    params = {
        "where": args.where,
        "outFields": args.fields or "*",
        "returnGeometry": "true",
    }
    if args.format == "geojson":
        params["f"] = "geojson"
        result = client.get_url(f"{url}/query", params=params)
        print(json.dumps(result, indent=2, default=str))
    else:
        params["resultRecordCount"] = 2000
        all_features = []
        offset = 0
        while True:
            params["resultOffset"] = offset
            result = client.get_url(f"{url}/query", params=params)
            features = result.get("features", [])
            if not features:
                break
            all_features.extend(features)
            if not result.get("exceededTransferLimit"):
                break
            offset += len(features)

        if args.format == "csv":
            if all_features:
                fields = list(all_features[0].get("attributes", {}).keys())
                print(",".join(fields))
                for feat in all_features:
                    attrs = feat.get("attributes", {})
                    print(",".join(str(attrs.get(f, "")) for f in fields))
        else:
            print(json.dumps(all_features, indent=2, default=str))

    print(f"\n# Exported {len(all_features) if args.format != 'geojson' else 'n/a'} features", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="ArcGIS Online Feature Services")
    sub = parser.add_subparsers(dest="command")

    p_q = sub.add_parser("query")
    p_q.add_argument("service_url")
    p_q.add_argument("layer_id")
    p_q.add_argument("--where", default="1=1")
    p_q.add_argument("--fields", default=None)
    p_q.add_argument("--geometry", action="store_true", default=False)
    p_q.add_argument("--num", type=int, default=10)
    p_q.add_argument("--offset", type=int, default=0)

    p_c = sub.add_parser("count")
    p_c.add_argument("service_url")
    p_c.add_argument("layer_id")
    p_c.add_argument("--where", default="1=1")

    p_i = sub.add_parser("info")
    p_i.add_argument("service_url")
    p_i.add_argument("layer_id")

    p_e = sub.add_parser("export")
    p_e.add_argument("service_url")
    p_e.add_argument("layer_id")
    p_e.add_argument("--where", default="1=1")
    p_e.add_argument("--fields", default=None)
    p_e.add_argument("--format", choices=["geojson", "json", "csv"], default="geojson")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = ArcGISOnlineClient()
    cmds = {"query": cmd_query, "count": cmd_count, "info": cmd_info, "export": cmd_export}
    cmds[args.command](client, args)


if __name__ == "__main__":
    main()
