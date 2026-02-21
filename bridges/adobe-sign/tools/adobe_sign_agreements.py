#!/usr/bin/env python3
"""
Adobe Sign Agreements Tool

Manage e-signature agreements: list, inspect, download documents,
audit trails, send new agreements, cancel, and send reminders.

Usage:
    python3 adobe_sign_agreements.py list [--status STATUS] [--limit N]
    python3 adobe_sign_agreements.py info <agreement_id>
    python3 adobe_sign_agreements.py documents <agreement_id>
    python3 adobe_sign_agreements.py download <agreement_id> [output_path]
    python3 adobe_sign_agreements.py audit <agreement_id> [output_path]
    python3 adobe_sign_agreements.py form-data <agreement_id>
    python3 adobe_sign_agreements.py events <agreement_id>
    python3 adobe_sign_agreements.py signing-urls <agreement_id>
    python3 adobe_sign_agreements.py send --name NAME --signer EMAIL --template TEMPLATE_ID
    python3 adobe_sign_agreements.py send --name NAME --signer EMAIL --file PATH
    python3 adobe_sign_agreements.py cancel <agreement_id>
    python3 adobe_sign_agreements.py remind <agreement_id> [--message TEXT]
    python3 adobe_sign_agreements.py read <agreement_id> [--page N]
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adobe_sign_client import AdobeSignClient


def cmd_list(client, args):
    limit = 50
    status_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1].upper()
            i += 2
        else:
            i += 1

    agreements = client.list_agreements(page_size=min(limit, 100), max_pages=max(1, limit // 100))

    if status_filter:
        agreements = [a for a in agreements if a.get("status", "").upper() == status_filter]

    agreements = agreements[:limit]
    print(f"Agreements ({len(agreements)} shown):")
    print(f"{'Status':20s}  {'Name':50s}  {'Modified'}")
    print("-" * 90)
    for a in agreements:
        status = a.get("status", "?")
        name = a.get("name", "Untitled")[:50]
        modified = a.get("lastEventDate", a.get("displayDate", "?"))
        if isinstance(modified, str) and "T" in modified:
            modified = modified[:19].replace("T", " ")
        print(f"{status:20s}  {name:50s}  {modified}")


def cmd_info(client, agreement_id):
    agreement = client.get_agreement(agreement_id)
    print(json.dumps(agreement, indent=2, default=str))


def cmd_documents(client, agreement_id):
    docs = client.get_agreement_documents(agreement_id)
    print(f"Documents for agreement {agreement_id}:")
    for d in docs:
        doc_id = d.get("id", "?")
        name = d.get("name", "Untitled")
        mime = d.get("mimeType", "?")
        print(f"  {doc_id}  {name}  ({mime})")


def cmd_download(client, agreement_id, output_path=None):
    if not output_path:
        output_path = f"agreement_{agreement_id[:12]}.pdf"
    data = client.get_agreement_combined_document(agreement_id)
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"Downloaded combined document to {output_path} ({len(data)} bytes)")


def cmd_audit(client, agreement_id, output_path=None):
    if not output_path:
        output_path = f"audit_{agreement_id[:12]}.pdf"
    data = client.get_agreement_audit_trail(agreement_id)
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"Downloaded audit trail to {output_path} ({len(data)} bytes)")


def cmd_form_data(client, agreement_id):
    data = client.get_agreement_form_data(agreement_id)
    print(data)


def cmd_events(client, agreement_id):
    events = client.get_agreement_events(agreement_id)
    print(f"Events for agreement {agreement_id} ({len(events)} events):")
    for e in events:
        etype = e.get("type", "?")
        date = e.get("date", "?")
        if isinstance(date, str) and "T" in date:
            date = date[:19].replace("T", " ")
        participant = e.get("participantEmail", e.get("actingUserEmail", ""))
        desc = e.get("description", "")
        print(f"  {date}  {etype:30s}  {participant:35s}  {desc}")


def cmd_signing_urls(client, agreement_id):
    result = client.get_agreement_signing_urls(agreement_id)
    signing_url_sets = result.get("signingUrlSetInfos", [])
    if not signing_url_sets:
        print("No signing URLs available (agreement may be completed or cancelled)")
        return
    for url_set in signing_url_sets:
        for url_info in url_set.get("signingUrls", []):
            email = url_info.get("email", "?")
            url = url_info.get("esignUrl", "?")
            print(f"  {email}: {url}")


def cmd_send(client, args):
    name = None
    signers = []
    template_id = None
    file_path = None
    message = ""

    i = 0
    while i < len(args):
        if args[i] == "--name" and i + 1 < len(args):
            name = args[i + 1]
            i += 2
        elif args[i] == "--signer" and i + 1 < len(args):
            signers.append(args[i + 1])
            i += 2
        elif args[i] == "--template" and i + 1 < len(args):
            template_id = args[i + 1]
            i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            file_path = args[i + 1]
            i += 2
        elif args[i] == "--message" and i + 1 < len(args):
            message = args[i + 1]
            i += 2
        else:
            i += 1

    if not name:
        print("ERROR: --name is required", file=sys.stderr)
        sys.exit(1)
    if not signers:
        print("ERROR: at least one --signer EMAIL is required", file=sys.stderr)
        sys.exit(1)
    if not template_id and not file_path:
        print("ERROR: --template TEMPLATE_ID or --file PATH is required", file=sys.stderr)
        sys.exit(1)

    file_infos = []
    if template_id:
        file_infos.append({
            "libraryDocumentId": template_id,
        })
    elif file_path:
        transient_id = client.upload_transient_document(file_path)
        file_infos.append({
            "transientDocumentId": transient_id,
        })

    participant_sets = []
    for idx, email in enumerate(signers):
        participant_sets.append({
            "memberInfos": [{"email": email}],
            "order": idx + 1,
            "role": "SIGNER",
        })

    agreement_info = {
        "fileInfos": file_infos,
        "name": name,
        "participantSetsInfo": participant_sets,
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
    }
    if message:
        agreement_info["message"] = message

    result = client.create_agreement(agreement_info)
    agreement_id = result.get("id", "?")
    print(f"Agreement created: {agreement_id}")
    print(json.dumps(result, indent=2))


def cmd_cancel(client, agreement_id):
    result = client.cancel_agreement(agreement_id)
    print(f"Agreement {agreement_id} cancelled")
    if result:
        print(json.dumps(result, indent=2))


def cmd_read(client, agreement_id, args):
    from adobe_sign_document_reader import _download_agreement_pdf, _extract_text_hybrid
    page_filter = None
    i = 0
    while i < len(args):
        if args[i] == "--page" and i + 1 < len(args):
            page_filter = int(args[i + 1])
            i += 2
        else:
            i += 1

    pdf_path = _download_agreement_pdf(client, agreement_id)
    try:
        pages = _extract_text_hybrid(pdf_path)
        if page_filter:
            pages = [p for p in pages if p["page"] == page_filter]
        for page_info in pages:
            print(f"--- Page {page_info['page']} [{page_info['method']}, {page_info['char_count']} chars] ---")
            print(page_info["text"])
            print()
    finally:
        import os
        os.unlink(pdf_path)


def cmd_remind(client, agreement_id, args):
    message = ""
    i = 0
    while i < len(args):
        if args[i] == "--message" and i + 1 < len(args):
            message = args[i + 1]
            i += 2
        else:
            i += 1
    result = client.send_agreement_reminder(agreement_id, message=message)
    print(f"Reminder sent for agreement {agreement_id}")
    if result:
        print(json.dumps(result, indent=2))


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
    elif action == "documents" and len(sys.argv) >= 3:
        cmd_documents(client, sys.argv[2])
    elif action == "download" and len(sys.argv) >= 3:
        output = sys.argv[3] if len(sys.argv) >= 4 else None
        cmd_download(client, sys.argv[2], output)
    elif action == "audit" and len(sys.argv) >= 3:
        output = sys.argv[3] if len(sys.argv) >= 4 else None
        cmd_audit(client, sys.argv[2], output)
    elif action == "form-data" and len(sys.argv) >= 3:
        cmd_form_data(client, sys.argv[2])
    elif action == "events" and len(sys.argv) >= 3:
        cmd_events(client, sys.argv[2])
    elif action == "signing-urls" and len(sys.argv) >= 3:
        cmd_signing_urls(client, sys.argv[2])
    elif action == "send":
        cmd_send(client, sys.argv[2:])
    elif action == "cancel" and len(sys.argv) >= 3:
        cmd_cancel(client, sys.argv[2])
    elif action == "remind" and len(sys.argv) >= 3:
        cmd_remind(client, sys.argv[2], sys.argv[3:])
    elif action == "read" and len(sys.argv) >= 3:
        cmd_read(client, sys.argv[2], sys.argv[3:])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
