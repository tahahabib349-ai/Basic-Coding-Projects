"""PDF reading: text, page numbers, headings, clause references and tables."""

from __future__ import annotations

import io
import re

from ..config import settings
from ..errors import CorruptFileError, EmptyDocumentError, PasswordProtectedError
from .models import PdfPage, SourceDocument

# A line that looks like a heading: "12. Events of Default", "12.3 Cure Period",
# "ARTICLE 5", "SCHEDULE 2 – Conditions Precedent", or a short ALL-CAPS line.
_NUMBERED_HEADING = re.compile(
    r"^\s*((ARTICLE|Article|SECTION|Section|CLAUSE|Clause|SCHEDULE|Schedule|PART|Part|ANNEX|Annex)\s+[\dIVXA-Z]+"
    r"|\d{1,2}(\.\d{1,2}){0,3}\.?\s+[A-Z])"
)
_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 &,/\-–:()']{3,80}$")
_CLAUSE_REF = re.compile(
    r"\b(?:Clause|Section|Article|Schedule|Paragraph|Annex)\s+\d+(?:\.\d+)*(?:\s*\([a-z0-9ivx]+\))*",
    re.IGNORECASE,
)
_LEADING_NUMBER = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){1,3})\s+\S")


def _detect_headings(text: str) -> list[str]:
    headings = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) > 90:
            continue
        if _NUMBERED_HEADING.match(s) or (_CAPS_HEADING.match(s) and len(s.split()) >= 2):
            # Exclude lines that are clearly sentences or table rows of numbers.
            if s.endswith(".") and len(s.split()) > 8:
                continue
            if sum(ch.isdigit() for ch in s) > len(s) * 0.4:
                continue
            headings.append(s)
    return headings[:25]


def _font_headings(page) -> list[str]:
    """Headings detected from typography: lines in a larger or bold font
    (outside tables) compared with the page's normal body text."""
    try:
        words = page.extract_words(extra_attrs=["size", "fontname"], use_text_flow=True)
    except Exception:
        return []
    if not words:
        return []
    try:
        table_boxes = [t.bbox for t in page.find_tables()]
    except Exception:
        table_boxes = []

    def in_table(w) -> bool:
        return any(x0 - 1 <= w["x0"] and w["x1"] <= x1 + 1 and top - 1 <= w["top"] and w["bottom"] <= bottom + 1
                   for x0, top, x1, bottom in table_boxes)

    sizes = sorted(w["size"] for w in words)
    body = sizes[len(sizes) // 2]
    lines: dict[int, list] = {}
    for w in words:
        if not in_table(w):
            lines.setdefault(round(w["top"] / 3), []).append(w)
    out = []
    for key in sorted(lines):
        ws = lines[key]
        text = " ".join(w["text"] for w in ws).strip()
        if not text or len(text) > 90 or len(ws) > 12:
            continue
        size = max(w["size"] for w in ws)
        bold = all("bold" in str(w["fontname"]).lower() for w in ws)
        if size >= body * 1.15 or bold:
            out.append(text)
    return out


def _detect_clause_refs(text: str) -> list[str]:
    refs = {m.group(0).strip() for m in _CLAUSE_REF.finditer(text)}
    for line in text.splitlines():
        m = _LEADING_NUMBER.match(line)
        if m:
            refs.add(m.group(1))
    return sorted(refs)[:60]


def _clean_table(table: list[list]) -> list[list[str]]:
    rows = []
    for row in table or []:
        cells = [" ".join(str(c).split()) if c is not None else "" for c in row]
        if any(cells):
            rows.append(cells)
    return rows


def read_pdf(filename: str, data: bytes) -> SourceDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    doc = SourceDocument(filename=filename, kind="pdf", size_bytes=len(data))

    # 1) Validate the file and handle encryption with pypdf.
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        password = None
        if reader.is_encrypted:
            # Many "protected" PDFs only restrict printing/copying and open with
            # an empty password. Truly password-locked files cannot be read.
            try:
                ok = reader.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise PasswordProtectedError(
                    f"'{filename}' is password-protected. Please upload an unlocked copy."
                )
            password = ""
        n_pages = len(reader.pages)
    except PasswordProtectedError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise CorruptFileError(
            f"'{filename}' could not be opened. It appears to be damaged or is not a valid PDF.",
            detail=type(exc).__name__,
        ) from None
    except Exception as exc:
        if "password" in str(exc).lower() or "decrypt" in str(exc).lower():
            raise PasswordProtectedError(
                f"'{filename}' is password-protected. Please upload an unlocked copy."
            ) from None
        raise CorruptFileError(
            f"'{filename}' could not be opened. It appears to be damaged or is not a valid PDF.",
            detail=type(exc).__name__,
        ) from None

    if n_pages == 0:
        raise EmptyDocumentError(f"'{filename}' contains no pages.")

    limit = settings.max_pdf_pages
    if n_pages > limit:
        doc.warnings.append(
            f"Document has {n_pages} pages; only the first {limit} were read (prototype limit)."
        )

    # 2) Extract text and tables page by page with pdfplumber (better layout
    #    handling); fall back to pypdf text if pdfplumber fails on a page.
    import pdfplumber

    blank_pages: list[int] = []
    try:
        pdf = pdfplumber.open(io.BytesIO(data), password=password)
    except Exception:
        pdf = None
    try:
        for i in range(min(n_pages, limit)):
            text, tables, font_heads = "", [], []
            try:
                if pdf is None:
                    raise RuntimeError
                page = pdf.pages[i]
                text = page.extract_text() or ""
                tables = [_clean_table(t) for t in page.extract_tables()]
                tables = [t for t in tables if len(t) >= 2]
                font_heads = _font_headings(page)
            except Exception:
                try:
                    text = reader.pages[i].extract_text() or ""
                except Exception:
                    text = ""
            text = text.replace("\x00", "").strip()
            if len(text) < 15:
                blank_pages.append(i + 1)
            doc.pages.append(
                PdfPage(
                    number=i + 1,
                    text=text,
                    headings=list(dict.fromkeys(font_heads + _detect_headings(text)))[:25],
                    clause_refs=_detect_clause_refs(text),
                    tables=tables,
                )
            )
    finally:
        if pdf is not None:
            pdf.close()

    if len(blank_pages) == len(doc.pages):
        raise EmptyDocumentError(
            f"No readable text was found in '{filename}'. It may be a scanned image; "
            "this prototype does not yet perform OCR (text recognition on images)."
        )
    if blank_pages:
        shown = ", ".join(map(str, blank_pages[:15])) + ("…" if len(blank_pages) > 15 else "")
        doc.warnings.append(
            f"No readable text on page(s) {shown} (possibly scanned images or charts); "
            "their content was not analysed."
        )
    return doc
