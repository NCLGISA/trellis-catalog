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

"""NAVEX PolicyTech CLI -- search and list published policy documents."""

import argparse
import json
import sys

from policytech_client import PolicyTechClient


def jprint(obj):
    print(json.dumps(obj, indent=2, default=str))


def cmd_search(client, args):
    if not args.query:
        print("--query required", file=sys.stderr)
        sys.exit(1)
    result = client.search(
        args.query,
        items_per_page=args.limit,
        start_index=args.offset,
        search_field=args.field,
    )
    jprint(result)


def cmd_search_all(client, args):
    if not args.query:
        print("--query required", file=sys.stderr)
        sys.exit(1)
    result = client.search_all(args.query, search_field=args.field)
    jprint(result)


def cmd_list(client, args):
    result = client.list_all()
    jprint(result)


def cmd_info(client, _args):
    jprint(client.info())


def build_parser():
    parser = argparse.ArgumentParser(description="NAVEX PolicyTech CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Search published documents")
    p_search.add_argument("--query", "-q", required=True,
                          help="Search keywords")
    p_search.add_argument("--field", default="ALL",
                          choices=["ALL", "TITLE"],
                          help="Field to search (default: ALL)")
    p_search.add_argument("--limit", type=int, default=25,
                          help="Results per page (default: 25)")
    p_search.add_argument("--offset", type=int, default=0,
                          help="Start index for pagination")
    p_search.set_defaults(func=cmd_search)

    p_all = sub.add_parser("search-all",
                           help="Search all pages of results")
    p_all.add_argument("--query", "-q", required=True,
                       help="Search keywords")
    p_all.add_argument("--field", default="ALL",
                       choices=["ALL", "TITLE"],
                       help="Field to search (default: ALL)")
    p_all.set_defaults(func=cmd_search_all)

    p_list = sub.add_parser("list", help="List all published documents")
    p_list.set_defaults(func=cmd_list)

    p_info = sub.add_parser("info", help="Connection info")
    p_info.set_defaults(func=cmd_info)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    client = PolicyTechClient()
    args.func(client, args)


if __name__ == "__main__":
    main()
