"""Turns an AnalysisReport into Markdown, HTML, Word (.docx) and JSON.

The report always has the same skeleton:
  1. Header (title, mode, files, AI engine, date) and the label legend
  2. AI analysis sections (each point tagged FACT / CALCULATED / INFERENCE / MISSING)
  3. Issues table (Legal/DD and Model Review modes)
  4. Appendix A – Calculated metrics (deterministic, with formulas and sources)
  5. Appendix B – Integrity & consistency checks
  6. Appendix C – Automated model inspection findings
  7. Appendix D – Verification notes (flags, rejected figures, omitted material)
"""

from __future__ import annotations

import html
import io
import json
from dataclasses import asdict

from ..analysis.schema import AnalysisReport
from ..calculations.metrics import fmt

LABEL_COLORS = {
    "FACT": "#1b6e43",
    "CALCULATED": "#1f4f99",
    "INFERENCE": "#8a5a00",
    "MISSING": "#a32020",
}
LABEL_HELP = {
    "FACT": "Directly supported by the uploaded material (source cited).",
    "CALCULATED": "Computed by the application's deterministic calculator, not by AI.",
    "INFERENCE": "Analyst interpretation based on the available information.",
    "MISSING": "Required information not identified in the provided materials.",
}
DISCLAIMER = ("Prototype output generated with AI assistance. All FACT statements cite their source and were "
              "automatically checked where possible; items marked ⚠ could not be verified. Verify material "
              "points against the source documents before reliance.")
PERIOD_COLS_UNITS = {"EBITDA margin": "%", "Debt / EBITDA": "x", "Interest cover": "x", "DSCR (calc.)": "x"}


def _period_cell(col: str, v) -> str:
    return fmt(v, PERIOD_COLS_UNITS.get(col, "amount")) if v is not None else "–"


def _files_line(rep: AnalysisReport) -> str:
    return ", ".join(f"{d.filename} ({d.summary})" for d in rep.documents)


def _engine_line(rep: AnalysisReport) -> str:
    if rep.is_demo:
        return "Demo mode (no AI)"
    tokens = f"; {rep.input_tokens:,} input / {rep.output_tokens or 0:,} output tokens" if rep.input_tokens else ""
    return f"{rep.provider} · {rep.model}{tokens}"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def _md_escape_cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _md_table(columns: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(_md_escape_cell(c) for c in columns) + " |",
           "|" + "|".join("---" for _ in columns) + "|"]
    for r in rows:
        r = list(r) + [""] * (len(columns) - len(r))
        out.append("| " + " | ".join(_md_escape_cell(c) for c in r[: len(columns)]) + " |")
    return "\n".join(out)


def to_markdown(rep: AnalysisReport) -> str:
    L = [f"# {rep.title}", "",
         f"**Analysis mode:** {rep.mode_title}  ",
         f"**Prepared:** {rep.created_at:%d %b %Y %H:%M}  ",
         f"**Material:** {_files_line(rep)}  ",
         f"**Engine:** {_engine_line(rep)}", "",
         f"> {DISCLAIMER}", "",
         "**Labels:** " + " · ".join(f"**{k}** – {v}" for k, v in LABEL_HELP.items()), ""]
    for n in rep.context_notes:
        L.append(f"> ℹ️ {n}")
    L.append("")
    for s in rep.sections:
        L.append(f"## {s.heading}")
        for f in s.flags:
            L.append(f"> ⚠ {f}")
        if s.commentary:
            L.append(f"*{s.commentary}*")
            L.append("")
        for p in s.points:
            src = f" — _Source: {p.source}_" if p.source else ""
            flag = "".join(f" ⚠ _{f}_" for f in p.flags)
            L.append(f"- **[{p.label}]** {p.statement}{src}{flag}")
        if s.table:
            L += ["", _md_table(s.table["columns"], s.table["rows"])]
        L.append("")
    if rep.issues:
        L.append(f"## {rep.issues_title}")
        rows = [[str(i + 1), it.issue, it.source + ("" if not it.flags else " ⚠ " + "; ".join(it.flags)),
                 it.why_it_matters, it.risk, it.recommended_comment] for i, it in enumerate(rep.issues)]
        L += [_md_table(["#", "Issue", "Relevant provision / source", "Why it matters to the lender", "Risk",
                         "Recommended lender comment / question"], rows), ""]
    L += _md_appendices(rep)
    return "\n".join(L)


