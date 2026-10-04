"""Orchestrates one analysis run: figures → calculations → AI → verification → report.

    uploaded documents
          │
          ├─► Excel figures (deterministic)          ┐
          ├─► PDF figures (AI locates, code verifies)├─► calculator ─► metrics & checks
          │                                          ┘
          └─► context builder ─► AI analyst (Gemini) ─► validator ─► AnalysisReport
"""

from __future__ import annotations

from typing import Callable

from ..calculations.figures import SCALE, Figure, FigureSet, figures_from_workbook, verify_quote_on_page
from ..calculations.metrics import compute_metrics
from ..config import get_logger, settings
from ..errors import AnalystError, LLMResponseError
from ..ingestion.models import SourceDocument
from ..llm.base import LLMProvider
from ..prompts.common import OUTPUT_RULES, SYSTEM_PROMPT
from ..prompts.extraction import EXTRACTION_INSTRUCTIONS, EXTRACTION_SCHEMA, EXTRACTION_SYSTEM
from ..prompts.modes import MODES, AnalysisMode
from .context_builder import build_context, build_pdf_context
from .schema import AnalysisReport, report_schema
from .validator import validate_report

log = get_logger()
Progress = Callable[[str], None]

RATIO_ITEMS = {"min_dscr_reported", "avg_dscr_reported", "dscr_reported"}


def _excel_scale(unit_text: str) -> float | None:
    """Multiplier to convert a workbook unit to millions (None = unknown)."""
    u = unit_text.lower()
    if any(k in u for k in ("bn", "billion")):
        return 1e3
    if any(k in u for k in ("mn", "million", "mln")) or u.strip().endswith(" m"):
        return 1.0
    if any(k in u for k in ("'000", "000s", "thousand")):
        return 1e-3
    return None


def extract_document_figures(docs: list[SourceDocument], provider: LLMProvider, figset: FigureSet,
                             mode: AnalysisMode) -> None:
    """Pass 1: the AI locates figures in PDFs; code verifies each against the page text."""
    pdfs = [d for d in docs if d.kind == "pdf"]
    if not pdfs or provider.is_demo:
        return
    ctx = build_pdf_context(pdfs, mode, budget=min(settings.max_context_chars, 250_000))
    prompt = f"{EXTRACTION_INSTRUCTIONS}\n\nDOCUMENT MATERIAL:\n{ctx.text}"
    try:
        result = provider.generate_json(system=EXTRACTION_SYSTEM, prompt=prompt, schema=EXTRACTION_SCHEMA,
                                        task={"kind": "extract_figures"})
    except LLMResponseError as exc:
        figset.notes.append(f"Figure extraction from PDFs was skipped: {exc.user_message}")
        return

    # Work out the model's unit so document figures can be compared like-for-like.
    excel_units = [f.unit for f in figset.all_figures() if f.origin == "excel" and f.unit]
    excel_scale = next((s for s in (_excel_scale(u) for u in excel_units) if s), None)

    by_name = {d.filename.lower(): d for d in pdfs}
    for raw in result.data.get("figures", []):
        try:
            item = raw["item"]
            fname = str(raw.get("file", "")).strip()
            doc = by_name.get(fname.lower()) or next((d for d in pdfs if d.filename.lower() in fname.lower()
                                                       or fname.lower() in d.filename.lower()), None)
            page = int(raw.get("page") or 0)
            value = float(raw["value"])
            printed = str(raw.get("value_as_printed", ""))
            quote = str(raw.get("quote", ""))
        except (KeyError, TypeError, ValueError):
            continue
        source = f"{doc.filename if doc else fname} p.{page}"
        scale = SCALE.get(str(raw.get("scale", "millions")).lower(), 1.0)
        if item in RATIO_ITEMS:
            norm_value, unit = value, "x"
        else:
            millions = value * scale
            norm_value = millions / excel_scale if excel_scale else millions
            unit = f"{raw.get('currency', '')} mn".strip() if not excel_scale else (excel_units[0] if excel_units else "")
        fig = Figure(item=item, value=norm_value, source=source, period=str(raw.get("period", "")), unit=unit,
                     label=printed, origin="document", quote=quote)
        if not doc or not verify_quote_on_page(doc, page, quote, printed):
            fig.verified = False
            figset.unverified.append(fig)
            continue
        figset.document_figures.append(fig)
        # Use document figures for calculations only where the model does not provide the item.
        if item in figset.series or (item in figset.scalars and figset.scalars[item].origin == "excel"):
            continue
        if fig.period and item not in ("project_cost", "debt_amount", "equity_amount", "total_sources",
                                       "min_dscr_reported", "avg_dscr_reported"):
            figset.series.setdefault(f"__doc_{item}", []).append(fig)
        elif item not in figset.scalars:
            figset.scalars[item] = fig

    # Promote period figures from documents into series when no model series exists.
    for key in [k for k in figset.series if k.startswith("__doc_")]:
        item = key[len("__doc_"):]
        figs = figset.series.pop(key)
        if item not in figset.series:
            seen = {}
            for f in figs:
                seen.setdefault(f.period, f)
            figset.series[item] = list(seen.values())


