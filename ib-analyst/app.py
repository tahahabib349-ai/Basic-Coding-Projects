"""Investment Banking Analyst – web interface (Streamlit).

Run with:  streamlit run app.py
"""

from __future__ import annotations

import hashlib
import re

import pandas as pd
import streamlit as st

from ib_analyst.analysis.engine import run_analysis
from ib_analyst.calculations.metrics import fmt
from ib_analyst.config import find_api_key, get_logger, mask_secret, settings
from ib_analyst.errors import AnalystError
from ib_analyst.ingestion.loader import SUPPORTED_EXT, read_file
from ib_analyst.llm import get_provider
from ib_analyst.prompts.modes import MODES
from ib_analyst.reporting.render import (
    CSS, LABEL_HELP, PERIOD_COLS_UNITS, badge, issues_html, section_html, to_docx, to_html, to_json, to_markdown,
)

log = get_logger()
st.set_page_config(page_title="Investment Banking Analyst", page_icon="📊", layout="wide")

APP_CSS = """
<style>
.block-container{padding-top:2rem;max-width:1200px}
.iba-title{font-size:1.9rem;font-weight:700;color:#14365d;margin-bottom:0}
.iba-sub{color:#5a6878;margin-top:.1rem;margin-bottom:1.2rem}
.iba-step{font-weight:700;color:#14365d;font-size:1.05rem;margin:1.2rem 0 .3rem}
.iba-report h2{font-size:1.15rem}
</style>
"""
st.markdown(APP_CSS, unsafe_allow_html=True)
# Report styles (badges, tables) shared with the HTML export, scoped to the report area.
st.markdown("<style>" + re.sub(r"body\{[^}]*\}", "", CSS).replace(":root", ".iba-report") + "</style>",
            unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar – AI engine & key
# ---------------------------------------------------------------------------
def sidebar() -> dict:
    with st.sidebar:
        st.header("AI engine")
        engine = st.radio("Engine", ["Gemini", "Demo mode (no AI)"], index=0,
                          help="Demo mode runs everything except the AI commentary, without an API key.")
        cfg = {"provider": "gemini" if engine == "Gemini" else "demo"}
        if cfg["provider"] == "gemini":
            cfg["model"] = st.text_input("Gemini model", value=settings.gemini_model,
                                         help="e.g. gemini-3.5-flash (fast, economical) or a newer/pro model.")
            typed = st.text_input("API key (optional, this session only)", type="password",
                                  help="Not saved anywhere. For permanent setup use the .env file (see README).")
            st.session_state["session_key"] = typed
            key, where = find_api_key(typed)
            if key:
                st.success(f"Key found: {mask_secret(key)}\n\nSource: {where}")
            else:
                st.warning("No Gemini API key configured. Paste one above, add it to the .env file, or use "
                           "Demo mode.")
            if st.button("Test Gemini connection", use_container_width=True):
                with st.spinner("Contacting Gemini…"):
                    try:
                        msg = get_provider("gemini", session_key=typed, model=cfg["model"]).test_connection()
                        st.success(msg)
                    except AnalystError as exc:
                        st.error(exc.user_message)
        with st.expander("Advanced settings"):
            settings.max_context_chars = st.slider(
                "Max material sent to AI (thousand characters)", 50, 1500, settings.max_context_chars // 1000,
                step=50, help="≈ 4 characters per token. Larger = more complete but slower/costlier.") * 1000
        st.caption("Labels used in reports:")
        st.markdown("<div class='iba-report'>" + "<br>".join(f"{badge(k)}<small>{v}</small>"
                                                            for k, v in LABEL_HELP.items()) + "</div>",
                    unsafe_allow_html=True)
    return cfg


@st.cache_data(show_spinner=False, max_entries=64)
def ingest_cached(name: str, digest: str, data: bytes):
    """Read one file (cached by content, so re-runs are instant). Returns (document, error)."""
    try:
        return read_file(name, data), None
    except AnalystError as exc:
        return None, exc.user_message
    except Exception as exc:  # never show a stack trace
        log.exception("Unexpected ingestion error")
        return None, f"'{name}' could not be read due to an unexpected problem ({type(exc).__name__})."


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
cfg = sidebar()
st.markdown("<div class='iba-title'>Investment Banking Analyst</div>"
            "<div class='iba-sub'>Upload transaction materials, choose an analysis, and receive a sourced, "
            "verified analyst report.</div>", unsafe_allow_html=True)

st.markdown("<div class='iba-step'>1 · Upload materials</div>", unsafe_allow_html=True)
uploads = st.file_uploader(
    "PDF or Excel files (financial models, statements, IMs, term sheets, agreements, DD reports…)",
    type=[e.lstrip(".") for e in SUPPORTED_EXT], accept_multiple_files=True)

docs = []
if uploads:
    rows = []
    for up in uploads:
        data = up.getvalue()
        doc, err = ingest_cached(up.name, hashlib.sha256(data).hexdigest(), data)
        size = "<1 KB" if len(data) < 1024 else f"{len(data) / 1024:,.0f} KB" if len(data) < 1024 ** 2 else f"{len(data) / 1024 ** 2:,.1f} MB"
        if doc:
            docs.append(doc)
            status = "⚠️ " + " ".join(doc.warnings) if doc.warnings else "✅ Ready"
            extra = ""
            if doc.workbook:
                n_issues = len(doc.workbook.issues)
                roles = ", ".join(f"{s.name} ({s.role})" for s in doc.workbook.sheets[:6])
                extra = f" · {roles}" + (f" · {n_issues} model findings" if n_issues else "")
            rows.append({"File": up.name, "Type": doc.kind.upper(), "Size": size,
                         "Contents": doc.summary + extra, "Status": status})
        else:
            rows.append({"File": up.name, "Type": "–", "Size": size, "Contents": "–", "Status": "❌ " + err})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={"Status": st.column_config.TextColumn(width="large")})
