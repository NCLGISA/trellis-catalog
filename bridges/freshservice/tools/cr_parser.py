"""
Change Request Markdown Parser

Parses the structured docs/cr-*.md files into Python dicts suitable for
Freshservice Change API integration.

Handles two document formats:
  Format A (inline metadata):
    # Change Request: <Title>
    **CR Number:** CR-YYYY-MMDD-XXX
    **Date:** YYYY-MM-DD
    **Requested By:** <name>
    **Status:** <STATUS>

  Format B (table metadata):
    # Change Request: CR-YYYY-MMDD-NNN
    ## <Title>
    | **CR Number** | CR-YYYY-MMDD-NNN |
    | **Title** | <title> |
    | **Priority** | <priority> |
    ...
"""

import re
import os
from pathlib import Path
from datetime import datetime


def parse_cr_file(filepath: str) -> dict:
    """Parse a single CR markdown file and return a structured dict."""
    text = Path(filepath).read_text(encoding="utf-8")
    filename = os.path.basename(filepath)

    cr = {
        "source_file": filename,
        "source_path": filepath,
        "cr_number": "",
        "title": "",
        "date": "",
        "requested_by": "",
        "implemented_by": "",
        "status": "",
        "priority": "Medium",
        "risk_level": "Low",
        "change_type": "Standard Change",
        "change_window": "",
        "completed_date": "",
        "summary": "",
        "description_html": "",
        "affected_servers": [],
        "rollback_procedure": "",
        "implementation_plan": "",
    }

    lines = text.split("\n")

    # ── Extract title from first heading ───────────────────────────────
    for line in lines:
        if line.startswith("# "):
            heading = line.lstrip("# ").strip()
            # Format A: "Change Request: <Title>"
            if heading.startswith("Change Request:"):
                title_part = heading.split(":", 1)[1].strip()
                # Could be CR number or actual title
                if title_part.startswith("CR-"):
                    cr["cr_number"] = title_part
                else:
                    cr["title"] = title_part
            break

    # Look for ## subtitle as title (Format B)
    for line in lines:
        if line.startswith("## ") and not line.startswith("## Change Request"):
            subtitle = line.lstrip("# ").strip()
            # Skip numbered sections like "## 1. Change Description"
            if re.match(r"^\d+\.", subtitle):
                continue
            if not cr["title"]:
                cr["title"] = subtitle
            break

    # ── Parse inline metadata (Format A) ───────────────────────────────
    inline_patterns = {
        "cr_number": r"\*\*CR Number:\*\*\s*(.+)",
        "date": r"\*\*Date:\*\*\s*(.+)",
        "requested_by": r"\*\*Requested By:\*\*\s*(.+)",
        "status": r"\*\*Status:\*\*\s*(.+)",
        "completed_date": r"\*\*Completed:\*\*\s*(.+)",
    }
    for key, pattern in inline_patterns.items():
        m = re.search(pattern, text)
        if m:
            cr[key] = m.group(1).strip().rstrip("\\").strip()

    # ── Parse table metadata (Format B) ────────────────────────────────
    table_patterns = {
        "cr_number": r"\|\s*\*\*CR Number\*\*\s*\|\s*(.+?)\s*\|",
        "title": r"\|\s*\*\*Title\*\*\s*\|\s*(.+?)\s*\|",
        "priority": r"\|\s*\*\*Priority\*\*\s*\|\s*(.+?)\s*\|",
        "risk_level": r"\|\s*\*\*Risk Level\*\*\s*\|\s*(.+?)\s*\|",
        "status": r"\|\s*\*\*Status\*\*\s*\|\s*(.+?)\s*\|",
        "change_type": r"\|\s*\*\*Type\*\*\s*\|\s*(.+?)\s*\|",
        "change_window": r"\|\s*\*\*Change Window\*\*\s*\|\s*(.+?)\s*\|",
        "date": r"\|\s*\*\*Requested Date\*\*\s*\|\s*(.+?)\s*\|",
        "completed_date": r"\|\s*\*\*Implemented Date\*\*\s*\|\s*(.+?)\s*\|",
        "implemented_by": r"\|\s*\*\*Implemented By\*\*\s*\|\s*(.+?)\s*\|",
        "requested_by": r"\|\s*\*\*Requested By\*\*\s*\|\s*(.+?)\s*\|",
    }
    for key, pattern in table_patterns.items():
        m = re.search(pattern, text)
        if m:
            val = m.group(1).strip()
            if val and (not cr.get(key) or key in ("priority", "risk_level", "change_type", "change_window")):
                cr[key] = val

    # ── Derive unique CR number from filename if document CR is generic ──
    # Some Format B docs share the same CR number (e.g. CR-2026-0131-003).
    # Use the filename slug as a unique suffix to prevent sync-state collisions.
    _generic_pattern = re.compile(r"^CR-\d{4}-\d{4}-\d{3}$")
    if cr["cr_number"] and _generic_pattern.match(cr["cr_number"]):
        # Extract a meaningful slug from the filename, e.g.
        # "cr-2026-0131-azure-tag-sync.md" -> "AZURE-TAG-SYNC"
        slug_match = re.match(r"cr-\d{4}-\d{4}-(.+)\.md$", filename, re.IGNORECASE)
        if slug_match:
            slug = slug_match.group(1).upper()
            # Reconstruct as e.g. CR-2026-0131-AZURE-TAG-SYNC
            base = cr["cr_number"].rsplit("-", 1)[0]  # "CR-2026-0131"
            cr["cr_number"] = f"{base}-{slug}"

    # ── Use title from CR number if still missing ──────────────────────
    if not cr["title"] and cr["cr_number"]:
        cr["title"] = cr["cr_number"]

    # ── Extract Summary section ────────────────────────────────────────
    cr["summary"] = _extract_section(text, "Summary")
    if not cr["summary"]:
        # Try "Change Description" > "Problem Statement" or "Solution"
        cr["summary"] = _extract_section(text, "1.1 Problem Statement")
        if not cr["summary"]:
            cr["summary"] = _extract_section(text, "Change Description")

    # ── Build full HTML description ────────────────────────────────────
    cr["description_html"] = _markdown_to_simple_html(text)

    # ── Extract affected servers ───────────────────────────────────────
    cr["affected_servers"] = _extract_server_names(text)

    # ── Extract rollback procedure (Backout Plan) ───────────────────────
    cr["rollback_procedure"] = _extract_section(text, "Rollback")
    if not cr["rollback_procedure"]:
        cr["rollback_procedure"] = _extract_section(text, "Backout")

    # ── Extract implementation plan (Rollout Plan) ─────────────────────
    cr["implementation_plan"] = _extract_section(text, "Implementation")
    if not cr["implementation_plan"]:
        cr["implementation_plan"] = _extract_section(text, "Remediation")
    if not cr["implementation_plan"]:
        cr["implementation_plan"] = _extract_section(text, "Rollout")

    # ── Extract reason for change ──────────────────────────────────────
    cr["reason_for_change"] = _extract_section(text, "Problem")
    if not cr["reason_for_change"]:
        cr["reason_for_change"] = _extract_section(text, "Problem Statement")
    if not cr["reason_for_change"]:
        cr["reason_for_change"] = _extract_section(text, "Change Description")
    if not cr["reason_for_change"]:
        cr["reason_for_change"] = cr["summary"]

    # ── Extract impact / risk assessment ───────────────────────────────
    cr["impact_analysis"] = _extract_section(text, "Risk Assessment")
    if not cr["impact_analysis"]:
        cr["impact_analysis"] = _extract_section(text, "Impact")
    if not cr["impact_analysis"]:
        cr["impact_analysis"] = _extract_section(text, "Risk")

    return cr


