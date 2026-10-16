# AI Classification Rubric (frozen before coding)

Version 1.0 (6 October 2026). Hash recorded in the treatment-freeze manifest. A rubric change after any coder has begun requires a `deviations_log.md` entry and a documented re-coding of affected rows, and **must precede any look at valuation comparisons**.

## 0. Ground rules

1. Classify the **target as it was at or before the announcement date**. Evidence dated after announcement may only help locate an older source; it never classifies.
2. Coders see no deal values, prices, multiples or premiums. Do not look them up. Do not infer AI status from how excited the buyer's press release is.
3. Coders work independently and do not see each other's sheets. Adjudication is a third pass that sees both rationales and the sources.
4. The four tests structure the evidence; the intensity levels decide. The "two of four tests" guide is not applied mechanically.
5. When unsure between two levels, record the primary choice, set `confidence`, and (adjudicator only) record the alternative in `alt_intensity`. Do not resolve doubt by looking at anything about the deal's price.

## 1. The four tests (record 0/1 plus evidence ids)

| Test | Pass if | Fail / does not count |
|---|---|---|
| `product_test` | The principal product would lose its essential function if the ML/AI model were removed (generative model, vision inference, autonomous decisioning, ML prediction platform, model-serving product) | Normal SaaS with an optional assistant; dashboards with a few ML features; workflow tools that recently added generative AI |
| `technical_asset_test` | Documented proprietary trained models, dedicated training infrastructure, ML-specific inference system, proprietary AI architecture, AI accelerator silicon, or a substantial dedicated ML research organisation (papers, patents, named research team) | "Powered by AI", "AI-driven", generic claims, use of a third-party API |
| `revenue_test` | Credible evidence that AI/ML is a primary monetised product, drives material demand, or is explicitly responsible for material revenue/bookings/growth. A clearly AI-native firm without disclosed revenue split is **not** failed automatically | Marketing claims of AI-driven growth without product dependence |
| `persistence_12m` | AI positioning documented at least 12 months before announcement (archived site, prior annual report, earlier funding announcement, product launch, technical publication, archived press release) | AI wording first appearing within 12 months of announcement or only on a current website. If the company is younger than 12 months at announcement set `persistence_not_testable = 1` and leave `persistence_12m` = 0 |

## 2. Intensity levels

| Level | Rule of thumb |
|---|---|
| 0 Non-AI | AI absent or incidental. Core product does not materially depend on AI |
| 1 AI-enabled | AI improves the product but is not fundamental (CRM plus assistant; workflow plus generative feature; security product with ML detection as one component; recommendation engine inside SaaS) |
| 2 AI-native | AI/ML is central to the product and commercial value proposition; removing it changes what is sold |
| 3 Frontier / core AI infrastructure | Foundation-model developer; AI model-serving infrastructure; AI accelerator company; dedicated training/inference infrastructure; MLOps/model infrastructure whose central purpose is AI workloads |

Primary treatment `ai_flag_strict = 1` iff final intensity >= 2. `ai_flag_broad = 1` iff final intensity >= 1.

## 3. Sector-specific rules

- **Semiconductors.** Not every chip company is AI. Level 3 only if the core product is primarily AI acceleration, ML training/inference or neural processing. CPUs, networking, memory, analog and RF are Level 0 unless the target is explicitly AI-focused. A general-purpose chip with an "AI-ready" feature is Level 1 at most.
- **Cybersecurity.** ML as a detection feature is Level 1. Level 2 only if the core architecture and value proposition are fundamentally ML-native (for example the product is a behavioural model, not rules plus an ML module). Document the reasoning.
- **Enterprise software.** The largest AI-washing risk. CRM/ERP/HCM plus an AI assistant is Level 1. A dedicated enterprise model platform, or a product whose function is the model's output, can be Level 2. Use the product-dependency test.
- **AI infrastructure boundary.** Infrastructure built specifically for AI qualifies. General cloud management, storage and networking used by AI customers does not.
- **Internet platforms / IT services.** Recommendation, search ranking or analytics inside a platform is Level 1 unless the model is the product sold. IT services firms that implement AI for clients are Level 1 at most unless they own a proprietary model platform.

## 4. Era-specific language (do not bias toward generative-AI wording)

Pre-2022 AI often appears as predictive analytics, statistical learning, cognitive computing, pattern recognition, neural networks, deep learning, "smart" or "intelligent" products. Judge by product dependence on a trained model, not by modern vocabulary. Conversely, a 2023-24 "AI" rebrand of unchanged analytics fails persistence.

## 5. Acqui-hires and technology licences

Set `acquihire_ai_flag = 1` if the product was shut down, founders joined the buyer, IP was licensed rather than the company bought, or there is little or no recurring business. These stay outside the primary sample whatever the intensity.

## 6. Subsector (final strict-AI targets, one primary, optional secondary)

1 Foundation Models / Generative AI; 2 AI Developer Tools / MLOps / AI Data Infrastructure; 3 Enterprise AI Software; 4 Vertical AI; 5 Computer Vision / NLP / Conversational AI; 6 Autonomous Systems / Robotics; 7 AI Cybersecurity; 8 AI Semiconductors / Accelerators / Infrastructure; 9 Traditional ML / Predictive Analytics. Choose by what the product does; hybrids get a secondary label.

Collapsing for estimation uses **counts only**: {1,2,8} Core AI Platform / Infrastructure, {3,4,5,9} AI Applications, {6,7} Specialized AI; any group with N < 8 is merged into "Other AI". Never grouped by anything about valuation.

## 7. Confidence

| Level | Meaning |
|---|---|
| High | Multiple Tier A/B or historical sources and clear product dependence |
| Medium | Strong evidence but incomplete commercial disclosure |
| Low | Ambiguous business model or limited historical information |

## 8. Evidence source tiers

A historical company filing or product documentation; B archived company website, technical paper or official funding announcement; C reliable press or database description; D current website describing a historical company (**never sufficient**, and not used for classification). A final strict-AI label needs at least one source dated on or before the announcement and, where possible, two supporting sources with at least one at tier A/B. No final strict-AI label may rest on NLP alone.

## 9. Counter-evidence (record in `counterevidence_notes`)

Examples: years as workflow SaaS; AI feature launched shortly before the deal; core revenue still non-AI; company description changed only after the rumour. Counter-evidence is considered at adjudication.

## 10. Disagreement categories (adjudicator assigns one)

AI-enabled vs AI-native; Marketing vs core technology; Software vs AI infrastructure; Persistence evidence unavailable; AI was core only after acquisition; Semiconductor AI exposure ambiguity; Other (explain).

## 11. Optional descriptors

`company_founded_year` (target founding or first AI product year, not the deal date) drives `ai_company_vintage` (pre-2015 established ML; 2015-2019; 2020-2022; 2023 and later). `commercial_maturity`: Pre-revenue, Early revenue, Scaling or Mature, from financial or commercial disclosures only, never from deal value.
