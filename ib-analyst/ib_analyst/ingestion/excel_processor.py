"""Excel workbook inspection.

Builds a structured picture of a financial model *before* any AI sees it:
sheets and their roles, timeline, units, every labelled row with its values
and formulas, plus deterministic integrity checks (errors, hard-codes inside
formula rows, inconsistent formulas, external links).
"""

from __future__ import annotations

import io
import re
import zipfile
from collections import Counter
from datetime import date, datetime

from ..config import settings
from ..errors import CorruptFileError, EmptyDocumentError, PasswordProtectedError, UnsupportedFileError
from .models import CellValue, ModelIssue, RowInfo, SheetInfo, SourceDocument, WorkbookInfo

OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
EXCEL_ERRORS = ("#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!", "#SPILL!", "#CALC!")

_UNIT_RE = re.compile(
    r"(?i)\b(PKR|USD|US\$|EUR|GBP|AED|SAR|INR|Rs\.?|\$|€|£)\s*(?:in\s+)?"
    r"(bn|billion|mn|mln|m|million|millions|'?000s?|thousands?|k)\b"
    r"|\(\s*in\s+(millions|billions|thousands)\s*\)"
    r"|\b(PKR|USD|EUR|GBP)\b"
)
_ROW_UNIT_RE = re.compile(r"(?i)^(%|x|times|days|months|years|MW|MWh|GWh|kWh|tons?|bbl|PKR.*|USD.*|EUR.*|\$.*|Rs.*|#)$")
_YEAR_RE = re.compile(r"^(?:FY\s?|CY\s?)?((?:19|20)\d{2})(?:[AEFPB]|\s?[AEFPB])?$|^FY\s?(\d{2})[AEFPB]?$", re.I)
_REF_RE = re.compile(r"(?<![A-Za-z_\d.$])(\$?)([A-Z]{1,3})(\$?)(\d{1,7})(?![\d(A-Za-z_!])")
_SHEET_REF_RE = re.compile(r"(?:'([^']+)'|([A-Za-z_][\w.]*))!")
_STRING_LIT_RE = re.compile(r'"[^"]*"')
_EMBEDDED_CONST_RE = re.compile(r"(?<![A-Za-z$\d.])(\d+\.\d+|\d{2,})(?![\d:A-Za-z!])")
_BENIGN_CONSTANTS = {"0", "1", "2", "3", "4", "6", "10", "12", "24", "52", "100", "360", "365", "366", "1000", "1000000",
                      "8760", "8784", "1000000000"}

ROLE_KEYWORDS = [
    ("input", ("input", "assumption", "driver", "scenario", "sensitivit", "macro", "parameters")),
    ("debt_schedule", ("debt", "loan", "financing", "facility", "funding", "repayment", "interest")),
    ("financial_statements", ("p&l", "pnl", "income", "profit", "balance", "bs", "cash flow", "cashflow", "cf",
                              "is", "financial statement", "fs", "statements")),
    ("output", ("summary", "dashboard", "output", "returns", "ratio", "cover", "kpi", "results")),
    ("calculation", ("calc", "working", "ops", "operation", "revenue", "opex", "capex", "tax", "depreciation",
                     "construction", "wc", "working capital")),
]


def col_letter(idx: int) -> str:
    from openpyxl.utils import get_column_letter

    return get_column_letter(idx)


def _col_index(letters: str) -> int:
    from openpyxl.utils import column_index_from_string

    return column_index_from_string(letters)


def relative_formula(formula: str, row: int, col: int) -> str:
    """Express a formula relative to its own cell (like Excel's R1C1 notation).

    "=D10-D11" in E12 and "=E10-E11" in F12 both become "=R[-2]C[-1]-R[-1]C[-1]",
    which lets us spot a formula that breaks the pattern of its row.
    """
    body = _STRING_LIT_RE.sub('""', formula)

    def repl(m: re.Match) -> str:
        abs_c, letters, abs_r, num = m.groups()
        c = _col_index(letters)
        r = int(num)
        rr = f"R{r}" if abs_r else f"R[{r - row}]"
        cc = f"C{c}" if abs_c else f"C[{c - col}]"
        return rr + cc

    return _REF_RE.sub(repl, body)


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _period_label(v) -> str | None:
    if isinstance(v, (datetime, date)):
        return v.strftime("%b-%Y") if isinstance(v, datetime) else v.isoformat()
    if _is_number(v) and float(v).is_integer() and 1990 <= v <= 2100:
        return str(int(v))
    if isinstance(v, str) and _YEAR_RE.match(v.strip()):
        return v.strip()
    return None


