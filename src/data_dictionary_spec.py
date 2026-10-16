"""Single source of truth for docs/data_dictionary.md. Run: python src/data_dictionary_spec.py
A test asserts that every column of deals_stage2.csv and financials_stage2.csv has an entry here."""
from __future__ import annotations

from pathlib import Path

# (name, definition, unit, source, transformation, null_allowed, example)
D = lambda *a: a  # noqa: E731
ROWS = [
 # ---- identity & status -----------------------------------------------------------------------
 D("deal_id", "Unique ID of the primary (winning/final) announcement; one row per deal", "text", "universe / generated", "SHA1(canonical_key)[:10] if not supplied", "No", "D3F2A9C01B"),
 D("target_id", "companies.company_id of the target", "int", "01_collect.py", "name normalisation + alias map", "No", "17"),
 D("buyer_id", "companies.company_id of the buyer", "int", "01_collect.py", "same", "Yes", "42"),
 D("target_name", "Target name as recorded in the universe", "text", "universe", "none", "No", "Alpha Systems Inc"),
 D("buyer_name", "Acquirer name", "text", "universe", "none", "No", "Omega Corp"),
 D("announcement_date", "First date definitive terms were announced", "date", "Tier 1 filing / press release", "parsed to date", "No", "2023-03-15"),
 D("close_date", "Completion date", "date", "filings", "parsed", "Yes (not completed)", "2023-06-30"),
 D("deal_status", "announced / definitive / completed / withdrawn / rejected / competing_bid / terminated", "enum", "filings / news", "lower-case snake_case", "No", "completed"),
 D("status_primary_sample", "1 if status is completed or definitive", "0/1", "derived", "deal_status in {completed, definitive}", "No", "1"),
 D("contested", "1 if rival bidders (different buyers) existed within 365 days; row is the winning bid", "0/1", "01_collect.py", "cluster by target within 365d", "No", "0"),
 D("needs_review", "1 if competing/revised-bid winner was ambiguous and requires manual confirmation", "0/1", "01_collect.py", "see duplicate protocol", "No", "0"),
 D("canonical_key", "normalised_target|announcement_date|normalised_buyer", "text", "derived", "legal suffixes stripped, ASCII, lower-case", "No", "alpha systems|2023-03-15|omega"),
 D("source_universe", "Screen(s) that produced the row (merged on duplicates)", "text", "universe", "concatenated with ';'", "No", "synthetic_screen"),
 D("source_url", "URL of the universe source", "url", "universe", "none", "Yes", ""),
 D("notes", "Free-text analyst notes", "text", "analyst", "none", "Yes", ""),
 D("classification_source", "Provenance label of sector classification (target business, never buyer)", "text", "derived", "target_business_<source>", "No", "target_business_screen"),
 # ---- type / geography / sector -------------------------------------------------------------------
 D("deal_type", "control (default) / minority / venture_round / pipe / asset_only / spac / distressed / acquihire / internal", "enum", "universe", "blank => control (control_assumed=1)", "No", "control"),
 D("control_deal", "1 if buyer obtains >=50% / control", "0/1", "derived", "deal_type in {blank, control}", "No", "1"),
 D("control_assumed", "1 if control status was inferred from blank deal_type", "0/1", "derived", "none", "No", "1"),
 D("structural_exclusion", "Reason code for Phase 1 structural exclusion (minority, venture_round, pipe, asset_only, carveout_no_standalone, internal, spac, distressed, acquihire)", "enum", "derived / analyst", "see utils.STRUCTURAL_EXCLUSION_CODES", "Yes (eligible)", "minority"),
 D("spac_flag", "1 if SPAC business combination", "0/1", "derived", "structural_exclusion == spac", "No", "0"),
 D("distressed_flag", "1 if distressed / insolvency sale", "0/1", "derived", "structural_exclusion == distressed", "No", "0"),
 D("acquihire_flag", "1 if acqui-hire / licence-and-hire", "0/1", "derived", "structural_exclusion == acquihire", "No", "0"),
 D("standalone_financials", "Analyst flag (1) that a subsidiary target has standalone financials", "0/1", "analyst", "subsidiary without 1 => excluded", "Yes", "1"),
 D("target_country", "Target country, ISO-3166 alpha-2", "ISO2", "universe", "names mapped to ISO2", "No", "US"),
 D("buyer_country", "Buyer country, ISO2", "ISO2", "universe", "same", "Yes", "US"),
 D("target_region", "US / Canada / UK / Israel / EU_EEA_CH (Switzerland grouped; see deviations_log D-000)", "enum", "derived", "utils.REGION_MAP", "Yes (out of scope)", "EU_EEA_CH"),
 D("primary_geography", "1 if target in US, CA, UK, EU/EEA, CH, IL", "0/1", "derived", "country in PRIMARY_COUNTRIES", "No", "1"),
 D("cross_border", "1 if buyer and target countries differ", "0/1", "derived", "none", "No", "0"),
 D("sector", "Sector label as supplied", "text", "universe", "none", "No", "Software"),
 D("sector_primary", "Standardised primary sector (6 categories) of the TARGET business", "enum", "derived", "SECTOR_ALIASES map", "Yes (out of scope)", "Cybersecurity"),
 D("primary_sector", "1 if sector_primary is one of the six primary sectors", "0/1", "derived", "none", "No", "1"),
 D("subsector", "Granular subsector", "text", "universe", "none", "Yes", "endpoint security"),
 D("target_public_private", "public / private / subsidiary at announcement", "enum", "universe", "lower-case", "No", "public"),
 D("public_target", "1 if listed at announcement", "0/1", "derived", "target_public_private == public", "No", "1"),
 D("buyer_type", "strategic / sponsor / consortium / government_swf / other", "enum", "universe", "normalised", "No", "strategic"),
 D("strategic_buyer", "1 if buyer_type == strategic", "0/1", "derived", "none", "No", "1"),
 D("sponsor_buyer", "1 if buyer_type == sponsor", "0/1", "derived", "none", "No", "0"),
 D("mixed_consortium", "1 if a consortium contains both strategic and sponsor investors", "0/1", "universe", "not forced into either class", "No", "0"),
 D("in_period", "1 if announced 2015-01-01..2026-09-30", "0/1", "derived", "none", "No", "1"),
 D("post_genai", "1 if announced after 2022-11-30 (fixed primary date)", "0/1", "derived", "none", "No", "1"),
 D("announce_year", "Calendar year of announcement", "year", "derived", "none", "No", "2023"),
 # ---- value ----------------------------------------------------------------------------------------
 D("headline_raw", "Headline transaction value exactly as recorded (may hold ND/NF/NR/NA)", "text", "universe", "none", "Yes", "ND"),
 D("headline_value", "Headline value, numeric, original currency; NOT assumed to be EV", "currency units", "universe / terms", "numeric parse", "Yes", ""),
 D("headline_value_type", "headline / equity / enterprise / consideration / implied_ev / undisclosed", "enum", "analyst", "none", "Yes", "equity"),
 D("equity_value", "Equity value at offer, original currency", "currency units", "Tier 1 doc", "stock deals: shares issued x acquirer price at announcement", "Yes", "1000000000"),
 D("enterprise_value", "Explicit transaction EV from source, original currency", "currency units", "Tier 1-3", "none", "Yes", "900000000"),
 D("ev_basis", "reported source basis / calculated_from_bridge / undisclosed", "text", "derived", "none", "No", "calculated_from_bridge"),
 D("ev_quality", "Quality grade A-D of the EV evidence", "A-D", "analyst", "upper-case", "Yes", "A"),
 D("debt_assumed", "Debt assumed/refinanced, latest balance sheet before announcement", "currency units", "filings", "none", "Yes", "50000000"),
 D("cash_acquired", "Cash & equivalents, latest balance sheet before announcement", "currency units", "filings", "subtracted in bridge", "Yes", "150000000"),
 D("preferred", "Preferred equity", "currency units", "filings", "none", "Yes", "0"),
 D("minority_interest", "Non-controlling interest", "currency units", "filings", "none", "Yes", "0"),
 D("other_ev_adjustments", "Other debt-like items (leases, pensions); missing treated as 0 in the bridge, documented", "currency units", "analyst", "none", "Yes", "0"),
 D("ev_reported", "= enterprise_value", "currency units", "derived", "none", "Yes", ""),
 D("ev_calculated", "equity + debt + preferred + minority - cash + other; requires all four bridge items (never imputed)", "currency units", "derived", "none", "Yes", ""),
 D("ev_final", "ev_reported if present else ev_calculated", "currency units", "derived", "hierarchy per Phase 2 s.11", "Yes", ""),
 D("ev_disclosed", "1 if an explicit EV was available (vs reconstructed)", "0/1", "derived", "none", "No", "1"),
 D("ev_disclosed_in", "Analyst field reserved for source of disclosure", "text", "analyst", "none", "Yes", ""),
 D("ev_recon_diff_pct", "(ev_reported - ev_calculated)/ev_reported; QC check, tolerance 5%", "ratio", "derived", "none", "Yes", "0.0"),
 D("contingent_consideration", "1 if earn-out/CVR/milestone exists", "0/1", "terms", "defaults to contingent_max present", "No", "0"),
 D("contingent_type", "earn-out / CVR / milestone / deferred / retention", "text", "terms", "none", "Yes", "earn-out"),
 D("contingent_max", "Maximum contingent payment, original currency", "currency units", "Tier 1", "none", "Yes", "50000000"),
 D("contingent_expected", "Expected contingent payment if disclosed", "currency units", "Tier 1", "none", "Yes", ""),
 D("included_in_ev", "1 if the reported EV already includes contingent value (flagged for review)", "0/1", "terms", "none", "No", "0"),
 D("contingent_review", "1 if included_in_ev == 1 and contingent_max known", "0/1", "derived", "none", "No", "0"),
 D("ev_incl_contingent_max_usd", "Robustness EV including maximum contingent value", "USD", "derived", "(ev_final + contingent_max) x fx unless already included", "Yes", ""),
 D("cash_pct", "Cash share of consideration", "percent 0-100", "Tier 1", "none", "Yes", "100"),
 D("stock_pct", "Stock share of consideration", "percent 0-100", "Tier 1", "none", "Yes", "0"),
 D("other_pct", "Other consideration share", "percent 0-100", "Tier 1", "none", "Yes", "0"),
 D("consideration_sum", "cash+stock+other", "percent", "derived", "QC: should be ~100", "Yes", "100"),
 D("currency_original", "ISO currency of deal values", "ISO4217", "terms", "default USD", "No", "EUR"),
 D("fx_rate_announcement", "USD per 1 unit of currency_original at announcement date", "USD/unit", "market data", "1.0 if USD", "Yes", "1.10"),
 D("ev_usd", "ev_final x fx_rate_announcement", "USD", "derived", "none", "Yes", "110000000"),
 D("equity_value_usd", "equity_value x fx", "USD", "derived", "none", "Yes", ""),
 # ---- price data -------------------------------------------------------------------------------------
 D("offer_price", "Offer price per share (public targets)", "currency/share", "Tier 1", "none", "Yes", "20.00"),
 D("diluted_shares", "Fully diluted shares at offer", "shares", "Tier 1", "treasury method per merger doc", "Yes", "50000000"),
 D("unaffected_date", "Last trading day before the earliest credible leak/approach/announcement", "date", "analyst", "NOT announcement-1 by default", "Yes", "2024-01-10"),
 D("unaffected_reason", "Result of leak/rumour search justifying unaffected_date", "text", "analyst", "none", "Yes", "no leak found"),
 D("unaffected_price_1d", "Close on unaffected_date", "currency/share", "market data", "none", "Yes", "16.00"),
 D("price_1w", "Close one week before unaffected_date", "currency/share", "market data", "none", "Yes", ""),
 D("price_1m", "Close one month before unaffected_date", "currency/share", "market data", "none", "Yes", ""),
 D("vwap_30", "30-day VWAP ending unaffected_date", "currency/share", "market data", "none", "Yes", ""),
 D("price_90d", "Close 90 days before unaffected_date", "currency/share", "market data", "none", "Yes", ""),
 D("rumor_date", "Date of earliest credible leak", "date", "Reuters/Bloomberg/FT", "none", "Yes", ""),
 D("rumor_source", "Source of earliest leak", "text", "analyst", "none", "Yes", ""),
 D("leak_flag", "1 if a pre-announcement leak was found", "0/1", "analyst", "none", "Yes", "0"),
 D("premium_1d", "offer / unaffected_price_1d - 1 (PRIMARY premium)", "ratio", "derived", "public targets only", "Yes", "0.25"),
 D("premium_1w", "offer / price_1w - 1", "ratio", "derived", "none", "Yes", ""),
 D("premium_1m", "offer / price_1m - 1", "ratio", "derived", "none", "Yes", ""),
 D("premium_vwap30", "offer / vwap_30 - 1", "ratio", "derived", "none", "Yes", ""),
 D("ln1p_premium_1d", "ln(1 + premium_1d)", "log", "derived", "robustness", "Yes", ""),
 D("runup_90d", "unaffected_price_1d / price_90d - 1", "ratio", "derived", "control for N model", "Yes", ""),
 D("premium_date_ok", "1 if unaffected_date exists and precedes announcement", "0/1", "derived", "none", "No", "1"),
 D("predeal_market_cap", "Market cap at unaffected price", "currency units", "market data", "none", "Yes", ""),
 D("predeal_ev", "predeal_market_cap + debt + preferred + NCI - cash (+other)", "currency units", "derived", "none", "Yes", ""),
 D("predeal_ev_revenue", "predeal_ev / revenue_ltm (same currency); addresses RQ9", "x", "derived", "none", "Yes", ""),
 D("implied_equity_check", "equity_value / (offer x diluted shares) - 1; QC", "ratio", "derived", "tolerance 5%", "Yes", ""),
 # ---- financials ---------------------------------------------------------------------------------------
 D("revenue_period_end", "End date of the LTM revenue period (must precede announcement)", "date", "filings", "none", "Yes", "2022-12-31"),
 D("revenue_ltm", "LTM revenue, financial-statement currency", "currency units", "Tier 1", "FY + YTD - prior YTD", "Yes", "50000000"),
 D("revenue_prior_ltm", "LTM revenue one year earlier", "currency units", "Tier 1", "none", "Yes", "40000000"),
 D("ebitda_ltm", "LTM EBITDA (definition in ebitda_definition)", "currency units", "Tier 1", "none", "Yes", "5000000"),
 D("ebitda_definition", "reported / adjusted / database_normalized", "enum", "analyst", "never mixed silently", "Yes", "reported"),
 D("currency", "Currency of the financial statements", "ISO4217", "filings", "defaults to deal currency", "No", "EUR"),
 D("fx_to_usd", "USD per unit of statement currency when it differs from the deal currency", "USD/unit", "market data", "none", "Yes", ""),
 D("fx_fin", "FX actually applied to financials (deal FX if same currency, so EV/Revenue is currency-invariant)", "USD/unit", "derived", "none", "Yes", "1.10"),
 D("source_revenue", "Source of revenue figure", "text", "analyst", "none", "Yes", ""),
 D("source_ebitda", "Source of EBITDA figure", "text", "analyst", "none", "Yes", ""),
 D("revenue_ltm_usd", "revenue_ltm x fx_fin; NULL if alignment_error", "USD", "derived", "none", "Yes", "22000000"),
 D("ebitda_ltm_usd", "ebitda_ltm x fx_fin", "USD", "derived", "none", "Yes", ""),
 D("staleness_days", "announcement_date - revenue_period_end", "days", "derived", ">365 stale; <=180 fresh", "Yes", "74"),
 D("financials_stale_flag", "1 if staleness_days > 365", "0/1", "derived", "none", "Yes", "0"),
 D("freshness_band", "ERROR_post_announcement / fresh / acceptable / stale", "enum", "derived", "none", "Yes", "fresh"),
 D("alignment_error", "1 if financial period end >= announcement date (post-deal information)", "0/1", "derived", "ERROR in QC; revenue set NULL", "No", "0"),
 D("revenue_growth", "revenue_ltm / revenue_prior_ltm - 1 (needs two LTM periods)", "ratio", "derived", "no annualisation or guidance", "Yes", "0.25"),
 D("ebitda_margin", "ebitda_ltm / revenue_ltm", "ratio", "derived", "none", "Yes", "0.10"),
 D("ebitda_positive", "1 if ebitda_ltm > 0", "0/1", "derived", "none", "Yes", "1"),
 D("financials_quality", "Quality grade A-D of the financials", "A-D", "analyst", "none", "Yes", "A"),
 D("financials_disclosed", "1 if revenue/EBITDA were disclosed by a party (vs database estimate)", "0/1", "analyst", "disclosure-bias tracking", "Yes", "1"),
 D("data_quality_flag", "Worst of ev_quality and financials_quality", "A-D", "derived", "A-C primary; D robustness only", "Yes", "B"),
 # ---- outcomes -----------------------------------------------------------------------------------------
 D("ev_revenue", "ev_usd / revenue_ltm_usd (positive values only)", "x", "derived", "no outlier removal", "Yes", "6.0"),
 D("ln_ev_revenue", "ln(ev_revenue); PRIMARY outcome", "log", "derived", "none", "Yes", "1.79"),
 D("ev_ebitda", "ev_usd / ebitda_ltm_usd (EBITDA > 0 only)", "x", "derived", "none", "Yes", "20"),
 D("ln_ev_ebitda", "ln(ev_ebitda)", "log", "derived", "none", "Yes", ""),
 D("ln_revenue", "ln(revenue_ltm_usd); size control", "log USD", "derived", "none", "Yes", "17.7"),
 # ---- AI screen (SCREEN ONLY) ---------------------------------------------------------------------------
 D("candidate_keyword_hits", "Matched AI keyword patterns (screen only; never the final classification)", "text", "derived", "regex over description corpus", "Yes", "machine-learning;neural"),
 D("n_keyword_hits", "Number of distinct keyword patterns hit", "int", "derived", "none", "Yes", "2"),
 D("has_description_text", "1 if any description text exists", "0/1", "derived", "none", "Yes", "1"),
 D("ai_candidate_flag", "1 if >=1 keyword hit. SCREEN ONLY. Final ai_flag is created in Phase 3", "0/1", "derived", "NULL if no text", "Yes", "1"),
 D("ai_terms_preexisting", "1 if AI keywords appear in the 12-month-prior website snapshot (persistence evidence input, not a classification)", "0/1", "derived", "none", "Yes", ""),
 # ---- sample flags ---------------------------------------------------------------------------------------
 D("in_primary_sample_evrev", "1 if the deal passes every EV/Revenue waterfall step (not filtered on AI)", "0/1", "derived", "mirrors v_evrev_candidates", "No", "1"),
 D("in_primary_sample_ebitda", "1 if in EV/EBITDA sample", "0/1", "derived", "none", "No", "1"),
 D("in_primary_sample_premium", "1 if in takeover-premium sample", "0/1", "derived", "none", "No", "0"),
]
NAMES = {r[0] for r in ROWS}


