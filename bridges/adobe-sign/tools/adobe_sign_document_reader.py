#!/usr/bin/env python3
"""
Adobe Sign Document Reader

Extract text content from agreement PDFs using a hybrid pipeline:
native text extraction for born-digital documents, OCR for scanned pages.

Usage:
    python3 adobe_sign_document_reader.py text <agreement_id>
    python3 adobe_sign_document_reader.py text <agreement_id> --document <doc_id>
    python3 adobe_sign_document_reader.py text <agreement_id> --page <n>
    python3 adobe_sign_document_reader.py pages <agreement_id>
    python3 adobe_sign_document_reader.py search <agreement_id> <query>
    python3 adobe_sign_document_reader.py compare <agreement_id_1> <agreement_id_2>

Extraction pipeline:
    1. Download PDF from Adobe Sign API
    2. Try pdfminer.six for native text extraction (fast, handles born-digital)
    3. For pages with no/minimal text, render via PyMuPDF and OCR with Tesseract
    4. Return combined text with page markers
"""

import json
import os
import re
import sys
import tempfile
from difflib import unified_diff
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from adobe_sign_client import AdobeSignClient

MIN_TEXT_THRESHOLD = 50  # chars per page before OCR fallback triggers


def _extract_text_pdfminer(pdf_path: str) -> list[dict]:
    """Extract text per page using pdfminer.six. Returns list of {page, text, method}."""
    from pdfminer.high_level import extract_text
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument

    pages = []
    with open(pdf_path, "rb") as f:
        parser = PDFParser(f)
        doc = PDFDocument(parser)
        page_count = sum(1 for _ in PDFPage.create_pages(doc))

    for page_num in range(page_count):
        text = extract_text(pdf_path, page_numbers=[page_num])
        pages.append({
            "page": page_num + 1,
            "text": text.strip(),
            "method": "pdfminer",
            "char_count": len(text.strip()),
        })
    return pages


def _ocr_page(pdf_path: str, page_num: int, dpi: int = 300) -> str:
    """Render a single PDF page to image via PyMuPDF, then OCR with Tesseract."""
    import fitz
    import pytesseract
    from PIL import Image
    import io

    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    doc.close()

    img = Image.open(io.BytesIO(img_data))
    text = pytesseract.image_to_string(img)
    return text.strip()


def _extract_text_hybrid(pdf_path: str) -> list[dict]:
    """
    Hybrid extraction: try native text first, fall back to OCR for sparse pages.
    """
    pages = _extract_text_pdfminer(pdf_path)

    for page_info in pages:
        if page_info["char_count"] < MIN_TEXT_THRESHOLD:
            try:
                ocr_text = _ocr_page(pdf_path, page_info["page"] - 1)
                if len(ocr_text) > page_info["char_count"]:
                    page_info["text"] = ocr_text
                    page_info["method"] = "ocr-tesseract"
                    page_info["char_count"] = len(ocr_text)
            except Exception as e:
                page_info["ocr_error"] = str(e)

    return pages


def _download_agreement_pdf(client: AdobeSignClient, agreement_id: str,
                            document_id: str = None) -> str:
    """Download agreement PDF to a temp file. Returns path."""
    if document_id:
        resp = client.get_raw(f"/agreements/{agreement_id}/documents/{document_id}")
        data = resp.content
    else:
        data = client.get_agreement_combined_document(agreement_id)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def cmd_text(client, agreement_id, args):
    document_id = None
    page_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--document" and i + 1 < len(args):
            document_id = args[i + 1]
            i += 2
        elif args[i] == "--page" and i + 1 < len(args):
            page_filter = int(args[i + 1])
            i += 2
        else:
            i += 1

    pdf_path = _download_agreement_pdf(client, agreement_id, document_id)
    try:
        pages = _extract_text_hybrid(pdf_path)

        if page_filter:
            pages = [p for p in pages if p["page"] == page_filter]
            if not pages:
                print(f"No page {page_filter} found", file=sys.stderr)
                sys.exit(1)

        for page_info in pages:
            print(f"--- Page {page_info['page']} [{page_info['method']}, {page_info['char_count']} chars] ---")
            print(page_info["text"])
            print()
    finally:
        os.unlink(pdf_path)