def _md_appendices(rep: AnalysisReport) -> list[str]:
    calc = rep.calculations
    L = ["---", "## Appendix A – Calculated Metrics (deterministic)",
         "_Computed by the application from source figures. No AI arithmetic._", ""]
    if calc.metrics:
        L.append(_md_table(["Metric", "Value", "Period", "Formula", "Source figures"],
                           [[m.name, m.display, m.period, m.formula, m.sources or "per-period table"]
                            for m in calc.metrics]))
    else:
        L.append("No metrics could be calculated from the identified source data.")
    if calc.period_table:
        cols = list(calc.period_table[0].keys())
        L += ["", "**Per-period calculations**", "",
              _md_table(cols, [[_period_cell(c, r[c]) if c != "Period" else r[c] for c in cols]
                               for r in calc.period_table])]
    if calc.missing:
        L += ["", "**Not calculable:**"] + [f"- {m}" for m in calc.missing]
    L += ["", "## Appendix B – Integrity & Consistency Checks", ""]
    if calc.checks:
        L.append(_md_table(["Check", "Result", "Detail"],
                           [[c.name, "PASS" if c.passed else "FAIL" if c.passed is False else "n/a", c.detail]
                            for c in calc.checks]))
    else:
        L.append("No checks could be performed with the identified data.")
    if any(d.kind == "excel" for d in rep.documents):
        L += ["", "## Appendix C – Automated Model Inspection", ""]
        for d in rep.documents:
            if d.workbook:
                L.append(f"**{d.filename}**")
                L.append(_md_table(["Sheet", "Role", "Used range", "Formulas", "Hard-coded numbers", "Timeline",
                                    "Units"],
                                   [[s.name + (" (hidden)" if s.hidden else ""), s.role, s.dimensions,
                                     str(s.n_formulas), str(s.n_numeric_inputs),
                                     f"{s.period_header[0][1]}–{s.period_header[-1][1]}" if s.period_header else "–",
                                     ", ".join(s.units[:2]) or "–"] for s in d.workbook.sheets]))
                L.append("")
        if rep.model_issues:
            L.append(_md_table(["Severity", "Finding", "Location", "Detail"],
                               [[i.severity, i.category, i.location, i.detail] for i in rep.model_issues]))
        else:
            L.append("No structural issues detected.")
    L += ["", "## Appendix D – Verification Notes", ""]
    flagged = rep.flagged_points
    L.append(f"- Statements with verification warnings: {len(flagged)}")
    counts = rep.label_counts()
    L.append("- Label mix: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    for f in rep.unverified_figures:
        L.append(f"- Rejected figure (quote not found on cited page): {f.item} {f.period} '{f.label}' at {f.source}")
    for w in rep.warnings:
        L.append(f"- File warning: {w}")
    return L


# ---------------------------------------------------------------------------
# HTML (self-contained, printable to PDF from any browser)
# ---------------------------------------------------------------------------
CSS = """
:root{--ink:#14202e;--muted:#5a6878;--line:#d9dee5;--navy:#14365d;--bg:#ffffff;--soft:#f4f6f9}
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg);
 margin:0;line-height:1.45;font-size:14px}
.wrap{max-width:1000px;margin:0 auto;padding:32px 24px 64px}
header{border-bottom:3px solid var(--navy);padding-bottom:14px;margin-bottom:18px}
h1{font-size:24px;margin:0 0 6px;color:var(--navy)}
h2{font-size:17px;color:var(--navy);border-bottom:1px solid var(--line);padding-bottom:4px;margin:28px 0 10px}
.meta{color:var(--muted);font-size:12.5px}
.meta b{color:var(--ink)}
.disclaimer{background:var(--soft);border-left:3px solid var(--navy);padding:8px 12px;font-size:12px;color:var(--muted);margin:12px 0}
.note{background:#fff7e0;border-left:3px solid #c99400;padding:6px 10px;font-size:12.5px;margin:6px 0}
.legend span{margin-right:14px;font-size:12px}
.badge{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.03em;color:#fff;border-radius:3px;
 padding:1px 6px;margin-right:6px;vertical-align:1px;min-width:78px;text-align:center}
ul.points{list-style:none;padding:0;margin:6px 0}
ul.points li{padding:5px 0;border-bottom:1px dotted var(--line)}
.src{color:var(--muted);font-size:12px}
.flag{color:#a32020;font-size:12px;display:block;margin-left:90px}
.commentary{font-style:italic;color:#2c3b4d;margin:4px 0 6px}
table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:12.5px}
th{background:var(--navy);color:#fff;text-align:left;padding:6px 8px;font-weight:600}
td{border-bottom:1px solid var(--line);padding:5px 8px;vertical-align:top}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.risk-High{color:#a32020;font-weight:700}.risk-Medium{color:#8a5a00;font-weight:700}.risk-Low{color:#1b6e43;font-weight:700}
.pass{color:#1b6e43;font-weight:700}.fail{color:#a32020;font-weight:700}
.appendix h2{font-size:15px}
@media print{.wrap{padding:0}h2{break-after:avoid}tr{break-inside:avoid}}
"""


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def badge(label: str) -> str:
    return f'<span class="badge" style="background:{LABEL_COLORS.get(label, "#555")}">{_e(label)}</span>'


def _html_table(columns, rows, numeric_cols: set[int] | None = None, raw_cols: set[int] | None = None) -> str:
    numeric_cols, raw_cols = numeric_cols or set(), raw_cols or set()
    head = "".join(f"<th>{_e(c)}</th>" for c in columns)
    body = []
    for r in rows:
        tds = []
        for i, c in enumerate(r):
            cls = ' class="num"' if i in numeric_cols else ""
            tds.append(f"<td{cls}>{c if i in raw_cols else _e(c)}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def section_html(s) -> str:
    out = [f"<h2>{_e(s.heading)}</h2>"]
    out += [f'<div class="note">⚠ {_e(f)}</div>' for f in s.flags]
    if s.commentary:
        out.append(f'<p class="commentary">{_e(s.commentary)}</p>')
    if s.points:
        out.append('<ul class="points">')
        for p in s.points:
            src = f' <span class="src">— {_e(p.source)}</span>' if p.source else ""
            flags = "".join(f'<span class="flag">⚠ {_e(f)}</span>' for f in p.flags)
            out.append(f"<li>{badge(p.label)}{_e(p.statement)}{src}{flags}</li>")
        out.append("</ul>")
    if s.table:
        out.append(_html_table(s.table["columns"], s.table["rows"]))
    return "\n".join(out)


def issues_html(rep: AnalysisReport) -> str:
    rows = []
    for i, it in enumerate(rep.issues, 1):
        src = _e(it.source) + "".join(f'<span class="flag" style="margin:0">⚠ {_e(f)}</span>' for f in it.flags)
        rows.append([str(i), _e(it.issue), src, _e(it.why_it_matters),
                     f'<span class="risk-{_e(it.risk)}">{_e(it.risk)}</span>', _e(it.recommended_comment)])
    return _html_table(["#", "Issue", "Relevant provision / source", "Why it matters to the lender", "Risk",
                        "Recommended lender comment / question"], rows, raw_cols={0, 1, 2, 3, 4, 5})


def appendices_html(rep: AnalysisReport) -> str:
    calc = rep.calculations
    out = ['<div class="appendix">', "<h2>Appendix A – Calculated Metrics (deterministic)</h2>",
           '<p class="meta">Computed by the application from source figures; no AI arithmetic.</p>']
    if calc.metrics:
        out.append(_html_table(["Metric", "Value", "Period", "Formula", "Source figures"],
                               [[m.name, m.display, m.period, m.formula, m.sources or "per-period table"]
                                for m in calc.metrics], numeric_cols={1}))
    else:
        out.append("<p>No metrics could be calculated from the identified source data.</p>")
    if calc.period_table:
        cols = list(calc.period_table[0].keys())
        out.append("<p><b>Per-period calculations</b></p>")
        out.append(_html_table(cols, [[r[c] if c == "Period" else _period_cell(c, r[c]) for c in cols]
                                      for r in calc.period_table], numeric_cols=set(range(1, len(cols)))))
    if calc.missing:
        out.append("<p><b>Not calculable:</b></p><ul>" + "".join(f"<li>{_e(m)}</li>" for m in calc.missing) + "</ul>")
    out.append("<h2>Appendix B – Integrity &amp; Consistency Checks</h2>")
    if calc.checks:
        out.append(_html_table(["Check", "Result", "Detail"],
                               [[_e(c.name), '<span class="pass">PASS</span>' if c.passed else
                                 '<span class="fail">FAIL</span>' if c.passed is False else "n/a", _e(c.detail)]
                                for c in calc.checks], raw_cols={0, 1, 2}))
    else:
        out.append("<p>No checks could be performed with the identified data.</p>")
    if any(d.kind == "excel" for d in rep.documents):
        out.append("<h2>Appendix C – Automated Model Inspection</h2>")
        for d in rep.documents:
            if d.workbook:
                out.append(f"<p><b>{_e(d.filename)}</b></p>")
                out.append(_html_table(
                    ["Sheet", "Role", "Used range", "Formulas", "Hard-coded numbers", "Timeline", "Units"],
                    [[s.name + (" (hidden)" if s.hidden else ""), s.role, s.dimensions, s.n_formulas,
                      s.n_numeric_inputs,
                      f"{s.period_header[0][1]}–{s.period_header[-1][1]}" if s.period_header else "–",
                      ", ".join(s.units[:2]) or "–"] for s in d.workbook.sheets], numeric_cols={3, 4}))
        if rep.model_issues:
            out.append(_html_table(["Severity", "Finding", "Location", "Detail"],
                                   [[f'<span class="risk-{_e(i.severity)}">{_e(i.severity)}</span>', _e(i.category),
                                     _e(i.location), _e(i.detail)] for i in rep.model_issues], raw_cols={0, 1, 2, 3}))
        else:
            out.append("<p>No structural issues detected.</p>")
    out.append("<h2>Appendix D – Verification Notes</h2><ul>")
    counts = rep.label_counts()
    out.append(f"<li>Statements with verification warnings: {len(rep.flagged_points)}</li>")
    out.append("<li>Label mix: " + ", ".join(f"{badge(k)}{v}" for k, v in counts.items()) + "</li>")
    for f in rep.unverified_figures:
        out.append(f"<li>Rejected figure (quote not found on cited page): {_e(f.item)} {_e(f.period)} "
                   f"'{_e(f.label)}' at {_e(f.source)}</li>")
    for w in rep.warnings:
        out.append(f"<li>File warning: {_e(w)}</li>")
    out.append("</ul></div>")
    return "\n".join(out)


def to_html(rep: AnalysisReport) -> str:
    legend = "".join(f"<span>{badge(k)}{_e(v)}</span>" for k, v in LABEL_HELP.items())
    notes = "".join(f'<div class="note">ℹ {_e(n)}</div>' for n in rep.context_notes)
    body = [f"<header><h1>{_e(rep.title)}</h1><div class='meta'><b>{_e(rep.mode_title)}</b> · Prepared "
            f"{rep.created_at:%d %b %Y %H:%M} · Engine: {_e(_engine_line(rep))}<br>Material: {_e(_files_line(rep))}"
            f"</div></header>",
            f'<div class="disclaimer">{_e(DISCLAIMER)}</div>', f'<div class="legend">{legend}</div>', notes]
    body += [section_html(s) for s in rep.sections]
    if rep.issues:
        body.append(f"<h2>{_e(rep.issues_title)}</h2>{issues_html(rep)}")
    body.append(appendices_html(rep))
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{_e(rep.title)}</title><style>{CSS}</style>"
            f"</head><body><div class='wrap'>{''.join(body)}</div></body></html>")


# ---------------------------------------------------------------------------
# Word (.docx)
# ---------------------------------------------------------------------------
def to_docx(rep: AnalysisReport) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    def rgb(hex_color: str) -> RGBColor:
        return RGBColor.from_string(hex_color.lstrip("#").upper())

    def table(columns, rows, numeric: set[int] = frozenset()):
        t = doc.add_table(rows=1, cols=len(columns))
        t.style = "Light Grid Accent 1"
        for i, c in enumerate(columns):
            t.rows[0].cells[i].text = str(c)
        for r in rows:
            cells = t.add_row().cells
            for i, c in enumerate(list(r)[: len(columns)]):
                cells[i].text = str(c)
                if i in numeric:
                    cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for row in t.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(8.5)
        doc.add_paragraph()

    doc.add_heading(rep.title, 0)
    meta = doc.add_paragraph()
    meta.add_run(f"{rep.mode_title} · Prepared {rep.created_at:%d %b %Y %H:%M} · Engine: {_engine_line(rep)}\n"
                 f"Material: {_files_line(rep)}").font.size = Pt(8.5)
    d = doc.add_paragraph()
    r = d.add_run(DISCLAIMER)
    r.italic, r.font.size = True, Pt(8.5)
    leg = doc.add_paragraph()
    for k, v in LABEL_HELP.items():
        run = leg.add_run(f"[{k}] ")
        run.bold, run.font.color.rgb, run.font.size = True, rgb(LABEL_COLORS[k]), Pt(8.5)
        leg.add_run(v + "   ").font.size = Pt(8.5)
    for n in rep.context_notes:
        doc.add_paragraph(f"ℹ {n}").runs[0].font.size = Pt(8.5)

    for s in rep.sections:
        doc.add_heading(s.heading, level=1)
        for f in s.flags:
            p = doc.add_paragraph()
            run = p.add_run(f"⚠ {f}")
            run.font.color.rgb = rgb("#A32020")
        if s.commentary:
            doc.add_paragraph().add_run(s.commentary).italic = True
        for pt in s.points:
            p = doc.add_paragraph(style="List Bullet")
            lab = p.add_run(f"[{pt.label}] ")
            lab.bold, lab.font.color.rgb = True, rgb(LABEL_COLORS.get(pt.label, "#555555"))
            p.add_run(pt.statement)
            if pt.source:
                src = p.add_run(f"  — {pt.source}")
                src.italic, src.font.size, src.font.color.rgb = True, Pt(8.5), rgb("#5A6878")
            for f in pt.flags:
                fr = p.add_run(f"  ⚠ {f}")
                fr.font.size, fr.font.color.rgb = Pt(8.5), rgb("#A32020")
        if s.table:
            table(s.table["columns"], s.table["rows"])

    if rep.issues:
        doc.add_heading(rep.issues_title, level=1)
        table(["#", "Issue", "Provision / source", "Why it matters", "Risk", "Recommended comment"],
              [[i + 1, it.issue, it.source + ("" if not it.flags else " ⚠ " + "; ".join(it.flags)),
                it.why_it_matters, it.risk, it.recommended_comment] for i, it in enumerate(rep.issues)])

    calc = rep.calculations
    doc.add_heading("Appendix A – Calculated Metrics (deterministic)", level=1)
    if calc.metrics:
        table(["Metric", "Value", "Period", "Formula", "Source figures"],
              [[m.name, m.display, m.period, m.formula, m.sources or "per-period table"] for m in calc.metrics],
              numeric={1})
    if calc.period_table:
        cols = list(calc.period_table[0].keys())
        table(cols, [[r[c] if c == "Period" else _period_cell(c, r[c]) for c in cols] for r in calc.period_table],
              numeric=set(range(1, len(cols))))
    for m in calc.missing:
        doc.add_paragraph(m, style="List Bullet")
    doc.add_heading("Appendix B – Integrity & Consistency Checks", level=1)
    if calc.checks:
        table(["Check", "Result", "Detail"],
              [[c.name, "PASS" if c.passed else "FAIL" if c.passed is False else "n/a", c.detail] for c in calc.checks])
    if rep.model_issues:
        doc.add_heading("Appendix C – Automated Model Inspection", level=1)
        table(["Severity", "Finding", "Location", "Detail"],
              [[i.severity, i.category, i.location, i.detail] for i in rep.model_issues])
    doc.add_heading("Appendix D – Verification Notes", level=1)
    doc.add_paragraph(f"Statements with verification warnings: {len(rep.flagged_points)}", style="List Bullet")
    for f in rep.unverified_figures:
        doc.add_paragraph(f"Rejected figure: {f.item} {f.period} '{f.label}' at {f.source}", style="List Bullet")
    for w in rep.warnings:
        doc.add_paragraph(f"File warning: {w}", style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# JSON (machine-readable; distinguishes source data, calculations and AI text)
# ---------------------------------------------------------------------------
def to_json(rep: AnalysisReport) -> str:
    calc = rep.calculations
    payload = {
        "title": rep.title,
        "mode": rep.mode_title,
        "created_at": rep.created_at.isoformat(timespec="seconds"),
        "engine": {"provider": rep.provider, "model": rep.model, "demo": rep.is_demo,
                   "input_tokens": rep.input_tokens, "output_tokens": rep.output_tokens},
        "documents": [{"filename": d.filename, "type": d.kind, "summary": d.summary, "warnings": d.warnings}
                      for d in rep.documents],
        "ai_interpretation": {
            "sections": [asdict(s) for s in rep.sections],
            "issues": [asdict(i) for i in rep.issues],
        },
        "calculated_values": {
            "metrics": [{"name": m.name, "value": m.value, "display": m.display, "unit": m.unit,
                         "period": m.period, "formula": m.formula,
                         "inputs": [asdict(f) for f in m.inputs]} for m in calc.metrics],
            "per_period": calc.period_table,
            "checks": [asdict(c) for c in calc.checks],
            "not_calculable": calc.missing,
        },
        "source_data": {
            "figures": [asdict(f) for f in calc.figures.all_figures()],
            "document_figures": [asdict(f) for f in calc.figures.document_figures],
            "rejected_figures": [asdict(f) for f in rep.unverified_figures],
            "model_inspection_findings": [asdict(i) for i in rep.model_issues],
        },
        "notes": rep.context_notes,
    }
    return json.dumps(payload, indent=2, default=str)
