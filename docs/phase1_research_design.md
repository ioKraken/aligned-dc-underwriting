# Is There an AI Acquisition Premium?
## Phase 1: Research Design, Hypotheses and Empirical Framework

Status: design frozen before data collection. Version 1.0, 6 October 2026.
Rule: any change after Phase 2 begins is logged in `docs/deviations_log.md` with a reason and date.

---

## A. Final Research Question

> **Conditional on a technology company being acquired, do AI-related targets command systematically higher acquisition valuations (EV/Revenue) or takeover premiums than comparable non-AI technology targets, after controlling for growth, profitability, size, sector, geography, buyer type, public/private status and deal year?**

The claim is a **conditional association among completed or announced control transactions**. It is not a causal claim and not a claim about AI companies in general (see Section Z).

Sub-questions (each maps to one outcome and one sample):

| ID | Question | Outcome | Sample |
|---|---|---|---|
| RQ1 | Do AI targets receive higher EV/Revenue? | ln(EV/Revenue) | All with EV and LTM revenue |
| RQ2 | Higher EV/EBITDA among profitable targets? | ln(EV/EBITDA) | LTM EBITDA > 0 |
| RQ3 | Higher takeover premiums? | Premium vs unaffected price | Public targets |
| RQ4 | How large economically? | exp(b)-1, turns of revenue, pp of premium | All of the above |
| RQ5 | Does it survive controls? | b_AI across specifications | RQ1 sample |
| RQ6 | Which AI subsectors? | b by subsector | Subject to cell sizes |
| RQ7 | Strategic vs sponsor? | AI x Strategic | RQ1 sample |
| RQ8 | Change after generative-AI boom? | AI x PostGenAI | RQ1 sample |
| RQ9 (added) | Are public AI targets already priced richly before the bid? | pre-deal trading EV/Revenue, run-up | Public targets |

RQ9 is added because it is the mechanism that could reconcile a high deal multiple with a low takeover premium (outcome 8 in your brief).

---

## B. Formal Hypotheses

Primary (one confirmatory test): **H1**. Everything else is secondary.

| ID | Null | Alternative | Test |
|---|---|---|---|
| **H1** (primary) | b_AI = 0 | b_AI > 0 | Preferred model, ln(EV/Rev), HC3 |
| H2 | AI has no effect on premium | AI targets receive larger premiums | Premium regression, public sample |
| H3 | b_AI unchanged by adding growth | b_AI falls materially | Compare model (1) vs (2); report % change in b_AI and bootstrap CI on the difference |
| H4 | AI x Strategic = 0 | > 0 | Interaction |
| H5 | AI x PostGenAI = 0 | > 0 (two-sided also reported; sign not assumed) | Interaction |

Directional alternatives are stated for power. **All headline inference is reported two-sided** with 95% CIs. A negative AI coefficient is a legitimate finding.

Multiple testing: H1 is the only confirmatory hypothesis. H2 to H5 and RQ6 subsector tests are treated as one secondary family with Holm-adjusted p-values reported next to raw ones.

---

## C. Unit of Observation

One row = one **target acquisition announcement** (control transaction). Primary key `deal_id`. If a target receives competing bids, keep the **winning/final** bid as the row and flag `contested = 1`. The initial bid goes in a side table.

## D. Sample Period, Geography, Sector

**Period:** announcements 1 Jan 2015 to 30 Sep 2026.
- Pre-GenAI: 1 Jan 2015 to 29 Nov 2022 (includes the machine-learning M&A wave).
- Post-GenAI: 30 Nov 2022 onward (ChatGPT public release, fixed in advance as the only primary date). 1 Jan 2023 is a robustness alternative only.
- Deals announced but not closed are included if terms are final (definitive agreement). Withdrawn deals are kept and flagged (`status`), since the bid price was still observed.

