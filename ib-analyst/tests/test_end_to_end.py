"""Whole pipeline, all four modes, multiple files, context-size management."""

import pytest

from ib_analyst.analysis.context_builder import build_pdf_context
from ib_analyst.analysis.engine import run_analysis
from ib_analyst.ingestion.models import PdfPage, SourceDocument
from ib_analyst.llm.demo_provider import DemoProvider
from ib_analyst.prompts.modes import MODES


@pytest.mark.parametrize("mode", list(MODES))
def test_every_mode_with_all_files(sample_docs, scripted, mode):
    prov = scripted()
    rep = run_analysis(sample_docs, mode, prov, extra_instructions="Focus on DSCR headroom")
    assert [s.heading for s in rep.sections] == list(MODES[mode].sections)
    assert prov.prompts == ["extract_figures", "report"]  # two-pass: locate figures, then analyse
    p = prov.last_prompt
    # The AI receives page/cell markers, the deterministic calculations and model-check findings.
    assert "[Term_Sheet_Thar_Sun.pdf p.2]" in p and "Financial_Model_Thar_Sun.xlsx" in p
    assert "Minimum DSCR (2027) = 1.53x" in p
    assert "Hard-coded value in formula row at Operations!H10" in p
    assert "Focus on DSCR headroom" in p


def test_demo_mode_runs_without_key(sample_docs):
    rep = run_analysis(sample_docs, "ib_summary", DemoProvider())
    assert rep.is_demo and rep.calculations.metric("Minimum DSCR") is not None
    assert "DEMO MODE" in rep.context_notes[0]


def test_pdf_only_has_no_calculations_but_reports_missing(sample_docs, scripted):
    pdfs = [d for d in sample_docs if d.kind == "pdf"]
    rep = run_analysis(pdfs, "credit_review", scripted())
    assert rep.calculations.missing  # nothing extracted -> explicitly not calculable


def test_large_material_selects_relevant_pages():
    filler = "lorem ipsum " * 400
    pages = [PdfPage(number=i, text=filler) for i in range(1, 41)]
    pages[29] = PdfPage(number=30, text="Events of default and financial covenants clause security " * 30,
                        headings=["22. EVENTS OF DEFAULT"])
    doc = SourceDocument("Big.pdf", "pdf", 1, pages=pages)
    ctx = build_pdf_context([doc], MODES["legal_dd_review"], budget=30_000)
    assert "[Big.pdf p.30]" in ctx.text and "[Big.pdf p.1]" in ctx.text
    assert "[Big.pdf p.20]" not in ctx.text
    assert ctx.notes and "not sent to the AI" in ctx.notes[0]
