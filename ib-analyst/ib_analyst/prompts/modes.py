"""The four analysis modes: required sections and mode-specific guidance.

To change what a report contains, edit the section lists or guidance here; no
other part of the application needs to change. To add a new mode, add a new
`AnalysisMode` to MODES.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalysisMode:
    key: str
    title: str
    description: str
    sections: tuple[str, ...]
    guidance: str
    include_issues: bool = False
    issues_title: str = "Key Issues"
    # Words used to pick the most relevant PDF pages when material is too large.
    keywords: tuple[str, ...] = field(default_factory=tuple)
    concise: bool = False


FINANCIAL_MODEL_REVIEW = AnalysisMode(
    key="financial_model_review",
    title="Financial Model Review",
    description="Inspect an Excel financial model: structure, assumptions, debt, cash flows, ratios and potential errors.",
    sections=(
        "Model Structure",
        "Key Assumptions",
        "Revenue Assumptions",
        "Operating Costs",
        "CAPEX and Project Cost",
        "Working Capital",
        "Financing Assumptions",
        "Debt Schedule: Interest and Repayment",
        "Financial Statements and Cash Flows",
        "Key Metrics: EBITDA, Margins, Leverage, DSCR, Debt/Equity",
        "Funding Structure",
        "Sensitivities",
        "Potential Inconsistencies and Model Errors",
        "Unusual Assumptions",
        "Missing Information",
        "Overall Assessment",
    ),
    guidance="""MODE: FINANCIAL MODEL REVIEW
Review the workbook as a model auditor working for the lender.
- Describe the model structure from the WORKBOOK STRUCTURE block (sheet roles, flow of calculations,
  timeline, units). Distinguish hard-coded inputs from formulas and outputs.
- For assumptions, cite the input cell (e.g. "Model.xlsx › Inputs!C7").
- The AUTOMATED MODEL CHECKS block lists findings produced by code (hard-codes in formula rows,
  inconsistent formulas, error values, external links, balance checks). Explain the significance of each
  material finding; do not invent other errors. You may add INFERENCE points for assumptions that look
  aggressive or unusual relative to the rest of the model, explaining why.
- If an item (e.g. working capital, sensitivities, tax) is not modelled, label it MISSING.
- In "issues", list each material model issue with its cell location, why it matters to a lender,
  risk rating and the question to put to the model owner.""",
    include_issues=True,
    issues_title="Model Issues Log",
    keywords=("assumption", "revenue", "tariff", "capex", "project cost", "ebitda", "dscr", "debt", "model"),
)

CREDIT_REVIEW = AnalysisMode(
    key="credit_review",
    title="Credit / Transaction Review",
    description="Lender's credit analysis of a proposed financing: structure, terms, metrics, risks, mitigants, DD gaps.",
    sections=(
        "Executive Summary",
        "Transaction Overview",
        "Company / Sponsor Overview",
        "Project Overview",
        "Transaction Structure",
        "Sources & Uses",
        "Financing Structure",
        "Debt Terms",
        "Pricing",
        "Tenor",
        "Repayment",
        "Security Package",
        "Financial Analysis",
        "Key Credit Metrics",
        "Key Strengths",
        "Key Risks",
        "Mitigants",
        "Conditions Precedent",
        "Key Covenants",
        "Due-Diligence Issues",
        "Outstanding Information",
        "Questions for Management / Client",
        "Analyst Conclusion",
    ),
    guidance="""MODE: CREDIT / TRANSACTION REVIEW
Write as the lender's credit analyst preparing a credit paper.
- Key Credit Metrics must use the CALCULATED METRICS block (label CALCULATED). Compare them against
  covenant levels stated in the documents where available (e.g. minimum DSCR covenant) and comment on
  headroom qualitatively; do not compute headroom yourself unless provided.
- Key Strengths, Key Risks and Mitigants are INFERENCE unless directly stated in the material; tie each
  to supporting evidence (cite the source of the underlying fact).