**Geography (primary):** US, Canada, UK, EU/EEA plus Switzerland, Israel. Rationale: consistent disclosure regimes and the deepest AI deal flow.
**Excluded from primary, included as an extension:** Japan, Australia, Singapore, South Korea, India. China is excluded entirely because of disclosure, valuation and regulatory distortions.

**Sector (primary):** application and infrastructure software, internet platforms, semiconductors, cybersecurity, IT services.
**Excluded from primary:** data-center and digital-infrastructure real assets (valued on EBITDA per MW, not revenue); telecom operators; hardware OEMs without a software/semiconductor core. A sector-expanded run is a robustness check.

## E. Inclusion and Exclusion Rules

**Inclusion (all required):**
1. Identifiable target operating company
2. Announcement date (day-level)
3. Acquirer obtains control (>= 50%), or agrees to a transaction that does
4. Target classified into one of the primary sectors
5. Buyer identity known
6. Target description available as of announcement, so AI status can be coded (Section F)
7. Outcome-specific requirement (separate regression samples):
   - ln(EV/Rev): EV > 0 and LTM revenue >= US$5M, so near-zero revenue does not create meaningless multiples
   - EV/EBITDA: additionally LTM EBITDA > 0
   - Premium: publicly listed target, offer price, and an unaffected price

**Exclusions (applied and counted in the waterfall):**
- Minority stakes, venture or growth rounds, PIPEs, secondary share sales
- Asset-only purchases and carve-outs where no operating target has standalone revenue
- Internal restructurings and intra-group transfers
- SPAC business combinations (flagged; used only in a robustness run)
- Distressed or insolvency sales (going-concern warning, court-supervised sale)
- Acqui-hire and licence-and-hire structures (kept in a separate flagged table; excluded from primary because price reflects talent, not a going concern)
- EV < US$25M
- Data-entry errors, verified against the primary source and corrected or removed. **Never removed for being extreme.**

**Sample-selection waterfall** (tracked in `results/sample_waterfall.csv`): screened universe -> sector filter -> geography -> control filter -> structural exclusions -> EV available -> revenue available -> size filters -> AI-coded -> quality flag A to C -> final N by outcome. N is logged at every step by AI status.

---

## F. AI Classification Methodology

**Definition.** A target is AI (`ai_flag = 1`) only if, **as evidenced before or at announcement**, AI/ML is a core product, core technology, or a primary driver of revenue. Marketing language alone does not qualify.

**Evidence tests (at least two of four needed for flag = 1):**
1. **Product test:** the main product's function depends on a trained model (prediction, generation, perception, decisioning) rather than rules, workflow or analytics.
2. **Technical-asset test:** proprietary models, model-training infrastructure, ML-specific hardware, or a dedicated research team documented in filings, technical publications, patents, or product documentation.
3. **Revenue test:** management or filings attribute a material share of revenue or growth to the AI/ML product.
4. **Pre-announcement persistence test:** the AI positioning existed at least 12 months before announcement (Wayback Machine snapshots, 10-K/annual reports, earlier funding announcements), **to defend against post-2022 relabelling**. A company that added "AI" to its website after the first takeover rumour fails this test.

**Three methods, all run:**

| Method | Description | Role |
|---|---|---|
| A. Manual | Two coders review description, announcement, website snapshot, filings, Crunchbase text against the evidence tests | Ground truth |
| B. NLP score | TF-IDF/dictionary and (optional) embedding similarity of business description to a seed AI vocabulary (AI, ML, deep learning, generative AI, LLM, computer vision, neural network, NLP, autonomous). Output: score 0 to 1 | Candidate screen and alternative definition |
| C. Hybrid (**primary**) | NLP flags candidates and a random 20% sample of unflagged targets; manual coding decides final label | Primary `ai_flag` |

