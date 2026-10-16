# Phase 4 report - descriptive and diagnostic (UNADJUSTED)

No number below is an 'AI premium'. All AI vs non-AI differences are unadjusted.


Data version: ANALYSIS_V1_PHASE4. Treatment version: AI_CLASSIFICATION_V1_20261013.

## A. Sample waterfall

```
outcome,stage,step,total_N,strict_AI_N,non_AI_N,AI_enabled_N(intensity=1)
EV/Revenue,1,Raw identified tech M&A universe (post-dedupe),55,3,51,13
EV/Revenue,2,Correct period (2015-01-01..2026-09-30),55,3,51,13
EV/Revenue,3,Primary geography,55,3,51,13
EV/Revenue,4,Primary sectors,54,3,51,13
EV/Revenue,5,Control transactions,54,3,51,13
EV/Revenue,6,Status: completed / definitive,54,3,51,13
EV/Revenue,7,Structural exclusions removed,54,3,51,13
EV/Revenue,8,EV available,35,2,33,9
EV/Revenue,9,EV >= $25m,35,2,33,9
EV/Revenue,10,Revenue available,35,2,33,9
EV/Revenue,11,Revenue >= $5m,35,2,33,9
EV/Revenue,12,"Financial freshness (<=365d, aligned)",35,2,33,9
EV/Revenue,13,Quality A-C,35,2,33,9
EV/Revenue,14,AI classification available (frozen Phase 3),35,2,33,9
EV/Revenue,15,Not acqui-hire / licence (acquihire_ai_flag = 0),35,2,33,9
EV/EBITDA,1,Raw identified tech M&A universe (post-dedupe),55,3,51,13
EV/EBITDA,2,Correct period (2015-01-01..2026-09-30),55,3,51,13
EV/EBITDA,3,Primary geography,55,3,51,13
EV/EBITDA,4,Primary sectors,54,3,51,13
EV/EBITDA,5,Control transactions,54,3,51,13
EV/EBITDA,6,Status: completed / definitive,54,3,51,13
EV/EBITDA,7,Structural exclusions removed,54,3,51,13
EV/EBITDA,8,EV available,35,2,33,9
EV/EBITDA,9,EV >= $25m,35,2,33,9
EV/EBITDA,10,Revenue available,35,2,33,9
EV/EBITDA,11,Revenue >= $5m,35,2,33,9
EV/EBITDA,12,"Financial freshness (<=365d, aligned)",35,2,33,9
EV/EBITDA,13,Quality A-C,35,2,33,9
EV/EBITDA,14,EBITDA available,33,2,31,8
EV/EBITDA,15,EBITDA > 0,17,2,15,3
EV/EBITDA,16,AI classification available (frozen Phase 3),17,2,15,3
EV/EBITDA,17,Not acqui-hire / licence (acquihire_ai_flag = 0),17,2,15,3
Takeover premium,1,Raw identified tech M&A universe (post-dedupe),55,3,51,13
Takeover premium,2,Correct period (2015-01-01..2026-09-30),55,3,51,13
Takeover premium,3,Primary geography,55,3,51,13
Takeover premium,4,Primary sectors,54,3,51,13
Takeover premium,5,Control transactions,54,3,51,13
Takeover premium,6,Status: completed / definitive,54,3,51,13
Takeover premium,7,Structural exclusions removed,54,3,51,13
Takeover premium,8,Public target,54,3,51,13
Takeover premium,9,Offer price available,54,3,51,13
Takeover premium,10,Unaffected price available,20,2,18,2
Takeover premium,11,Unaffected date valid (< announcement),20,2,18,2
Takeover premium,12,Quality A-C,20,2,18,2
Takeover premium,13,AI classification available (frozen Phase 3),20,2,18,2
Takeover premium,14,Not acqui-hire / licence (acquihire_ai_flag = 0),20,2,18,2
```

## Waterfall consistency with Phase 2

