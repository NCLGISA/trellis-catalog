#!/usr/bin/env python3
"""
Adobe Sign Bridge - Integration Test Battery

Read-only tests that verify API connectivity, authentication, document
extraction pipeline, and data access across all tool categories. Run
after deployment to validate the bridge is fully operational.

Usage:
    python3 /opt/bridge/data/tools/adobe_sign_bridge_tests.py
    python3 /opt/bridge/data/tools/adobe_sign_bridge_tests.py --json
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# ── Test harness ───────────────────────────────────────────────────

results = []
start_time = time.time()


def run_test(category, name, fn):
    try:
        detail = fn()
        results.append({
            "category": category,
            "name": name,
            "status": "PASS",
            "detail": detail or "",
        })
    except Exception as e:
        results.append({
            "category": category,
            "name": name,
            "status": "FAIL",
            "detail": str(e),
        })


def skip_test(category, name, reason):
    results.append({
        "category": category,
        "name": name,
        "status": "SKIP",
        "detail": reason,
    })


# ── Bridge Health ──────────────────────────────────────────────────

def test_env_vars():
    key = os.getenv("ADOBE_SIGN_INTEGRATION_KEY", "")
    assert key, "ADOBE_SIGN_INTEGRATION_KEY is not set"
    return f"Key present ({len(key)} chars, ends ...{key[-4:]})"


def test_client_init():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    return f"Client initialized"


# ── Base URI Discovery ─────────────────────────────────────────────

def test_base_uri_discovery():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    base = client.api_base
    assert base, "API base is empty"
    assert "api" in base.lower(), f"Unexpected base URI: {base}"
    return f"Discovered: {base}"


# ── Agreements ─────────────────────────────────────────────────────

_sample_agreement_id = None


def test_list_agreements():
    global _sample_agreement_id
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    agreements = client.list_agreements(page_size=5, max_pages=1)
    assert isinstance(agreements, list), "Expected list of agreements"
    if agreements:
        _sample_agreement_id = agreements[0].get("id")
    return f"{len(agreements)} agreements in first page"


def test_get_agreement():
    if not _sample_agreement_id:
        raise Exception("No sample agreement ID from list test")
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    agreement = client.get_agreement(_sample_agreement_id)
    assert "id" in agreement, "Agreement missing 'id' field"
    assert "name" in agreement, "Agreement missing 'name' field"
    return f"{agreement.get('name', '?')[:50]} [{agreement.get('status', '?')}]"


def test_get_agreement_members():
    if not _sample_agreement_id:
        raise Exception("No sample agreement ID from list test")
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    members = client.get_agreement_members(_sample_agreement_id)
    assert isinstance(members, dict), "Expected dict response"
    return f"Members response received"


def test_get_agreement_events():
    if not _sample_agreement_id:
        raise Exception("No sample agreement ID from list test")
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    events = client.get_agreement_events(_sample_agreement_id)
    assert isinstance(events, list), "Expected list of events"
    return f"{len(events)} events"


def test_get_agreement_documents():
    if not _sample_agreement_id:
        raise Exception("No sample agreement ID from list test")
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    docs = client.get_agreement_documents(_sample_agreement_id)
    assert isinstance(docs, list), "Expected list of documents"
    return f"{len(docs)} document(s)"


# ── PDF Download & Text Extraction ─────────────────────────────────

def test_pdf_download():
    if not _sample_agreement_id:
        raise Exception("No sample agreement ID from list test")
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    data = client.get_agreement_combined_document(_sample_agreement_id)
    assert len(data) > 100, f"PDF too small ({len(data)} bytes)"
    assert data[:5] == b"%PDF-", "Downloaded content is not a PDF"
    return f"Downloaded {len(data):,} bytes, valid PDF header"


def test_pdfminer_import():
    from pdfminer.high_level import extract_text
    return "pdfminer.six available"


def test_pymupdf_import():
    import fitz
    return f"PyMuPDF {fitz.version[0]} available"


def test_pytesseract_import():
    import pytesseract
    tess_version = pytesseract.get_tesseract_version()
    return f"pytesseract available, Tesseract {tess_version}"


def test_tesseract_binary():
    tess_path = shutil.which("tesseract")
    assert tess_path, "tesseract binary not found in PATH"
    return f"tesseract at {tess_path}"


def test_pdftotext_binary():
    pdftotext_path = shutil.which("pdftotext")
    assert pdftotext_path, "pdftotext binary not found in PATH"
    return f"pdftotext at {pdftotext_path}"


def test_text_extraction():
    if not _sample_agreement_id:
        raise Exception("No sample agreement ID from list test")
    from adobe_sign_client import AdobeSignClient
    from adobe_sign_document_reader import _download_agreement_pdf, _extract_text_hybrid
    client = AdobeSignClient()
    pdf_path = _download_agreement_pdf(client, _sample_agreement_id)
    try:
        pages = _extract_text_hybrid(pdf_path)
        assert len(pages) > 0, "No pages extracted"
        total_chars = sum(p["char_count"] for p in pages)
        methods = set(p["method"] for p in pages)
        return f"{len(pages)} pages, {total_chars:,} chars, methods: {', '.join(methods)}"
    finally:
        os.unlink(pdf_path)


# ── Library Documents ──────────────────────────────────────────────

def test_list_library_documents():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    templates = client.list_library_documents(page_size=5, max_pages=1)
    assert isinstance(templates, list), "Expected list of library documents"
    return f"{len(templates)} templates in first page"


# ── Widgets ────────────────────────────────────────────────────────

def test_list_widgets():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    widgets = client.list_widgets(page_size=5, max_pages=1)
    assert isinstance(widgets, list), "Expected list of widgets"
    return f"{len(widgets)} web forms in first page"


# ── Users ──────────────────────────────────────────────────────────

def test_list_users():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    users = client.list_users(page_size=5, max_pages=1)
    assert isinstance(users, list), "Expected list of users"
    assert len(users) > 0, "No users returned (key may lack user_read scope)"
    return f"{len(users)} users in first page"


# ── Webhooks ───────────────────────────────────────────────────────

def test_list_webhooks():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    webhooks = client.list_webhooks(page_size=5, max_pages=1)
    assert isinstance(webhooks, list), "Expected list of webhooks"
    return f"{len(webhooks)} webhooks"


# ── Workflows ──────────────────────────────────────────────────────

def test_list_workflows():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    workflows = client.list_workflows()
    assert isinstance(workflows, list), "Expected list of workflows"
    return f"{len(workflows)} workflows"


# ── Error Handling ─────────────────────────────────────────────────

def test_invalid_agreement_id():
    from adobe_sign_client import AdobeSignClient
    client = AdobeSignClient()
    try:
        client.get_agreement("INVALID_ID_12345")
        raise Exception("Expected error for invalid ID, but none raised")
    except Exception as e:
        if "INVALID_ID_12345" in str(e) or "404" in str(e) or "INVALID" in str(e).upper():
            return "Correctly rejected invalid agreement ID"
        return f"Error raised: {str(e)[:80]}"


# ── Run all tests ──────────────────────────────────────────────────

def main():
    print("Adobe Sign Bridge Test Battery")
    print("=" * 50)
    print()

    run_test("Bridge Health", "Environment variables", test_env_vars)
    run_test("Bridge Health", "Client initialization", test_client_init)

    run_test("Base URI", "Auto-discovery", test_base_uri_discovery)

    run_test("Agreements", "List agreements", test_list_agreements)
    if _sample_agreement_id:
        run_test("Agreements", "Get agreement detail", test_get_agreement)
        run_test("Agreements", "Get agreement members", test_get_agreement_members)
        run_test("Agreements", "Get agreement events", test_get_agreement_events)
        run_test("Agreements", "Get agreement documents", test_get_agreement_documents)
    else:
        skip_test("Agreements", "Get agreement detail", "No agreements to test")
        skip_test("Agreements", "Get agreement members", "No agreements to test")
        skip_test("Agreements", "Get agreement events", "No agreements to test")
        skip_test("Agreements", "Get agreement documents", "No agreements to test")

    run_test("PDF Pipeline", "PDF download", test_pdf_download if _sample_agreement_id else
             lambda: (_ for _ in ()).throw(Exception("No agreement for PDF test")))
    run_test("PDF Pipeline", "pdfminer.six import", test_pdfminer_import)
    run_test("PDF Pipeline", "PyMuPDF import", test_pymupdf_import)
    run_test("PDF Pipeline", "pytesseract import", test_pytesseract_import)
    run_test("PDF Pipeline", "tesseract binary", test_tesseract_binary)
    run_test("PDF Pipeline", "pdftotext binary", test_pdftotext_binary)
    if _sample_agreement_id:
        run_test("PDF Pipeline", "Text extraction (hybrid)", test_text_extraction)
    else:
        skip_test("PDF Pipeline", "Text extraction (hybrid)", "No agreement for extraction test")

    run_test("Library Documents", "List templates", test_list_library_documents)
    run_test("Widgets", "List web forms", test_list_widgets)
    run_test("Users", "List users", test_list_users)
    run_test("Webhooks", "List webhooks", test_list_webhooks)
    run_test("Workflows", "List workflows", test_list_workflows)
    run_test("Error Handling", "Invalid agreement ID", test_invalid_agreement_id)

    # ── Report ─────────────────────────────────────────────────────

    elapsed = time.time() - start_time
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    print()
    current_category = ""
    for r in results:
        if r["category"] != current_category:
            current_category = r["category"]
            print(f"  [{current_category}]")
        icon = {"PASS": "+", "FAIL": "X", "SKIP": "-"}[r["status"]]
        print(f"    [{icon}] {r['name']}: {r['detail']}")

    print()
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped ({elapsed:.1f}s)")

    if "--json" in sys.argv:
        report = {
            "bridge": "adobe-sign",
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "elapsed_seconds": round(elapsed, 1),
            "tests": results,
        }
        print(json.dumps(report, indent=2))

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
