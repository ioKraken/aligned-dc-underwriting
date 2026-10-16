# Universe Construction & Data Acquisition Protocol (Phase 2)

Frozen from Phase 1: period 1 Jan 2015 to 30 Sep 2026; geography US, Canada, UK, EU/EEA, Switzerland, Israel; sectors application software, infrastructure software, internet platforms, semiconductors, cybersecurity, IT services; control transactions (>= 50%); Phase 1 exclusions carried forward.

## 1. Principle: select on structure, never on the treatment

The universe is built from systematic screens over **all** technology control deals meeting the frozen criteria. No query contains an AI term, and no deal is entered because it is famous, large or "interesting". AI status is assigned later (Phase 3) by blind coding. The only AI-related field in Phase 2 is a keyword screen (`ai_candidate_flag`), used to size the coding workload and the 20% audit sample.

## 2. Screens (record each in `source_universe`)

| Priority | Source | Screen design |
|---|---|---|
| 1 | SEC EDGAR: 8-K item 1.01/2.01, DEFM14A, SC TO-T / SC 14D-9, S-4; SEDAR+; UK RNS Rule 2.7 announcements; ISA / EU national exchange filings | Filing type plus SIC/NACE-type sector codes for software (7370-7374, 3674, 7371-7379 etc.) and primary geography. Enumerate by date window (quarterly), not by keyword |
| 2 | Transaction databases if the user has access (Capital IQ, Bloomberg, Refinitiv, PitchBook, Mergermarket, Crunchbase, Dealroom) | Industry classification = technology sub-industries above; deal type = merger/acquisition of majority; geography = primary; date window. Export **all** results, not top-N |
| 3 | Reuters, Bloomberg News, FT, WSJ, TechCrunch | Used for private deals, deal terms, leak dates and gap-filling, not as the sole enumerator |

Rules: use at least two enumerating sources per year where possible; log the exact query, date and export row count in `docs/collection_log.csv`; keep raw exports untouched in `data_raw/`.

## 3. Duplicate and competing-bid protocol (implemented in `01_collect.py`)

- Canonical key = normalised target + announcement date + normalised buyer. Exact duplicates are merged, sources concatenated, every merge written to `duplicates_log.csv`.
- Rows for the same target within 365 days form a cluster. The **winning/final** bid is the primary row (completed if exactly one; otherwise the latest live bid, flagged `needs_review`). Losers go to `deal_bids_history.csv` as `competing_bid` (different buyer) or `revised_bid` (same buyer). `contested = 1` when more than one buyer was involved.
- `needs_review = 1` must be cleared by hand against the primary filing before Phase 3.

## 4. Status, type, buyer, sector

- Primary universe: `completed` or `definitive`. Withdrawn/terminated/rejected deals stay in the file with `status_primary_sample = 0` (robustness only).
- Public = listed at announcement (ticker and venue recorded in `companies.csv`). Subsidiary/carve-out targets are excluded unless `standalone_financials = 1`.
- Buyer type: strategic (operating company), sponsor (PE/growth/VC-led), consortium (mixed investors, `mixed_consortium = 1` when both types), government/SWF, other. Primary regressions use `strategic_buyer` and `sponsor_buyer` with "other" omitted.
- Sector classification uses the **target's** business, never the acquirer's. Targets whose AI use is incidental to a non-technology business (healthcare, industrial, etc.) are out of scope and logged.

## 5. Transaction value and EV

1. Record headline value, equity value and EV separately and label `headline_value_type`. A press-release "transaction value" is never assumed to be EV.
2. EV hierarchy: (1) explicit EV in a primary transaction document; (2) EV calculated from merger materials: equity + debt + preferred + NCI - cash (latest balance sheet before announcement, all four bridge items required, none imputed; other debt-like items default to zero and must be documented); (3) professional database; (4) triangulated secondary sources.
3. Stock deals: equity value = shares issued x acquirer price using announcement terms; prefer a disclosed implied value.
4. Contingent consideration (earn-outs, CVRs, milestones, deferred, retention): primary EV uses firm upfront consideration. If a reported EV already includes contingent value it is flagged (`contingent_review`) and resolved manually. `ev_incl_contingent_max_usd` supports the later robustness run. Maximum earn-out is never added by default.
5. Currency: store original currency, FX at announcement date and USD value. EV/Revenue uses the same currency for numerator and denominator; when the currencies match, the same FX is applied to both, so the multiple is exactly currency-invariant.

## 6. Target financials

