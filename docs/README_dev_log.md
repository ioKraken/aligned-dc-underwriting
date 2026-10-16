# Is There an AI Acquisition Premium? — Phase 2 build

Phase 2 = transaction universe, deal screening and data-acquisition architecture. **No AI classification, no AI-vs-non-AI comparison and no regressions are performed here** (those are Phases 3 to 5).

## Status (read this first)

| Item | State |
|---|---|
| Pipeline code (ingest, dedupe, EV, LTM, ratios, premiums, waterfall, coverage, SQL, QC, audit) | Built and **tested end-to-end on synthetic data** (`make test`) |
| Schema, views, data dictionary (133 fields), protocol, deviations log, source register, collection log | Built |
| Raw transaction universe (`data_raw/deal_universe_raw.csv`) | **Empty (header only).** Requires data access and manual verification; nothing was fabricated |
| Waterfall, coverage tables, QC report on real data | Not yet producible; they regenerate automatically once data is loaded |
| Phase 1 sample-size targets (N >= 250, AI-native >= 60) | Cannot be assessed until the universe exists |

## What you need to do next (data acquisition)

1. Enumerate all technology control deals in the frozen window using the screens in `docs/universe_construction_protocol.md` section 2 (EDGAR / SEDAR+ / RNS enumeration, plus any database exports you can access). Fill `data_raw/deal_universe_raw.csv` (template in `data_raw/templates/`).
2. Fill `deal_terms_raw.csv`, `financials_raw.csv`, `descriptions_raw.csv` (same folder for templates), one row per `deal_id`. Use `ND/NF/NR/NA` instead of blanks for missing numbers. Put sources in `docs/source_register.csv`.
3. Optionally add `data_raw/company_aliases.csv`, `data_raw/market_data.csv` and the three `external_benchmarks/*.csv` files (rename the `.template.csv` files) for the completeness audit.
4. Run `make phase2`, clear every ERROR in `results/data_quality_report.csv`, and review `needs_review` deals.

## Layout

```
data_raw/      inputs and templates (never edited by code)
data_clean/    companies, deals_stage1/2, financials_stage2, ai_coding_blind, ai_coding_pool_key, exclusions_log, ai_premium.db
sql/           schema.sql, views_samples.sql (no view filters on AI status)
docs/          data_dictionary.md, deviations_log.md, source_register.csv, collection_log.csv,
               universe_construction_protocol.md, phase1_research_design.md
src/           utils.py, 01_collect.py, 02_validate_raw.py, 02b_build_stage2.py, 02c_coverage_audit.py,
               data_dictionary_spec.py, tests/test_pipeline.py
results/       sample_waterfall_phase2.csv, yearly/sector/geographic/public_private coverage, deal_size_distribution,
               disclosure_tracking, sample_size_checkpoints, missingness_report, sql_view_check, data_quality_report, coverage_audit
```

## Run order

`make collect` -> `make stage2` -> `make validate` -> `make audit` (or `make phase2`). Fixed seed 20261006. `make test` runs the synthetic end-to-end test and touches none of your data.

## Guardrails built into the code

- No imputation: ND/NF/NR/NA become NULL plus a reason code; EV is reconstructed only if all four bridge items exist.
- Financial period must precede the announcement date (otherwise ERROR and revenue is nulled).
- Extreme multiples are flagged, never removed (cleaning is Phase 4).
- `ai_flag` is never written; the blind coding file has no valuation columns, scrubbed text, shuffled rows, and a separate pool key.
- SQL views are checked against the pandas waterfall (`sql_view_check.csv`).

## Phase 3 status (AI classification)

**No real classification has been performed.** The universe is empty (D-005) and there are no human coders. The Phase 3 machinery is built and tested on synthetic data only (`make test3`).

Order once the universe exists: `make phase3-prep` (coder sheets) -> two independent coders fill `data_clean/ai_coding_raw_coder1/2.csv` using `docs/ai_rubric.md` -> `make phase3-agree` (kappa, confusion matrices, disagreements; creates the adjudication file) -> adjudicator completes it and fills `docs/ai_classification_sources.csv` -> `make phase3-nlp` -> `make phase3-audit`, auditor fills the audit sheet -> `make phase3-final` (gate report) -> `make phase3-freeze` only if the gate passes -> `make phase3-verify`.

Never open any valuation file or compare AI vs non-AI multiples before the freeze.

## Phase 4 status (descriptive valuation analysis)

**Not run on real data.** `make phase4` refuses unless the Phase 3 freeze manifest exists and its checksum verifies. Tested on synthetic data only (`make test4`). On a real run it writes the raw snapshot, `data_clean/deals_analysis_v1.csv` (with `docs/ANALYSIS_V1_PHASE4.json` hash), winsorised/trimmed variants, `results/p4_*.csv`, 14 charts and `results/phase4_report.md`.

Manual steps it cannot do: LTM spot-check (`results/p4_ltm_audit_sample.csv`), outlier verification (`p4_outlier_validation_queue.csv`, `p4_evrev_gt_100_verification_queue.csv`). Optional input: `data_raw/market_data.csv` (date, nasdaq_ret_12m, software_index_ev_rev, ust10y, fed_funds, vix).

## Phases 5-7 status
Code complete and synthetic-tested: `make test567`. Run order: `make phase5 && make phase6 && make phase7` (each gated on the previous freeze). No real result exists; the pilot sample is too small and unlabelled. Outputs carry a SYNTHETIC / PILOT banner when applicable.

## Final status
See `docs/PROJECT_CLOSEOUT.md`. Code complete and synthetic-tested; **no empirical finding yet** (needs real universe + two blind coders).

## FINAL (2026-10-14)
Project complete as a student research project. Start with `deliverables/INDEX.md`. Master workbook: `deliverables/AI_Premium_Study_Master.xlsx` (built by `src/10_master_workbook.py`). Exploratory analysis: `src/09_exploratory_broad.py`.
