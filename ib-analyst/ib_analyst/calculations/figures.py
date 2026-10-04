"""Source figures used by the calculator, with provenance.

A `Figure` is a single number taken from the uploaded material (an Excel cell,
or a number on a PDF page that has been verified to appear on that page).
Calculations only ever use Figures, so every result can be traced back to its
source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ingestion.models import RowInfo, SourceDocument

# Canonical line items and the labels that identify them in a model.
# Order matters: earlier synonyms are better matches.
LINE_ITEMS: dict[str, dict] = {
    "revenue": {"labels": ["total revenue", "revenue", "net revenue", "net sales", "sales", "turnover"],
                "exclude": ["growth", "margin", "%", "per ", "/kwh", "tariff"]},
    "ebitda": {"labels": ["ebitda"], "exclude": ["margin", "%", "growth", "/"]},
    "interest": {"labels": ["interest expense", "finance cost", "financial charges", "interest paid", "interest"],
                 "exclude": ["rate", "%", "cover", "during construction", "kibor", "margin", "income"]},
    "debt_service": {"labels": ["total debt service", "debt service"], "exclude": ["coverage", "ratio", "dscr", "reserve"]},
    "repayment": {"labels": ["principal repayment", "repayment", "principal"], "exclude": ["period", "years", "%"]},
    "cfads": {"labels": ["cfads", "cash flow available for debt service", "cash flow before debt service"],
              "exclude": ["ratio", "%"]},
    "debt_closing": {"labels": ["closing balance", "closing debt", "debt outstanding", "senior debt",
                                "total debt", "borrowings", "long term debt", "loan balance"],
                     "exclude": ["share", "%", "service", "ratio", "repayment", "interest", "fee"]},
    "debt_opening": {"labels": ["opening balance", "opening debt"], "exclude": ["cash"]},
    "dscr_reported": {"labels": ["dscr", "debt service coverage ratio", "debt service cover ratio"],
                      "exclude": ["minimum", "min ", "average", "lock", "covenant", "target"]},
    "total_assets": {"labels": ["total assets"], "exclude": []},
    "total_liabilities_equity": {"labels": ["total liabilities and equity", "total equity and liabilities",
                                            "total liabilities & equity", "total equity & liabilities"], "exclude": []},
    "net_income": {"labels": ["net profit", "net income", "profit after tax", "pat"], "exclude": ["margin", "%"]},
    # Scalars (typically on an inputs / sources & uses sheet)
    "project_cost": {"labels": ["total project cost", "project cost", "total uses", "total capex"],
                     "exclude": ["%", "overrun"]},
    "total_sources": {"labels": ["total sources", "total funding", "total financing"], "exclude": ["%"]},
    "debt_amount": {"labels": ["senior debt", "total debt", "debt amount", "facility amount", "loan amount"],
                    "exclude": ["share", "%", "service", "ratio", "repayment", "interest", "fee", "closing", "opening"]},
    "equity_amount": {"labels": ["sponsor equity", "total equity", "equity contribution", "equity", "share capital"],
                      "exclude": ["share %", "%", "ratio", "irr", "return", "liabilities"]},
    "min_dscr_reported": {"labels": ["minimum dscr", "min dscr", "min. dscr"], "exclude": []},
    "avg_dscr_reported": {"labels": ["average dscr", "avg dscr", "avg. dscr"], "exclude": []},
}

SERIES_ITEMS = {"revenue", "ebitda", "interest", "debt_service", "repayment", "cfads", "debt_closing",
                "debt_opening", "dscr_reported", "total_assets", "total_liabilities_equity", "net_income"}
SCALAR_ITEMS = set(LINE_ITEMS) - SERIES_ITEMS

PRETTY = {
    "revenue": "Revenue", "ebitda": "EBITDA", "interest": "Interest", "debt_service": "Debt service",
    "repayment": "Principal repayment", "cfads": "CFADS", "debt_closing": "Debt (period end)",
    "debt_opening": "Debt (opening)", "dscr_reported": "DSCR (as reported in model)",
    "total_assets": "Total assets", "total_liabilities_equity": "Total liabilities & equity",
    "net_income": "Net income", "project_cost": "Total project cost", "total_sources": "Total sources",
    "debt_amount": "Debt amount", "equity_amount": "Equity amount",
    "min_dscr_reported": "Minimum DSCR (as reported)", "avg_dscr_reported": "Average DSCR (as reported)",
}


@dataclass
class Figure:
    item: str
    value: float
    source: str  # e.g. "Model.xlsx › Operations!C14" or "IM.pdf p.3"
    period: str = ""
    unit: str = ""
    label: str = ""  # label as written in the source
    origin: str = "excel"  # "excel" | "document"
    verified: bool = True
    quote: str = ""


@dataclass
class FigureSet:
    """All source figures, grouped by canonical line item."""

    series: dict[str, list[Figure]] = field(default_factory=dict)  # item -> figures per period (in order)
    scalars: dict[str, Figure] = field(default_factory=dict)
    document_figures: list[Figure] = field(default_factory=list)  # verified figures stated in PDFs
    unverified: list[Figure] = field(default_factory=list)  # figures that failed source verification
    notes: list[str] = field(default_factory=list)

    def get_series(self, item: str) -> dict[str, Figure]:
        return {f.period: f for f in self.series.get(item, [])}

    def all_figures(self) -> list[Figure]:
        out = list(self.scalars.values())
        for figs in self.series.values():
            out.extend(figs)
        return out


def _norm(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&%/ ]", " ", label.lower())).strip()


def _match_score(label: str, item: str) -> int:
    """Higher is better; 0 = no match."""
    spec = LINE_ITEMS[item]
    n = _norm(label)
    if any(x in n for x in spec["exclude"]):
        return 0
    for rank, syn in enumerate(spec["labels"]):
        base = 100 - rank * 5
        if n == syn:
            return base + 50
        if n.startswith(syn + " ") or n.endswith(" " + syn):
            return base + 20
        if re.search(r"(?<![a-z])" + re.escape(syn) + r"(?![a-z])", n):
            return base
    return 0


ROLE_PREFERENCE = {
    "revenue": ("calculation", "financial_statements"), "ebitda": ("calculation", "financial_statements"),
    "interest": ("debt_schedule", "financial_statements"), "debt_service": ("debt_schedule",),
    "repayment": ("debt_schedule",), "cfads": ("debt_schedule", "financial_statements"),
    "debt_closing": ("debt_schedule", "financial_statements"), "debt_opening": ("debt_schedule",),
    "dscr_reported": ("debt_schedule", "output"), "total_assets": ("financial_statements",),
    "total_liabilities_equity": ("financial_statements",), "net_income": ("financial_statements",),
    "project_cost": ("input", "output"), "debt_amount": ("input", "output"), "equity_amount": ("input", "output"),
}


def figures_from_workbook(doc: SourceDocument, figset: FigureSet) -> None:
    """Locate key line items in a workbook and add them to `figset`."""
    wb = doc.workbook
    if not wb:
        return
    candidates: dict[str, list[tuple[int, RowInfo, object]]] = {}
    for sheet in wb.sheets:
        period_by_col = dict(sheet.period_header)
        for row in sheet.rows:
            nums = row.numeric_values()
            if not nums:
                continue
            for item in LINE_ITEMS:
                score = _match_score(row.label, item)
                if not score:
                    continue
                if sheet.role in ROLE_PREFERENCE.get(item, ()):
                    score += 10
                in_periods = [(ref, v) for ref, v in nums if re.sub(r"\d", "", ref) in period_by_col]
                is_series = len(in_periods) >= 2
                if item in SERIES_ITEMS and is_series:
                    score += 5
                elif item in SCALAR_ITEMS and not is_series:
                    score += 5
                else:
                    continue
                candidates.setdefault(item, []).append((score, row, sheet))

    for item, cands in candidates.items():
        cands.sort(key=lambda c: (-c[0], c[1].row))
        _, row, sheet = cands[0]
        period_by_col = dict(sheet.period_header)
        unit = row.unit or (sheet.units[0] if sheet.units else "")
        if item in SERIES_ITEMS:
            figs = []
            for ref, v in row.numeric_values():
                col = re.sub(r"\d", "", ref)
                if col in period_by_col:
                    figs.append(Figure(item=item, value=v, period=period_by_col[col], unit=unit, label=row.label,
                                       source=f"{doc.filename} › {sheet.name}!{ref}"))
            if figs and item not in figset.series:
                figset.series[item] = figs
        else:
            ref, v = row.numeric_values()[0]
            if item not in figset.scalars:
                figset.scalars[item] = Figure(item=item, value=v, unit=unit, label=row.label,
                                              source=f"{doc.filename} › {sheet.name}!{ref}")


# --- Figures taken from documents (PDFs) ---------------------------------
SCALE = {"units": 1e-6, "unit": 1e-6, "thousands": 1e-3, "thousand": 1e-3, "millions": 1.0, "million": 1.0,
         "billions": 1e3, "billion": 1e3}


def _digits(s: str) -> str:
    return re.sub(r"[^\d.]", "", s)


def verify_quote_on_page(doc: SourceDocument, page: int, quote: str, value_as_printed: str) -> bool:
    """True if the quoted text (and the printed number) really appear on that page."""
    p = doc.page(page) if doc.kind == "pdf" else None
    if not p:
        return False
    hay = " ".join((p.text + " " + " ".join(" ".join(r) for t in p.tables for r in t)).split()).lower()
    q = " ".join(quote.split()).lower()
    printed = re.sub(r"\s+", "", value_as_printed).lower()
    flat = re.sub(r"\s+", "", hay)
    if not _digits(printed):
        return False
    number_ok = printed in flat or printed.replace(",", "") in flat.replace(",", "")
    quote_ok = (q in hay) if len(q) >= 6 else True
    return number_ok and quote_ok
