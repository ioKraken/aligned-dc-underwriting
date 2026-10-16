# Resume & Interview Pack - AI Acquisition Premium Study (student project)

## Resume entry
**Empirical Study: Is There an AI Acquisition Premium in Technology M&A?** - Independent Research Project, 2026
- Designed a pre-registered empirical study testing whether AI targets command higher acquisition multiples (EV/Revenue) than comparable tech targets after controlling for growth, margin, size, sector and timing.
- Built a 55-deal dataset of US public tech acquisitions (2015-2025) from SEC filings, reconciling enterprise-value bridges and LTM revenue to source documents.
- Developed a Python pipeline (HC3 regressions, matching, bootstrap and placebo tests), validated on simulated data where it detected a planted effect and rejected a growth-only confound.
- Ran a two-coder blind classification of target AI intensity (kappa 0.77; weighted kappa 0.91).
- Found no evidence that AI-enabled targets traded at higher multiples in the sample (median 7.5x vs 8.0x EV/Revenue) and identified the data required for a definitive test.

**One-liner:** Independent research testing for an "AI premium" in tech M&A: built a 55-deal SEC-sourced dataset and a statistically validated Python pipeline; found no premium in the sample.

## 30-second pitch
"I wanted to know whether buyers really pay more for AI companies, or whether AI firms just grow faster. I built a dataset of 55 tech acquisitions from SEC filings, had two people classify the targets blind, and tested it with the controls a banker would use. In my sample, AI-enabled targets didn't trade at higher revenue multiples. With only a handful of truly AI-native deals I can't say a premium doesn't exist market-wide, but the takeaway for valuation work is: don't add a mechanical 'AI premium' to precedents without matching on growth and margins first."

## Likely questions
- **What did you find?** No higher EV/Revenue for AI-enabled targets in a 55-deal sample; not definitive (2-3 AI-native deals).
- **Did AI cause anything?** No causal claim - association only; AI firms differ in growth, size and timing.
- **Why EV/Revenue?** Many software targets have negative EBITDA; EV/EBITDA is secondary.
- **How did you build EV?** Equity value + debt + preferred + minority interest - cash, from filings; reported EV used when the company stated it.
- **Takeover premium vs valuation premium?** Premium = offer vs unaffected share price; valuation premium = multiple vs comparable deals. A 20x deal can carry a 10% premium.
- **Why HC3 / bootstrap / placebo?** Small samples with outliers; inference without normality; checks how big an effect arises by chance.
- **Biggest limitation?** Hand-picked sample, few AI-native targets, selection into being acquired.
- **Next step?** Capital IQ/PitchBook universe of ~300 deals with 30+ AI-native targets; rerun the same pipeline.

## Don't say
"Proved there is no AI premium" - "Used Capital IQ" - any % presented as "the AI premium".