```
outcome,matches_phase2_flag_after_ai_and_acquihire
EV/Revenue,True
EV/EBITDA,True
Takeover premium,True
```

## C. EV reconciliation

```
N_with_components,N,mean,median,sd,min,p1,p5,p25,p75,p95,p99,max,N_flagged_gt_5pct,tolerance
3,3,0.04805409393939394,0.036,0.025018971098477925,0.0313441,0.031437218,0.03180969,0.033672049999999995,0.05640909090909091,0.07273636363636363,0.07600181818181817,0.07681818181818181,1,5% of reported EV
```

## D. Staleness

```
N,mean,median,sd,min,p1,p5,p25,p75,p95,p99,max,group,mannwhitney_p_AI_vs_nonAI
3,101.0,102.0,16.522711641858304,84,84.36,85.8,93.0,109.5,115.5,116.7,117,strict_AI,0.1511122753837473
51,76.76470588235294,72.0,30.42997747964603,30,31.0,34.5,51.5,101.5,125.0,129.0,130,non_AI,0.1511122753837473
```

## H. Missingness

```
variable,group,available,missing,pct_missing
EV,all,35,19,0.35185185185185186
EV,AI,2,1,0.3333333333333333
EV,nonAI,33,18,0.35294117647058826
Revenue,all,54,0,0.0
Revenue,AI,3,0,0.0
Revenue,nonAI,51,0,0.0
Growth,all,35,19,0.35185185185185186
Growth,AI,1,2,0.6666666666666666
Growth,nonAI,34,17,0.3333333333333333
EBITDA,all,52,2,0.037037037037037035
EBITDA,AI,3,0,0.0
EBITDA,nonAI,49,2,0.0392156862745098
Margin,all,52,2,0.037037037037037035
Margin,AI,3,0,0.0
Margin,nonAI,49,2,0.0392156862745098
Premium (public only),all,20,34,0.6296296296296297
Premium (public only),AI,2,1,0.3333333333333333
Premium (public only),nonAI,18,33,0.6470588235294118
```

## Missingness tests

```
availability,AI_available_rate,nonAI_available_rate,chi2_p,fisher_p
EV,0.6666666666666666,0.6470588235294118,0.9448994387119289,1.0
Revenue,1.0,1.0,,1.0
Growth,0.3333333333333333,0.6666666666666666,0.2400243188128361,0.2803580067731011
EBITDA,1.0,0.9607843137254902,0.7266906743330388,1.0
Margin,1.0,0.9607843137254902,0.7266906743330388,1.0
```

## K. Raw comparison (UNADJUSTED)

```
metric,AI,non_AI,difference,label
Median EV/Revenue,7.848344728628552,7.987040786809373,-0.13869605818082054,UNADJUSTED difference (turns of revenue)
Median EV/Revenue ratio-1,7.848344728628552,7.987040786809373,-0.017365137086801652,UNADJUSTED percentage difference
Mean ln(EV/Revenue),1.7015082567514823,2.1088967972485784,-0.40738854049709605,UNADJUSTED log-point difference
Median EV/EBITDA,51.36887826182029,42.6016499946748,8.76722826714549,UNADJUSTED
Median premium 1D,0.3227140259246455,0.29062738515277203,0.032086640771873454,UNADJUSTED
Median revenue growth,,0.2397449103247697,,descriptive
Median EBITDA margin,0.15225093887451846,-0.0424227595471118,0.19467369842163026,descriptive
Median LTM revenue (USD),1179553000.0,768142000.0,411411000.0,descriptive
```

## X. Univariate tests (descriptive)