def _extract_section(text: str, heading_keyword: str) -> str:
    """Extract text under a heading that contains the keyword."""
    pattern = re.compile(
        rf"^(#{{2,4}})\s+.*{re.escape(heading_keyword)}.*$",
        re.MULTILINE | re.IGNORECASE
    )
    m = pattern.search(text)
    if not m:
        return ""
    level = len(m.group(1))  # number of # characters
    start = m.end()
    # Find next heading at same or higher level
    next_heading = re.compile(rf"^#{{{1},{level}}}\s+", re.MULTILINE)
    m2 = next_heading.search(text, start)
    end = m2.start() if m2 else len(text)
    return text[start:end].strip()


def _extract_server_names(text: str) -> list:
    """Extract server hostnames (is01sNNN, az01sNNN patterns) from text."""
    pattern = re.compile(r'\b([ia][sz]01s\d{3})\b', re.IGNORECASE)
    servers = sorted(set(pattern.findall(text.lower())))
    return servers


def _inline_markdown(text: str) -> str:
    """Convert inline markdown (bold, italic, code, links) to HTML."""
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic: *text* or _text_ (but not inside bold)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    # Inline code: `text`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    # Checkboxes
    text = text.replace("[ ]", "&#9744;").replace("[x]", "&#9745;").replace("[X]", "&#9745;")
    return text


