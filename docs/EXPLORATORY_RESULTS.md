# Exploratory results (hand-picked 55-deal sample; NOT the pre-registered test)
Pre-registered H1 (strict AI, preferred model): **still NOT ESTIMABLE** (strict-AI N=2 of 31 complete-case deals). Phase 6 classification: **NOT ASSESSABLE**.

## 1. Broad-AI (intensity >= 1) vs non-AI, ln(EV/Revenue), N=31 (9 broad AI)
| Specification | Coefficient (log pts) | 95% CI (HC3) | Permutation p |
|---|---|---|---|
| (1) broad AI only | -0.22 | -0.71 to +0.26 | 0.31 |
| (2) + growth, margin, size | -0.08 | -0.59 to +0.42 | 0.72 |
| (3) + period dummies, strategic buyer | -0.46 | -0.99 to +0.07 | 0.03 |
Reading: no evidence of a positive association. Specifications (1) and (2) are indistinguishable from zero; (3) is negative with a CI that includes zero under HC3 but a small permutation p, and it is the least stable (31 observations, 5 extra parameters). Do not cherry-pick (3). With 9 AI-enabled targets the study cannot rule out moderate effects in either direction.

## 2. Growth-adjusted precedent regression (no AI label), N=31
ln(EV/Revenue) on revenue growth (+1.39, CI -1.5 to +4.3), EBITDA margin (-0.34) and ln revenue (+0.11): **adjusted R2 = 0.11, no coefficient individually significant.** In this hand-picked set growth, margin and size explain little of the multiple dispersion (EV/Revenue 2.2x-36.1x, median 8.0x). Residuals are in results/p9_precedent_residuals.csv (large positives: Altair, Ansys; large negatives: Carbonite).

## 3. Takeover premium (descriptive, N=20)
Median 1-day premium: broad AI 35.2% (n=4) vs non-AI 27.7% (n=16). Not testable at this size.

## Banker takeaway supported by these data
In a hand-picked set of 31 software precedents, simple growth/margin/size adjustment does not tighten the multiple range much, and AI-enabled targets did not trade at higher multiples. This is a caution against mechanical "AI premium" adjustments, not evidence for or against a premium in the wider market.
