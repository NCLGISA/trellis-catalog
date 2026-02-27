#!/usr/bin/env python3
"""Confluence Cloud CLI -- spaces, pages, search, blog posts, and more."""

import argparse
import json
import sys

from confluence_client import ConfluenceClient


def jprint(obj):
    print(json.dumps(obj, indent=2, default=str))


# ===== Spaces ==============================================================

def cmd_spaces_list(client, args):
    jprint(client.list_spaces(limit=args.limit))

def cmd_spaces_get(client, args):
    jprint(client.get_space(args.id))

# ===== Pages ===============================================================

def cmd_pages_list(client, args):
    jprint(client.list_pages(
        space_id=args.space_id, limit=args.limit,
        body_format=args.body_format if args.body_format else None))

def cmd_pages_get(client, args):
    jprint(client.get_page(args.id, body_format=args.body_format))

def cmd_pages_create(client, args):
    jprint(client.create_page(
        space_id=args.space_id, title=args.title, body=args.body,
        body_format=args.body_format, parent_id=args.parent_id))

def cmd_pages_update(client, args):
    if not args.version:
        page = client.get_page(args.id)
        args.version = page.get("version", {}).get("number", 1) + 1
    jprint(client.update_page(
        page_id=args.id, title=args.title, body=args.body,
        version_number=args.version, body_format=args.body_format))

def cmd_pages_delete(client, args):
    client.delete_page(args.id)
    print(json.dumps({"deleted": args.id}))

# ===== Search ==============================================================

def cmd_search(client, args):
    jprint(client.search(args.cql, limit=args.limit))

# ===== Blog Posts ==========================================================

def cmd_blogposts_list(client, args):
    jprint(client.list_blogposts(space_id=args.space_id, limit=args.limit))

def cmd_blogposts_get(client, args):
    jprint(client.get_blogpost(args.id, body_format=args.body_format))

# ===== Comments ============================================================

def cmd_comments_list(client, args):
    jprint(client.get_page_comments(args.page_id, limit=args.limit))

def cmd_comments_create(client, args):
    jprint(client.create_comment(args.page_id, args.body))

# ===== Labels ==============================================================

def cmd_labels_list(client, args):
    jprint(client.get_page_labels(args.page_id, limit=args.limit))

def cmd_labels_add(client, args):
    jprint(client.add_page_label(args.page_id, args.label))

# ===== Tasks ===============================================================

def cmd_tasks_list(client, args):
    jprint(client.list_tasks(limit=args.limit, status=args.status))

# ===== Info ================================================================

def cmd_info(client, args):
    jprint(client.info())