def _markdown_table_to_html(lines: list) -> str:
    """Convert a block of markdown table lines to an HTML table."""
    html = ['<table border="1" cellpadding="6" cellspacing="0" '
            'style="border-collapse:collapse; margin:8px 0;">']
    is_header = True
    for line in lines:
        # Skip separator rows (|---|---|)
        stripped = line.strip().strip("|")
        if re.match(r'^[\s\-:|]+$', stripped):
            is_header = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        tag = "th" if is_header else "td"
        row_html = "".join(f"<{tag}>{_inline_markdown(c)}</{tag}>" for c in cells)
        html.append(f"<tr>{row_html}</tr>")
        if is_header and len(lines) > 1:
            # After first row, check if next is separator
            pass
    html.append("</table>")
    return "\n".join(html)


def _markdown_to_simple_html(md_text: str) -> str:
    """Convert markdown to clean HTML for Freshservice description field."""
    html_lines = []
    in_code_block = False
    in_table = False
    table_lines = []
    in_list = False
    list_type = None  # "ul" or "ol"

    for line in md_text.split("\n"):
        # ── Code blocks ────────────────────────────────────────────
        if line.startswith("```"):
            # Flush table if pending
            if in_table:
                html_lines.append(_markdown_table_to_html(table_lines))
                table_lines = []
                in_table = False
            # Flush list if pending
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            if in_code_block:
                html_lines.append("</pre></code>")
                in_code_block = False
            else:
                lang = line.lstrip("`").strip()
                html_lines.append(f"<code><pre>")
                in_code_block = True
            continue
        if in_code_block:
            html_lines.append(line)
            continue

        # ── Tables ─────────────────────────────────────────────────
        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            in_table = True
            table_lines.append(line)
            continue
        elif in_table:
            html_lines.append(_markdown_table_to_html(table_lines))
            table_lines = []
            in_table = False

        # ── Headings ───────────────────────────────────────────────
        if line.startswith("#"):
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            level = len(re.match(r'^#+', line).group())
            content = _inline_markdown(line.lstrip("#").strip())
            html_lines.append(f"<h{level}>{content}</h{level}>")
            continue

        # ── Horizontal rule ────────────────────────────────────────
        if line.strip() == "---" or line.strip() == "***":
            if in_list:
                html_lines.append(f"</{list_type}>")
                in_list = False
            html_lines.append("<hr/>")
            continue

        # ── Unordered list items ───────────────────────────────────
        if re.match(r'^(\s*)[-*]\s+', line):
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            content = re.sub(r'^(\s*)[-*]\s+', '', line)
            html_lines.append(f"<li>{_inline_markdown(content)}</li>")
            continue

        # ── Ordered list items ─────────────────────────────────────
        if re.match(r'^\s*\d+\.\s+', line):
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(f"</{list_type}>")
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            content = re.sub(r'^\s*\d+\.\s+', '', line)
            html_lines.append(f"<li>{_inline_markdown(content)}</li>")
            continue

        # ── End list on non-list line ──────────────────────────────
        if in_list and line.strip():
            html_lines.append(f"</{list_type}>")
            in_list = False

        # ── Regular text / blank lines ─────────────────────────────
        if line.strip():
            html_lines.append(f"<p>{_inline_markdown(line)}</p>")
        else:
            if in_list:
                # Blank lines inside lists are OK
                continue

    # Flush any remaining state
    if in_code_block:
        html_lines.append("</pre></code>")
    if in_table:
        html_lines.append(_markdown_table_to_html(table_lines))
    if in_list:
        html_lines.append(f"</{list_type}>")

    return "\n".join(html_lines)


# ── Freshservice Field Mapping ─────────────────────────────────────────

STATUS_MAP = {
    # Local status -> Freshservice change status integer
    "planned": 2,           # Planning
    "pending approval": 3,  # Awaiting Approval
    "pending review": 5,    # Pending Review
    "completed": 6,         # Closed
    "implemented": 6,       # Closed
    "implemented - production": 6,  # Closed
    "closed": 6,            # Closed
    "open": 1,              # Open
    "in progress": 2,       # Planning (active work)
}

PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
}