def run_analysis(docs: list[SourceDocument], mode_key: str, provider: LLMProvider,
                 extra_instructions: str = "", progress: Progress | None = None) -> AnalysisReport:
    progress = progress or (lambda msg: None)
    if not docs:
        raise AnalystError("No readable documents to analyse. Please upload at least one PDF or Excel file.")
    mode = MODES.get(mode_key)
    if mode is None:
        raise AnalystError(f"Unknown analysis mode '{mode_key}'.")

    warnings: list[str] = []
    for d in docs:
        warnings += [f"{d.filename}: {w}" for w in d.warnings]

    progress("Extracting figures from Excel models…")
    figset = FigureSet()
    for d in docs:
        if d.kind == "excel":
            figures_from_workbook(d, figset)

    if any(d.kind == "pdf" for d in docs) and not provider.is_demo:
        progress("Locating key figures in PDFs and verifying them against the page text…")
        extract_document_figures(docs, provider, figset, mode)

    progress("Running deterministic financial calculations…")
    calc = compute_metrics(figset)
    model_issues = [i for d in docs if d.workbook for i in d.workbook.issues]

    progress("Preparing material for the AI analyst…")
    ctx = build_context(docs, mode, calc, model_issues, settings.max_context_chars)
    extra = f"\nADDITIONAL FOCUS REQUESTED BY THE USER (still subject to all rules):\n{extra_instructions.strip()}\n" \
        if extra_instructions.strip() else ""
    prompt = (
        f"{mode.guidance}\n\nREQUIRED SECTIONS (in this order):\n"
        + "\n".join(f"- {s}" for s in mode.sections)
        + ("\n\nAlso return an 'issues' list (" + mode.issues_title + ")." if mode.include_issues
           else "\n\nReturn an empty 'issues' list.")
        + f"\n{extra}\n{OUTPUT_RULES}\n\n==================== MATERIAL ====================\n{ctx.text}"
    )

    progress(f"Asking the AI analyst ({provider.name}: {provider.model})… this can take a minute.")
    result = provider.generate_json(system=SYSTEM_PROMPT, prompt=prompt, schema=report_schema(mode.include_issues),
                                    task={"kind": "report", "sections": list(mode.sections), "title": mode.title})

    progress("Verifying the AI's statements against sources and calculations…")
    title, sections, issues = validate_report(result.data, mode, docs, calc)

    notes = list(ctx.notes) + list(figset.notes)
    if provider.is_demo:
        notes.insert(0, "DEMO MODE: no AI was used. Document reading, Excel inspection, calculations and checks "
                        "are real; narrative sections are placeholders.")
    return AnalysisReport(
        mode_key=mode.key, mode_title=mode.title, title=title, sections=sections, issues=issues,
        issues_title=mode.issues_title, calculations=calc, model_issues=model_issues, documents=docs,
        provider=result.provider, model=result.model, is_demo=provider.is_demo, context_notes=notes,
        warnings=warnings, input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        unverified_figures=list(figset.unverified),
    )
