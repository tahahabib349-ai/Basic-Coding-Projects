# Investment Banking Analyst (prototype)

Upload transaction materials (Excel models, IMs, term sheets, facility agreements, DD reports…),
choose an analysis mode, and receive a structured, sourced and automatically verified analyst report.

> **Prototype.** Output is AI-assisted. Verify material points against source documents before reliance.

---

## 1. Quick start

```bash
cd ib-analyst
pip install -r requirements.txt
streamlit run app.py
```

A browser tab opens at `http://localhost:8501`. Without an API key, choose **Demo mode** in the sidebar:
everything runs except the AI commentary.

Sample (fictional) transaction files are in `sample_data/`. Regenerate them with
`python sample_data/generate_samples.py`.

## 2. Adding your Gemini API key

An **API key** is a private password proving the app may use your Gemini account.

1. Get a key at <https://aistudio.google.com/apikey> (sign in with Google → *Create API key*).
2. In the `ib-analyst` folder, copy `.env.example` to a new file named `.env`.
3. Open `.env` in Notepad/TextEdit and replace `paste-your-key-here` with your key:
   `GEMINI_API_KEY=AIza...`
4. Restart the app. The sidebar shows **Key found: AIza…xxxx** (only first/last 4 characters are ever shown).
5. Click **Test Gemini connection**.

Alternatives: paste the key in the sidebar (kept for the current session only, never saved), or set the
environment variable `GEMINI_API_KEY`. The `.env` file is excluded from git so the key is never uploaded.

To change model, edit the *Gemini model* box in the sidebar or set `IBA_GEMINI_MODEL` in `.env`
(default `gemini-3.5-flash`).

## 3. Analysis modes

| Mode | Use for | Output |
|---|---|---|
| Financial Model Review | Excel models | Structure, assumptions, debt, cash flows, ratios, model errors + issues log |
| Credit / Transaction Review | Full deal package | 23-section credit paper incl. risks, mitigants, DD gaps, questions |
| Legal / Due-Diligence Review | Term sheets, facility & project agreements | Lender protections review + issues list (issue, provision, why it matters, risk, comment) |
| Investment Banking Summary | Any deal material | Concise senior-management briefing |

## 4. How reliability is enforced

Every statement is labelled **FACT** (cited source), **CALCULATED** (by Python), **INFERENCE** (analyst view)
or **MISSING** ("Not identified in the provided materials.").

1. **Excel is inspected by code first.** Sheets are classified (inputs / calculations / statements / debt /
   outputs), timelines and units detected, every row tagged hard-coded vs formula (formula text kept), and
   automatic checks run: error values, hard-codes inside formula rows, formulas that break their row's pattern,
   constants embedded in formulas, external links, hidden sheets.
2. **The AI never does the maths.** Python computes leverage, DSCR, interest cover, debt/equity, gearing,
   margins, growth, sources = uses, balance-sheet balance, debt roll-forward, and reconciles the model's own
   reported ratios. Each result lists its formula and source cells.
3. **PDF figures are verified.** The AI only *locates* figures in PDFs (with a verbatim quote); code confirms
   the quote and number appear on that page before the figure is used. Document figures are cross-checked
   against the model (e.g. IM says average DSCR 1.86x, model says 2.37x → flagged).
4. **The AI's answer is audited.** For every FACT/CALCULATED point the app checks the cited file, page and
   sheet exist, the numbers appear in the cited source or match the calculator, and cited clause numbers are
   printed on that page. Failures are shown with ⚠, never silently changed.
5. **Missing sections are never filled in.** If the AI skips a section it is shown as MISSING.

## 5. Architecture

```
app.py                         User interface (Streamlit)
ib_analyst/
  config.py                    Settings, API-key lookup, masking, log redaction
  errors.py                    Friendly error types (no stack traces for users)
  ingestion/                   File ingestion
    loader.py                    type/size checks, routes files, isolates failures
    pdf_processor.py             PDF text, pages, headings, clause refs, tables
    excel_processor.py           Workbook inspection & model integrity checks
    models.py                    Data structures with source "addresses"
  calculations/                Deterministic financial calculations
    figures.py                   Locates line items (EBITDA, debt…) with provenance; verifies PDF quotes
    metrics.py                   Ratios, per-period table, integrity & cross-document checks
  llm/                         AI communication (swap providers here)
    base.py                      Provider-neutral interface
    gemini_provider.py           Google Gemini (google-genai SDK): retries, rate limits, errors
    demo_provider.py             Offline placeholder engine
    factory.py                   Chooses provider
  prompts/                     Analyst prompts
    common.py                    House rules (labels, citations, no invention)
    modes.py                     The four modes: sections + guidance
    extraction.py                Figure-location prompt
  analysis/
    context_builder.py           Selects material within size budget, with source markers
    engine.py                    Orchestrates a run
    validator.py                 Hallucination control
    schema.py                    Required JSON structure & report objects
  reporting/render.py          Report generation: Markdown, HTML, Word, JSON
tests/                         Automated tests (pytest)
sample_data/                   Fictional test transaction
```

**Adding OpenAI/Anthropic later:** create `ib_analyst/llm/openai_provider.py` implementing
`generate_json()` and `test_connection()` from `base.py`, and register it in `factory.py`. Nothing else changes.

## 6. Testing

```bash
python -m pytest tests -q
```

Covers PDF/Excel ingestion, corrupt/encrypted/empty/oversized/unsupported files, calculations, missing data,
all four modes with multiple files, the hallucination validator, report exports, and the Gemini layer
(invalid key, rate limits, server errors, truncated/invalid answers, network failure). A live Gemini test runs
automatically when `GEMINI_API_KEY` is set.

## 7. Known limitations (prototype)

- No OCR: scanned (image-only) PDFs are rejected with an explanation.
- `.xls`/`.xlsb` must be re-saved as `.xlsx`. Password-protected files must be unlocked first.
- Excel values come from the results saved in the file; files generated by software without Excel
  recalculation may lack them (the app warns).
- Line-item detection relies on common labels (e.g. "EBITDA", "CFADS", "Total debt service"); unusual labels
  may not be recognised, in which case the metric is reported as not calculable.
- Units: document figures are converted to millions for cross-checks; mixed-unit workbooks are not reconciled.
- Covenant headroom, LLCR/PLCR, IRR and sensitivities are not yet calculated.
- Single-user local app; no login, audit trail or document storage.