- Use the latest financial information **available before announcement**. LTM = latest FY + current YTD - prior YTD. Prior-year LTM is required for growth; no annualised quarters, no guidance.
- EBITDA: record the definition (`reported` preferred, `adjusted` only if clearly identified, `database_normalized`). Never mix silently. No EV/EBITDA for EBITDA <= 0.
- Staleness = announcement date - period end: <= 180 days fresh, 181-365 acceptable, > 365 stale (excluded from the preferred sample, kept for robustness). A period ending on or after the announcement date is an ERROR and the revenue is nulled.
- Private targets: use acquisition announcements, acquirer filings, seller filings, investor decks, credit documents, statutory filings (for example Companies House) and funding announcements. "Approximately $X million" is stored and flagged. "Sources say" figures are quality D. Private financials are never invented or imputed.

## 7. Quality grades (apply to EV evidence and to financials; deal grade = the worse of the two)

| Grade | Meaning | Use |
|---|---|---|
| A | Primary filing or merger document | Primary |
| B | Professional database or reliable primary-adjacent source | Primary |
| C | Triangulated from multiple reliable sources (reconciliation documented) | Primary |
| D | Weak estimate or unverified press report | Robustness only |

## 8. Public-target price data and unaffected date

- Collect offer price, unaffected price, prices one week and one month earlier, 30-day VWAP and the price 90 days before the unaffected date.
- **Unaffected date = last trading day before the earliest credible leak, rumour, approach or announcement**, not automatically T-1. Search Reuters, Bloomberg, FT, company filings and exchange announcements; record `rumor_date`, `rumor_source`, `leak_flag`, `unaffected_reason`. If nothing is found, use the last close before the official announcement and say so in `unaffected_reason`.
- Premium_1D = offer / unaffected - 1 (primary); 1-week, 1-month and VWAP premiums and ln(1 + premium) are robustness. Pre-deal EV/Revenue uses the unaffected market capitalisation (RQ9).

## 9. Conflicts and provenance

- Conflict hierarchy: primary transaction filing, latest official company release, exchange filing, professional database, Reuters/Bloomberg, other secondary. Record `conflict_flag`, `conflicting_values`, `selected_value`, `selection_reason` in `source_register.csv`; never silently choose.
- Provenance is **field-level** and long-form: one `source_register.csv` row per deal x field (EV, revenue, EBITDA, price, AI evidence). Every such value must be traceable to at least one source.
- Missing values carry a reason code: `NA` not applicable, `ND` not disclosed, `NF` not found after search, `NR` not reliable. `missingness_report.csv` lists any missing value without a code ("UNEXPLAINED").

## 10. Collection workflow

1. Build the candidate universe (header fields only; no financials required).
2. Verify transaction terms.
3. Collect target financials.
4. Collect public-market price data.
5. Collect business descriptions and AI evidence (the text corpus).
6. Assign quality flags.
7. Run `02_validate_raw.py`; clear every ERROR, document every WARN.

AI is not classified until step 5 is complete for the whole coding pool.

## 11. Automate vs review manually

| Automate | Review manually |
|---|---|
| duplicate detection, date validation, FX, LTM formulas, ratios, joins, keyword screen | EV definitions, unusual structures, merger proxies, leak/unaffected dates, private-company financial estimates, sector classification, (later) AI classification |

## 12. Blinding for Phase 3

`ai_coding_blind.csv` has no EV, equity value, multiple, premium or price columns, and descriptions are scrubbed of money amounts, multiples and price language. Rows are shuffled with the fixed seed so row order carries no information. The pool label (candidate vs random audit sample) and keyword hits are held in `ai_coding_pool_key.csv`, which coders never see. The audit sample is a fixed-seed random 20% of the non-candidate pool; the analyst does not choose which firms are audited.

## 13. Completeness audit (not sample construction)

`02c_coverage_audit.py` compares the universe with (A) external annual deal counts, (B) annual league-table top deals, and (C) lists of known AI and non-AI deals, reporting coverage rates and any AI-vs-non-AI coverage gap. Deals found missing are added **only** if they pass the same frozen rules, and the addition is logged as a universe repair. The data may be called the "research universe", never the "complete universe", unless all three checks are performed with documented coverage.

## 14. Sample-size checkpoints (Phase 1 targets)

EV/Revenue sample N >= 250; AI-native >= 60 (assessed after Phase 3); public premium sample >= 120 with >= 30 AI. Quality is never degraded to hit these numbers.