else:
    st.info("No files uploaded yet. Sample files are in the project's `sample_data` folder.")

st.markdown("<div class='iba-step'>2 · Choose analysis</div>", unsafe_allow_html=True)
mode_key = st.radio("Analysis mode", list(MODES), format_func=lambda k: MODES[k].title, horizontal=True,
                    label_visibility="collapsed")
st.caption(MODES[mode_key].description)
if mode_key == "financial_model_review" and docs and not any(d.kind == "excel" for d in docs):
    st.warning("Financial Model Review works best with an Excel model; none has been uploaded.")
extra = st.text_area("Optional: specific focus or questions for the analyst", height=70,
                     placeholder="e.g. Focus on construction risk and sponsor support")

st.markdown("<div class='iba-step'>3 · Run</div>", unsafe_allow_html=True)
run = st.button("Run analysis", type="primary", disabled=not docs)

if run:
    try:
        provider = get_provider(cfg["provider"], session_key=st.session_state.get("session_key"),
                                model=cfg.get("model"))
        with st.status("Running analysis…", expanded=True) as status:
            report = run_analysis(docs, mode_key, provider, extra, progress=status.write)
            status.update(label="Analysis complete", state="complete", expanded=False)
        st.session_state["report"] = report
    except AnalystError as exc:
        st.error(exc.user_message)
    except Exception as exc:
        log.exception("Unexpected analysis error")
        st.error(f"Something unexpected went wrong ({type(exc).__name__}). Please try again; if it persists, "
                 "try fewer files or a different mode.")


