"""Hallucination control: the validator must flag unverifiable AI statements."""

from ib_analyst.analysis.engine import run_analysis

IM = "Information_Memorandum_Thar_Sun.pdf"
TS = "Term_Sheet_Thar_Sun.pdf"
FA = "Facility_Agreement_Extract_Thar_Sun.pdf"


def _pt(statement, label, source=""):
    return {"statement": statement, "label": label, "source": source}


REPORT = {
    "report_title": "Credit Review",
    "sections": [{
        "heading": "Executive Summary", "commentary": "",
        "points": [
            _pt("Total project cost is PKR 24,000 million.", "FACT", f"{IM} p.1"),       # 0 ok
            _pt("Facility amount is PKR 18,000 million.", "FACT", f"{TS} p.9"),          # 1 page does not exist
            _pt("Pricing is 6-month KIBOR + 3.50%.", "FACT", f"{TS} p.1"),               # 2 invented figure
            _pt("Minimum DSCR is 1.53x.", "CALCULATED", "Calculated: Minimum DSCR"),     # 3 ok
            _pt("Debt/EBITDA is 4.10x.", "CALCULATED", "Calculated: Debt / first-year EBITDA"),  # 4 invented
            _pt("Lenders may accelerate.", "FACT", f"{FA} p.2, clause 22.5"),            # 5 ok
            _pt("Equity cure rights apply.", "FACT", f"{FA} p.2, clause 41.2"),          # 6 fake clause
            _pt("The borrower is rated AA.", "FACT", "Rating_Report.pdf p.1"),           # 7 file not uploaded
            _pt("Credit rating.", "MISSING", ""),                                        # 8 phrase added
            _pt("Upfront fee is 0.75%.", "FACT", f"{TS} p.1"),                           # 9 ok
            _pt("Margin is 2.25% per annum.", "FACT", ""),                               # 10 no source
        ],
    }],
    "issues": [{"issue": "MAE definition is circular", "source": f"{FA} p.1, clause 1.2",
                "why_it_matters": "x", "risk": "high", "recommended_comment": "y", "label": "FACT"}],
}


def _run(sample_docs, scripted, figures=None):
    return run_analysis(sample_docs, "credit_review", scripted(report=REPORT, figures=figures or []))


def test_flags(sample_docs, scripted):
    rep = _run(sample_docs, scripted)
    pts = rep.sections[0].points
    assert pts[0].flags == []
    assert any("page 9 does not exist" in f for f in pts[1].flags)
    assert any("3.50" in f for f in pts[2].flags)
    assert pts[3].flags == []
    assert any("4.10" in f for f in pts[4].flags)
    assert pts[5].flags == []
    assert any("41.2" in f for f in pts[6].flags)
    assert any("does not match any uploaded file" in f for f in pts[7].flags)
    assert pts[8].statement.startswith("Not identified in the provided materials.")
    assert pts[9].flags == []
    assert any("No source" in f for f in pts[10].flags)
    assert rep.issues[0].risk == "High" and rep.issues[0].flags == []


def test_all_required_sections_present(sample_docs, scripted):
    rep = _run(sample_docs, scripted)
    from ib_analyst.prompts.modes import MODES

    assert [s.heading for s in rep.sections] == list(MODES["credit_review"].sections)
    omitted = rep.sections[1]
    assert omitted.flags and omitted.points[0].label == "MISSING"


def test_document_figures_verified_and_cross_checked(sample_docs, scripted):
    figures = [
        {"item": "project_cost", "value_as_printed": "24,000", "value": 24000, "scale": "millions",
         "currency": "PKR", "period": "", "file": IM, "page": 2, "quote": "Total project cost 24,000"},
        {"item": "avg_dscr_reported", "value_as_printed": "1.86x", "value": 1.86, "scale": "units",
         "currency": "", "period": "", "file": IM, "page": 3, "quote": "an average DSCR of 1.86x"},
        {"item": "ebitda", "value_as_printed": "9,999", "value": 9999, "scale": "millions", "currency": "PKR",
         "period": "FY2030", "file": IM, "page": 3, "quote": "EBITDA 9,999"},  # fabricated
    ]
    rep = _run(sample_docs, scripted, figures)
    assert [f.value for f in rep.unverified_figures] == [9999]
    checks = {c.name: c for c in rep.calculations.checks}
    assert checks["Document vs model: Total project cost"].passed is True
    assert checks["Document vs model: Average DSCR (as reported)"].passed is False  # 1.86x vs 2.37x
