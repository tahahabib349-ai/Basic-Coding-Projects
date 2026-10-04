"""Data structures describing uploaded documents after they have been read.

These are the application's internal "filing system": every PDF page and every
Excel row keeps a reference back to where it came from (file, page, sheet, cell),
so the AI can cite sources and the app can verify those citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PdfPage:
    number: int  # 1-based, as printed in a PDF viewer
    text: str
    headings: list[str] = field(default_factory=list)
    clause_refs: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class CellValue:
    ref: str  # e.g. "D12"
    value: Any  # value as last calculated by Excel (cached), or the constant
    formula: str | None = None  # e.g. "=D10-D11"; None for hard-coded inputs

    @property
    def is_formula(self) -> bool:
        return self.formula is not None


@dataclass
class RowInfo:
    sheet: str
    row: int
    label: str
    kind: str  # "input" | "formula" | "mixed" | "empty"
    cells: list[CellValue] = field(default_factory=list)
    unit: str = ""

    def numeric_values(self) -> list[tuple[str, float]]:
        out = []
        for c in self.cells:
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                out.append((c.ref, float(c.value)))
        return out


@dataclass
class SheetInfo:
    name: str
    dimensions: str
    max_row: int
    max_col: int
    role: str = "unclassified"  # input | calculation | output | financial_statements | debt_schedule ...
    role_reason: str = ""
    n_formulas: int = 0
    n_numeric_inputs: int = 0
    n_text: int = 0
    n_dates: int = 0
    units: list[str] = field(default_factory=list)
    period_header: list[tuple[str, str]] = field(default_factory=list)  # (column letter, period label)
    label_col: str = "A"
    rows: list[RowInfo] = field(default_factory=list)
    error_cells: list[str] = field(default_factory=list)  # "B7 (#REF!)"
    hidden: bool = False
    referenced_sheets: list[str] = field(default_factory=list)


@dataclass
class ModelIssue:
    """A deterministic finding from programmatic inspection of a workbook."""

    category: str  # e.g. "Hard-coded value in calculation row"
    location: str  # e.g. "Debt!F14"
    detail: str
    severity: str = "Medium"  # High | Medium | Low


@dataclass
class WorkbookInfo:
    sheets: list[SheetInfo] = field(default_factory=list)
    defined_names: dict[str, str] = field(default_factory=dict)
    external_links: list[str] = field(default_factory=list)
    has_cached_values: bool = True
    issues: list[ModelIssue] = field(default_factory=list)

    def sheet(self, name: str) -> SheetInfo | None:
        return next((s for s in self.sheets if s.name == name), None)


@dataclass
class SourceDocument:
    filename: str
    kind: str  # "pdf" | "excel"
    size_bytes: int
    pages: list[PdfPage] = field(default_factory=list)
    workbook: WorkbookInfo | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.kind == "pdf":
            return f"{len(self.pages)} pages"
        if self.workbook:
            return f"{len(self.workbook.sheets)} sheets"
        return ""

    def page(self, number: int) -> PdfPage | None:
        if 1 <= number <= len(self.pages):
            return self.pages[number - 1]
        return None


@dataclass
class IngestionResult:
    documents: list[SourceDocument] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (filename, friendly message)