# ---------------------------------------------------------------------------
# Report view
# ---------------------------------------------------------------------------
def show_report(rep) -> None:
    st.divider()
    st.subheader(rep.title)
    counts = rep.label_counts()
    c = st.columns(6)
    c[0].metric("Sections", len(rep.sections))
    for i, k in enumerate(["FACT", "CALCULATED", "INFERENCE", "MISSING"], start=1):
        c[i].metric(k.title(), counts.get(k, 0))
    c[5].metric("⚠ Unverified", len(rep.flagged_points))
    for n in rep.context_notes:
        st.info(n)

    stem = re.sub(r"[^A-Za-z0-9]+", "_", rep.title).strip("_")[:60] or "report"
    d = st.columns(4)
    d[0].download_button("⬇ Word (.docx)", to_docx(rep), f"{stem}.docx",
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                         use_container_width=True)
    d[1].download_button("⬇ HTML (print to PDF)", to_html(rep), f"{stem}.html", "text/html",
                         use_container_width=True)
    d[2].download_button("⬇ Markdown", to_markdown(rep), f"{stem}.md", "text/markdown", use_container_width=True)
    d[3].download_button("⬇ JSON (data)", to_json(rep), f"{stem}.json", "application/json",
                         use_container_width=True)

    tabs = ["Report"] + ([rep.issues_title] if rep.issues else []) + ["Calculations", "Model inspection",
                                                                      "Verification"]
    t = dict(zip(tabs, st.tabs(tabs)))
    with t["Report"]:
        st.markdown("<div class='iba-report'>" + "".join(section_html(s) for s in rep.sections) + "</div>",
                    unsafe_allow_html=True)
    if rep.issues:
        with t[rep.issues_title]:
            st.markdown("<div class='iba-report'>" + issues_html(rep) + "</div>", unsafe_allow_html=True)

    calc = rep.calculations
    with t["Calculations"]:
        st.caption("Computed by Python from source figures – no AI arithmetic. Each value lists its formula and "
                   "source cells/pages.")
        if calc.metrics:
            st.dataframe(pd.DataFrame([{"Metric": m.name, "Value": m.display, "Period": m.period,
                                        "Formula": m.formula, "Source figures": m.sources}
                                       for m in calc.metrics]), hide_index=True, use_container_width=True)
        if calc.period_table:
            st.markdown("**Per-period calculations**")
            st.dataframe(pd.DataFrame([{k: (v if k == "Period" else fmt(v, PERIOD_COLS_UNITS.get(k, "amount"))
                                            if v is not None else "–") for k, v in r.items()}
                                       for r in calc.period_table]), hide_index=True, use_container_width=True)
        if calc.checks:
            st.markdown("**Integrity & consistency checks**")
            st.dataframe(pd.DataFrame([{"Result": "✅ PASS" if c.passed else "❌ FAIL" if c.passed is False else "–",
                                        "Check": c.name, "Detail": c.detail} for c in calc.checks]),
                         hide_index=True, use_container_width=True)
        for m in calc.missing:
            st.warning(m)
        if calc.is_empty and not calc.missing:
            st.info("No financial data identified for calculations.")

    with t["Model inspection"]:
        wbs = [d for d in rep.documents if d.workbook]
        if not wbs:
            st.info("No Excel workbook was included in this analysis.")
        for doc in wbs:
            st.markdown(f"**{doc.filename}**")
            st.dataframe(pd.DataFrame([{
                "Sheet": s.name + (" (hidden)" if s.hidden else ""), "Role": s.role, "Why": s.role_reason,
                "Used range": s.dimensions, "Formulas": s.n_formulas, "Hard-coded numbers": s.n_numeric_inputs,
                "Timeline": f"{s.period_header[0][1]}–{s.period_header[-1][1]}" if s.period_header else "–",
                "Units": ", ".join(s.units[:2]), "Feeds from": ", ".join(s.referenced_sheets)}
                for s in doc.workbook.sheets]), hide_index=True, use_container_width=True)
        if rep.model_issues:
            st.markdown("**Automated findings**")
            st.dataframe(pd.DataFrame([{"Severity": i.severity, "Finding": i.category, "Location": i.location,
                                        "Detail": i.detail} for i in rep.model_issues]),
                         hide_index=True, use_container_width=True)

    with t["Verification"]:
        st.caption("The application checks every FACT/CALCULATED statement: does the cited file/page/sheet exist, "
                   "do the numbers appear there, do calculated numbers match the calculator, do cited clause "
                   "numbers appear on the page?")
        flagged = rep.flagged_points
        if flagged:
            st.dataframe(pd.DataFrame([{"Section": h, "Label": p.label, "Statement": p.statement,
                                        "Source": p.source, "Warning": " | ".join(p.flags)} for h, p in flagged]),
                         hide_index=True, use_container_width=True)
        else:
            st.success("All sourced statements passed the automated checks.")
        for f in rep.unverified_figures:
            st.warning(f"Rejected figure (not found on cited page): {f.item} {f.period} '{f.label}' at {f.source}")
        for w in rep.warnings:
            st.warning(w)
        engine = "Demo mode (no AI)" if rep.is_demo else f"{rep.provider} · {rep.model}"
        tokens = f" · {rep.input_tokens:,} input / {rep.output_tokens or 0:,} output tokens" if rep.input_tokens else ""
        st.caption(f"Engine: {engine}{tokens} · Prepared {rep.created_at:%d %b %Y %H:%M}")


if "report" in st.session_state:
    show_report(st.session_state["report"])
