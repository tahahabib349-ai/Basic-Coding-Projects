# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Static single-page app (Vite + React + TypeScript), no server. Hosted free on GitHub Pages from a public repository. Gemini is called directly from the browser (Google's API allows cross-origin requests). Chosen by the user over returning to ChatGPT Sites. Budget is strictly $0: no paid services, no billing, no paid fallbacks.

## Users
One user: the owner, an investment-banking professional based in Pakistan targeting a move into IB, project finance or private equity abroad. The owner has no programming background and cannot install developer tools on an office laptop. The owner uses Ascent equally on a phone and a laptop, in short sessions between deal work: triage a vacancy, check fit, move a status, draft a letter.

## Product Purpose
A personal job-application agent for a finance career move abroad. Workflow: find or paste a vacancy → extract its facts → compare against the master résumé → score professional fit with reasons → see strengths and gaps → prepare materials → the user approves and submits personally → track status. Success means the owner spends time only on the openings worth applying to, and every claim in a draft is true.

## Positioning
Built around one person's real résumé and one career thesis (IB, project and infrastructure finance, PE, M&A and debt advisory across London, the Gulf, Singapore, Hong Kong and Pakistan). Professional fit and work authorization are scored separately, so an unknown visa status never hides a strong match. Approval-first: it never submits anything.

## Operating Context
- Target roles: IB Analyst/Associate, Project & Infrastructure Finance/Advisory, Leveraged/Acquisition/Structured/Corporate Finance, PE and Infrastructure PE, Investment Analyst, M&A and Debt Advisory. Configurable.
- Target markets: London, Dubai, Abu Dhabi, Riyadh, Doha, Singapore, Hong Kong, Pakistan, other financial centres. Configurable.
- Sources: manual paste (LinkedIn, Workday, bank careers sites) and public Greenhouse / Lever employer feeds on demand.
- Data lives in the browser (localStorage) with JSON backup/restore. The Gemini key may be remembered on the device by choice, never in backups or the repo.
- Status vocabulary: DISCOVERED, REVIEWING, STRONG MATCH, PREPARING, NEEDS USER INPUT, READY FOR APPROVAL, APPLIED, ASSESSMENT, INTERVIEW, REJECTED, OFFER, WITHDRAWN, SAVED FOR LATER.
- Fit is eight weighted components (role, experience, skills, sector, transactions, seniority, education, location) → 0–100 → STRONG APPLY / APPLY / BORDERLINE / LOW PRIORITY / NOT SUITABLE.

## Capabilities and Constraints
- Never invent employers, dates, deals, values, qualifications, skills, languages, work authorization, salary or personal facts; unknowns read NEEDS USER INPUT.
- Never auto-submit; never bypass CAPTCHAs, logins or rate limits. "Applied" only records the user's own submission after confirmation.
- No personal data in the public source. The résumé arrives through a private starter-profile file the user imports once.
- Not built: internet-wide crawling, scheduling, CV tailoring with diff, PDF/DOCX export, form filling, email monitoring.

## Brand Commitments
Name: Ascent. Mountain-inspired identity, previously accepted by the user. Tone: professional, precise, finance-literate; plain English for anything technical.

## Evidence on Hand
The user's résumé (private, supplied via the starter-profile file). No real jobs, scores or testimonials exist yet; the earlier Base44 sample jobs were fake and must not be reused.

## Product Principles
1. The user decides, every time. The app prepares; it never acts on the user's behalf.
2. Facts over flattery. Every score shows its evidence and its gaps.
3. Fit and eligibility are separate questions.
4. Errors say what actually happened (status, cause, next step), never a generic "try again".
5. Zero cost, zero setup: open a link and work.

## Accessibility & Inclusion
WCAG AA contrast; full keyboard use; works one-handed on a phone.
