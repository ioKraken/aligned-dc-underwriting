# Project Close-Out: "Is There an AI Acquisition Premium?"
Status date: 2026-10-13. **FINAL STATUS (2026-10-14): complete as a student research project.** Lite 55-deal study run end-to-end; pre-registered test NOT ASSESSABLE (too few AI-native deals); exploratory result: no evidence AI-enabled targets traded at higher multiples. See deliverables/.

## 1. What is complete
| Phase | Deliverable | State |
|---|---|---|
| 1 | Research design, hypotheses H1-H5, evidence standard | Frozen (`docs/phase1_research_design.md`) |
| 2 | Data pipeline, validation, EV bridge, waterfall, Excel entry workbook | Built, tested; run on 8-deal pilot |
| 3 | Blinded AI classification, kappa, adjudication, NLP screen, freeze | Built, tested (synthetic); **no real labels** |
| 4 | Descriptives, diagnostics, frozen analysis file | Built, tested (synthetic) |
| 5 | Progressive models, HC3, interactions, premium model | Built, tested (synthetic) |
| 6 | CEM/PSM, 12 checks, bootstrap, placebo, rule-based classification | Built, tested (synthetic) |
| 7 | Gelbach/Oaxaca, pre-deal vs premium, subgroups, frameworks, conclusion freeze | Built, tested (synthetic) |

Tests: `make test`, `test3`, `test4`, `test567` all pass on synthetic data. The three synthetic scenarios show the method recovers a planted effect (Robust), does not mistake a growth confound for an AI effect (Growth / Composition), and refuses small samples (NOT ASSESSABLE).

## 2. What the real-data pilot is (and is not)
8 hand-picked US public-target deals (Splunk, Nuance, Anaplan, Alteryx, Juniper, Altair, Smartsheet, Qualtrics). Non-systematic, no AI labels, 7 EV/Revenue-usable, 4 premium-usable. It demonstrates the Phase 2 pipeline on real figures. It supports **no** AI-vs-non-AI inference.

## 3. What is needed to finish the empirical study
1. Build a systematic universe (target >= 150 completed tech deals, 2015-2026, strict AI >= 30): Capital IQ / PitchBook / Refinitiv export or the data-entry workbook.
2. Fill the workbook; run Phase 2 (`00_excel_workbook.py --import`, `02_validate_raw`, `02b_build_stage2`, `02c_coverage_audit`).
3. Two humans code AI intensity blind (`03a`), then `03b`, `03c`, `03d` freeze.
4. `04_descriptives`, `05_regressions`, `06_matching`, `07_robustness`, `08_interpretation`.
5. Manually review the residual case studies and the EV/Revenue > 100x queue.
Only then does `FINAL_EMPIRICAL_CONCLUSION_V1` carry a real headline.

## 4. Honest claims you can make today
**Resume (methods/build framing):**
- Designed and built a pre-registered, gated research pipeline (7 phases, ~20 scripts) to test for an AI acquisition valuation premium in technology M&A: blinded classification with inter-coder agreement, EV bridge and data-quality waterfall, HC3 regressions, CEM/PSM matching, bootstrap and placebo inference, Gelbach decomposition.
- Validated the method on synthetic data with planted effects and confounds: recovers a known effect, rejects a growth-only confound, and refuses underpowered samples; every stage refuses to run without upstream checksum freezes.
- Piloted the data layer on 8 real public technology take-privates, reconciling EV bridges to filings and flagging a 7.7% EV reconciliation gap.

Do **not** write: "found", "showed", or any AI-premium percentage.

**Interview story (60 seconds):** "I wanted to know whether AI targets sell at a premium after controlling for growth, size and timing, rather than just looking at raw multiples. I pre-registered the design, built the pipeline with safeguards against data-snooping, and proved on synthetic data that it separates a real premium from a growth effect. I've piloted the data on eight real deals; the full result needs a licensed deal database and two coders, which is the next step."

**Likely questions:** Did AI cause the premium? (No causal claim.) What did you find? (Method built and validated; empirical result pending data.) Why EV/Revenue? (Loss-making targets.) Why HC3, matching, bootstrap, placebo? (Small samples, functional form, chance.) Limitations? (Selection into being acquired, private disclosure bias, label error, no bid-process data.)

## 5. Open items
Missing pilot inputs: 1-week/1-month prices, unaffected closes for Alteryx, Altair, Smartsheet, prior-LTM for Nuance and Alteryx. Local test run: needs `pip install scikit-learn scipy matplotlib openpyxl tabulate pandas numpy`.