def _classify_role(sheet: SheetInfo, labels_text: str) -> tuple[str, str]:
    name = sheet.name.lower()
    tokens = set(re.split(r"[^a-z&]+", name))
    for role, words in ROLE_KEYWORDS:
        for w in words:
            # Short words must match a whole word ("IS", "BS"); longer ones the
            # start of a word ("assumption" matches "Assumptions", but "ratio"
            # must not match "Operations").
            if (len(w) <= 3 and w in tokens) or (len(w) > 3 and re.search(r"(?<![a-z])" + re.escape(w), name)):
                return role, f"sheet name contains '{w}'"
    lt = labels_text.lower()
    if "total assets" in lt and ("total liabilities" in lt or "equity" in lt):
        return "financial_statements", "contains balance-sheet line items"
    if "dscr" in lt or ("opening balance" in lt and "repayment" in lt):
        return "debt_schedule", "contains debt-service line items"
    total = sheet.n_formulas + sheet.n_numeric_inputs
    if total == 0:
        return "notes/text", "no numbers"
    share = sheet.n_formulas / total
    if share < 0.2:
        return "input", f"{share:.0%} of numeric cells are formulas (mostly hard-coded inputs)"
    if share > 0.6:
        return "calculation", f"{share:.0%} of numeric cells are formulas"
    return "mixed", f"{share:.0%} of numeric cells are formulas"


def _open_workbooks(filename: str, data: bytes):
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException

    lower = filename.lower()
    if lower.endswith(".xls") or lower.endswith(".xlsb"):
        raise UnsupportedFileError(
            f"'{filename}' uses an older/binary Excel format (.xls/.xlsb). "
            "Please open it in Excel and 'Save As' .xlsx, then upload again."
        )
    if data[:8] == OLE_SIGNATURE:
        # Modern Excel files are ZIP archives; an OLE container with an .xlsx
        # name means the workbook is encrypted with a password.
        raise PasswordProtectedError(
            f"'{filename}' is password-protected (encrypted). Please upload an unlocked copy."
        )
    try:
        keep_vba = lower.endswith(".xlsm")
        wb_f = openpyxl.load_workbook(io.BytesIO(data), data_only=False, keep_vba=keep_vba)
        wb_v = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, ValueError, OSError, TypeError) as exc:
        raise CorruptFileError(
            f"'{filename}' could not be opened as an Excel workbook. It may be damaged "
            "or not a genuine .xlsx file.",
            detail=type(exc).__name__,
        ) from None
    return wb_f, wb_v