RISK_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "very high": 4,
}

CHANGE_TYPE_MAP = {
    "minor": 1,
    "standard": 2,
    "standard change": 2,
    "major": 3,
    "emergency": 4,
}


def to_freshservice_change(cr: dict, requester_id: int = 7000348606,
                            department_id: int = 7000161748) -> dict:
    """Convert a parsed CR dict to Freshservice Change API payload."""
    # Normalize status: strip markdown bold markers, extra text
    status_raw = cr["status"].lower().strip().strip("*").strip()
    # Try exact match first, then try prefix matching
    fs_status = STATUS_MAP.get(status_raw)
    if fs_status is None:
        # Try matching just the first key words
        for key, val in STATUS_MAP.items():
            if status_raw.startswith(key) or key in status_raw:
                fs_status = val
                break
    if fs_status is None:
        fs_status = 2  # Default to Planning

    priority_key = cr["priority"].lower().strip()
    fs_priority = PRIORITY_MAP.get(priority_key, 2)  # Default Medium

    risk_key = cr["risk_level"].lower().strip()
    fs_risk = RISK_MAP.get(risk_key)
    if fs_risk is None:
        # Handle compound values like "Low-Medium" -> take the higher
        if "medium" in risk_key:
            fs_risk = 2
        elif "high" in risk_key:
            fs_risk = 3
        else:
            fs_risk = 1  # Default Low

    type_key = cr["change_type"].lower().strip()
    fs_type = CHANGE_TYPE_MAP.get(type_key, 2)  # Default Standard

    # Build subject
    subject = cr["title"]
    if cr["cr_number"] and cr["cr_number"] not in subject:
        subject = f"[{cr['cr_number']}] {subject}"

    # Parse date for planned dates
    planned_start = None
    planned_end = None
    if cr["date"]:
        try:
            dt = datetime.strptime(cr["date"], "%Y-%m-%d")
            planned_start = dt.strftime("%Y-%m-%dT08:00:00Z")
            planned_end = dt.strftime("%Y-%m-%dT17:00:00Z")
        except ValueError:
            pass
    if cr["completed_date"]:
        try:
            dt = datetime.strptime(cr["completed_date"], "%Y-%m-%d")
            planned_end = dt.strftime("%Y-%m-%dT17:00:00Z")
        except ValueError:
            pass

    # Map impact from risk (Low->1, Medium->2, High->3)
    fs_impact = min(fs_risk, 3)  # impact only goes to 3

    payload = {
        "subject": subject,
        "description": cr["description_html"],
        "status": fs_status,
        "priority": fs_priority,
        "impact": fs_impact,
        "risk": fs_risk,
        "change_type": fs_type,
        "requester_id": requester_id,
        "department_id": department_id,
    }

    if planned_start:
        payload["planned_start_date"] = planned_start
    if planned_end:
        payload["planned_end_date"] = planned_end

    return payload


def parse_all_crs(docs_dir: str = None) -> list:
    """Parse all CR markdown files from the docs directory."""
    if docs_dir is None:
        docs_dir = str(Path(__file__).resolve().parents[2] / "docs" / "cr")

    cr_files = sorted(Path(docs_dir).glob("cr-*.md"))
    results = []
    for f in cr_files:
        try:
            cr = parse_cr_file(str(f))
            results.append(cr)
        except Exception as e:
            print(f"  Error parsing {f.name}: {e}")
    return results


if __name__ == "__main__":
    """Quick test: parse all CRs and print summary."""
    crs = parse_all_crs()
    print(f"Parsed {len(crs)} change requests:\n")
    for cr in crs:
        servers = ", ".join(cr["affected_servers"][:5])
        if len(cr["affected_servers"]) > 5:
            servers += f" (+{len(cr['affected_servers']) - 5} more)"
        print(f"  {cr['cr_number']}")
        print(f"    Title:    {cr['title'][:70]}")
        print(f"    Status:   {cr['status']} -> FS status {STATUS_MAP.get(cr['status'].lower().strip(), '?')}")
        print(f"    Priority: {cr['priority']} -> FS priority {PRIORITY_MAP.get(cr['priority'].lower().strip(), '?')}")
        print(f"    Risk:     {cr['risk_level']} -> FS risk {RISK_MAP.get(cr['risk_level'].lower().strip(), '?')}")
        print(f"    Date:     {cr['date']}")
        print(f"    Servers:  {servers or '(none detected)'}")
        print()