def covered(col: str) -> bool:
    return col in NAMES or col.endswith("_missing_code")


def write(path: Path) -> None:
    out = ["# Data Dictionary (Phase 2)", "",
           "Generated by `src/data_dictionary_spec.py`; do not edit by hand. Every column of `deals_stage2.csv` and "
           "`financials_stage2.csv` is covered (enforced by `src/tests/test_pipeline.py`).", "",
           "**Missingness codes** (stored in `<field>_missing_code` columns; the numeric field itself is NULL): "
           "`NA` not applicable, `ND` not disclosed, `NF` not found after search, `NR` not reliable enough. "
           "No missing value is imputed.", "",
           "**Final `ai_flag`, `ai_intensity`, `ai_subsector` do not exist in Phase 2** (created in Phase 3 only). "
           "`ai_candidate_flag` is a keyword screen.", "",
           "| name | definition | unit | source | transformation | null allowed | example |", "|---|---|---|---|---|---|---|"]
    for r in ROWS:
        out.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
    out += ["", "| `<field>_missing_code` | Reason code (NA/ND/NF/NR) for a missing numeric input | enum | analyst | split from raw value | Yes | ND |", ""]
    path.write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    write(Path(__file__).resolve().parents[1] / "docs" / "data_dictionary.md")
    print("wrote docs/data_dictionary.md with", len(ROWS), "fields")
