-- Sample views. NONE of these filter on AI status (ai_candidate_flag is exposed as a column only).
-- Thresholds are frozen from Phase 1: EV >= US$25m, LTM revenue >= US$5m, quality A-C, staleness <= 365 days.

DROP VIEW IF EXISTS v_deal_universe;
CREATE VIEW v_deal_universe AS
SELECT d.*
FROM deals d
WHERE d.announcement_date BETWEEN '2015-01-01' AND '2026-09-30';

-- Deals that pass the structural/sample-definition filters (everything except financial availability).
DROP VIEW IF EXISTS v_primary_structure;
CREATE VIEW v_primary_structure AS
SELECT d.*
FROM v_deal_universe d
WHERE d.control_deal = 1
  AND d.primary_geography = 1
  AND d.primary_sector = 1
  AND d.status_primary_sample = 1
  AND d.structural_exclusion IS NULL
  AND COALESCE(d.spac_flag,0) = 0
  AND COALESCE(d.distressed_flag,0) = 0
  AND COALESCE(d.acquihire_flag,0) = 0;

DROP VIEW IF EXISTS v_evrev_candidates;
CREATE VIEW v_evrev_candidates AS
SELECT d.deal_id, d.announcement_date, d.target_id, d.buyer_id, d.sector_primary, d.subsector,
       d.target_country, d.public_target, d.buyer_type, d.strategic_buyer, d.sponsor_buyer,
       d.mixed_consortium, d.cross_border, d.cash_pct, d.stock_pct,
       d.ev_usd, f.revenue_ltm_usd, f.revenue_growth, f.ebitda_margin, f.ebitda_positive,
       f.staleness_days, d.data_quality_flag, d.ai_candidate_flag,
       d.ev_usd / f.revenue_ltm_usd        AS ev_revenue,
       CAST(strftime('%Y', d.announcement_date) AS INTEGER) AS announce_year
FROM v_primary_structure d
JOIN financials f ON f.deal_id = d.deal_id AND f.company_id = d.target_id
WHERE d.ev_usd >= 25000000
  AND f.revenue_ltm_usd >= 5000000
  AND d.data_quality_flag IN ('A','B','C')
  AND f.financials_stale_flag = 0;

DROP VIEW IF EXISTS v_ebitda_candidates;
CREATE VIEW v_ebitda_candidates AS
SELECT e.*, f.ebitda_ltm_usd, e.ev_usd / f.ebitda_ltm_usd AS ev_ebitda
FROM v_evrev_candidates e
JOIN financials f ON f.deal_id = e.deal_id AND f.company_id = e.target_id
WHERE f.ebitda_ltm_usd > 0;

DROP VIEW IF EXISTS v_public_premium_candidates;
CREATE VIEW v_public_premium_candidates AS
SELECT d.deal_id, d.announcement_date, d.target_id, d.sector_primary, d.target_country,
       d.buyer_type, d.strategic_buyer, d.offer_price, d.unaffected_date, d.unaffected_price_1d,
       d.price_1w, d.price_1m, d.vwap_30, d.price_90d, d.leak_flag, d.data_quality_flag,
       d.ai_candidate_flag,
       d.offer_price / d.unaffected_price_1d - 1 AS premium_1d,
       d.offer_price / d.price_1w - 1            AS premium_1w,
       d.offer_price / d.price_1m - 1            AS premium_1m,
       d.offer_price / d.vwap_30 - 1             AS premium_vwap30,
       d.price_90d IS NOT NULL                   AS has_runup_inputs
FROM v_primary_structure d
WHERE d.public_target = 1
  AND d.offer_price > 0
  AND d.unaffected_price_1d > 0
  AND d.unaffected_date IS NOT NULL
  AND d.unaffected_date < d.announcement_date;

-- Coder-facing view: NO valuation, price or deal-term columns. Valuation columns are excluded by construction.
DROP VIEW IF EXISTS v_ai_coding_blind;
CREATE VIEW v_ai_coding_blind AS
SELECT c.company_id,
       c.canonical_name         AS target_name,
       d.announcement_date,
       d.sector_primary         AS sector,
       b.target_description     AS business_description,
       b.snapshot_announcement  AS website_snapshot_text,
       b.filing_description,
       b.historical_description AS technical_description
FROM v_primary_structure d
JOIN companies c ON c.company_id = d.target_id
LEFT JOIN business_descriptions b ON b.deal_id = d.deal_id AND b.company_id = d.target_id;
