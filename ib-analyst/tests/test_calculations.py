"""Deterministic calculations: correctness, traceability, missing data, failed checks."""

import pytest

from ib_analyst.calculations.figures import Figure, FigureSet, figures_from_workbook
from ib_analyst.calculations.metrics import compute_metrics, fmt


def _series(item, values, start=2027):
    return [Figure(item=item, value=v, period=str(start + i), source=f"t.xlsx › S!{chr(67 + i)}1")
            for i, v in enumerate(values)]


def test_user_example_debt_to_ebitda():
    fs = FigureSet()
    fs.scalars["debt_amount"] = Figure("debt_amount", 18_000, "TS p.1")
    fs.series["ebitda"] = _series("ebitda", [6_000])
    res = compute_metrics(fs)
    m = res.metric("Debt / first-year EBITDA")
    assert m.value == pytest.approx(3.0) and m.display == "3.00x"
    assert {f.source for f in m.inputs} == {"TS p.1", "t.xlsx › S!C1"}  # traceable inputs


def test_sample_model_metrics(sample_docs):
    fs = FigureSet()
    figures_from_workbook(next(d for d in sample_docs if d.kind == "excel"), fs)
    res = compute_metrics(fs)
    assert res.metric("Debt / first-year EBITDA").value == pytest.approx(18000 / 6466.08, rel=1e-6)
    assert res.metric("Minimum DSCR").value == pytest.approx(6466.08 / 4230, rel=1e-6)
    assert res.metric("Debt / Equity").value == pytest.approx(3.0)
    assert res.metric("Debt share of funding (gearing)").display == "75.0%"
    assert all(c.passed for c in res.checks), [c for c in res.checks if not c.passed]
    assert res.missing == []


def test_balance_sheet_imbalance_and_dscr_mismatch_detected():
    fs = FigureSet()
    fs.series["total_assets"] = _series("total_assets", [100, 110])
    fs.series["total_liabilities_equity"] = _series("total_liabilities_equity", [100, 105])
    fs.series["cfads"] = _series("cfads", [120, 130])
    fs.series["debt_service"] = _series("debt_service", [100, 100])
    fs.series["dscr_reported"] = _series("dscr_reported", [1.20, 1.45])  # 2028 wrong (should be 1.30)
    res = compute_metrics(fs)
    checks = {c.name: c for c in res.checks}
    assert checks["Balance sheet balances"].passed is False and "2028" in checks["Balance sheet balances"].detail
    assert checks["DSCR reconciliation 2028"].passed is False


def test_missing_data_is_reported_not_invented():
    fs = FigureSet()
    fs.series["revenue"] = _series("revenue", [100, 110])
    res = compute_metrics(fs)
    assert res.metric("Minimum DSCR") is None
    text = " ".join(res.missing)
    assert "DSCR could not be calculated" in text and "Leverage could not be calculated" in text
    assert res.metric("Revenue CAGR").value == pytest.approx(0.10)


def test_no_data_at_all():
    res = compute_metrics(FigureSet())
    assert res.is_empty and len(res.missing) == 5


def test_formatting():
    assert fmt(2.784, "x") == "2.78x" and fmt(0.75, "%") == "75.0%" and fmt(18000, "amount") == "18,000"
    assert fmt(None, "x") == "n/a"
