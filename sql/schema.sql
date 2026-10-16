-- Phase 2 schema (SQLite dialect; portable to PostgreSQL with minor type changes).
-- Missingness codes: NA = not applicable, ND = not disclosed, NF = not found after search,
-- NR = not reliable enough. Numeric columns hold true NULL; the reason is stored in
-- the *_missing_code columns / collection_log.csv.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  company_id      INTEGER PRIMARY KEY,
  canonical_name  TEXT NOT NULL,
  former_name     TEXT,
  ticker          TEXT,
  exchange        TEXT,
  country         TEXT,
  website         TEXT,
  public_private  TEXT CHECK (public_private IN ('public','private','subsidiary')),
  sector          TEXT,
  subsector       TEXT
);

CREATE TABLE IF NOT EXISTS deals (
  deal_id                 TEXT PRIMARY KEY,
  target_id               INTEGER REFERENCES companies(company_id),
  buyer_id                INTEGER REFERENCES companies(company_id),
  announcement_date       DATE NOT NULL,
  close_date              DATE,
  deal_status             TEXT CHECK (deal_status IN
                           ('announced','definitive','completed','withdrawn','rejected','competing_bid','terminated')),
  status_primary_sample   INTEGER,            -- 1 if completed or definitive
  contested               INTEGER DEFAULT 0,
  deal_type               TEXT,               -- control / minority / asset / spac / acquihire / carveout ...
  control_deal            INTEGER,
  target_country          TEXT,
  buyer_country           TEXT,
  primary_geography       INTEGER,
  cross_border            INTEGER,
  public_target           INTEGER,
  buyer_type              TEXT CHECK (buyer_type IN
                           ('strategic','sponsor','consortium','government_swf','other')),
  strategic_buyer         INTEGER,
  sponsor_buyer           INTEGER,
  mixed_consortium        INTEGER DEFAULT 0,
  sector_primary          TEXT,
  subsector               TEXT,
  primary_sector          INTEGER,
  classification_source   TEXT,
  structural_exclusion    TEXT,               -- reason code or NULL
  spac_flag               INTEGER DEFAULT 0,
  distressed_flag         INTEGER DEFAULT 0,
  acquihire_flag          INTEGER DEFAULT 0,
  -- value terminology
  headline_value          REAL,
  headline_value_type     TEXT CHECK (headline_value_type IN
                           ('headline','equity','enterprise','consideration','implied_ev','undisclosed')),
  equity_value            REAL,
  enterprise_value        REAL,
  ev_basis                TEXT,
  -- EV construction
  debt_assumed            REAL,
  cash_acquired           REAL,
  preferred               REAL,
  minority_interest       REAL,
  other_ev_adjustments    REAL,
  ev_reported             REAL,
  ev_calculated           REAL,
  ev_final                REAL,
  -- contingent consideration
  contingent_consideration INTEGER DEFAULT 0,
  contingent_type         TEXT,
  contingent_max          REAL,
  contingent_expected     REAL,
  included_in_ev          INTEGER DEFAULT 0,
  -- consideration mix
  cash_pct                REAL,
  stock_pct               REAL,
  other_pct               REAL,
  -- currency
  currency_original       TEXT,
  value_original          REAL,
  fx_rate_announcement    REAL,
  ev_usd                  REAL,
  equity_value_usd        REAL,
  -- public price data
  offer_price             REAL,
  unaffected_date         DATE,
  unaffected_reason       TEXT,
  unaffected_price_1d     REAL,
  price_1w                REAL,
  price_1m                REAL,
  vwap_30                 REAL,
  price_90d               REAL,
  rumor_date              DATE,
  rumor_source            TEXT,
  leak_flag               INTEGER,
  predeal_market_cap      REAL,
  predeal_ev              REAL,
  -- quality / disclosure
  ev_disclosed            INTEGER,
  financials_disclosed    INTEGER,
  data_quality_flag       TEXT CHECK (data_quality_flag IN ('A','B','C','D')),
  ai_candidate_flag       INTEGER,            -- SCREEN ONLY; final ai_flag lives in ai_classifications (Phase 3)
  candidate_keyword_hits  TEXT,
  source_universe         TEXT,
  source_url              TEXT,
  notes                   TEXT
);

