"""Deterministic financial calculations.

All arithmetic happens here, in plain Python, never inside the AI. Every
metric records its formula and the exact source figures used, so it can be
audited. If an input is missing, the metric is reported as not calculable;
nothing is ever assumed or plugged to make numbers reconcile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import mean

from .figures import PRETTY, Figure, FigureSet


@dataclass
class Metric:
    name: str
    value: float | None
    unit: str  # "x" | "%" | "amount"
    formula: str
    inputs: list[Figure] = field(default_factory=list)
    period: str = ""
    category: str = "General"
    comment: str = ""

    @property
    def display(self) -> str:
        return fmt(self.value, self.unit)

    @property
    def sources(self) -> str:
        return "; ".join(f"{PRETTY.get(f.item, f.item)} {fmt(f.value, 'amount')} [{f.source}]" for f in self.inputs)


@dataclass
class Check:
    name: str
    passed: bool | None  # None = could not be performed
    detail: str
    severity: str = "Medium"


@dataclass
class CalculationResults:
    figures: FigureSet
    metrics: list[Metric] = field(default_factory=list)
    period_table: list[dict] = field(default_factory=list)  # one row per period
    checks: list[Check] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def metric(self, name: str) -> Metric | None:
        return next((m for m in self.metrics if m.name == name), None)

    @property
    def is_empty(self) -> bool:
        return not self.metrics and not self.period_table


def fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "x":
        return f"{value:,.2f}x"
    if unit == "%":
        return f"{value * 100:,.1f}%"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _year(period: str) -> str:
    m = re.search(r"(19|20)\d{2}", period)
    if m:
        return m.group(0)
    m = re.search(r"FY\s?(\d{2})", period, re.I)
    return f"20{m.group(1)}" if m else period


def _close(a: float, b: float, rel: float = 0.0005, abs_tol: float = 0.5) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b)))


def compute_metrics(fs: FigureSet) -> CalculationResults:
    res = CalculationResults(figures=fs)
    S = {k: fs.get_series(k) for k in fs.series}

    def ser(item: str) -> dict[str, Figure]:
        return S.get(item, {})

    rev, ebitda, interest = ser("revenue"), ser("ebitda"), ser("interest")
    ds, rep, cfads = ser("debt_service"), ser("repayment"), ser("cfads")
    debt_c, debt_o, dscr_rep = ser("debt_closing"), ser("debt_opening"), ser("dscr_reported")

    periods = list(dict.fromkeys(list(ebitda) + list(rev) + list(cfads) + list(debt_c)))

    # ---------------- Per-period analysis ----------------
    dscrs: list[tuple[str, float, list[Figure]]] = []
    for p in periods:
        row: dict = {"Period": p}
        e, r = ebitda.get(p), rev.get(p)
        i, d = interest.get(p), debt_c.get(p)
        c = cfads.get(p)
        dsv = ds.get(p)
        ds_inputs: list[Figure] = []
        ds_value = None
        if dsv:
            ds_value, ds_inputs = abs(dsv.value), [dsv]
        elif i and rep.get(p):
            ds_value, ds_inputs = abs(i.value) + abs(rep[p].value), [i, rep[p]]
        row["Revenue"] = r.value if r else None
        row["EBITDA"] = e.value if e else None
        row["EBITDA margin"] = _div(e.value, r.value) if e and r else None
        row["Debt (end)"] = d.value if d else None
        row["Debt / EBITDA"] = _div(d.value, e.value) if d and e and e.value > 0 else None
        row["Interest cover"] = _div(e.value, abs(i.value)) if e and i and i.value else None
        row["Debt service"] = ds_value
        dscr = _div(c.value, ds_value) if c and ds_value else None
        row["DSCR (calc.)"] = dscr
        if dscr is not None:
            dscrs.append((p, dscr, [c] + ds_inputs))
            rep_f = dscr_rep.get(p)
            if rep_f is not None and not _close(rep_f.value, dscr, rel=0.005, abs_tol=0.005):
                res.checks.append(Check(
                    f"DSCR reconciliation {p}", False,
                    f"Model shows DSCR {fmt(rep_f.value, 'x')} [{rep_f.source}] but CFADS / debt service = "
                    f"{fmt(dscr, 'x')}", "High"))
        res.period_table.append(row)

    if dscrs and dscr_rep:
        compared = [p for p, _, _ in dscrs if p in dscr_rep]
        if compared and not any(c.name.startswith("DSCR reconciliation") for c in res.checks):
            res.checks.append(Check("DSCR reconciliation", True,
                                    f"Model DSCR row agrees with CFADS / debt service in all {len(compared)} periods."))

    # ---------------- Headline metrics ----------------
    first_p = periods[0] if periods else None
    debt_amt = fs.scalars.get("debt_amount") or (debt_o.get(first_p) if first_p else None)
    equity = fs.scalars.get("equity_amount")
    cost = fs.scalars.get("project_cost")
    e1 = ebitda.get(first_p) if first_p else None

    def add(name, value, unit, formula, inputs, category, period="", comment=""):
        res.metrics.append(Metric(name, value, unit, formula, [x for x in inputs if x], period, category, comment))

    if debt_amt and e1:
        add("Debt / first-year EBITDA", _div(debt_amt.value, e1.value), "x",
            "Debt amount ÷ EBITDA (first projection year)", [debt_amt, e1], "Leverage", first_p)
    if debt_c and ebitda:
        lev = [(p, row["Debt / EBITDA"]) for p, row in zip(periods, res.period_table) if row["Debt / EBITDA"] is not None]
        if lev:
            p_max, v_max = max(lev, key=lambda t: t[1])
            add("Peak Debt (period end) / EBITDA", v_max, "x", "max over periods of closing debt ÷ EBITDA",
                [debt_c.get(p_max), ebitda.get(p_max)], "Leverage", p_max)
    if debt_amt and equity:
        add("Debt / Equity", _div(debt_amt.value, equity.value), "x", "Debt amount ÷ equity amount",
            [debt_amt, equity], "Capital structure")
        add("Debt share of funding (gearing)", _div(debt_amt.value, debt_amt.value + equity.value), "%",
            "Debt ÷ (debt + equity)", [debt_amt, equity], "Capital structure")
    if cost and debt_amt and equity:
        gap = debt_amt.value + equity.value - cost.value
        add("Sources minus uses", gap, "amount", "(Debt + equity) − total project cost", [debt_amt, equity, cost],
            "Sources & uses")
        res.checks.append(Check("Sources = Uses", _close(gap, 0, abs_tol=1.0),
                                f"Debt {fmt(debt_amt.value, 'amount')} + equity {fmt(equity.value, 'amount')} "
                                f"vs project cost {fmt(cost.value, 'amount')}: difference {fmt(gap, 'amount')}",
                                "High"))
    if cost and debt_amt:
        add("Debt as % of project cost", _div(debt_amt.value, cost.value), "%", "Debt ÷ total project cost",
            [debt_amt, cost], "Sources & uses")

    if dscrs:
        p_min, v_min, inp_min = min(dscrs, key=lambda t: t[1])
        add("Minimum DSCR", v_min, "x", "min over periods of CFADS ÷ debt service", inp_min, "Debt service", p_min)
        avg = mean(v for _, v, _ in dscrs)
        add("Average DSCR", avg, "x", f"simple average of CFADS ÷ debt service over {len(dscrs)} periods",
            [], "Debt service", f"{dscrs[0][0]}–{dscrs[-1][0]}")
        for key, calc_val, label in (("min_dscr_reported", v_min, "Minimum"), ("avg_dscr_reported", avg, "Average")):
            reported = fs.scalars.get(key)
            if reported:
                ok = _close(reported.value, calc_val, rel=0.005, abs_tol=0.005)
                res.checks.append(Check(f"{label} DSCR vs reported", ok,
                                        f"Reported {fmt(reported.value, 'x')} [{reported.source}] vs recalculated "
                                        f"{fmt(calc_val, 'x')}", "Medium" if ok else "High"))

    margins = [(p, row["EBITDA margin"]) for p, row in zip(periods, res.period_table) if row["EBITDA margin"] is not None]
    if margins:
        add("EBITDA margin (first year)", margins[0][1], "%", "EBITDA ÷ revenue",
            [ebitda.get(margins[0][0]), rev.get(margins[0][0])], "Profitability", margins[0][0])
        add("Average EBITDA margin", mean(v for _, v in margins), "%", "average of EBITDA ÷ revenue", [],
            "Profitability", f"{margins[0][0]}–{margins[-1][0]}")
    covers = [(p, row["Interest cover"]) for p, row in zip(periods, res.period_table) if row["Interest cover"] is not None]
    if covers:
        p, v = min(covers, key=lambda t: t[1])
        add("Minimum interest cover (EBITDA / interest)", v, "x", "min over periods of EBITDA ÷ interest",
            [ebitda.get(p), interest.get(p)], "Debt service", p)
    rev_pts = [(p, f) for p, f in rev.items() if f.value > 0]
    if len(rev_pts) >= 2:
        (p0, f0), (p1, f1) = rev_pts[0], rev_pts[-1]
        n = len(rev_pts) - 1
        add("Revenue CAGR", (f1.value / f0.value) ** (1 / n) - 1, "%", f"(revenue {p1} ÷ revenue {p0})^(1/{n}) − 1",
            [f0, f1], "Growth", f"{p0}–{p1}")

    # ---------------- Integrity checks ----------------
    ta, tle = ser("total_assets"), ser("total_liabilities_equity")
    if ta and tle:
        bad = [p for p in ta if p in tle and not _close(ta[p].value, tle[p].value, abs_tol=1.0)]
        res.checks.append(Check(
            "Balance sheet balances", not bad,
            "Total assets equal total liabilities & equity in every period." if not bad else
            "Imbalance in " + ", ".join(f"{p} ({fmt(ta[p].value - tle[p].value, 'amount')})" for p in bad[:6]),
            "High"))
    if debt_o and debt_c and rep:
        bad = []
        for p in debt_c:
            if p in debt_o and p in rep:
                expected = debt_o[p].value - abs(rep[p].value)
                if not _close(expected, debt_c[p].value, abs_tol=1.0):
                    bad.append(f"{p}: opening {fmt(debt_o[p].value, 'amount')} − repayment "
                               f"{fmt(abs(rep[p].value), 'amount')} ≠ closing {fmt(debt_c[p].value, 'amount')}")
        res.checks.append(Check("Debt roll-forward (opening − repayment = closing)", not bad,
                                "Consistent in every period (no drawdowns in projection)." if not bad
                                else "; ".join(bad[:4]) + " (drawdowns or other movements may explain this)",
                                "Medium"))
    if debt_c:
        last_p = list(debt_c)[-1]
        last = debt_c[last_p]
        res.checks.append(Check("Debt fully repaid by end of projection", _close(last.value, 0, abs_tol=1.0),
                                f"Closing debt in {last_p}: {fmt(last.value, 'amount')} [{last.source}]", "Low"))

    _cross_check_documents(fs, res)

    # ---------------- What could not be calculated ----------------
    have = set(fs.series) | set(fs.scalars)
    if not dscrs:
        res.missing.append("DSCR could not be calculated: CFADS and/or debt service not identified.")
    if not (("debt_closing" in have or "debt_amount" in have) and "ebitda" in have):
        res.missing.append("Leverage could not be calculated: debt and/or EBITDA not identified.")
    if not covers:
        res.missing.append("Interest cover could not be calculated: EBITDA and/or interest not identified.")
    if not (debt_amt and equity):
        res.missing.append("Debt/Equity could not be calculated: debt and/or equity amount not identified.")
    if not cost:
        res.missing.append("Sources & uses could not be checked: total project cost not identified.")
    return res


def _cross_check_documents(fs: FigureSet, res: CalculationResults) -> None:
    """Compare figures stated in documents with the same items in the Excel model."""
    for f in fs.document_figures:
        if f.item in fs.series:
            model = {_year(p): x for p, x in fs.get_series(f.item).items()}
            m = model.get(_year(f.period))
        else:
            m = fs.scalars.get(f.item)
        if m is None or m.origin != "excel":
            continue
        ok = _close(f.value, m.value, rel=0.0025, abs_tol=0.5)
        res.checks.append(Check(
            f"Document vs model: {PRETTY.get(f.item, f.item)} {f.period}".strip(), ok,
            f"{f.source} states {fmt(f.value, 'amount')}; model shows {fmt(m.value, 'amount')} [{m.source}]",
            "Low" if ok else "High"))