def read_excel(filename: str, data: bytes) -> SourceDocument:
    wb_f, wb_v = _open_workbooks(filename, data)
    doc = SourceDocument(filename=filename, kind="excel", size_bytes=len(data))
    info = WorkbookInfo()
    doc.workbook = info

    try:
        for name, dn in wb_f.defined_names.items():
            info.defined_names[name] = str(dn.attr_text)[:120]
    except Exception:
        pass
    try:
        info.external_links = [str(getattr(l.file_link, "Target", "external file")) for l in wb_f._external_links]
    except Exception:
        info.external_links = []

    total_formulas = 0
    formulas_missing_cache = 0
    cells_scanned = 0
    cell_budget = settings.max_excel_cells

    for ws in wb_f.worksheets:
        wv = wb_v[ws.title]
        sheet = SheetInfo(
            name=ws.title,
            dimensions=ws.dimensions,
            max_row=ws.max_row,
            max_col=ws.max_column,
            hidden=ws.sheet_state != "visible",
        )
        info.sheets.append(sheet)
        if cells_scanned > cell_budget:
            sheet.role, sheet.role_reason = "not inspected", "workbook too large for prototype limit"
            continue

        label_cols: Counter = Counter()
        unit_hits: list[str] = []
        header_candidates: list[tuple[int, list[tuple[str, str]]]] = []
        raw_rows: list[tuple[int, str, str, list[CellValue]]] = []
        referenced: set[str] = set()
        labels_text_parts: list[str] = []

        for row_cells in ws.iter_rows():
            r = row_cells[0].row
            label_parts: list[str] = []
            label_col = None
            row_unit = ""
            cells: list[CellValue] = []
            periods: list[tuple[str, str]] = []
            for cell in row_cells:
                v = cell.value
                if v is None:
                    continue
                cells_scanned += 1
                ref = cell.coordinate
                cached = wv[ref].value
                is_formula = cell.data_type == "f" or (isinstance(v, str) and v.startswith("="))
                if is_formula:
                    f = str(v) if not hasattr(v, "text") else str(v.text)
                    sheet.n_formulas += 1
                    total_formulas += 1
                    if cached is None:
                        formulas_missing_cache += 1
                    for m in _SHEET_REF_RE.finditer(_STRING_LIT_RE.sub("", f)):
                        referenced.add(m.group(1) or m.group(2))
                    if "[" in f and "]" in f and "!" in f:
                        info.issues.append(ModelIssue("External link", f"{ws.title}!{ref}",
                                                      f"Formula refers to another workbook: {f[:80]}", "High"))
                    if isinstance(cached, str) and cached.strip() in EXCEL_ERRORS:
                        sheet.error_cells.append(f"{ref} ({cached.strip()})")
                    if cached is not None and (pl := _period_label(cached)):
                        periods.append((cell.column_letter, pl))
                    cells.append(CellValue(ref=ref, value=cached, formula=f))
                elif _is_number(v):
                    sheet.n_numeric_inputs += 1
                    if (pl := _period_label(v)):
                        periods.append((cell.column_letter, pl))
                    cells.append(CellValue(ref=ref, value=v))
                elif isinstance(v, (datetime, date)):
                    sheet.n_dates += 1
                    periods.append((cell.column_letter, _period_label(v) or str(v)))
                    cells.append(CellValue(ref=ref, value=_period_label(v)))
                elif isinstance(v, str):
                    s = " ".join(v.split())
                    if s in EXCEL_ERRORS:
                        sheet.error_cells.append(f"{ref} ({s})")
                        continue
                    sheet.n_text += 1
                    if (pl := _period_label(s)):
                        periods.append((cell.column_letter, pl))
                        continue
                    if r <= 12 and _UNIT_RE.search(s):
                        unit_hits.append(s[:60])
                    if not cells and cell.column <= 6:
                        if label_parts and _ROW_UNIT_RE.match(s):
                            row_unit = s
                        else:
                            label_parts.append(s)
                            label_col = label_col or cell.column_letter
                    elif not cells and _ROW_UNIT_RE.match(s):
                        row_unit = s
            if len(periods) >= 3:
                header_candidates.append((r, periods))
            label = " / ".join(label_parts)[:100]
            if label:
                labels_text_parts.append(label)
            if label and label_col:
                label_cols[label_col] += 1
            numeric_cells = [c for c in cells if c.is_formula or _is_number(c.value)]
            if label and numeric_cells:
                raw_rows.append((r, label, row_unit, numeric_cells))

        # Timeline: the first row containing 3+ period labels (years/dates).
        if header_candidates:
            r, periods = max(header_candidates[:5], key=lambda hc: len(hc[1]))
            sheet.period_header = periods
            header_rows = {r}
        else:
            header_rows = set()
        sheet.label_col = label_cols.most_common(1)[0][0] if label_cols else "A"
        sheet.units = list(dict.fromkeys(unit_hits))[:5]
        sheet.referenced_sheets = sorted(x for x in referenced if x != ws.title)
        period_cols = {c for c, _ in sheet.period_header}

        for r, label, unit, cells in raw_rows:
            if r in header_rows:
                continue
            kinds = {c.is_formula for c in cells}
            kind = "formula" if kinds == {True} else "input" if kinds == {False} else "mixed"
            row = RowInfo(sheet=ws.title, row=r, label=label, kind=kind, cells=cells, unit=unit)
            sheet.rows.append(row)
            _check_row(row, period_cols, info)

        sheet.role, sheet.role_reason = _classify_role(sheet, " ".join(labels_text_parts))
        if sheet.error_cells:
            info.issues.append(ModelIssue(
                "Excel error values", f"{ws.title}",
                f"{len(sheet.error_cells)} cell(s) show errors, e.g. {', '.join(sheet.error_cells[:5])}", "High"))
        if sheet.hidden:
            info.issues.append(ModelIssue("Hidden sheet", ws.title,
                                          "Sheet is hidden; review whether it contains relevant inputs.", "Low"))

    if cells_scanned > cell_budget:
        doc.warnings.append(
            f"Workbook is very large; inspection stopped after ~{cell_budget:,} cells. "
            "Later sheets were listed but not inspected."
        )
    for link in info.external_links:
        info.issues.append(ModelIssue("External workbook link", "Workbook", f"Linked to {link}", "High"))

    if total_formulas and formulas_missing_cache / total_formulas > 0.5:
        info.has_cached_values = False
        doc.warnings.append(
            "Most formulas have no saved results (the file was probably generated by software, "
            "not saved from Excel). Calculated values may be missing: open the file in Excel, "
            "save it, and re-upload for complete figures."
        )
    if sum(s.n_formulas + s.n_numeric_inputs for s in info.sheets) == 0:
        raise EmptyDocumentError(f"'{filename}' contains no numbers or formulas to analyse.")
    return doc


