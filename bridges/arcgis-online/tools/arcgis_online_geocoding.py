#!/usr/bin/env python3
"""
ArcGIS Online - Geocoding

Forward geocode, reverse geocode, batch geocode, and address suggestions.
Uses the org's configured geocode service or falls back to the ArcGIS World
Geocoding Service.

Usage:
    python3 arcgis_online_geocoding.py geocode "123 Main St, Springfield, IL"
    python3 arcgis_online_geocoding.py reverse 39.7817 -89.6501
    python3 arcgis_online_geocoding.py suggest "123 Main"
    python3 arcgis_online_geocoding.py batch addresses.txt
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from arcgis_online_client import ArcGISOnlineClient

WORLD_GEOCODER = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer"


def _get_geocode_url(client):
    """Discover the org's configured geocode service, fall back to world geocoder."""
    try:
        portal = client.get("portals/self")
        helpers = portal.get("helperServices", {})
        geocoders = helpers.get("geocode", [])
        if isinstance(geocoders, list) and geocoders:
            url = geocoders[0].get("url", WORLD_GEOCODER)
            return url
        if isinstance(geocoders, dict):
            return geocoders.get("url", WORLD_GEOCODER)
    except Exception:
        pass
    return WORLD_GEOCODER


def cmd_geocode(client, args):
    url = _get_geocode_url(client)
    params = {
        "singleLine": args.address,
        "outFields": "*",
        "maxLocations": args.max,
    }
    if args.country:
        params["countryCode"] = args.country

    result = client.get_url(f"{url}/findAddressCandidates", params=params)
    candidates = result.get("candidates", [])
    print(f"Candidates: {len(candidates)}")
    print()
    for c in candidates:
        loc = c.get("location", {})
        score = c.get("score", 0)
        addr = c.get("address", "?")
        print(f"  [{score:5.1f}]  {addr}")
        print(f"          lat={loc.get('y', '?')}, lon={loc.get('x', '?')}")
        attrs = c.get("attributes", {})
        if attrs.get("City"):
            print(f"          {attrs.get('City', '')}, {attrs.get('Region', '')} {attrs.get('Postal', '')}")


def cmd_reverse(client, args):
    url = _get_geocode_url(client)
    result = client.get_url(f"{url}/reverseGeocode", params={
        "location": f"{args.lon},{args.lat}",
        "outSR": "4326",
    })
    addr = result.get("address", {})
    loc = result.get("location", {})
    print(f"Address: {addr.get('Match_addr', addr.get('LongLabel', 'unknown'))}")
    print(f"Location: lat={loc.get('y', '?')}, lon={loc.get('x', '?')}")
    if addr:
        print(f"\nFull address fields:")
        for k, v in addr.items():
            if v:
                print(f"  {k}: {v}")


def cmd_suggest(client, args):
    url = _get_geocode_url(client)
    params = {"text": args.text, "maxSuggestions": args.max}
    if args.location:
        params["location"] = args.location
    result = client.get_url(f"{url}/suggest", params=params)
    suggestions = result.get("suggestions", [])
    print(f"Suggestions: {len(suggestions)}")
    for s in suggestions:
        print(f"  {s.get('text', '?')}")
        if s.get("magicKey"):
            print(f"    magicKey: {s['magicKey'][:40]}...")


def cmd_batch(client, args):
    url = _get_geocode_url(client)
    addresses = []
    with open(args.file) as f:
        for line in f:
            line = line.strip()
            if line:
                addresses.append(line)

    if not addresses:
        print("No addresses found in file")
        sys.exit(1)

    records = [
        {"attributes": {"OBJECTID": i + 1, "SingleLine": addr}}
        for i, addr in enumerate(addresses)
    ]

    result = client.post_url(f"{url}/geocodeAddresses", data={
        "addresses": json.dumps({"records": records}),
        "outSR": "4326",
        "f": "json",
    })

    locations = result.get("locations", [])
    print(f"Geocoded: {len(locations)} / {len(addresses)}")
    print()
    for loc in locations:
        attrs = loc.get("attributes", {})
        score = attrs.get("Score", 0)
        addr = attrs.get("Match_addr", "?")
        x = loc.get("location", {}).get("x", "?")
        y = loc.get("location", {}).get("y", "?")
        print(f"  [{score:5.1f}]  {addr}  ({y}, {x})")


def main():
    parser = argparse.ArgumentParser(description="ArcGIS Online Geocoding")
    sub = parser.add_subparsers(dest="command")

    p_gc = sub.add_parser("geocode")
    p_gc.add_argument("address")
    p_gc.add_argument("--max", type=int, default=5)
    p_gc.add_argument("--country", default=None)

    p_rv = sub.add_parser("reverse")
    p_rv.add_argument("lat", type=float)
    p_rv.add_argument("lon", type=float)

    p_sg = sub.add_parser("suggest")
    p_sg.add_argument("text")
    p_sg.add_argument("--max", type=int, default=10)
    p_sg.add_argument("--location", default=None)

    p_bt = sub.add_parser("batch")
    p_bt.add_argument("file")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = ArcGISOnlineClient()
    cmds = {
        "geocode": cmd_geocode, "reverse": cmd_reverse,
        "suggest": cmd_suggest, "batch": cmd_batch,
    }
    cmds[args.command](client, args)


if __name__ == "__main__":
    main()