def build_parser():
    parser = argparse.ArgumentParser(description="Confluence Cloud CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # -- spaces
    p_sp = sub.add_parser("spaces", help="Space operations")
    sp_sub = p_sp.add_subparsers(dest="subcommand", required=True)

    p_sp_list = sp_sub.add_parser("list", help="List spaces")
    p_sp_list.add_argument("--limit", type=int, default=25)
    p_sp_list.set_defaults(func=cmd_spaces_list)

    p_sp_get = sp_sub.add_parser("get", help="Get space by ID")
    p_sp_get.add_argument("--id", required=True)
    p_sp_get.set_defaults(func=cmd_spaces_get)

    # -- pages
    p_pg = sub.add_parser("pages", help="Page operations")
    pg_sub = p_pg.add_subparsers(dest="subcommand", required=True)

    p_pg_list = pg_sub.add_parser("list", help="List pages")
    p_pg_list.add_argument("--space-id", dest="space_id")
    p_pg_list.add_argument("--limit", type=int, default=25)
    p_pg_list.add_argument("--body-format", dest="body_format",
                           choices=["storage", "atlas_doc_format", "view"])
    p_pg_list.set_defaults(func=cmd_pages_list)

    p_pg_get = pg_sub.add_parser("get", help="Get page by ID")
    p_pg_get.add_argument("--id", required=True)
    p_pg_get.add_argument("--body-format", dest="body_format", default="storage",
                          choices=["storage", "atlas_doc_format", "view"])
    p_pg_get.set_defaults(func=cmd_pages_get)

    p_pg_create = pg_sub.add_parser("create", help="Create page")
    p_pg_create.add_argument("--space-id", dest="space_id", required=True)
    p_pg_create.add_argument("--title", required=True)
    p_pg_create.add_argument("--body", required=True,
                             help="Page body (Confluence storage format HTML)")
    p_pg_create.add_argument("--body-format", dest="body_format", default="storage")
    p_pg_create.add_argument("--parent-id", dest="parent_id")
    p_pg_create.set_defaults(func=cmd_pages_create)

    p_pg_update = pg_sub.add_parser("update", help="Update page")
    p_pg_update.add_argument("--id", required=True)
    p_pg_update.add_argument("--title", required=True)
    p_pg_update.add_argument("--body", required=True)
    p_pg_update.add_argument("--version", type=int,
                             help="Version number (auto-increments if omitted)")
    p_pg_update.add_argument("--body-format", dest="body_format", default="storage")
    p_pg_update.set_defaults(func=cmd_pages_update)

    p_pg_del = pg_sub.add_parser("delete", help="Delete page")
    p_pg_del.add_argument("--id", required=True)
    p_pg_del.set_defaults(func=cmd_pages_delete)

    # -- search
    p_search = sub.add_parser("search", help="CQL search")
    p_search.add_argument("--cql", required=True,
                          help='CQL query (e.g. \'type=page AND text~"keyword"\')')
    p_search.add_argument("--limit", type=int, default=25)
    p_search.set_defaults(func=cmd_search)

    # -- blogposts
    p_bp = sub.add_parser("blogposts", help="Blog post operations")
    bp_sub = p_bp.add_subparsers(dest="subcommand", required=True)

    p_bp_list = bp_sub.add_parser("list", help="List blog posts")
    p_bp_list.add_argument("--space-id", dest="space_id")
    p_bp_list.add_argument("--limit", type=int, default=25)
    p_bp_list.set_defaults(func=cmd_blogposts_list)

    p_bp_get = bp_sub.add_parser("get", help="Get blog post by ID")
    p_bp_get.add_argument("--id", required=True)
    p_bp_get.add_argument("--body-format", dest="body_format", default="storage",
                          choices=["storage", "atlas_doc_format", "view"])
    p_bp_get.set_defaults(func=cmd_blogposts_get)

    # -- comments
    p_cm = sub.add_parser("comments", help="Comment operations")
    cm_sub = p_cm.add_subparsers(dest="subcommand", required=True)

    p_cm_list = cm_sub.add_parser("list", help="List page comments")
    p_cm_list.add_argument("--page-id", dest="page_id", required=True)
    p_cm_list.add_argument("--limit", type=int, default=25)
    p_cm_list.set_defaults(func=cmd_comments_list)

    p_cm_create = cm_sub.add_parser("create", help="Add comment to page")
    p_cm_create.add_argument("--page-id", dest="page_id", required=True)
    p_cm_create.add_argument("--body", required=True)
    p_cm_create.set_defaults(func=cmd_comments_create)

    # -- labels
    p_lb = sub.add_parser("labels", help="Label operations")
    lb_sub = p_lb.add_subparsers(dest="subcommand", required=True)

    p_lb_list = lb_sub.add_parser("list", help="List page labels")
    p_lb_list.add_argument("--page-id", dest="page_id", required=True)
    p_lb_list.add_argument("--limit", type=int, default=25)
    p_lb_list.set_defaults(func=cmd_labels_list)

    p_lb_add = lb_sub.add_parser("add", help="Add label to page")
    p_lb_add.add_argument("--page-id", dest="page_id", required=True)
    p_lb_add.add_argument("--label", required=True)
    p_lb_add.set_defaults(func=cmd_labels_add)

    # -- tasks
    p_tk = sub.add_parser("tasks", help="Task operations")
    tk_sub = p_tk.add_subparsers(dest="subcommand", required=True)

    p_tk_list = tk_sub.add_parser("list", help="List tasks")
    p_tk_list.add_argument("--limit", type=int, default=25)
    p_tk_list.add_argument("--status", choices=["complete", "incomplete"])
    p_tk_list.set_defaults(func=cmd_tasks_list)

    # -- info
    p_info = sub.add_parser("info", help="Connection info")
    p_info.set_defaults(func=cmd_info)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    client = ConfluenceClient()
    args.func(client, args)


if __name__ == "__main__":
    main()