**Protocol safeguards:**
- **Blind to outcome:** coders see no EV, multiple, premium, or price. The coding sheet physically excludes valuation columns.
- Two independent coders; Cohen's kappa target >= 0.70; disagreements adjudicated by a third pass and documented.
- Classification date-stamped to announcement; later pivots are ignored.
- Report NLP-vs-manual agreement (precision/recall) and the false-negative rate from the unflagged audit sample.
- Coding rubric and seed vocabulary are frozen before coding starts, in `docs/ai_rubric.md`.

## G. AI Intensity System

| Level | Label | Rule |
|---|---|---|
| 0 | Non-AI | AI incidental or absent |
| 1 | AI-enabled | AI features support the product; product would function (less well) without them |
| 2 | AI-native | AI/ML central to the value proposition |
| 3 | Frontier / core AI infrastructure | Foundation-model developers, or infrastructure whose primary purpose is training or serving AI (for example accelerators, model-serving platforms) |

**Primary AI dummy = intensity >= 2** (strict, consistent with the definition in F).
**Broad definition = intensity >= 1** (robustness).
**Level 3** will likely have too few deals; it is merged with level 2 in the primary dummy and reported descriptively. No companies are assigned until evidence is coded in Phase 2.

## H. AI Subsector Taxonomy

Coded for AI targets only (`ai_subsector`), collapsed to preserve cell sizes (minimum 8 deals per cell to estimate; otherwise pooled into "Other AI"):

1. Foundation models / generative AI
2. AI developer tools / MLOps / data infrastructure for AI
3. Enterprise AI software (horizontal)
4. Vertical AI applications (including healthcare, financial services, legal)
5. Computer vision / NLP / conversational AI
6. Autonomous systems / robotics
7. AI cybersecurity
8. AI semiconductors / accelerators / AI infrastructure
9. Traditional ML / predictive analytics

Expected pooling for estimation: {1, 2, 8} "Core AI platform/infrastructure", {3, 4, 5, 9} "AI applications", {6, 7} "Specialised AI". Final grouping is fixed once the AI-native count is known, **using counts only, not outcomes**.

---

## I. Primary Dependent Variable

**ln(EV / LTM Revenue)**, chosen in advance because: widest usable sample, many AI targets have negative EBITDA, multiples are right-skewed, and the coefficient converts to a percentage difference: premium = exp(b) - 1.

## J. Secondary Dependent Variables

1. Raw EV/Revenue (economic magnitude in turns; sensitive to outliers)
2. ln(EV/EBITDA), EBITDA > 0 only
3. Takeover premium vs unaffected price: **1-day (primary premium measure)**, 1-week, 1-month, and 30-day VWAP
4. Pre-deal trading ln(EV/Revenue) of public targets (RQ9)
5. Optional: target CAR[-1,+1] (only if price data are readily available; not in the core scope)

Definitions: EV = equity value + debt + preferred + minorities - cash, at offer, using the latest balance sheet before announcement. Unaffected date = last close before the earliest credible leak, rumour or approach report (documented per deal), not simply T-1.

## K. Control Variables

| Variable | Definition | Treatment |
|---|---|---|
| Revenue growth | LTM revenue / prior-year LTM revenue - 1 | Winsorize 1/99; require two periods |
| EBITDA margin | LTM EBITDA / LTM revenue | Winsorize at 1/99; paired with EBITDA-positive dummy |
| EBITDA positive | 1 if LTM EBITDA > 0 | Dummy |
| Size | ln(LTM revenue) | **Revenue-based, not EV-based**, since EV is in the dependent variable's numerator |
| Public target | 1 if listed | |
| Strategic buyer | Operating-company buyer | |
| Sponsor buyer | PE/growth/VC-led consortium | Omitted category: other (government, SWF, management) |
| Cross-border | Buyer and target in different countries | Secondary spec |
| Cash / stock consideration | % cash, % stock | Secondary spec |
| Sector FE | Sector (primary list) | |
| Region FE | US / Canada / UK / EU / Israel | |
| Year FE | Announcement year | **Mandatory** (Section 52 of the brief) |
| Market conditions | NASDAQ trailing-12M return, software index forward EV/Rev, 10Y yield, VIX | Alternative to year FE only (collinear), not added together |