- Flag inconsistencies between documents (e.g. different covenant levels in term sheet vs agreement).
- Outstanding Information and Questions for Management must be specific to gaps you identified.
- Analyst Conclusion: balanced view and what must be resolved before credit approval. Do not
  recommend approval or rejection as a fact; frame it as INFERENCE.""",
    keywords=("facility", "tenor", "pricing", "margin", "security", "covenant", "dscr", "sponsor", "risk",
              "repayment", "project cost", "equity", "guarantee", "condition"),
)

LEGAL_DD_REVIEW = AnalysisMode(
    key="legal_dd_review",
    title="Legal / Due-Diligence Review",
    description="Lender-side review of facility agreements, term sheets and project documents for protections and gaps.",
    sections=(
        "Documents Reviewed",
        "Conditions Precedent",
        "Representations and Warranties",
        "Undertakings",
        "Financial Covenants",
        "Information Covenants",
        "Events of Default, Cure Periods and Materiality",
        "Security, Guarantees and Sponsor Support",
        "Accounts Structure and Cash Waterfall",
        "Intercreditor, Voting Thresholds and Standstill",
        "Enforcement and Acceleration",
        "Assignment and Change of Control",
        "Insurance",
        "Project-Document Protections and Termination",
        "Missing Lender Protections",
        "Ambiguous Drafting and Internal Inconsistencies",
    ),
    guidance="""MODE: LEGAL / DUE-DILIGENCE REVIEW
Review the documents as the lender's transaction counsel / DD analyst (not as a court).
- Cite clause numbers ONLY when the clause number is printed in the text you rely on, together with the
  page (e.g. "Facility_Agreement.pdf p.2, clause 22.4"). Otherwise cite the page and say the clause
  number could not be identified. Never create clause numbers.
- For each topic, summarise what the documents provide (FACT) and assess adequacy from a lender's view
  (INFERENCE). Where a topic is not covered, label it MISSING.
- Look actively for: undefined or weak definitions (e.g. Material Adverse Effect), missing cure periods or
  thresholds (e.g. cross-default without threshold), borrower-friendly drafting, inconsistencies between
  the term sheet and the agreement, missing standard protections (e.g. DSRA, cash sweep, negative pledge,
  sanctions, step-in rights).
- In "issues", list every material issue with: issue, relevant provision/source, why it matters to the
  lender, risk rating (High/Medium/Low), and the recommended lender comment or question.""",
    include_issues=True,
    issues_title="Issues List",
    keywords=("clause", "condition", "covenant", "default", "security", "guarantee", "assignment", "control",
              "insurance", "waterfall", "account", "majority", "enforcement", "termination", "represent",
              "undertak", "intercreditor", "cure"),
)

IB_SUMMARY = AnalysisMode(
    key="ib_summary",
    title="Investment Banking Summary",
    description="Concise senior-management briefing on the transaction.",
    sections=(
        "Executive Summary",
        "Transaction",
        "Client / Sponsors",
        "Transaction Rationale",
        "Project / Business",
        "Total Project / Transaction Cost",
        "Financing Requirement",
        "Proposed Bank Participation",
        "Financing Structure",
        "Key Terms",
        "Financial Highlights",
        "Key Risks",
        "Mitigants",
        "Outstanding Matters",
        "Required Approvals / Decisions",
    ),
    guidance="""MODE: INVESTMENT BANKING SUMMARY
Write a briefing a senior banker can read in three minutes.
- Maximum 3 points per section (Executive Summary up to 5). Short sentences. Lead with numbers.
- "Key Terms" works well as a two-column table (Term, Detail).
- "Financial Highlights" should use FACT figures from documents and CALCULATED metrics.
- "Required Approvals / Decisions": what management must decide or approve, based on the material
  (INFERENCE), and any approvals mentioned in the documents (FACT).""",
    keywords=("summary", "transaction", "facility", "sponsor", "project cost", "financing", "tenor", "pricing",
              "ebitda", "revenue", "risk", "participation", "ticket"),
    concise=True,
)

MODES: dict[str, AnalysisMode] = {m.key: m for m in (FINANCIAL_MODEL_REVIEW, CREDIT_REVIEW, LEGAL_DD_REVIEW, IB_SUMMARY)}
