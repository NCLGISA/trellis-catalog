#!/usr/bin/env python3
"""
Adobe Sign Templates (Library Documents) Tool

Browse and inspect reusable document templates in the Adobe Sign library.

Usage:
    python3 adobe_sign_templates.py list [--limit N]
    python3 adobe_sign_templates.py info <library_document_id>
    python3 adobe_sign_templates.py search <query>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adobe_sign_client import AdobeSignClient


def cmd_list(client, args):
    limit = 50
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    templates = client.list_library_documents(
        page_size=min(limit, 100),
        max_pages=max(1, limit // 100),
    )
    templates = templates[:limit]

    print(f"Library Documents ({len(templates)} shown):")
    print(f"{'Name':55s}  {'Sharing':12s}  {'Modified'}")
    print("-" * 90)
    for t in templates:
        name = t.get("name", "Untitled")[:55]
        sharing = t.get("sharingMode", t.get("scope", "?"))
        modified = t.get("modifiedDate", "?")
        if isinstance(modified, str) and "T" in modified:
            modified = modified[:19].replace("T", " ")
        print(f"{name:55s}  {sharing:12s}  {modified}")


def cmd_info(client, library_document_id):
    doc = client.get_library_document(library_document_id)
    print(json.dumps(doc, indent=2, default=str))


def cmd_search(client, query):
    templates = client.list_library_documents(page_size=100, max_pages=10)
    query_lower = query.lower()
    matches = [
        t for t in templates
        if query_lower in t.get("name", "").lower()
    ]

    if not matches:
        print(f"No templates matching '{query}'")
        return

    print(f"Templates matching '{query}' ({len(matches)} found):")
    print(f"{'Name':55s}  {'ID'}")
    print("-" * 90)
    for t in matches:
        name = t.get("name", "Untitled")[:55]
        tid = t.get("id", "?")
        print(f"{name:55s}  {tid}")


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = AdobeSignClient()

    if action == "list":
        cmd_list(client, sys.argv[2:])
    elif action == "info" and len(sys.argv) >= 3:
        cmd_info(client, sys.argv[2])
    elif action == "search" and len(sys.argv) >= 3:
        cmd_search(client, " ".join(sys.argv[2:]))
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
