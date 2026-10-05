# Design: Ascent

World: **the indicative term sheet.** Each vacancy reads as a draft term sheet: defined terms in a narrow left column, facts on the right, hairline rules between clauses, open points bracketed and highlighted. Mode: Operate. The layout is a standard app (side rail on desktop; top bar plus bottom tabs on phones). The world contributes only type, palette, density and one signature move.

## Signature move
Unknown facts render as **[●] open terms**: marker-yellow highlight, ink text, bracketed bullet (`OpenTerm` in `src/components/ui.tsx`). Used for NEEDS USER INPUT answers, unscored vacancies, stale analyses, setup steps, and gaps (lettered clauses with yellow markers). Yellow is reserved for this meaning; never decorative.

## Tokens (`src/styles.css :root`)
| Role | Token | Value |
|---|---|---|
| Page ground | `--ground` | #eef1ed |
| Sheet surface | `--sheet` | #ffffff |
| Ink / secondary / tertiary | `--ink` `--ink-2` `--ink-3` | #14181a · #47514e · #636d69 |
| Hairline / control border | `--rule` `--rule-2` | #dde2dd · #c3cbc5 |
| House colour (rail, top bar, primary action) | `--house` | #0f3a31 |
| Text on house | `--house-ink` `--house-muted` | #eef4f0 · #b7cbc2 |
| Open term | `--mark` `--mark-soft` `--mark-edge` | #ffe352 · #fff8cf · #e3c52f |
| Fit scale | `--strong` `--apply` `--borderline` `--low` `--unsuitable` | #1b6a52 · #4c9a7f · #c08f12 · #a2aaa6 · #b23f3b |
| Error | `--bad` `--bad-bg` | #a3302c · #fbeeed |

## Type
- UI and data: Hanken Grotesk (variable, self-hosted via @fontsource), tabular lining figures everywhere.
- Page titles, sheet titles, cover-letter drafts: Source Serif 4 (variable). Serif never appears in controls or labels.
- Scale: body 15px; field labels 14px/650; notes 13.6px; sheet titles 18px serif; page titles 32px serif (28px phone); vacancy title 36px serif.

## Components
- **Sheet**: white, 1px rule border, 2px ink top rule (the document rule), 6px bottom radius. No shadows.
- **Terms**: `dl` grid, 150–210px label column, hairline between rows; stacks on phones.
- **Fit rule**: score + 0–100 track with a tick at 70 (the "Apply" threshold); fill animates with `scaleX`.
- **Recommendation**: label with a 9px square swatch from the fit scale.
- **Status**: small 3px-radius chip; active statuses take the house colour; Offer takes `--strong`; Needs input takes `--mark`.
- **Clauses**: lists lettered (a), (b), (c) as in legal drafting; gaps use yellow markers.
- **Notices**: sticky at the top of content; errors carry a "Technical details" disclosure with HTTP status, Google reason and message.
- **Save bar**: ink bar sliding up from the bottom when a form has unsaved edits; primary action in marker yellow.
- Controls: 40px buttons (34px small), 42px inputs (16px text on phones), 4px radius, focus ring 2px `#1d6b55`.

## Motion
Only state: fit fill (700ms expo-out), notice entry (260ms), save bar (320ms). Reduced motion respected.

## Responsive
≥1100px: vacancy sheet plus 320px decision column. ≤900px: rail becomes top bar and bottom tab bar. ≤720px: tables become stacked rows; forms single-column.