**Deliberately excluded from the primary model:** ln(Deal Value) or ln(EV). Deal value is mechanically linked to the outcome (EV is the numerator), making it a "bad control." It enters only a labelled secondary specification, with the reasoning disclosed.

---

## L. Preferred Regression Specification

```
ln(EV/Rev)_i = a + b1*AI_i + b2*Growth_i + b3*Margin_i + b4*ln(Rev_i)
               + b5*Public_i + b6*Strategic_i
               + SectorFE + YearFE + RegionFE + e_i
```

- **Estimator:** OLS with **HC3** standard errors (small-sample, leverage-sensitive, appropriate with a small AI group and influential observations).
- **Clustering:** not primary. With about 12 deal years, cluster-robust SEs are unreliable (few clusters). Wild-cluster bootstrap by year and by subsector is run as a robustness check.
- **Progressive table** (Section 56 of the brief):

| Col | Controls |
|---|---|
| (1) | AI only (unconditional difference) |
| (2) | + Growth, Margin, ln(Rev) |
| (3) | + Year FE |
| (4) | + Sector FE |
| (5) | + Region FE, Public, Strategic (**preferred**) |

Reported: coefficient, HC3 SE, t, p, 95% CI, N, adj. R^2, and exp(b)-1. Also report how b_AI moves across columns, which is the core evidence for H3.

**Pre-specified interpretation of b_AI:** the average difference in log EV/Revenue between AI and non-AI targets with the same observed growth, margin, size, sector, region, buyer type, public status and year.

## M. Interaction Tests

Each added one at a time to the preferred model (never all together given power limits):
- AI x StrategicBuyer (H4)
- AI x PostGenAI (H5), with PostGenAI main effect absorbed by year FE; use period dummies instead of year FE in this model
- AI x Public
- AI intensity as categorical (1, 2, 3 vs 0) and as ordinal 0 to 3
- AI subsector dummies (RQ6) where cell sizes allow

Interactions have roughly four times the sampling variance of main effects. They are explicitly labelled **low-power / exploratory** in write-ups.

## N. Takeover-Premium Model (Public Targets)

```
Premium1D_i = a + b*AI_i + Growth + Margin + ln(Rev) + Strategic
              + PreDealRunup_i + PreDealEV/Rev_i (secondary)
              + YearFE + SectorFE + e_i
```

- Bounded outcome, so premium is winsorized 1/99 and also analysed with log(1+premium).
- Include pre-deal 90-day run-up as control: speculation can pre-embed the bid.
- Core interpretive point: **a high deal multiple does not imply a high premium.** If b_AI(EV/Rev) > 0 but b_AI(Premium) <= 0, the correct reading is that AI valuation was priced in before the bid (RQ9).
- Estimated on the public subsample only; not pooled with private deals.

## O. Matched-Sample Design

**Design 1: Control sampling for data collection (research sample).** For each AI deal select 3 to 5 non-AI tech deals matched on: announcement year (+/- 1), sector, size bucket (revenue tercile), region. Sampling uses covariates only, never outcomes. Because the sampling is on regressors, OLS remains valid if those variables are included as controls. Prevalence statistics (AI share of tech M&A) come only from the **full universe**, never from the matched sample.

**Design 2: Analysis-stage matching.** Simplest defensible method hierarchy:
1. **Coarsened exact matching** on year bucket, sector, region, growth tercile, size tercile (primary matching method)
2. Nearest-neighbour matching on a logit propensity score P(AI=1 | growth, margin, ln(Rev), sector, year, region), caliper 0.25 SD of logit, 1:3 with replacement, as check
3. Report: matched N, standardized mean differences before/after (target |SMD| < 0.10 for key covariates), common-support plot, median EV/Revenue (and median ln) difference with bootstrap CI.

