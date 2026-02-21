#!/usr/bin/env python3
"""
Adobe Sign Widgets (Web Forms) Tool

Browse and inspect web forms and their generated agreements.

Usage:
    python3 adobe_sign_widgets.py list
    python3 adobe_sign_widgets.py info <widget_id>
    python3 adobe_sign_widgets.py agreements <widget_id>
    python3 adobe_sign_widgets.py form-data <widget_id>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adobe_sign_client import AdobeSignClient


def cmd_list(client):
    widgets = client.list_widgets()
    print(f"Web Forms ({len(widgets)}):")
    print(f"{'Status':12s}  {'Name':50s}  {'Modified'}")
    print("-" * 80)
    for w in widgets:
        status = w.get("status", "?")
        name = w.get("name", "Untitled")[:50]
        modified = w.get("modifiedDate", "?")
        if isinstance(modified, str) and "T" in modified:
            modified = modified[:19].replace("T", " ")
        print(f"{status:12s}  {name:50s}  {modified}")


def cmd_info(client, widget_id):
    widget = client.get_widget(widget_id)
    print(json.dumps(widget, indent=2, default=str))


def cmd_agreements(client, widget_id):
    agreements = client.get_widget_agreements(widget_id)
    print(f"Agreements from web form {widget_id} ({len(agreements)}):")
    print(f"{'Status':20s}  {'Name':50s}")
    print("-" * 75)
    for a in agreements:
        status = a.get("status", "?")
        name = a.get("name", "Untitled")[:50]
        print(f"{status:20s}  {name}")


def cmd_form_data(client, widget_id):
    data = client.get_widget_form_data(widget_id)
    print(data)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = AdobeSignClient()

    if action == "list":
        cmd_list(client)
    elif action == "info" and len(sys.argv) >= 3:
        cmd_info(client, sys.argv[2])
    elif action == "agreements" and len(sys.argv) >= 3:
        cmd_agreements(client, sys.argv[2])
    elif action == "form-data" and len(sys.argv) >= 3:
        cmd_form_data(client, sys.argv[2])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