CREATE TABLE IF NOT EXISTS deal_bids_history (
  deal_id    TEXT REFERENCES deals(deal_id),
  bidder     TEXT,
  bid_date   DATE,
  bid_price  REAL,
  status     TEXT,
  source     TEXT
);

CREATE TABLE IF NOT EXISTS financials (
  company_id            INTEGER REFERENCES companies(company_id),
  deal_id               TEXT REFERENCES deals(deal_id),
  revenue_period_end    DATE,
  revenue_ltm           REAL,
  revenue_prior_ltm     REAL,
  ebitda_ltm            REAL,
  ebitda_definition     TEXT CHECK (ebitda_definition IN ('reported','adjusted','database_normalized') OR ebitda_definition IS NULL),
  currency              TEXT,
  revenue_ltm_usd       REAL,
  ebitda_ltm_usd        REAL,
  staleness_days        INTEGER,
  financials_stale_flag INTEGER,
  revenue_growth        REAL,
  ebitda_margin         REAL,
  ebitda_positive       INTEGER,
  source_revenue        TEXT,
  source_ebitda         TEXT,
  PRIMARY KEY (company_id, deal_id)
);

CREATE TABLE IF NOT EXISTS ai_classifications (   -- populated in Phase 3 only
  company_id     INTEGER REFERENCES companies(company_id),
  as_of_date     DATE,
  ai_flag        INTEGER,
  ai_intensity   INTEGER CHECK (ai_intensity BETWEEN 0 AND 3 OR ai_intensity IS NULL),
  ai_subsector   TEXT,
  method         TEXT,
  coder1         INTEGER,
  coder2         INTEGER,
  nlp_score      REAL,
  confidence     TEXT,
  evidence_url   TEXT
);

CREATE TABLE IF NOT EXISTS business_descriptions (
  company_id               INTEGER REFERENCES companies(company_id),
  deal_id                  TEXT REFERENCES deals(deal_id),
  target_description       TEXT,
  announcement_description TEXT,
  website_description      TEXT,
  filing_description       TEXT,
  historical_description   TEXT,
  snapshot_announcement    TEXT,
  snapshot_minus_12m       TEXT,
  ai_terms_preexisting     INTEGER,
  PRIMARY KEY (company_id, deal_id)
);

CREATE TABLE IF NOT EXISTS market_data (
  date            DATE PRIMARY KEY,
  nasdaq_ret_12m  REAL,
  software_ev_rev REAL,
  ust10y          REAL,
  fed_funds       REAL,
  vix             REAL
);

CREATE TABLE IF NOT EXISTS sources (         -- source register (long form, field-level provenance)
  source_id       INTEGER PRIMARY KEY,
  deal_id         TEXT,
  field           TEXT,
  source_type     TEXT,
  source_tier     INTEGER CHECK (source_tier IN (1,2,3)),
  source_name     TEXT,
  url             TEXT,
  document_date   DATE,
  retrieved_date  DATE,
  value_supported TEXT,
  conflict_flag   INTEGER DEFAULT 0,
  conflicting_values TEXT,
  selected_value  TEXT,
  selection_reason TEXT,
  notes           TEXT
);

CREATE TABLE IF NOT EXISTS collection_log (
  deal_id        TEXT,
  field          TEXT,
  researcher     TEXT,
  search_date    DATE,
  source_found   TEXT,
  source_quality TEXT,
  missing_code   TEXT CHECK (missing_code IN ('NA','ND','NF','NR') OR missing_code IS NULL),
  missing_reason TEXT,
  notes          TEXT
);

CREATE INDEX IF NOT EXISTS ix_deals_ann     ON deals(announcement_date);
CREATE INDEX IF NOT EXISTS ix_deals_target  ON deals(target_id);
CREATE INDEX IF NOT EXISTS ix_deals_sector  ON deals(sector_primary);
CREATE INDEX IF NOT EXISTS ix_deals_country ON deals(target_country);
CREATE INDEX IF NOT EXISTS ix_fin_company   ON financials(company_id);
CREATE INDEX IF NOT EXISTS ix_src_deal      ON sources(deal_id, field);