## P. Outlier Rules (Pre-defined)

| Version | Treatment |
|---|---|
| **Primary** | No trimming on ln(EV/Rev); only verified data errors removed; growth and margin winsorized 1/99 |
| R1 | All variables incl. outcome winsorized 1/99 |
| R2 | Trim outcome at 1st/99th percentile |
| R3 | Exclude EV/Revenue > 100x |
| R4 | Huber / MM robust regression |
| R5 | Drop top-5 highest-leverage observations (Cook's D, DFBETA) and report |

Raw and cleaned datasets are both retained. **Every deal removed is listed with the reason in `data_clean/exclusions_log.csv`.**

## Q. Missing-Data Rules

- No imputation of deal value, EV, revenue, EBITDA, offer price, or unaffected price.
- Missing growth: observation drops from models using growth; a "no-growth-control" model on the larger sample is reported in the table so selection into the growth-available sample is visible.
- Missing premium inputs: excluded from premium regressions only.
- Missing buyer type: coded "Unknown" in descriptives, excluded from interaction models.
- Disclosure bias check: `disclosed_flag` dummy (revenue or EV disclosed by target/buyer vs sourced from a database estimate); compare AI vs non-AI disclosure rates and run a Heckman-style or inverse-probability-weight sensitivity if rates differ materially.
- Financial staleness: flag if the financial period ends > 12 months before announcement; primary sample excludes stale financials, robustness includes them.

---

## R. Database Schema

**Master flat file** (`deals_master.csv`), one row per deal, with the columns in your brief plus these additions:

```text
deal_status, contested, deal_type, acquihire_flag, spac_flag, distressed_flag,
unaffected_date, premium_1d, premium_1w, premium_1m, premium_vwap30,
pre_deal_ev_revenue, pre_deal_runup_90d,
financials_period_end, financials_stale_flag, disclosed_flag, ev_basis (offer/implied/reported),
ai_intensity_coder1, ai_intensity_coder2, ai_nlp_score, ai_classification_method,
ai_evidence_url, ai_persistence_12m_flag, ai_subsector_group,
data_quality_flag, in_primary_sample_evrev, in_primary_sample_ebitda, in_primary_sample_premium,
currency_original, fx_rate_announcement, collected_by, collected_date
```

**SQL tables** (SQLite or PostgreSQL):

```sql
CREATE TABLE companies (
  company_id INTEGER PRIMARY KEY, name TEXT, country TEXT, public_private TEXT,
  ticker TEXT, sector TEXT, subsector TEXT, founded_year INTEGER );

CREATE TABLE deals (
  deal_id INTEGER PRIMARY KEY, target_id INTEGER REFERENCES companies(company_id),
  buyer_id INTEGER REFERENCES companies(company_id), announcement_date DATE, close_date DATE,
  status TEXT, buyer_type TEXT, cross_border INTEGER, contested INTEGER, deal_type TEXT,
  ev_usd REAL, equity_value_usd REAL, cash_pct REAL, stock_pct REAL,
  offer_price REAL, unaffected_price REAL, unaffected_date DATE );

CREATE TABLE financials (
  company_id INTEGER REFERENCES companies(company_id), period_end DATE,
  revenue_usd REAL, ebitda_usd REAL, prior_revenue_usd REAL, source_id INTEGER,
  PRIMARY KEY (company_id, period_end) );

CREATE TABLE ai_classifications (
  company_id INTEGER REFERENCES companies(company_id), as_of_date DATE,
  ai_flag INTEGER, ai_intensity INTEGER, ai_subsector TEXT, method TEXT,
  coder1 INTEGER, coder2 INTEGER, nlp_score REAL, confidence TEXT, evidence_url TEXT );

CREATE TABLE market_data (
  date DATE PRIMARY KEY, nasdaq_ret_12m REAL, software_ev_rev REAL,
  ust10y REAL, fed_funds REAL, vix REAL );

CREATE TABLE sources (
  source_id INTEGER PRIMARY KEY, deal_id INTEGER, field TEXT, tier INTEGER,
  citation TEXT, url TEXT, retrieved_date DATE, quality_flag TEXT );
```

SQL views produce the three regression samples, the waterfall counts, and summary statistics.

## S. Source Hierarchy

1. **Tier 1 (primary):** SEC filings (8-K, DEFM14A, SC 14D-9, 10-K/Q), merger proxies, acquirer and target announcements, exchange filings (SEDAR+, RNS, Israel ISA, EU regulators)
2. **Tier 2 (professional databases, only if accessible):** Capital IQ, Bloomberg, Refinitiv, PitchBook, Mergermarket
3. **Tier 3 (reliable secondary):** Reuters, FT, WSJ, Bloomberg News, company press releases, TechCrunch for private context, Crunchbase

Each important field (EV, revenue, EBITDA, price) carries a `source_id` and tier. **No database access is assumed.**

## T. Data-Quality Flags

| Flag | Meaning | Use |
|---|---|---|
| A | Primary-source verified | Primary |
| B | Reliable secondary / database | Primary |
| C | Derived from multiple sources (documented reconciliation) | Primary |
| D | Weak, uncertain, single unverified source, or private-deal revenue from press estimate | Robustness only |

Private-deal valuations reported only as "people familiar with the matter" are D unless confirmed by a filing or company statement.

## U. Sample-Size Target and Power

Targets: **N >= 250 for EV/Revenue, of which >= 60 AI-native targets**. Public premium sample: **>= 120 with >= 30 AI**. EV/EBITDA sample is expected to be smaller and AI-thin; treated as secondary.

Approximate minimum detectable effect (80% power, one-sided 5%, HC-type SE approximated by OLS):
- ln(EV/Rev), N = 250 (60 AI / 190 non-AI): residual SD 0.9 gives SE about 0.13, MDE about **0.33 log points (about +39%)**. With residual SD 0.7 after controls: MDE about 0.26 (about +30%).
- Premium, 30 AI / 90 non-AI, SD 25pp: SE about 5.1pp, MDE about **12.7pp**.
- Interactions: MDE roughly 2x larger. Treat as exploratory.

**Implication:** the design can detect large premiums but may not be able to reject modest ones (for example 10%). A null result will be reported as "CI excludes premiums larger than X," not "no premium."
If reliable data support fewer AI deals, the study proceeds and states its reduced power, rather than adding weak data.

---

## V. Statistical Tests

- **Univariate:** Welch t-test on ln(EV/Rev); Mann-Whitney / Wilcoxon rank-sum on raw multiples and premiums; reported as descriptive only
- **Descriptives:** mean, median, P25, P75, SD, N for AI vs non-AI (and by intensity) for EV/Rev, EV/EBITDA, premium, growth, margin, deal size, by year
- **Regressions:** OLS with HC3; coefficient, SE, t, p, CI, N, adj. R^2, exp(b)-1
- **Multicollinearity:** correlation matrix and VIF reported; variables are **not** dropped mechanically on a VIF threshold
- **Specification:** RESET test; Cook's D / DFBETA; residual QQ plot; Breusch-Pagan reported though HC3 used regardless
- **Bootstrap:** 10,000 pairs-bootstrap draws of b_AI, percentile and BCa 95% CI
- **Placebo:** 5,000 random reassignments of AI labels preserving the AI count (and within-year/sector-stratified version); compare observed b_AI to placebo distribution
- **Quantile regression:** median and 75th percentile, only if N supports it
- **Multiple comparisons:** Holm adjustment for the secondary family

**Evidence standard (fixed now): a "robust AI acquisition premium" is concluded only if all of the following hold:**
1. Preferred model b_AI > 0 with HC3 95% CI excluding zero and bootstrap CI excluding zero
2. Economic magnitude: point estimate >= 0.15 log points (about +16%), a threshold chosen as the minimum premium meaningful to a deal team
3. Sign preserved in all 12 robustness checks and magnitude >= half the baseline in at least 9 of 12
4. Result holds under the strict (AI-native) definition and is not driven solely by the broad definition
5. Matched-sample median difference is in the same direction with CI excluding zero
6. Placebo p-value < 0.05

Partial satisfaction yields a graded conclusion ("suggestive," "sector-specific," "regime-specific," or "no robust premium"). The conclusion matrix covers all eight outcomes in your brief.

## W. Robustness Framework

| # | Check |
|---|---|
| 1 | Raw EV/Revenue |
| 2 | ln(EV/Revenue) (baseline) |
| 3 | Winsorized 1/99 |
| 4 | Trimmed 1/99 |
| 5 | Public targets only |
| 6 | Private targets only |
| 7 | Strategic buyers only |
| 8 | Post-GenAI only (and pre-GenAI only) |
| 9 | Excluding semiconductors |
| 10 | Excluding mega-deals (top 5% by EV) |
| 11 | Matched samples (CEM and PSM) |
| 12 | Alternative AI definitions (strict / broad / intensity 0 to 3 / NLP score continuous) |
| 13 | Quality flags A to C vs A to D |
| 14 | Wild-cluster bootstrap by year and subsector |
| 15 | Including SPACs, acqui-hires, and stale financials |
| 16 | Adding ln(EV) control (disclosed bad-control sensitivity) |
| 17 | Market-condition controls in place of year FE |
| 18 | PostGenAI date 1 Jan 2023 |
| 19 | Leave-one-subsector-out and leave-one-year-out |
| 20 | Expanded geography (APAC) |

Items 1 to 12 form the formal "12 of 12" checklist; 13 to 20 are reported for completeness.

## X. SQL / Python Architecture

```text
project/
  data_raw/        # untouched downloads, filings, source PDFs
  data_clean/      # deals_master.csv, exclusions_log.csv, sample_waterfall.csv
  sql/             # schema.sql, views_samples.sql, summary_stats.sql
  notebooks/       # exploration only; no results of record
  src/             # 01_collect.py ... 08_charts.py, utils.py
  results/         # regression tables (CSV + LaTeX/Markdown), bootstrap, placebo
  charts/
  docs/            # ai_rubric.md, data_dictionary.md, source_register.csv,
                   # deviations_log.md, phase1_research_design.md
```

| Script | Purpose |
|---|---|
| 01_collect.py | Ingest deal lists, filings extracts, load to SQL |
| 02_clean.py | Currency conversion, LTM alignment, EV construction, flags, waterfall |
| 03_classify_ai.py | NLP score, candidate list, blind coding sheet, kappa, final labels |
| 04_descriptive.py | Summary statistics, univariate tests, correlation / VIF |
| 05_regressions.py | Progressive and preferred models, interactions, premium model |
| 06_matching.py | CEM, PSM, balance tables |
| 07_robustness.py | Robustness set, bootstrap, placebo, quantile |
| 08_charts.py | All figures |

Stack: pandas, numpy, statsmodels (HC3), scipy, scikit-learn (propensity and NLP only), matplotlib, SQLite. Fixed random seed (`20261006`), `requirements.txt`, results regenerate from raw with one command.

## Y. Chart Plan

1. Deal count by year (AI vs non-AI)
2. AI share of tech M&A (full universe)
3. EV/Revenue distribution, AI vs non-AI (log scale, violin/box)
4. Median EV/Revenue over time
5. Takeover premium comparison
6. Growth vs EV/Revenue scatter with group fit lines
7. Regression coefficient plot (preferred model, with CIs)
8. b_AI across specifications (columns 1 to 5, then robustness)
9. Matched-sample comparison and balance (SMD) plot
10. AI intensity (0 to 3) vs valuation
11. Strategic vs sponsor buyer (AI interaction)
12. Pre-GenAI vs post-GenAI premium
13. Residual / excess-multiple distribution and top and bottom residual deals
14. Placebo distribution with observed b_AI marked
15. Sample-selection waterfall

All charts show N, units, and intervals.

## Z. Known Limitations

1. **Not causal.** AI status co-moves with growth, intangibles, scarcity, venture backing and sentiment. Language will be "conditional association."
2. **Selection into being acquired.** Only transacted targets are observed; non-acquired AI firms and failed bids are invisible. Findings apply to valuation conditional on a deal.
3. **Disclosure bias.** Private-deal valuations and revenue are disclosed selectively; AI vs non-AI disclosure rates may differ.
4. **Classification error and time-varying labels.** Post-2022 relabelling can cause false positives; mitigated by the persistence test and blind coding, not eliminated. Misclassification likely biases b_AI toward zero.
5. **Revenue-multiple limitations.** Early-stage AI firms with tiny or fast-changing revenue produce volatile multiples; stale LTM revenue can overstate multiples for hypergrowth targets.
6. **Low power** for interactions and subsector estimates; AI-native count may be small (especially pre-2020).
7. **Regime confounding.** Post-2022 differences also reflect rates, software multiple compression and credit conditions, not only generative AI.
8. **Non-standard deal structures** (earn-outs, compute credits, equity rollovers, licence-and-hire) make "headline EV" imperfect; contingent consideration is recorded separately and a no-earn-out check is run.
9. **Public-market information advantage.** Public targets' financials are better measured than private ones; pooling may mismeasure.
10. **Small-sample specification risk.** Many FE with few AI deals; dummy-per-cell collinearity checked and reported.

## AA. Exact Data Required for Phase 2

**Deal-level (for every candidate transaction):** target and buyer names, announcement and close dates, status, target and buyer country, buyer type, consideration mix, headline equity value and EV with components (debt, cash, preferred, minorities), contingent consideration, offer price per share (public), advisor/source documents.

**Target financials (pre-announcement):** LTM and prior-year revenue, LTM EBITDA, period end dates, currency, source filing.

**Public-target market data:** unaffected date and price, 1-week and 1-month prior prices, 30-day VWAP, 90-day run-up, pre-deal EV/Revenue.

**AI classification inputs:** business description at announcement, website snapshots (12+ months prior), filings text, funding-round descriptions, announcement text, Crunchbase category.

**Market data:** NASDAQ, software index multiples, 10Y UST, Fed funds, VIX, FX at announcement date.

**Universe construction plan for Phase 2:**
1. Build the full-universe list of tech control deals 2015 to Q3 2026 in the primary geographies (all deals, not famous ones), with consistent screening and counts logged
2. Run NLP screen and blind manual coding on the universe or a stratified sample large enough to identify >= 60 AI-native deals
3. Draw 3 to 5 covariate-matched non-AI controls per AI deal
4. Collect financials and sources, assign A to D quality flags
5. Publish the waterfall before any regression

---

## Stop Condition Check

| Question | Answer in this document |
|---|---|
| What is an AI acquisition? | Target with AI/ML core to product, technology or revenue, meeting 2 of 4 evidence tests with a 12-month persistence check, coded blind (intensity >= 2) (Sec. F, G) |
| What is the comparison group? | Non-AI (intensity 0) technology control deals in the same primary sectors, geography and period, with covariate-matched 3 to 5 controls (Sec. D, E, O) |
| What outcome is tested? | Primary: ln(EV/LTM Revenue); secondary: EV/EBITDA, 1-day takeover premium (Sec. I, J) |
| What evidence would convince us? | The six-part evidence standard in Section V, including the economic threshold of 0.15 log points and the 12-check robustness rule |

**Phase 1 is complete. No data have been collected, no regressions run, and no conclusion about the existence of an AI premium is stated.**