```
outcome,AI_mean,nonAI_mean,AI_median,nonAI_median,welch_diff,welch_t,welch_p,welch_ci_low,welch_ci_high,mwu_p,rank_biserial,cohens_d,n_AI,n_nonAI,label
ln(EV/Revenue),1.7015082567514823,2.1088967972485784,1.7015082567514823,2.07782032657169,,,,,,,,,2,33,descriptive / unadjusted - not an AI premium
EV/Revenue (raw),7.848344728628552,9.49101242434219,7.848344728628552,7.987040786809373,,,,,,,,,2,33,descriptive / unadjusted - not an AI premium
Revenue growth,,0.2459600060721294,,0.2397449103247697,,,,,,,,,0,21,descriptive / unadjusted - not an AI premium
EBITDA margin,0.15225093887451846,-0.030206529265359564,0.15225093887451846,-0.0424227595471118,,,,,,,,,2,31,descriptive / unadjusted - not an AI premium
Premium 1D,0.3227140259246455,0.32926658784848395,0.3227140259246455,0.29062738515277203,,,,,,,,,2,18,descriptive / unadjusted - not an AI premium
```

## T. Intensity

```
ai_intensity,N,median_ev_revenue,median_growth,median_margin,median_revenue
0.0,24,7.997393970807675,0.25493940502998763,0.0039417332259024,776433500.0
1.0,9,7.507145542605657,0.1665779952241148,-0.10424065928617851,660002000.0
2.0,2,7.848344728628552,,0.15225093887451846,1179553000.0
```

## U. Pre/post GenAI

```
period,AI_N,nonAI_N,AI_median_EV_Rev,nonAI_median_EV_Rev,note
Pre-Nov 2022,1,17,13.464561547399358,8.787852158023764,descriptive; not a causal difference-in-differences
Post-Nov 2022,1,16,2.2321279098577467,6.627268502607824,descriptive; not a causal difference-in-differences
```

## Z. VIF

```
variable,VIF,flag_gt_5,N
revenue_growth,2.8434018515399777,0,21
ebitda_margin,2.1744937436285205,0,21
ln_revenue,1.261174145563404,0,21
public,0.0,0,21
strategic,1.7081999688965979,0,21
```

## AB. Common support

```
note
propensity model not estimable (too few AI or non-AI with complete covariates)
```

## AC. Balance

```
covariate,AI_mean,nonAI_mean,SMD,abs_SMD_ge_0.10
revenue_growth,,0.2459600060721294,,
ebitda_margin,0.15225093887451846,-0.030206529265359564,1.0730777832288991,1.0
ln_revenue,20.85864048834687,20.33323730365482,0.8244047376109574,1.0
public,1.0,1.0,,
strategic,0.5,0.30303030303030304,0.3287848297899281,1.0
post_genai,0.5,0.48484848484848486,0.024618298195866525,0.0
```

## AD. Power / MDE

```
model,N_AI,N_nonAI,outcome_sd,MDE_log_points,MDE_percent,note
EV/Revenue (log),2,33,0.5448443011360087,1.1115738065957244,2.039137647514174,"unconditional SD (conservative; covariates will reduce it); alpha .05, power .80"
Takeover premium 1D,2,18,0.18606796375143633,,0.38854308996549924,MDE in premium percentage points (fraction)
```

## AE. Model sample sizes

```
model,N,AI_N,nonAI_N
Unconditional,35,2,33
Fundamentals,21,0,21
+ Year FE,21,0,21
+ Sector FE,21,0,21
"Preferred (+ region, public, strategic)",21,0,21
```

## Interaction cells

```
cell,AI_N,nonAI_N,label
AI x Strategic,1,10,STRONGLY EXPLORATORY (cell N<15)
AI x Non-strategic,1,23,STRONGLY EXPLORATORY (cell N<15)
AI x Post-GenAI,1,16,STRONGLY EXPLORATORY (cell N<15)
AI x Pre-GenAI,1,17,STRONGLY EXPLORATORY (cell N<15)
AI x Public,2,33,STRONGLY EXPLORATORY (cell N<15)
AI x Private,0,0,STRONGLY EXPLORATORY (cell N<15)
```