def _check_row(row: RowInfo, period_cols: set[str], info: WorkbookInfo) -> None:
    """Deterministic checks on one row of a model."""
    loc = row.sheet
    cells = [c for c in row.cells if not period_cols or re.sub(r"\d", "", c.ref) in period_cols]
    formulas = [c for c in cells if c.is_formula]
    constants = [c for c in cells if not c.is_formula and _is_number(c.value)]

    # 1) Hard-coded numbers inside a row that is otherwise formulas.
    if len(formulas) >= 3 and constants:
        first_ref = cells[0].ref if cells else ""
        for c in constants[:5]:
            opening = c.ref == first_ref
            info.issues.append(ModelIssue(
                "Hard-coded value in formula row",
                f"{loc}!{c.ref}",
                f"'{row.label}': value {c.value:,} is typed in while {len(formulas)} other cells in "
                f"the row are formulas" + (" (first period – may be an opening balance)" if opening else ""),
                "Low" if opening else "Medium",
            ))

    # 2) A formula that breaks the pattern of the rest of the row.
    if len(formulas) >= 4:
        patterns = []
        for c in formulas:
            col = _col_index(re.sub(r"\d", "", c.ref))
            patterns.append((c, relative_formula(c.formula or "", row.row, col)))
        common, freq = Counter(p for _, p in patterns).most_common(1)[0]
        if freq >= len(patterns) * 0.6:
            for idx, (c, p) in enumerate(patterns):
                if p != common and idx != 0:  # first period often differs legitimately
                    info.issues.append(ModelIssue(
                        "Inconsistent formula in row",
                        f"{loc}!{c.ref}",
                        f"'{row.label}': {c.formula} differs from the pattern used in "
                        f"{freq} of {len(patterns)} cells in this row",
                        "Medium",
                    ))

    # 3) Constants embedded inside formulas (e.g. =D10*1.17).
    for c in formulas[:1] + formulas[1:]:
        body = _STRING_LIT_RE.sub("", c.formula or "")
        body = _REF_RE.sub("", body)
        consts = [k for k in _EMBEDDED_CONST_RE.findall(body) if k not in _BENIGN_CONSTANTS]
        if consts:
            info.issues.append(ModelIssue(
                "Constant embedded in formula",
                f"{loc}!{c.ref}",
                f"'{row.label}': {c.formula[:80]} contains hard-coded number(s) {', '.join(consts[:3])}",
                "Low",
            ))
            break  # one per row is enough
