# Is There an AI Acquisition Premium? An Empirical Study of Technology M&A Valuation

*Independent student research project, 2026*

**Question:** Conditional on being acquired, do AI-related technology targets sell at higher EV/Revenue multiples or takeover premiums than comparable non-AI targets, once growth, profitability, size, sector and timing are controlled for?

## Result (one line)
In a hand-selected sample of 55 US public technology acquisitions (2015-2025), **AI-enabled targets did not trade at higher EV/Revenue multiples** (median 7.5x vs 8.0x for non-AI). Only 2-3 targets were AI-native, so the pre-registered test was **not assessable**. The result is exploratory, not a market-wide conclusion.

## What was built
| Component | Detail |
|---|---|
| Deal dataset | 55 deals from SEC filings (DEFM14A, 8-K, 10-K/10-Q): offer terms, EV bridges, LTM revenue/EBITDA, unaffected prices, takeover premiums |
| AI classification | Written rubric (0-3 intensity), two blind coders, Cohen's kappa 0.77 / weighted kappa 0.91, adjudication, frozen with SHA-256 checksums |
| Statistical pipeline | HC3 regressions, progressive controls, Gelbach decomposition, CEM and propensity-score matching, bootstrap, placebo (permutation) tests, rule-based evidence classification |
| Validation | Synthetic tests: recovers a planted effect, rejects a growth-only confound, refuses under-powered samples |
| Governance | Pre-registered design, each phase gated on the previous freeze, every deviation logged |

## Start here
- `deliverables/AI_Premium_Study_Master.xlsx` - all deals with live formulas, AI coding, results
- `deliverables/EXPLORATORY_RESULTS.md` - findings
- `deliverables/PROJECT_CLOSEOUT.md` - status and limitations
- `docs/phase1_research_design.md` - hypotheses and evidence standard
- `docs/deviations_log.md` - every deviation from the plan

## Run it
```bash
pip install -r requirements.txt scikit-learn tabulate
python src/tests/test_phase567.py        # synthetic validation
python src/04_descriptives.py            # Phases 4-7, each gated on the previous freeze
python src/05_regressions.py
python src/06_matching.py && python src/07_robustness.py
python src/08_interpretation.py
python src/09_exploratory_broad.py       # exploratory broad-AI analysis
python src/10_master_workbook.py         # rebuilds the Excel workbook
```

## Limitations
Hand-picked (non-systematic) sample; few AI-native targets; selection into being acquired; no causal identification; unaffected prices missing for many deals. A definitive test needs a systematic Capital IQ / PitchBook universe (~300 deals, 30+ AI-native) - the same pipeline runs unchanged on it.

## Data sources
SEC EDGAR filings and company press releases (URLs per deal in the workbook and `docs/source_register.csv`). No proprietary data.
