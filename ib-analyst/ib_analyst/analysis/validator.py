"""Checks the AI's answer against the uploaded material and the calculator.

This is the hallucination-control layer. It never rewrites what the AI said;
it attaches visible warning flags to anything it cannot verify, so the reader
knows exactly which statements need checking.
"""

from __future__ import annotations

import re

from ..calculations.metrics import CalculationResults
from ..ingestion.models import SourceDocument
from ..prompts.common import MISSING_TEXT
from ..prompts.modes import AnalysisMode
from .schema import LABELS, RISKS, Issue, Point, Section

_NUM_RE = re.compile(r"(?<![A-Za-z\d])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{3,})(?![\d])")
_PAGE_RE = re.compile(r"\b(?:p|pp|pg|page)\.?\s*(\d{1,4})", re.I)
_CELL_RE = re.compile(r"(?:'([^']+)'|([A-Za-z0-9 _&\-().]+?))\s*!\s*\$?([A-Z]{1,3})\$?(\d{1,7})")
_CLAUSE_RE = re.compile(r"\b(?:clause|section|article|para(?:graph)?)\s+(\d+(?:\.\d+)*)", re.I)
_YEARS = re.compile(r"^(19|20)\d{2}$")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _numbers(text: str) -> list[str]:
    out = []
    for m in _NUM_RE.findall(text):
        if _YEARS.match(m):
            continue  # years are rarely the point of a figure check
        out.append(m)
    return out


def _num_variants(token: str) -> set[str]:
    """Textual forms a printed number may take in a source ("18,000" -> "18000")."""
    t = token.replace(",", "")
    v = {t}
    if "." in t:
        v.add(t.rstrip("0").rstrip("."))
    return v


def _to_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def _matches_value(token: str, values: list[float]) -> bool:
    """True if a stated number equals one of `values` at the precision it is stated."""
    x = _to_float(token)
    if x is None:
        return False
    decimals = len(token.split(".")[1]) if "." in token else 0
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    return any(abs(v - x) <= tol for v in values)


class SourceIndex:
    def __init__(self, docs: list[SourceDocument]):
        self.docs = docs
        self.by_norm = {}
        for d in docs:
            self.by_norm[_norm(d.filename)] = d
            stem = d.filename.rsplit(".", 1)[0]
            self.by_norm[_norm(stem)] = d

    def find_docs(self, source: str) -> list[SourceDocument]:
        ns = _norm(source)
        found = []
        for key, d in sorted(self.by_norm.items(), key=lambda kv: -len(kv[0])):
            if key and key in ns and d not in found:
                found.append(d)
        return found

    @staticmethod
    def pdf_text(doc: SourceDocument, page: int | None) -> str:
        pages = [doc.page(page)] if page else doc.pages
        txt = " ".join((p.text + " " + " ".join(" ".join(r) for t in p.tables for r in t)) for p in pages if p)
        return re.sub(r"(?<=\d),(?=\d{3})", "", txt).lower()  # drop thousand separators

    @staticmethod
    def excel_numbers(doc: SourceDocument, sheet: str | None) -> list[float]:
        nums: list[float] = []
        wb = doc.workbook
        if not wb:
            return nums
        for s in wb.sheets:
            if sheet and s.name.lower() != sheet.lower():
                continue
            for r in s.rows:
                for _, v in r.numeric_values():
                    nums += [v, v * 100]  # v*100: fractions are usually quoted as percentages
        return nums

    @staticmethod
    def clause_on_page(doc: SourceDocument, page: int, clause: str) -> bool:
        p = doc.page(page)
        if not p:
            return False
        if clause in p.clause_refs or any(r.endswith(" " + clause) for r in p.clause_refs):
            return True
        return bool(re.search(r"(?<![\d.])" + re.escape(clause) + r"(?![\d])", p.text))


def _split_sources(source: str) -> list[str]:
    return [s.strip() for s in re.split(r";|\n| and (?=[A-Z])", source) if s.strip()]