def cmd_pages(client, agreement_id):
    pdf_path = _download_agreement_pdf(client, agreement_id)
    try:
        pages = _extract_text_hybrid(pdf_path)
        file_size = os.path.getsize(pdf_path)

        print(f"Agreement: {agreement_id}")
        print(f"File size: {file_size:,} bytes")
        print(f"Pages: {len(pages)}")
        print()
        print(f"{'Page':>6s}  {'Chars':>8s}  {'Method':15s}  {'Classification'}")
        print("-" * 55)
        for p in pages:
            if p["char_count"] == 0:
                classification = "blank/image-only"
            elif p["method"] == "ocr-tesseract":
                classification = "scanned (OCR applied)"
            elif p["char_count"] < MIN_TEXT_THRESHOLD:
                classification = "sparse text"
            else:
                classification = "born-digital"
            print(f"{p['page']:>6d}  {p['char_count']:>8d}  {p['method']:15s}  {classification}")
    finally:
        os.unlink(pdf_path)


def cmd_search(client, agreement_id, query):
    pdf_path = _download_agreement_pdf(client, agreement_id)
    try:
        pages = _extract_text_hybrid(pdf_path)
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        matches = []
        for p in pages:
            for line_num, line in enumerate(p["text"].splitlines(), 1):
                if pattern.search(line):
                    matches.append({
                        "page": p["page"],
                        "line": line_num,
                        "text": line.strip(),
                    })

        print(f"Search: '{query}' in agreement {agreement_id}")
        print(f"Matches: {len(matches)}")
        print()
        for m in matches:
            highlighted = pattern.sub(lambda x: f">>>{x.group()}<<<", m["text"])
            print(f"  Page {m['page']}, Line {m['line']}: {highlighted}")
    finally:
        os.unlink(pdf_path)


def cmd_compare(client, agreement_id_1, agreement_id_2):
    pdf1 = _download_agreement_pdf(client, agreement_id_1)
    pdf2 = _download_agreement_pdf(client, agreement_id_2)
    try:
        pages1 = _extract_text_hybrid(pdf1)
        pages2 = _extract_text_hybrid(pdf2)

        text1 = "\n".join(p["text"] for p in pages1).splitlines(keepends=True)
        text2 = "\n".join(p["text"] for p in pages2).splitlines(keepends=True)

        diff = list(unified_diff(
            text1, text2,
            fromfile=f"agreement/{agreement_id_1[:16]}",
            tofile=f"agreement/{agreement_id_2[:16]}",
            lineterm="",
        ))

        if not diff:
            print("Documents are identical in text content.")
        else:
            print(f"Differences between agreements:")
            print(f"  A: {agreement_id_1}")
            print(f"  B: {agreement_id_2}")
            print()
            for line in diff:
                print(line)
    finally:
        os.unlink(pdf1)
        os.unlink(pdf2)


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip())
        sys.exit(1)

    action = sys.argv[1]
    client = AdobeSignClient()

    if action == "text" and len(sys.argv) >= 3:
        cmd_text(client, sys.argv[2], sys.argv[3:])
    elif action == "pages" and len(sys.argv) >= 3:
        cmd_pages(client, sys.argv[2])
    elif action == "search" and len(sys.argv) >= 4:
        cmd_search(client, sys.argv[2], sys.argv[3])
    elif action == "compare" and len(sys.argv) >= 4:
        cmd_compare(client, sys.argv[2], sys.argv[3])
    else:
        print(__doc__.strip())
        sys.exit(1)


if __name__ == "__main__":
    main()
