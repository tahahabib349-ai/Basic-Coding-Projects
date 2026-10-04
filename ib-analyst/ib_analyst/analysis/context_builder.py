"""Builds the material sent to the AI, within a size budget.

Every piece of content carries a source marker ([file p.N] or [file › Sheet!Cell])
so the AI can cite it and the application can verify those citations. When the
material is too large, the most relevant pages/rows for the chosen mode are kept
and the omissions are reported to the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..calculations.metrics import CalculationResults, fmt
from ..ingestion.models import ModelIssue, PdfPage, RowInfo, SheetInfo, SourceDocument
from ..prompts.modes import AnalysisMode

MAX_PERIODS_PER_ROW = 15
MAX_ROWS_PER_SHEET = 250


@dataclass
class BuiltContext:
    text: str
    notes: list[str] = field(default_factory=list)  # what was omitted, shown to user


def _fmt_value(v) -> str:
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, (int, float)):
        if abs(v) < 1 and v != 0:
            return f"{v:.4g}"
        return f"{v:,.2f}".rstrip("0").rstrip(".") if not float(v).is_integer() else f"{int(v):,}"
    return str(v)[:40]


def table_to_text(table: list[list[str]]) -> str:
    return "\n".join(" | ".join(c for c in row) for row in table)


def page_text(doc: SourceDocument, page: PdfPage) -> str:
    out = [f"--- [{doc.filename} p.{page.number}] ---"]
    if page.headings:
        out.append("Headings on page: " + " ; ".join(page.headings[:10]))
    out.append(page.text)
    for i, t in enumerate(page.tables, 1):
        out.append(f"[Table {i} on {doc.filename} p.{page.number}]\n{table_to_text(t)}")
    return "\n".join(out)


def _row_text(doc: SourceDocument, sheet: SheetInfo, row: RowInfo) -> str:
    period_by_col = dict(sheet.period_header)
    unit = f" [{row.unit}]" if row.unit else ""
    kind = {"input": "HARD-CODED INPUT", "formula": "FORMULA", "mixed": "MIXED (inputs+formulas)"}.get(row.kind, row.kind)
    vals = []
    cells = row.cells
    if len(cells) > MAX_PERIODS_PER_ROW:
        cells = cells[: MAX_PERIODS_PER_ROW - 3] + cells[-3:]
    for c in cells:
        col = re.sub(r"\d", "", c.ref)
        tag = period_by_col.get(col, c.ref)
        marker = "" if c.is_formula or row.kind == "input" else "*"  # * = hard-code in a formula row
        vals.append(f"{tag}={_fmt_value(c.value)}{marker}")
    first_formula = next((c for c in row.cells if c.is_formula), None)
    formula = f" | e.g. {first_formula.ref}: {first_formula.formula[:120]}" if first_formula else ""
    first_ref = row.cells[0].ref if row.cells else f"A{row.row}"
    more = f" (+{len(row.cells) - len(cells)} more)" if len(row.cells) > len(cells) else ""
    return f"[{sheet.name}!{first_ref}] {row.label}{unit} | {kind}{formula} | {', '.join(vals)}{more}"


def workbook_text(doc: SourceDocument, max_rows: int = MAX_ROWS_PER_SHEET) -> str:
    wb = doc.workbook
    assert wb is not None
    out = [f"=== WORKBOOK: {doc.filename} ({len(wb.sheets)} sheets) ===",
           f"Cite cells as \"{doc.filename} › <Sheet>!<Cell>\".",
           "WORKBOOK STRUCTURE:"]
    for s in wb.sheets:
        periods = f"{s.period_header[0][1]}–{s.period_header[-1][1]} ({len(s.period_header)} periods, columns " \
                  f"{s.period_header[0][0]}–{s.period_header[-1][0]})" if s.period_header else "no timeline"
        out.append(
            f"- Sheet '{s.name}'{' (HIDDEN)' if s.hidden else ''}: role={s.role} ({s.role_reason}); used range "
            f"{s.dimensions}; {s.n_formulas} formulas, {s.n_numeric_inputs} hard-coded numbers; timeline: {periods}; "
            f"units: {', '.join(s.units) or 'not stated'}; draws from: {', '.join(s.referenced_sheets) or 'none'}"
        )
    if wb.defined_names:
        out.append("Named ranges: " + "; ".join(f"{k}={v}" for k, v in list(wb.defined_names.items())[:30]))
    if not wb.has_cached_values:
        out.append("NOTE: formula results were not saved in this file; many calculated values are missing.")
    out.append("\nROW DETAIL (format: [Sheet!first cell] label [unit] | type | sample formula | period=value; "
               "'*' marks a hard-coded number inside a formula row):")
    for s in wb.sheets:
        if not s.rows:
            continue
        out.append(f"\n## Sheet '{s.name}' ({s.role})")
        rows = s.rows[:max_rows]
        for r in rows:
            out.append(_row_text(doc, s, r))
        if len(s.rows) > len(rows):
            out.append(f"... {len(s.rows) - len(rows)} further rows omitted for size")
    return "\n".join(out)


def model_issues_text(issues: list[ModelIssue]) -> str:
    if not issues:
        return "AUTOMATED MODEL CHECKS: no structural issues detected by the application."
    lines = ["AUTOMATED MODEL CHECKS (found by the application's code, not by AI):"]
    for i in issues[:80]:
        lines.append(f"- [{i.severity}] {i.category} at {i.location}: {i.detail}")
    if len(issues) > 80:
        lines.append(f"... and {len(issues) - 80} more")
    return "\n".join(lines)


def calculations_text(calc: CalculationResults) -> str:
    lines = ["CALCULATED METRICS (computed deterministically by the application; cite as "
             "\"Calculated: <metric name>\"; units as in source):"]
    if calc.is_empty:
        lines.append("- None: insufficient source data was identified for calculations.")
    for m in calc.metrics:
        period = f" ({m.period})" if m.period else ""
        lines.append(f"- {m.name}{period} = {m.display} | formula: {m.formula} | inputs: {m.sources or 'see period table'}")
    if calc.period_table:
        cols = [c for c in calc.period_table[0] if c != "Period"]
        lines.append("\nPER-PERIOD CALCULATIONS (Period | " + " | ".join(cols) + ")")
        for row in calc.period_table[:40]:
            vals = []
            for c in cols:
                v = row[c]
                unit = "x" if c in ("Debt / EBITDA", "Interest cover", "DSCR (calc.)") else "%" if "margin" in c else "amount"
                vals.append(fmt(v, unit))
            lines.append(f"{row['Period']} | " + " | ".join(vals))
    if calc.checks:
        lines.append("\nINTEGRITY AND CONSISTENCY CHECKS:")
        for c in calc.checks:
            status = "PASS" if c.passed else "FAIL" if c.passed is False else "N/A"
            lines.append(f"- {status}: {c.name}: {c.detail}")
    if calc.missing:
        lines.append("\nNOT CALCULABLE:")
        lines.extend(f"- {m}" for m in calc.missing)
    if calc.figures.unverified:
        lines.append("\nFIGURES REJECTED (quoted figure not found on cited page; do not rely on them):")
        for f in calc.figures.unverified[:20]:
            lines.append(f"- {f.item} {f.period} {f.value} claimed at {f.source}")
    return "\n".join(lines)


def _page_score(page: PdfPage, mode: AnalysisMode) -> float:
    t = page.text.lower()
    score = sum(t.count(k) for k in mode.keywords)
    score += 3 * sum(1 for h in page.headings for k in mode.keywords if k in h.lower())
    score += 2 * len(page.tables)
    return score / (1 + len(t) / 4000)


def build_pdf_context(docs: list[SourceDocument], mode: AnalysisMode, budget: int) -> BuiltContext:
    """Include all pages if they fit; otherwise the highest-scoring pages."""
    pdfs = [d for d in docs if d.kind == "pdf"]
    blocks = {(d.filename, p.number): page_text(d, p) for d in pdfs for p in d.pages}
    total = sum(len(b) for b in blocks.values())
    notes: list[str] = []
    if total <= budget:
        chosen = set(blocks)
    else:
        ranked = []
        for d in pdfs:
            for p in d.pages:
                bonus = 100 if p.number <= 2 else 0  # cover/summary pages are usually informative
                ranked.append((bonus + _page_score(p, mode), d.filename, p.number))
        ranked.sort(reverse=True)
        chosen, used = set(), 0
        for _, f, n in ranked:
            size = len(blocks[(f, n)])
            if used + size <= budget:
                chosen.add((f, n))
                used += size
        for d in pdfs:
            omitted = [p.number for p in d.pages if (d.filename, p.number) not in chosen]
            if omitted:
                notes.append(f"{d.filename}: {len(omitted)} of {len(d.pages)} pages not sent to the AI due to size "
                             f"(least relevant for this mode), e.g. pages {_ranges(omitted)}.")
    out = []
    for d in pdfs:
        out.append(f"=== DOCUMENT: {d.filename} (PDF, {len(d.pages)} pages) ===")
        for p in d.pages:
            if (d.filename, p.number) in chosen:
                out.append(blocks[(d.filename, p.number)])
    return BuiltContext("\n".join(out), notes)


def _ranges(nums: list[int]) -> str:
    nums = sorted(nums)
    parts, start, prev = [], nums[0], nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        if n is not None:
            start = prev = n
    return ", ".join(parts[:12]) + ("…" if len(parts) > 12 else "")


def build_context(docs: list[SourceDocument], mode: AnalysisMode, calc: CalculationResults,
                  model_issues: list[ModelIssue], budget: int) -> BuiltContext:
    notes: list[str] = []
    inventory = ["UPLOADED MATERIAL:"]
    for d in docs:
        inventory.append(f"- {d.filename} ({'PDF' if d.kind == 'pdf' else 'Excel'}, {d.summary})")
    head = "\n".join(inventory)
    calc_block = calculations_text(calc)
    issues_block = model_issues_text(model_issues) if any(d.kind == "excel" for d in docs) else ""

    # Workbooks: shrink rows per sheet until they fit within ~60% of the budget
    # (more for model review), leaving room for documents.
    wb_share = 0.75 if mode.key == "financial_model_review" else 0.45
    has_pdf = any(d.kind == "pdf" for d in docs)
    wb_budget = int(budget * (wb_share if has_pdf else 0.95))
    wb_texts = []
    for d in [d for d in docs if d.kind == "excel"]:
        rows = MAX_ROWS_PER_SHEET
        text = workbook_text(d, rows)
        while len(text) > wb_budget / max(1, sum(1 for x in docs if x.kind == "excel")) and rows > 20:
            rows = int(rows * 0.6)
            text = workbook_text(d, rows)
        if rows < MAX_ROWS_PER_SHEET and any(len(s.rows) > rows for s in d.workbook.sheets):
            notes.append(f"{d.filename}: large workbook – only the first {rows} labelled rows per sheet were sent "
                         "to the AI (all rows were used for automated checks and calculations).")
        wb_texts.append(text)
    used = len(head) + len(calc_block) + len(issues_block) + sum(len(t) for t in wb_texts)
    pdf_ctx = build_pdf_context(docs, mode, max(10_000, budget - used))
    notes.extend(pdf_ctx.notes)
    parts = [head, *wb_texts, issues_block, pdf_ctx.text, calc_block]
    return BuiltContext("\n\n".join(p for p in parts if p), notes)
