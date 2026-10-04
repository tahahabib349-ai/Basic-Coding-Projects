"""Generate a FICTIONAL sample transaction for testing.

All names, figures and terms are invented. The data deliberately contains:
  * gaps (no credit rating, no sensitivity analysis, undefined "Material Adverse Effect"),
  * an inconsistency (DSCR covenant 1.20x in the term sheet vs 1.10x in the facility agreement),
  * planted model errors (a hard-coded O&M cost, an inconsistent insurance formula
    with an embedded constant),
so we can check that the analyst detects them.

Run:  python sample_data/generate_samples.py
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent
styles = getSampleStyleSheet()
H1, H2, BODY = styles["Heading1"], styles["Heading2"], styles["BodyText"]


def _table(rows):
    t = Table(rows, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    return t


def _pdf(path: Path, story):
    SimpleDocTemplate(str(path), pagesize=A4, title=path.stem).build(story)


def P(text):
    return Paragraph(text, BODY)


# ---------------------------------------------------------------------------
def information_memorandum():
    s = [
        Paragraph("INFORMATION MEMORANDUM", H1),
        Paragraph("Thar Sun Power (Private) Limited – 150 MW Solar PV Project", H2),
        P("Strictly private and confidential. Prepared by the Arranger for discussion purposes only. "
          "All parties and figures in this document are fictional."),
        Paragraph("1. EXECUTIVE SUMMARY", H2),
        P("Thar Sun Power (Private) Limited (the <b>Company</b>) is developing a 150 MW solar photovoltaic "
          "power plant in District Tharparkar, Sindh, Pakistan (the <b>Project</b>). The total project cost is "
          "estimated at PKR 24,000 million, to be financed through senior debt of PKR 18,000 million and "
          "sponsor equity of PKR 6,000 million (debt:equity of 75:25)."),
        P("The Company seeks a syndicated long-term senior secured facility of PKR 18,000 million. "
          "The Arranger invites participating banks to commit a minimum ticket of PKR 2,000 million."),
        P("Electricity will be sold to the Central Power Purchasing Agency (Guarantee) Limited under a "
          "25-year Energy Purchase Agreement (EPA) on a take-and-pay basis at a levelised reference "
          "tariff of PKR 26.00 per kWh, indexed annually at 3.0%."),
        Paragraph("2. SPONSORS", H2),
        P("The Project is sponsored by Indus Renewable Holdings Limited (70%) and Karachi Infrastructure "
          "Partners (30%). Indus Renewable Holdings currently operates 300 MW of wind assets in Jhimpir. "
          "Audited financial statements of the sponsors have not been included in this memorandum."),
        PageBreak(),
        Paragraph("3. PROJECT OVERVIEW", H2),
        P("Commercial Operations Date (COD) is targeted for 1 July 2026 following an 18-month construction "
          "period. The EPC contractor is SinoSolar Engineering Co. under a fixed-price, date-certain "
          "turnkey EPC contract. Delay liquidated damages are capped at 10% of the EPC price. "
          "Operations and maintenance will be performed by the EPC contractor under a 5-year O&amp;M agreement."),
        P("Expected net capacity factor is 22.0% (P50), with annual module degradation of 0.5%. "
          "An independent energy yield assessment has been commissioned but is not yet available."),
        Paragraph("4. PROJECT COST AND FINANCING PLAN", H2),
        _table([
            ["Uses of funds", "PKR million"],
            ["EPC cost", "20,500"],
            ["Development costs", "1,200"],
            ["Interest during construction", "1,800"],
            ["Financing fees", "500"],
            ["Total project cost", "24,000"],
        ]),
        Spacer(1, 8),
        _table([
            ["Sources of funds", "PKR million", "%"],
            ["Senior debt", "18,000", "75%"],
            ["Sponsor equity", "6,000", "25%"],
            ["Total sources", "24,000", "100%"],
        ]),
        PageBreak(),
        Paragraph("5. FINANCIAL HIGHLIGHTS (BASE CASE)", H2),
        P("Figures below are extracted from the Sponsor's base case financial model (PKR million)."),
        _table([
            ["Item", "FY2027", "FY2028", "FY2029"],
            ["Revenue", "7,516", "7,703", "7,895"],
            ["EBITDA", "6,466", "6,580", "6,694"],
            ["Senior debt outstanding (year end)", "16,200", "14,400", "12,600"],
        ]),
        Spacer(1, 8),
        P("The base case projects a minimum DSCR of 1.53x and an average DSCR of 1.86x over the loan life."),
        Paragraph("6. KEY RISKS", H2),
        P("Key risks include construction delay, circular debt in the power sector leading to delayed "
          "payments by the power purchaser, KIBOR interest-rate movements, PKR depreciation affecting "
          "imported equipment cost, and solar resource variability. A sovereign guarantee from the "
          "Government of Pakistan is expected under the Implementation Agreement."),
    ]
    _pdf(OUT / "Information_Memorandum_Thar_Sun.pdf", s)


def term_sheet():
    s = [
        Paragraph("INDICATIVE TERM SHEET", H1),
        Paragraph("PKR 18,000 Million Senior Secured Syndicated Term Finance Facility", H2),
        P("Fictional – for testing only. Subject to credit approval and documentation."),
        _table([
            ["Term", "Description"],
            ["Borrower", "Thar Sun Power (Private) Limited"],
            ["Facility amount", "PKR 18,000 million"],
            ["Purpose", "Part-financing the 150 MW solar PV project"],
            ["Tenor", "12 years from first drawdown, including 2-year grace period"],
            ["Repayment", "20 equal semi-annual instalments after the grace period"],
            ["Pricing", "6-month KIBOR + 2.25% per annum"],
            ["Upfront fee", "0.75% of the Facility amount"],
            ["Commitment fee", "0.50% p.a. on undrawn amounts"],
            ["Debt:Equity", "Maximum 75:25"],
        ]),
        Paragraph("Security", H2),
        P("First-ranking mortgage over project land and plant; hypothecation of all present and future "
          "movable assets; assignment of project documents (EPA, IA, EPC, O&amp;M) and insurance proceeds; "
          "pledge of 100% of sponsor shares; lien over Project Accounts."),
        Paragraph("Sponsor Support", H2),
        P("Sponsor support for cost overruns to be agreed. Sponsors to provide an equity commitment letter "
          "backed by a standby letter of credit."),
        PageBreak(),
        Paragraph("Conditions Precedent", H2),
        P("Usual for transactions of this nature, including: executed finance documents; EPA and IA in "
          "full force; evidence of equity injection pro rata; legal opinions; insurance certificates; "
          "satisfactory lenders' technical adviser report."),
        Paragraph("Financial Covenants", H2),
        P("Minimum DSCR of 1.20x tested semi-annually on a historical 12-month basis. "
          "Distribution lock-up if DSCR falls below 1.15x. Maximum Debt:Equity of 75:25."),
        Paragraph("Events of Default", H2),
        P("Non-payment (3 business days grace); breach of financial covenants; misrepresentation; "
          "cross-default; insolvency; termination of any material project document; Material Adverse Effect; "
          "change of control without lender consent."),
        Paragraph("Governing Law", H2),
        P("Laws of Pakistan; courts of Karachi."),
    ]
    _pdf(OUT / "Term_Sheet_Thar_Sun.pdf", s)


def facility_agreement():
    s = [
        Paragraph("SYNDICATED TERM FINANCE AGREEMENT (EXTRACT)", H1),
        P("Fictional extract for testing. Between Thar Sun Power (Private) Limited as Borrower and the "
          "Financial Institutions listed in Schedule 1 as Lenders, with Fictional Bank Limited as Agent."),
        Paragraph("1. DEFINITIONS", H2),
        P("1.1 \"Finance Documents\" means this Agreement, the Security Documents, the Intercreditor "
          "Agreement and any fee letter."),
        P("1.2 \"Material Adverse Effect\" means a material adverse effect on the Borrower."),
        P("1.3 \"Project Documents\" means the EPA, the IA, the EPC Contract and the O&amp;M Agreement."),
        Paragraph("4. CONDITIONS PRECEDENT", H2),
        P("4.1 The Lenders shall not be obliged to fund any Drawdown unless the Agent has received the "
          "documents listed in Schedule 2 in form and substance satisfactory to the Agent."),
        P("4.2 The Agent may waive any condition precedent with the consent of the Majority Lenders."),
        PageBreak(),
        Paragraph("18. FINANCIAL COVENANTS", H2),
        P("18.1 The Borrower shall ensure that the Debt Service Coverage Ratio for each Calculation Period "
          "is not less than 1.10:1."),
        P("18.2 The Borrower shall not make any Distribution unless the DSCR for the preceding Calculation "
          "Period is at least 1.15:1 and no Event of Default is continuing."),
        P("18.3 The Debt to Equity ratio shall not exceed 75:25 at any time."),
        Paragraph("22. EVENTS OF DEFAULT", H2),
        P("22.1 Non-payment: the Borrower does not pay any amount due within three Business Days of its due date."),
        P("22.2 Financial covenants: any requirement of Clause 18 is not satisfied, subject to an equity cure "
          "right exercisable not more than twice during the life of the Facility."),
        P("22.3 Cross default: any Financial Indebtedness of the Borrower is not paid when due."),
        P("22.4 Material Adverse Change: any event occurs which the Majority Lenders reasonably believe has "
          "or is reasonably likely to have a Material Adverse Effect."),
        P("22.5 Acceleration: on and at any time after the occurrence of an Event of Default the Agent may, "
          "and shall if so directed by the Majority Lenders, declare all amounts outstanding immediately due."),
        Paragraph("24. CHANGE OF CONTROL", H2),
        P("24.1 Indus Renewable Holdings Limited shall maintain at least 51% of the shares of the Borrower "
          "until the Final Maturity Date."),
        Paragraph("27. ASSIGNMENT", H2),
        P("27.1 A Lender may assign any of its rights to another bank or financial institution with the "
          "consent of the Borrower, such consent not to be unreasonably withheld."),
        Paragraph("30. MAJORITY LENDERS", H2),
        P("30.1 \"Majority Lenders\" means Lenders whose commitments aggregate more than 66.67% of total "
          "commitments."),
    ]
    _pdf(OUT / "Facility_Agreement_Extract_Thar_Sun.pdf", s)


# ---------------------------------------------------------------------------
def financial_model(path: Path):
    years = list(range(2027, 2039))  # 12 operating years
    cols = [chr(ord("C") + i) for i in range(len(years))]  # C..N
    wb = Workbook()
    bold = Font(bold=True)

    inp = wb.active
    inp.title = "Inputs"
    inp["A1"] = "Thar Sun Power – Base Case Assumptions (fictional)"
    inp["A1"].font = bold
    inp["A2"] = "All amounts in PKR mn unless stated"
    rows = [
        ("Installed capacity", "MW", 150),
        ("Net capacity factor (P50)", "%", 0.22),
        ("Annual degradation", "%", 0.005),
        ("Reference tariff (Year 1)", "PKR/kWh", 26.0),
        ("Tariff indexation", "%", 0.03),
        ("O&M cost (Year 1)", "PKR mn", 900),
        ("Insurance cost (Year 1)", "PKR mn", 150),
        ("Opex escalation", "%", 0.07),
        ("EPC cost", "PKR mn", 20500),
        ("Development costs", "PKR mn", 1200),
        ("Interest during construction", "PKR mn", 1800),
        ("Financing fees", "PKR mn", 500),
        ("Total project cost", "PKR mn", "=SUM(C12:C15)"),
        ("Senior debt share", "%", 0.75),
        ("Senior debt", "PKR mn", "=C16*C17"),
        ("Sponsor equity", "PKR mn", "=C16-C18"),
        ("KIBOR", "%", 0.1125),
        ("Margin", "%", 0.0225),
        ("All-in interest rate", "%", "=C20+C21"),
        ("Repayment period", "years", 10),
        ("Tax rate (exempt)", "%", 0),
        ("Depreciation life", "years", 25),
    ]
    for i, (label, unit, val) in enumerate(rows, start=4):
        inp[f"A{i}"], inp[f"B{i}"], inp[f"C{i}"] = label, unit, val
    # Row map: C4 capacity, C5 CF, C6 degr, C7 tariff, C8 index, C9 O&M, C10 ins, C11 esc,
    # C12-15 costs, C16 total, C17 debt%, C18 debt, C19 equity, C20 KIBOR, C21 margin,
    # C22 rate, C23 repay yrs, C24 tax, C25 dep life
    # Grace years: operating repayment begins in FY2027 (grace covered construction).

    def header(ws, title):
        ws["A1"] = title
        ws["A1"].font = bold
        ws["A2"] = "PKR mn"
        ws["A3"] = "Fiscal year"
        for c, y in zip(cols, years):
            ws[f"{c}3"] = y
            ws[f"{c}3"].font = bold

    ops = wb.create_sheet("Operations")
    header(ops, "Operations")
    labels = {5: ("Operating year", "#"), 6: ("Energy generated", "GWh"), 7: ("Tariff", "PKR/kWh"),
              8: ("Revenue", "PKR mn"), 10: ("O&M cost", "PKR mn"), 11: ("Insurance", "PKR mn"),
              12: ("Total operating costs", "PKR mn"), 14: ("EBITDA", "PKR mn"), 15: ("EBITDA margin", "%")}
    for r, (l, u) in labels.items():
        ops[f"A{r}"], ops[f"B{r}"] = l, u
    for i, c in enumerate(cols):
        p = cols[i - 1] if i else None
        ops[f"{c}5"] = i + 1 if i == 0 else f"={p}5+1"
        ops[f"{c}6"] = f"=Inputs!$C$4*8760*Inputs!$C$5*(1-Inputs!$C$6)^({c}5-1)/1000"
        ops[f"{c}7"] = f"=Inputs!$C$7*(1+Inputs!$C$8)^({c}5-1)"
        ops[f"{c}8"] = f"={c}6*{c}7"
        ops[f"{c}10"] = f"=Inputs!$C$9*(1+Inputs!$C$11)^({c}5-1)"
        ops[f"{c}11"] = f"=Inputs!$C$10*(1+Inputs!$C$11)^({c}5-1)"
        ops[f"{c}12"] = f"={c}10+{c}11"
        ops[f"{c}14"] = f"={c}8-{c}12"
        ops[f"{c}15"] = f"={c}14/{c}8"
    # PLANTED ERROR 1: hard-coded O&M cost in FY2032 (column H)
    ops["H10"] = 1100
    # PLANTED ERROR 2: inconsistent insurance formula with embedded constant in FY2035 (column K)
    ops["K11"] = "=J11*1.05"

    debt = wb.create_sheet("Debt Schedule")
    header(debt, "Senior Debt Schedule")
    dl = {5: "Opening balance", 6: "Repayment", 7: "Closing balance", 9: "Interest",
          10: "Total debt service", 12: "CFADS", 13: "DSCR"}
    for r, l in dl.items():
        debt[f"A{r}"] = l
    debt["B13"] = "x"
    for i, c in enumerate(cols):
        p = cols[i - 1] if i else None
        debt[f"{c}5"] = "=Inputs!$C$18" if i == 0 else f"={p}7"
        debt[f"{c}6"] = f"=MIN({c}5,Inputs!$C$18/Inputs!$C$23)"
        debt[f"{c}7"] = f"={c}5-{c}6"
        debt[f"{c}9"] = f"={c}5*Inputs!$C$22"
        debt[f"{c}10"] = f"={c}6+{c}9"
        debt[f"{c}12"] = f"=Operations!{c}14-'Financial Statements'!{c}10"
        debt[f"{c}13"] = f"=IF({c}10>0,{c}12/{c}10,\"n/a\")"

    fs = wb.create_sheet("Financial Statements")
    header(fs, "Financial Statements")
    fl = {4: "INCOME STATEMENT", 5: "Revenue", 6: "Operating costs", 7: "EBITDA", 8: "Depreciation",
          9: "Interest expense", 10: "Tax", 11: "Net profit", 13: "CASH FLOW", 14: "Cash flow before debt service",
          15: "Debt service", 16: "Net cash flow", 17: "Closing cash", 19: "BALANCE SHEET",
          20: "Net fixed assets", 21: "Cash", 22: "Total assets", 23: "Senior debt", 24: "Share capital",
          25: "Retained earnings", 26: "Total liabilities and equity", 27: "Balance check"}
    for r, l in fl.items():
        fs[f"A{r}"] = l
    for i, c in enumerate(cols):
        p = cols[i - 1] if i else None
        fs[f"{c}5"] = f"=Operations!{c}8"
        fs[f"{c}6"] = f"=-Operations!{c}12"
        fs[f"{c}7"] = f"={c}5+{c}6"
        fs[f"{c}8"] = "=-Inputs!$C$16/Inputs!$C$25"
        fs[f"{c}9"] = f"=-'Debt Schedule'!{c}9"
        fs[f"{c}10"] = f"=MAX(0,({c}7+{c}8+{c}9)*Inputs!$C$24)"
        fs[f"{c}11"] = f"={c}7+{c}8+{c}9-{c}10"
        fs[f"{c}14"] = f"={c}7-{c}10"
        fs[f"{c}15"] = f"=-'Debt Schedule'!{c}10"
        fs[f"{c}16"] = f"={c}14+{c}15"
        fs[f"{c}17"] = f"={c}16" if i == 0 else f"={p}17+{c}16"
        fs[f"{c}20"] = f"=Inputs!$C$16+{c}8" if i == 0 else f"={p}20+{c}8"
        fs[f"{c}21"] = f"={c}17"
        fs[f"{c}22"] = f"={c}20+{c}21"
        fs[f"{c}23"] = f"='Debt Schedule'!{c}7"
        fs[f"{c}24"] = "=Inputs!$C$19"
        fs[f"{c}25"] = f"={c}11" if i == 0 else f"={p}25+{c}11"
        fs[f"{c}26"] = f"={c}23+{c}24+{c}25"
        fs[f"{c}27"] = f"={c}22-{c}26"

    summ = wb.create_sheet("Summary")
    summ["A1"] = "Key Outputs"
    summ["A1"].font = bold
    items = [
        ("Total project cost (PKR mn)", "=Inputs!C16"),
        ("Senior debt (PKR mn)", "=Inputs!C18"),
        ("Sponsor equity (PKR mn)", "=Inputs!C19"),
        ("Minimum DSCR (x)", "=MIN('Debt Schedule'!C13:N13)"),
        ("Average DSCR (x)", "=AVERAGE('Debt Schedule'!C13:N13)"),
        ("Year 1 EBITDA (PKR mn)", "=Operations!C14"),
    ]
    for i, (l, f) in enumerate(items, start=3):
        summ[f"A{i}"], summ[f"B{i}"] = l, f

    for ws in wb.worksheets:
        ws.column_dimensions["A"].width = 34
    tmp = Path(tempfile.mkdtemp())
    raw = tmp / path.name
    wb.save(raw)
    recalc_with_libreoffice(raw, path)


def recalc_with_libreoffice(src: Path, dest: Path) -> None:
    """Open and re-save via LibreOffice so formula results are stored, like a
    file saved from Excel. Falls back to the un-calculated file if unavailable."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        shutil.copy(src, dest)
        print("LibreOffice not found: saved without calculated values.")
        return
    outdir = Path(tempfile.mkdtemp())
    subprocess.run([soffice, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(outdir), str(src)],
                   check=True, capture_output=True, timeout=180)
    shutil.copy(outdir / src.name, dest)


if __name__ == "__main__":
    information_memorandum()
    term_sheet()
    facility_agreement()
    financial_model(OUT / "Financial_Model_Thar_Sun.xlsx")
    print("Sample files written to", OUT)
