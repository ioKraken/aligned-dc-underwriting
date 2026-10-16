# AI Classification Model Card (AI_CLASSIFICATION_V1_20261013)

**Status:** FROZEN-READY: decision gate passed.

## Purpose
Produce the treatment variable for the study 'Is There an AI Acquisition Premium?': whether a target was AI-native at or before its acquisition announcement, constructed without reference to any transaction valuation.

## Definition
`ai_flag_strict = 1` iff final adjudicated intensity >= 2 (AI-native or frontier/core AI infrastructure); `ai_flag_broad = 1` iff intensity >= 1. Rubric: `docs/ai_rubric.md` (hash-pinned at freeze). Four evidence tests (product, technical asset, revenue/commercial, persistence >= 12 months) structure the evidence; the intensity rubric decides.

## Input text
Pre-announcement target text only (target, website, filing, historical descriptions and the announcement-time website snapshot), with money amounts, multiples and price language scrubbed. Buyer announcement language, current websites and post-deal descriptions are not used for classification.

## Human coding procedure
Two independent coders see every pooled row (keyword-screen candidates plus a fixed-seed random 20% sample of non-candidates) in different shuffled orders, and cannot tell which rows are candidates. A third reviewer adjudicates disagreements and manually reviews every intensity 2/3 target against source evidence (>= 1 pre-announcement source required). Raw coder fields are never overwritten.

## NLP method
Transparent dictionary score (fixed category weights; weak terms count only alongside strong terms) plus a TF-IDF (1-2 gram) logistic regression trained on adjudicated labels with a stratified hold-out and out-of-fold scoring; composite = 0.5 dictionary + 0.5 TF-IDF probability. The review threshold is the highest threshold keeping out-of-fold recall >= 95%, recorded in `results/nlp_threshold.json` before Phase 4. An embedding score is optional and not implemented. NLP screens candidates; it never sets a final label.

## Performance
| evaluation                                         |   n |   n_pos |   tp |   fp |   fn |   tn |   precision |   recall |      f1 |   specificity |   fn_rate |   fn_rate_ci_low |   fn_rate_ci_high |   est_missed_strict_ai_in_noncandidate_pool |   recall_ci_low | note               |
|:---------------------------------------------------|----:|--------:|-----:|-----:|-----:|-----:|------------:|---------:|--------:|--------------:|----------:|-----------------:|------------------:|--------------------------------------------:|----------------:|:-------------------|
| phase2_keyword_screen_vs_human(on labelled rows)   |  19 |       3 |    3 |    5 |    0 |   11 |       0.375 |        1 |   0.545 |         0.688 |       nan |              nan |           nan     |                                         nan |         nan     | nan                |
| false_negative_audit(random 20% of non-candidates) |  11 |       0 |  nan |  nan |  nan |  nan |     nan     |      nan | nan     |       nan     |         0 |                0 |             0.259 |                                           0 |         nan     | nan                |
| candidate_screen_recall_estimate                   |   3 |     nan |  nan |  nan |  nan |  nan |     nan     |        1 | nan     |       nan     |       nan |              nan |           nan     |                                         nan |           0.201 | MEETS >=90% target |

Coder agreement: binary strict kappa = 0.7692307692307692; candidate-screen recall estimate = 1.0. See `results/coder_agreement.csv`, `results/nlp_performance.csv`.

## Counts
Deals in scope: 54; classified: 54 (human-adjudicated: 19; assumed non-AI from keyword-screen negatives: 35); strict AI N = 3; broad AI N = 16.

## Known errors
- Targets that the keyword screen did not flag and the random audit did not sample are assumed non-AI; the false-negative audit estimates how many strict-AI targets this misses.
- Misclassification in the treatment most likely attenuates (biases toward zero) a later AI coefficient; the stability table reports how many labels move under conservative/liberal resolution of ambiguous cases.
- Random re-audit status: complete; error rate 0.000

## Limitations
Small coded samples give wide confidence intervals on kappa and recall. Historical evidence for private targets can be thin, so Low-confidence labels are flagged for a later robustness exclusion. Pre-2022 AI uses different vocabulary; the rubric judges product dependence on a trained model, not wording. Acqui-hire detection after coding (`acquihire_ai_flag`) extends the Phase 2 exclusion and is logged in `deviations_log.md`.

## Decision gate
                                                                                     gate_condition  passed                     detail
                                                                coder kappa (binary strict) >= 0.70    True   kappa=0.7692307692307692
                                                            candidate-screen recall estimate >= 90%    True                 recall=1.0
                                                                            no pending adjudication    True                  pending=0
every strict-AI target has a pre-announcement source and >=1 supporting source (no NLP-only labels)    True               incomplete=0
                                               no sources dated after announcement / no tier-D used    True      violations=0, tierD=0
                                                                                 leakage check PASS    True                           
                                                      random re-audit complete and error rate <= 5%    True status=complete, error=0.0
                                                             no adjudication-file validation errors    True                   errors=0

## Version
AI_CLASSIFICATION_V1_20261013