def check_source(source: str, idx: SourceIndex, statement: str, label: str,
                 calc_numbers: list[float], check_numbers: bool) -> list[str]:
    flags: list[str] = []
    parts = _split_sources(source)
    if not parts:
        if label in ("FACT", "CALCULATED"):
            flags.append(f"No source given for a {label} statement.")
        return flags

    numbers = _numbers(statement) if check_numbers else []
    found_numbers: set[str] = set()
    any_doc = False
    for part in parts:
        if part.lower().startswith("calculated"):
            for n in numbers:
                if _matches_value(n, calc_numbers):
                    found_numbers.add(n)
            continue
        docs = idx.find_docs(part)
        if not docs:
            if label == "FACT" or re.search(r"\.(pdf|xlsx|xlsm)", part, re.I):
                flags.append(f"Cited source '{part[:80]}' does not match any uploaded file.")
            continue
        any_doc = True
        doc = docs[0]
        if doc.kind == "pdf":
            pm = _PAGE_RE.search(part)
            page = int(pm.group(1)) if pm else None
            if page is not None and doc.page(page) is None:
                flags.append(f"Cited page {page} does not exist in {doc.filename} ({len(doc.pages)} pages).")
                page = None
            text = idx.pdf_text(doc, page)
            for cm in _CLAUSE_RE.finditer(part):
                clause = cm.group(1)
                if page and not idx.clause_on_page(doc, page, clause):
                    flags.append(f"Clause {clause} not found on {doc.filename} p.{page}.")
            for n in numbers:
                if any(re.search(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", text) for v in _num_variants(n)):
                    found_numbers.add(n)
        else:
            cm = _CELL_RE.search(part.split("›")[-1])
            sheet = (cm.group(1) or cm.group(2)).strip() if cm else None
            if sheet and doc.workbook and not doc.workbook.sheet(sheet):
                flags.append(f"Cited sheet '{sheet}' does not exist in {doc.filename}.")
                sheet = None
            nums = idx.excel_numbers(doc, sheet)
            for n in numbers:
                if _matches_value(n, nums):
                    found_numbers.add(n)

    if check_numbers and numbers and (any_doc or label == "CALCULATED"):
        missing = [n for n in numbers if n not in found_numbers]
        if missing:
            where = "the application's calculations" if label == "CALCULATED" else "the cited source"
            flags.append(f"Figure(s) {', '.join(missing[:4])} could not be matched in {where}; verify.")
    return flags


def calc_number_set(calc: CalculationResults) -> list[float]:
    """Every number the calculator produced (and the inputs it used)."""
    nums: list[float] = []
    for m in calc.metrics:
        if m.value is not None:
            nums.append(m.value * 100 if m.unit == "%" else m.value)
        nums += [f.value for f in m.inputs]
    for row in calc.period_table:
        for k, v in row.items():
            if isinstance(v, (int, float)):
                nums.append(v * 100 if "margin" in k else v)
    return nums


def _heading_key(h: str) -> str:
    return _norm(h.replace("&", "and"))


def validate_report(data: dict, mode: AnalysisMode, docs: list[SourceDocument],
                    calc: CalculationResults) -> tuple[str, list[Section], list[Issue]]:
    idx = SourceIndex(docs)
    calc_numbers = calc_number_set(calc)
    title = str(data.get("report_title") or mode.title).strip()

    raw_sections = data.get("sections") or []
    by_key: dict[str, dict] = {}
    extras: list[dict] = []
    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        key = _heading_key(str(s.get("heading", "")))
        match = next((h for h in mode.sections if _heading_key(h) == key), None)
        if match and match not in by_key:
            by_key[match] = s
        else:
            extras.append(s)

    sections: list[Section] = []
    for heading in list(mode.sections) + [str(e.get("heading", "Additional")) for e in extras]:
        raw = by_key.get(heading) or next((e for e in extras if str(e.get("heading")) == heading), None)
        sec = Section(heading=heading)
        if raw is None:
            sec.points.append(Point(statement=MISSING_TEXT, label="MISSING"))
            sec.flags.append("The AI did not address this section.")
            sections.append(sec)
            continue
        sec.commentary = str(raw.get("commentary") or "").strip()
        tbl = raw.get("table")
        if isinstance(tbl, dict) and tbl.get("columns") and tbl.get("rows"):
            sec.table = {"columns": [str(c) for c in tbl["columns"]],
                         "rows": [[str(c) for c in r] for r in tbl["rows"] if isinstance(r, list)]}
        for p in raw.get("points") or []:
            if not isinstance(p, dict):
                continue
            label = str(p.get("label", "")).upper().strip()
            stmt = str(p.get("statement", "")).strip()
            src = str(p.get("source", "") or "").strip()
            if not stmt:
                continue
            point = Point(statement=stmt, label=label if label in LABELS else "INFERENCE", source=src)
            if label not in LABELS:
                point.flags.append(f"AI used an invalid label '{label}'; shown as INFERENCE.")
            if point.label == "MISSING" and "not identified in the provided materials" not in stmt.lower():
                point.statement = f"{MISSING_TEXT} {stmt}"
            if point.label in ("FACT", "CALCULATED"):
                point.flags += check_source(src, idx, stmt, point.label, calc_numbers, check_numbers=True)
            elif src and point.label == "INFERENCE":
                point.flags += [f for f in check_source(src, idx, stmt, "INFERENCE", calc_numbers, False)]
            sec.points.append(point)
        if not sec.points and not sec.commentary:
            sec.points.append(Point(statement=MISSING_TEXT, label="MISSING"))
        sections.append(sec)

    issues: list[Issue] = []
    for it in data.get("issues") or []:
        if not isinstance(it, dict):
            continue
        risk = str(it.get("risk", "Medium")).capitalize()
        label = str(it.get("label", "INFERENCE")).upper()
        issue = Issue(
            issue=str(it.get("issue", "")).strip(),
            source=str(it.get("source", "")).strip(),
            why_it_matters=str(it.get("why_it_matters", "")).strip(),
            risk=risk if risk in RISKS else "Medium",
            recommended_comment=str(it.get("recommended_comment", "")).strip(),
            label=label if label in LABELS else "INFERENCE",
        )
        if issue.source:
            issue.flags += check_source(issue.source, idx, "", issue.label, calc_numbers, check_numbers=False)
        if issue.issue:
            issues.append(issue)
    order = {"High": 0, "Medium": 1, "Low": 2}
    issues.sort(key=lambda i: order.get(i.risk, 1))
    return title, sections, issues
