"""Report exports: every format renders and contains the key elements."""

import io
import json

from ib_analyst.analysis.engine import run_analysis
from ib_analyst.reporting.render import to_docx, to_html, to_json, to_markdown
from tests.test_validation import REPORT


def test_all_formats(sample_docs, scripted):
    rep = run_analysis(sample_docs, "legal_dd_review", scripted(report=REPORT))
    md, page = to_markdown(rep), to_html(rep)
    for text in (md, page):
        assert "Appendix A" in text and "Minimum DSCR" in text and "1.53x" in text
        assert "Hard-coded value in formula row" in text  # model inspection finding
    assert "<script" not in page
    data = json.loads(to_json(rep))
    assert set(data) >= {"ai_interpretation", "calculated_values", "source_data"}
    from docx import Document

    doc = Document(io.BytesIO(to_docx(rep)))
    assert any("Appendix A" in p.text for p in doc.paragraphs)
