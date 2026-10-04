"""Prompt for pass 1: pulling key figures out of PDFs (no arithmetic).

The AI only *locates* numbers and quotes them. The application then verifies
each quote really appears on the cited page before any figure is used in a
calculation.
"""

from ..calculations.figures import LINE_ITEMS

EXTRACTABLE_ITEMS = [
    "project_cost", "debt_amount", "equity_amount", "total_sources", "revenue", "ebitda", "interest",
    "debt_service", "cfads", "debt_closing", "net_income", "min_dscr_reported", "avg_dscr_reported",
]
assert all(i in LINE_ITEMS for i in EXTRACTABLE_ITEMS)

EXTRACTION_SYSTEM = """You extract financial figures from transaction documents for a bank's analysis system.
You never calculate, estimate, convert or round. You only copy numbers exactly as printed."""

EXTRACTION_INSTRUCTIONS = """Find figures in the DOCUMENT MATERIAL below for these items (only if explicitly stated):
- project_cost: total project / transaction cost (total uses)
- debt_amount: total senior debt / facility amount in the financing plan
- equity_amount: total sponsor equity in the financing plan
- total_sources: total sources of funds
- revenue, ebitda, interest, debt_service, cfads, net_income, debt_closing (debt outstanding at period
  end): per-period projected or historical figures (give the period, e.g. "FY2027")
- min_dscr_reported, avg_dscr_reported: minimum / average DSCR stated in the documents

For each figure return:
- item: one of the names above
- value_as_printed: the number exactly as printed (e.g. "24,000" or "1.53x" or "18.0")
- value: the same number as a plain number without separators (e.g. 24000, 1.53, 18.0)
- scale: "units", "thousands", "millions" or "billions" as stated in the document (ratios: "units")
- currency: e.g. "PKR", "USD" ("" for ratios)
- period: e.g. "FY2027" ("" if not period-specific)
- file and page: from the [file p.N] markers
- quote: a short verbatim snippet (5–15 words) from that page containing the number

Do not include figures you are unsure about. Return an empty list if none are stated."""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "enum": EXTRACTABLE_ITEMS},
                    "value_as_printed": {"type": "string"},
                    "value": {"type": "number"},
                    "scale": {"type": "string", "enum": ["units", "thousands", "millions", "billions"]},
                    "currency": {"type": "string"},
                    "period": {"type": "string"},
                    "file": {"type": "string"},
                    "page": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["item", "value_as_printed", "value", "scale", "currency", "period", "file", "page",
                             "quote"],
            },
        }
    },
    "required": ["figures"],
}
