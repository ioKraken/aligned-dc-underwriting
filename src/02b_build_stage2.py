"""Stage 2 build: EV construction, LTM alignment, ratios, premiums, flags, waterfalls, coverage tables,
AI-candidate SCREEN, blind coding file, SQLite load.

Inputs (data_raw/): deal_terms_raw.csv, financials_raw.csv, descriptions_raw.csv, [market_data.csv]
Inputs (data_clean/): deals_stage1.csv, companies.csv, deal_bids_history.csv   (from 01_collect.py)

Outputs (data_clean/): deals_stage2.csv, financials_stage2.csv, ai_coding_blind.csv, ai_coding_pool_key.csv,
                       exclusions_log.csv, ai_premium.db
Outputs (results/):    sample_waterfall_phase2.csv, yearly_coverage.csv, sector_coverage.csv,
                       geographic_coverage.csv, public_private_coverage.csv, deal_size_distribution.csv,
                       disclosure_tracking.csv, sample_size_checkpoints.csv, missingness_report.csv,
                       sql_view_check.csv, candidate_screen_counts.csv

PHASE 2 BOUNDARIES: no AI classification (only a keyword SCREEN), no AI-vs-non-AI valuation comparison,
no regressions. The final ai_flag does not exist in any output of this script.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa: E402

TERMS_NUM = ["equity_value", "enterprise_value", "debt_assumed", "cash_acquired", "preferred", "minority_interest",
             "other_ev_adjustments", "contingent_max", "contingent_expected", "cash_pct", "stock_pct", "other_pct",
             "offer_price", "diluted_shares", "unaffected_price_1d", "price_1w", "price_1m", "vwap_30", "price_90d",
             "predeal_market_cap", "fx_rate_announcement", "headline_value"]
FIN_NUM = ["revenue_ltm", "revenue_prior_ltm", "ebitda_ltm", "fx_to_usd"]
QUAL_RANK = {"A": 1, "B": 2, "C": 3, "D": 4}


def worst_quality(a, b):
    vals = [x for x in (a, b) if isinstance(x, str) and x in QUAL_RANK]
    return max(vals, key=QUAL_RANK.get) if vals else np.nan


def load_inputs(root: Path):
    d = U.read_csv_safe(root / "data_clean" / "deals_stage1.csv")
    for c in ("announcement_date", "close_date"):
        d[c] = U.to_date(d[c])
    terms_p, fin_p, desc_p = (root / "data_raw" / n for n in ("deal_terms_raw.csv", "financials_raw.csv", "descriptions_raw.csv"))
    terms = U.read_csv_safe(terms_p) if terms_p.exists() else pd.DataFrame(columns=["deal_id"])
    fin = U.read_csv_safe(fin_p) if fin_p.exists() else pd.DataFrame(columns=["deal_id"])
    desc = U.read_csv_safe(desc_p) if desc_p.exists() else pd.DataFrame(columns=["deal_id"])
    for name, t in (("deal_terms_raw", terms), ("financials_raw", fin), ("descriptions_raw", desc)):
        if t["deal_id"].duplicated().any():
            raise SystemExit(f"{name}.csv has duplicate deal_id rows; one row per deal required.")
    return d, terms, fin, desc


def build_deals(d: pd.DataFrame, terms: pd.DataFrame) -> pd.DataFrame:
    terms = U.split_missing_codes(terms, [c for c in TERMS_NUM])
    for c in ("unaffected_date", "rumor_date"):
        terms[c] = U.to_date(terms[c]) if c in terms.columns else pd.NaT
    for c in ["currency_original", "ev_basis", "ev_quality", "contingent_type", "unaffected_reason", "rumor_source",
              "included_in_ev", "contingent_consideration", "leak_flag", "standalone_financials", "ev_disclosed_in"]:
        if c not in terms.columns:
            terms[c] = np.nan
    x = d.merge(terms.drop(columns=[c for c in terms.columns if c in d.columns and c != "deal_id"]), on="deal_id", how="left")
    x = x.rename(columns={"headline_transaction_value": "headline_raw"})
    hv = U.split_missing_codes(x[["headline_raw"]].rename(columns={"headline_raw": "h"}), ["h"])
    x["headline_value"] = np.where(x["headline_value"].notna(), x["headline_value"], hv["h"])

    # --- geography / sector / status / type flags ---------------------------------------------------
    x["target_region"] = x["target_country"].map(U.region_of)
    x["primary_geography"] = x["target_country"].isin(U.PRIMARY_COUNTRIES).astype(int)
    x["cross_border"] = ((x["target_country"] != x["buyer_country"]) & x["target_country"].notna()
                         & x["buyer_country"].notna()).astype(int)
    x["sector_primary"] = x["sector"].str.strip().str.lower().map(U.SECTOR_ALIASES)
    x["primary_sector"] = x["sector_primary"].notna().astype(int)
    x["classification_source"] = "target_business_" + x["source_universe"].fillna("unknown").str.split(";").str[0]
    x["in_period"] = x["announcement_date"].between(U.PERIOD_START, U.PERIOD_END).astype(int)
    x["status_primary_sample"] = x["deal_status"].isin(U.PRIMARY_STATUSES).astype(int)

    pp = x["target_public_private"].str.strip().str.lower()
    x["public_target"] = (pp == "public").fillna(False).astype(int)
    x["target_public_private"] = pp

    dt = x["deal_type"].astype("string").str.strip().str.lower().fillna("")
    x["control_assumed"] = (dt == "").fillna(False).astype(int)
    x["control_deal"] = dt.isin(["", "control"]).fillna(False).astype(int)

    excl = x["structural_exclusion"].astype("string").str.strip().str.lower()
    excl = excl.where(excl.isin(U.STRUCTURAL_EXCLUSION_CODES), pd.NA)
    for code in ("minority", "venture_round", "pipe", "asset_only", "internal", "spac", "distressed", "acquihire"):
        excl = excl.where(~((dt == code) | (dt == code.replace("_", "-"))) | excl.notna(), code)
    sub_no_standalone = ((pp == "subsidiary").fillna(False)) & (x["standalone_financials"].astype("string").fillna("").str.strip() != "1")
    excl = excl.where(~sub_no_standalone | excl.notna(), "carveout_no_standalone")
    x["structural_exclusion"] = excl
    x["spac_flag"] = (excl == "spac").fillna(False).astype(int)
    x["distressed_flag"] = (excl == "distressed").fillna(False).astype(int)
    x["acquihire_flag"] = (excl == "acquihire").fillna(False).astype(int)
    x["deal_type"] = dt.replace("", "control")

    # --- buyer type -------------------------------------------------------------------------------------
    bt = x["buyer_type"].str.strip().str.lower().str.replace("/", "_").str.replace(" ", "_")
    bt = bt.replace({"government": "government_swf", "swf": "government_swf", "financial_sponsor": "sponsor"})
    x["buyer_type"] = bt.where(bt.isin(U.BUYER_TYPES), "other")
    x["strategic_buyer"] = (x["buyer_type"] == "strategic").fillna(False).astype(int)
    x["sponsor_buyer"] = (x["buyer_type"] == "sponsor").fillna(False).astype(int)
    x["mixed_consortium"] = pd.to_numeric(x["mixed_consortium"], errors="coerce").fillna(0).astype(int)

    # --- currency / EV construction ----------------------------------------------------------------------
    cur = x["currency_original"].fillna("USD").str.upper()
    x["currency_original"] = cur
    fx = x["fx_rate_announcement"].where(x["fx_rate_announcement"].notna(), np.where(cur == "USD", 1.0, np.nan))
    x["fx_rate_announcement"] = fx
    bridge_cols = ["debt_assumed", "preferred", "minority_interest", "cash_acquired"]
    have_bridge = x[bridge_cols].notna().all(axis=1)
    adj = x["other_ev_adjustments"].fillna(0.0)
    x["ev_reported"] = x["enterprise_value"]
    x["ev_calculated"] = np.where(x["equity_value"].notna() & have_bridge,
                                  x["equity_value"] + x["debt_assumed"] + x["preferred"] + x["minority_interest"]
                                  - x["cash_acquired"] + adj, np.nan)
    x["ev_final"] = x["ev_reported"].where(x["ev_reported"].notna(), x["ev_calculated"])
    basis_in = x["ev_basis"].astype("string")
    x["ev_basis"] = np.where(x["ev_reported"].notna(), basis_in.fillna("reported"),
                             np.where(x["ev_calculated"].notna(), "calculated_from_bridge", "undisclosed"))
    x["ev_disclosed"] = x["ev_reported"].notna().astype(int)
    x["ev_usd"] = x["ev_final"] * fx
    x["equity_value_usd"] = x["equity_value"] * fx
    x["ev_recon_diff_pct"] = np.where(x["ev_reported"].notna() & x["ev_calculated"].notna(),
                                      (x["ev_reported"] - x["ev_calculated"]) / x["ev_reported"], np.nan)
    inc = pd.to_numeric(x["included_in_ev"], errors="coerce").fillna(0)
    x["included_in_ev"] = inc.astype(int)
    x["contingent_consideration"] = pd.to_numeric(x["contingent_consideration"], errors="coerce").fillna(
        x["contingent_max"].notna().astype(int)).astype(int)
    x["contingent_review"] = ((x["included_in_ev"] == 1) & x["contingent_max"].notna()).astype(int)
    x["ev_incl_contingent_max_usd"] = np.where(x["included_in_ev"] == 0, (x["ev_final"] + x["contingent_max"].fillna(0)) * fx,
                                               x["ev_usd"])
    # consideration mix
    mix = x[["cash_pct", "stock_pct", "other_pct"]]
    x["consideration_sum"] = mix.sum(axis=1, min_count=1)

    # --- takeover premiums / pre-deal valuation --------------------------------------------------------------
    pub = x["public_target"] == 1
    for nm, base in (("premium_1d", "unaffected_price_1d"), ("premium_1w", "price_1w"), ("premium_1m", "price_1m"),
                     ("premium_vwap30", "vwap_30")):
        x[nm] = np.where(pub & (x["offer_price"] > 0) & (x[base] > 0), x["offer_price"] / x[base] - 1, np.nan)
    x["ln1p_premium_1d"] = np.log1p(x["premium_1d"].where(x["premium_1d"] > -1))
    x["runup_90d"] = np.where(pub & (x["unaffected_price_1d"] > 0) & (x["price_90d"] > 0),
                              x["unaffected_price_1d"] / x["price_90d"] - 1, np.nan)
    x["premium_date_ok"] = (x["unaffected_date"].notna() & (x["unaffected_date"] < x["announcement_date"])).astype(int)
    x["predeal_ev"] = np.where(pub & x["predeal_market_cap"].notna() & have_bridge,
                               x["predeal_market_cap"] + x["debt_assumed"] + x["preferred"] + x["minority_interest"]
                               - x["cash_acquired"] + adj, np.nan)
    x["implied_equity_check"] = np.where(pub & x["offer_price"].notna() & x["diluted_shares"].notna() & x["equity_value"].notna(),
                                         x["equity_value"] / (x["offer_price"] * x["diluted_shares"]) - 1, np.nan)
    x["post_genai"] = (x["announcement_date"] > U.GENAI_DATE).astype(int)
    x["announce_year"] = x["announcement_date"].dt.year
    x["ev_quality"] = x["ev_quality"].astype("string").str.upper()
    return x


def build_financials(x: pd.DataFrame, fin: pd.DataFrame) -> pd.DataFrame:
    fin = U.split_missing_codes(fin, FIN_NUM)
    for c in ("source_revenue", "source_ebitda", "ebitda_definition", "currency", "financials_quality", "financials_disclosed"):
        if c not in fin.columns:
            fin[c] = np.nan
    fin["revenue_period_end"] = U.to_date(fin["revenue_period_end"]) if "revenue_period_end" in fin.columns else pd.NaT
    f = x[["deal_id", "target_id", "announcement_date", "currency_original", "fx_rate_announcement"]].merge(
        fin.drop(columns=["target_id"], errors="ignore"), on="deal_id", how="left")
    f["currency"] = f["currency"].fillna(f["currency_original"]).str.upper()
    # same-currency => reuse deal FX so EV/Revenue is exactly currency-invariant; otherwise need explicit fx_to_usd
    f["fx_fin"] = np.where(f["currency"] == f["currency_original"], f["fx_rate_announcement"],
                           np.where(f["currency"] == "USD", 1.0, f["fx_to_usd"]))
    f["staleness_days"] = (f["announcement_date"] - f["revenue_period_end"]).dt.days
    f["alignment_error"] = (f["revenue_period_end"].notna() & (f["revenue_period_end"] >= f["announcement_date"])).astype(int)
    f["financials_stale_flag"] = np.where(f["staleness_days"].isna(), np.nan, (f["staleness_days"] > U.STALE_DAYS).astype(float))
    f["freshness_band"] = pd.cut(f["staleness_days"], [-10**6, 0, U.FRESH_DAYS, U.STALE_DAYS, 10**7],
                                 labels=["ERROR_post_announcement", "fresh", "acceptable", "stale"]).astype("string")
    ok = f["alignment_error"] == 0
    f["revenue_ltm_usd"] = np.where(ok, f["revenue_ltm"] * f["fx_fin"], np.nan)
    f["ebitda_ltm_usd"] = np.where(ok, f["ebitda_ltm"] * f["fx_fin"], np.nan)
    f["revenue_growth"] = np.where(ok & (f["revenue_prior_ltm"] > 0) & f["revenue_ltm"].notna(),
                                   f["revenue_ltm"] / f["revenue_prior_ltm"] - 1, np.nan)
    f["ebitda_margin"] = np.where(ok & (f["revenue_ltm"] > 0) & f["ebitda_ltm"].notna(), f["ebitda_ltm"] / f["revenue_ltm"], np.nan)
    f["ebitda_positive"] = np.where(f["ebitda_ltm"].notna(), (f["ebitda_ltm"] > 0).astype(float), np.nan)
    f["financials_quality"] = f["financials_quality"].astype("string").str.upper()
    ed = f["ebitda_definition"].astype("string").str.strip().str.lower().str.replace(" ", "_")
    f["ebitda_definition"] = ed.where(ed.isin(["reported", "adjusted", "database_normalized"]), pd.NA)
    return f


def add_ratios_and_flags(x: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    cols = ["deal_id", "revenue_ltm_usd", "ebitda_ltm_usd", "revenue_growth", "ebitda_margin", "ebitda_positive",
            "staleness_days", "financials_stale_flag", "alignment_error", "financials_quality", "financials_disclosed",
            "revenue_ltm", "revenue_period_end"]
    x = x.merge(f[cols], on="deal_id", how="left")
    x["data_quality_flag"] = [worst_quality(a, b) for a, b in zip(x["ev_quality"], x["financials_quality"])]
    x["ev_revenue"] = np.where((x["ev_usd"] > 0) & (x["revenue_ltm_usd"] > 0), x["ev_usd"] / x["revenue_ltm_usd"], np.nan)
    x["ln_ev_revenue"] = np.log(x["ev_revenue"])
    x["ev_ebitda"] = np.where((x["ev_usd"] > 0) & (x["ebitda_ltm_usd"] > 0), x["ev_usd"] / x["ebitda_ltm_usd"], np.nan)
    x["ln_ev_ebitda"] = np.log(x["ev_ebitda"])
    x["predeal_ev_revenue"] = np.where((x["predeal_ev"] > 0) & (x["revenue_ltm"] > 0), x["predeal_ev"] / x["revenue_ltm"], np.nan)
    x["ln_revenue"] = np.log(x["revenue_ltm_usd"].where(x["revenue_ltm_usd"] > 0))
    x["financials_disclosed"] = pd.to_numeric(x["financials_disclosed"], errors="coerce")
    return x


def waterfall_steps(x: pd.DataFrame):
    """Sequential (cumulative) filters. Each step = (label, boolean mask, reason code)."""
    s = {}
    A_C = x["data_quality_flag"].isin(["A", "B", "C"])
    structure = [
        ("Raw identified tech M&A universe (post-dedupe)", pd.Series(True, index=x.index), "universe"),
        ("Correct period (2015-01-01..2026-09-30)", x["in_period"] == 1, "out_of_period"),
        ("Primary geography", x["primary_geography"] == 1, "geography"),
        ("Primary sectors", x["primary_sector"] == 1, "sector_out_of_scope"),
        ("Control transactions", x["control_deal"] == 1, "not_control"),
        ("Status: completed / definitive", x["status_primary_sample"] == 1, "status_not_primary"),
        ("Structural exclusions removed", x["structural_exclusion"].isna(), "structural_exclusion"),
    ]
    evrev = structure + [
        ("EV available", x["ev_usd"].notna() & (x["ev_usd"] > 0), "ev_missing"),
        ("EV >= $25m", x["ev_usd"] >= U.EV_MIN_USD, "ev_below_25m"),
        ("Revenue available", x["revenue_ltm_usd"].notna() & (x["revenue_ltm_usd"] > 0), "revenue_missing"),
        ("Revenue >= $5m", x["revenue_ltm_usd"] >= U.REV_MIN_USD, "revenue_below_5m"),
        ("Financial freshness (<=365d, aligned)", (x["financials_stale_flag"] == 0) & (x["alignment_error"] == 0), "stale_or_misaligned_financials"),
        ("Quality A-C", A_C, "quality_D_or_missing"),
        ("AI coded (Phase 3)", pd.Series(True, index=x.index), "ai_coding_pending"),
    ]
    s["EV/Revenue"] = evrev
    base_ev = evrev[:-1]
    s["EV/EBITDA"] = base_ev + [
        ("EBITDA available", x["ebitda_ltm_usd"].notna(), "ebitda_missing"),
        ("EBITDA > 0", x["ebitda_ltm_usd"] > 0, "ebitda_nonpositive"),
        ("AI coded (Phase 3)", pd.Series(True, index=x.index), "ai_coding_pending"),
    ]
    s["Takeover premium"] = structure + [
        ("Public target", x["public_target"] == 1, "not_public"),
        ("Offer price available", x["offer_price"] > 0, "offer_price_missing"),
        ("Unaffected price available", x["unaffected_price_1d"] > 0, "unaffected_price_missing"),
        ("Unaffected date valid (< announcement)", x["premium_date_ok"] == 1, "unaffected_date_invalid"),
        ("Quality A-C", A_C, "quality_D_or_missing"),
        ("AI coded (Phase 3)", pd.Series(True, index=x.index), "ai_coding_pending"),
    ]
    return s


def run_waterfalls(x: pd.DataFrame):
    rows, excl_rows = [], []
    steps = waterfall_steps(x)
    final_masks = {}
    for outcome, st in steps.items():
        cur = pd.Series(True, index=x.index)
        for i, (label, mask, reason) in enumerate(st):
            keep = cur & mask.fillna(False)
            if reason != "universe":
                removed = x.loc[cur & ~keep, "deal_id"]
                if reason != "ai_coding_pending":
                    excl_rows += [{"outcome": outcome, "step": label, "reason": reason, "deal_id": d} for d in removed]
            cur = keep
            is_ai_step = reason == "ai_coding_pending"
            rows.append({"outcome": outcome, "stage": i + 1, "step": label, "total_N": int(cur.sum()),
                         "ai_candidate_N": int((cur & (x["ai_candidate_flag"] == 1)).sum()),
                         "non_candidate_N": int((cur & (x["ai_candidate_flag"] == 0)).sum()),
                         "AI_N": np.nan, "nonAI_N": np.nan,
                         "note": "AI counts are blank until Phase 3; candidate counts are a keyword SCREEN only" if is_ai_step else ""})
        final_masks[outcome] = cur
    wf = pd.DataFrame(rows)
    wf["removed_at_step"] = wf.groupby("outcome")["total_N"].diff().mul(-1)
    return wf, pd.DataFrame(excl_rows), final_masks


def ai_screen(x: pd.DataFrame, desc: pd.DataFrame) -> pd.DataFrame:
    text_cols = ["target_description", "announcement_description", "website_description", "filing_description",
                 "historical_description", "snapshot_announcement"]
    for c in text_cols + ["snapshot_minus_12m"]:
        if c not in desc.columns:
            desc[c] = np.nan
    d = desc[["deal_id"] + text_cols + ["snapshot_minus_12m"]].copy()
    hits = d[text_cols].fillna("").agg(" ".join, axis=1).map(U.ai_keyword_hits)
    d["candidate_keyword_hits"] = hits.map(lambda h: ";".join(h))
    d["n_keyword_hits"] = hits.map(len)
    d["has_description_text"] = d[text_cols].fillna("").agg("".join, axis=1).str.strip().ne("").astype(int)
    pre = d["snapshot_minus_12m"].fillna("").map(U.ai_keyword_hits).map(len)
    d["ai_terms_preexisting"] = np.where(d["snapshot_minus_12m"].fillna("").str.strip() == "", np.nan, (pre > 0).astype(float))
    x = x.merge(d, on="deal_id", how="left")
    x["ai_candidate_flag"] = np.where(x["has_description_text"] == 1, (x["n_keyword_hits"] >= 1).astype(float), np.nan)
    return x


def build_blind_file(x: pd.DataFrame, desc: pd.DataFrame, root: Path) -> None:
    pool = x[(x["primary_sector"] == 1) & (x["primary_geography"] == 1) & (x["control_deal"] == 1) &
             (x["status_primary_sample"] == 1) & x["structural_exclusion"].isna() & (x["in_period"] == 1) &
             (x["has_description_text"] == 1)].copy()
    cand = pool[pool["ai_candidate_flag"] == 1]
    non = pool[pool["ai_candidate_flag"] == 0]
    rng = np.random.default_rng(U.SEED)
    n_audit = int(np.ceil(U.AUDIT_FRACTION * len(non))) if len(non) else 0
    audit_ids = set(rng.choice(non["deal_id"].to_numpy(), size=n_audit, replace=False)) if n_audit else set()
    sel = pd.concat([cand.assign(coding_pool="candidate"),
                     non[non["deal_id"].isin(audit_ids)].assign(coding_pool="audit_random_20pct")])
    sel = sel.sample(frac=1.0, random_state=U.SEED).reset_index(drop=True)      # shuffle: order carries no information
    sel["coder_row"] = np.arange(1, len(sel) + 1)
    sel[["coder_row", "deal_id", "target_id", "coding_pool", "ai_candidate_flag", "candidate_keyword_hits"]].to_csv(
        root / "data_clean" / "ai_coding_pool_key.csv", index=False)        # NOT coder-facing
    dd = desc.set_index("deal_id")

    def g(col):
        return sel["deal_id"].map(dd[col]) if col in dd.columns else pd.Series("", index=sel.index)

    blind = pd.DataFrame({
        "coder_row": sel["coder_row"], "company_id": sel["target_id"], "target_name": sel["target_name"],
        "announcement_date": sel["announcement_date"].dt.strftime("%Y-%m-%d"), "sector": sel["sector_primary"],
        "business_description": g("target_description").map(U.redact_valuation),
        "website_snapshot_text": g("snapshot_announcement").map(U.redact_valuation),
        "filing_description": g("filing_description").map(U.redact_valuation),
        "technical_description": g("historical_description").map(U.redact_valuation)})
    forbidden = {"ev", "equity", "premium", "offer", "price", "multiple", "value"}
    assert not any(any(f in c.lower() for f in forbidden) for c in blind.columns), "valuation column leaked into blind file"
    blind.to_csv(root / "data_clean" / "ai_coding_blind.csv", index=False)


def coverage_tables(x: pd.DataFrame, masks: dict, root: Path) -> None:
    r = root / "results"
    r.mkdir(exist_ok=True)
    ev_el = masks["EV/Revenue"]
    inuni = x["in_period"] == 1
    x = x.assign(ev_avail=x["ev_usd"].notna().astype(int), rev_avail=x["revenue_ltm_usd"].notna().astype(int),
                 in_sample_evrev=ev_el.astype(int), cand=(x["ai_candidate_flag"] == 1).astype(int))
    u = x[inuni]
    yc = u.groupby("announce_year").agg(universe_deals=("deal_id", "count"), ev_available=("ev_avail", "sum"),
                                         revenue_available=("rev_avail", "sum"), public_deals=("public_target", "sum"),
                                         evrev_sample=("in_sample_evrev", "sum"), ai_candidates=("cand", "sum")).reset_index()
    yc["private_deals"] = yc["universe_deals"] - yc["public_deals"]
    yc.to_csv(r / "yearly_coverage.csv", index=False)
    u.groupby(u["sector_primary"].fillna("OUT_OF_SCOPE")).agg(universe_N=("deal_id", "count"), evrev_eligible_N=("in_sample_evrev", "sum"),
                                                              candidate_AI_N=("cand", "sum")).reset_index().rename(
        columns={"sector_primary": "sector"}).to_csv(r / "sector_coverage.csv", index=False)
    u.groupby(u["target_region"].fillna("OUT_OF_SCOPE")).agg(universe_N=("deal_id", "count"), eligible_N=("in_sample_evrev", "sum")
                                                             ).reset_index().to_csv(r / "geographic_coverage.csv", index=False)
    pp = u.assign(target_type=np.where(u["public_target"] == 1, "Public", "Private")).groupby("target_type").agg(
        universe=("deal_id", "count"), ev_known=("ev_avail", "sum"), revenue_known=("rev_avail", "sum"),
        final_candidate_sample=("in_sample_evrev", "sum")).reset_index()
    pp.to_csv(r / "public_private_coverage.csv", index=False)

    def q(s, p):
        return s.quantile(p)

    ue = u[u["ev_usd"].notna()].assign(target_type=lambda d_: np.where(d_["public_target"] == 1, "Public", "Private"))
    ds = ue.groupby(["announce_year", "target_type"])["ev_usd"].agg(
        N="count", median_ev_usd="median", P25=lambda s: q(s, .25), P75=lambda s: q(s, .75)).reset_index()
    ds.to_csv(r / "deal_size_distribution.csv", index=False)
    disc = u.assign(public=np.where(u["public_target"] == 1, "Public", "Private"),
                    size_bucket=pd.cut(u["ev_usd"], [0, 1e8, 5e8, 2e9, np.inf], labels=["<100m", "100-500m", "0.5-2bn", ">2bn"]).astype("string").fillna("EV_unknown"),
                    ev_disclosed_f=u["ev_disclosed"], fin_disclosed_f=u["financials_disclosed"]).groupby(
        ["announce_year", "public"]).agg(N=("deal_id", "count"), ev_disclosed_rate=("ev_disclosed_f", "mean"),
                                         financials_disclosed_rate=("fin_disclosed_f", "mean"),
                                         candidate_share=("cand", "mean")).reset_index()
    disc.to_csv(r / "disclosure_tracking.csv", index=False)
    m = masks["EV/Revenue"]
    chk = pd.DataFrame([
        {"checkpoint": "Total deals in universe (period)", "N": int(inuni.sum())},
        {"checkpoint": "Deals with EV", "N": int(u["ev_avail"].sum())},
        {"checkpoint": "Deals with revenue", "N": int(u["rev_avail"].sum())},
        {"checkpoint": "Deals with growth", "N": int(u["revenue_growth"].notna().sum())},
        {"checkpoint": "Deals with EBITDA", "N": int(u["ebitda_ltm_usd"].notna().sum())},
        {"checkpoint": "Public deals with price data", "N": int(((u["public_target"] == 1) & (u["premium_1d"].notna())).sum())},
        {"checkpoint": "Candidate AI deals (keyword screen, NOT final)", "N": int(u["cand"].sum())},
        {"checkpoint": "EV/Revenue research sample (A-C, fresh)", "N": int(m.sum()), "phase1_target": 250,
         "meets_target": bool(m.sum() >= 250)},
        {"checkpoint": "EV/Revenue sample with growth available", "N": int((m & x["revenue_growth"].notna()).sum())},
        {"checkpoint": "Public premium sample", "N": int(masks["Takeover premium"].sum()), "phase1_target": 120,
         "meets_target": bool(masks["Takeover premium"].sum() >= 120)},
        {"checkpoint": "AI-native >=60 (assessed after Phase 3)", "N": np.nan, "phase1_target": 60},
    ])
    chk.to_csv(r / "sample_size_checkpoints.csv", index=False)
    # Selection inputs preserved for later P(InSample) modelling (no model fitted here)
    x.loc[inuni, ["deal_id", "announce_year", "public_target", "sector_primary", "target_region", "ev_usd",
                  "revenue_ltm_usd", "cand", "in_sample_evrev"]].rename(
        columns={"cand": "ai_candidate", "in_sample_evrev": "InSample"}).to_csv(root / "data_clean" / "selection_inputs.csv", index=False)


def missingness_report(x: pd.DataFrame, terms: pd.DataFrame, fin: pd.DataFrame, root: Path) -> None:
    t = U.split_missing_codes(terms.copy(), ["enterprise_value", "equity_value", "offer_price", "unaffected_price_1d"])
    f = U.split_missing_codes(fin.copy(), ["revenue_ltm", "revenue_prior_ltm", "ebitda_ltm"])
    base = x[(x["primary_sector"] == 1) & (x["primary_geography"] == 1) & (x["in_period"] == 1)][["deal_id", "public_target"]]
    rows = []
    for field, src, need_public in (("enterprise_value", t, False), ("equity_value", t, False), ("revenue_ltm", f, False),
                                    ("revenue_prior_ltm", f, False), ("ebitda_ltm", f, False),
                                    ("offer_price", t, True), ("unaffected_price_1d", t, True)):
        m = base.merge(src[["deal_id", field, field + "_missing_code"]], on="deal_id", how="left")
        if need_public:
            m = m[m["public_target"] == 1]
        miss = m[m[field].isna()]
        if field == "enterprise_value":      # EV may be reconstructable from the equity bridge
            ev_ok = x.set_index("deal_id")["ev_final"].reindex(miss["deal_id"]).notna().to_numpy()
            miss = miss[~ev_ok]
        code = miss[field + "_missing_code"].fillna("UNEXPLAINED")
        for c, n in code.value_counts().items():
            rows.append({"field": field, "missing_code": c, "N": int(n), "of_N": int(len(m))})
    pd.DataFrame(rows, columns=["field", "missing_code", "N", "of_N"]).to_csv(root / "results" / "missingness_report.csv", index=False)


def load_sqlite(x: pd.DataFrame, f: pd.DataFrame, desc: pd.DataFrame, companies: pd.DataFrame, bids: pd.DataFrame,
                root: Path, masks: dict) -> None:
    db = root / "data_clean" / "ai_premium.db"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.executescript((root / "sql" / "schema.sql").read_text())

    def cols_of(table):
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]

    def put(df, table):
        c = [k for k in cols_of(table) if k in df.columns]
        out = df[c].copy()
        for k in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[k]):
                out[k] = out[k].dt.strftime("%Y-%m-%d")
        out.to_sql(table, con, if_exists="append", index=False)

    put(companies, "companies")
    xx = x.copy()
    xx["ai_candidate_flag"] = xx["ai_candidate_flag"]
    put(xx, "deals")
    put(bids, "deal_bids_history")
    ff = f.copy()
    ff = ff.rename(columns={"revenue_period_end": "revenue_period_end"})
    ff["company_id"] = ff["target_id"]
    ff = ff[ff["revenue_period_end"].notna() | ff["revenue_ltm"].notna()]
    put(ff, "financials")
    dd = desc.merge(x[["deal_id", "target_id"]], on="deal_id", how="inner").rename(columns={"target_id": "company_id"})
    put(dd, "business_descriptions")
    md = root / "data_raw" / "market_data.csv"
    if md.exists():
        m = U.read_csv_safe(md)
        put(m, "market_data")
    con.executescript((root / "sql" / "views_samples.sql").read_text())
    chk = []
    for view, key in (("v_evrev_candidates", "EV/Revenue"), ("v_public_premium_candidates", "Takeover premium")):
        n_sql = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
        n_pd = int(masks[key].sum())
        if view == "v_public_premium_candidates":      # SQL view has no quality filter; compare structure-level count
            n_pd = int(((x["public_target"] == 1) & (x["offer_price"] > 0) & (x["unaffected_price_1d"] > 0) &
                        (x["premium_date_ok"] == 1) & (x["in_period"] == 1) & (x["primary_geography"] == 1) &
                        (x["primary_sector"] == 1) & (x["control_deal"] == 1) & (x["status_primary_sample"] == 1) &
                        x["structural_exclusion"].isna()).sum())
        chk.append({"view": view, "rows_sql": n_sql, "rows_pandas_waterfall": n_pd, "match": n_sql == n_pd})
    n_sql = con.execute("SELECT COUNT(*) FROM v_ebitda_candidates").fetchone()[0]
    chk.append({"view": "v_ebitda_candidates", "rows_sql": n_sql, "rows_pandas_waterfall": int(masks["EV/EBITDA"].sum()),
                "match": n_sql == int(masks["EV/EBITDA"].sum())})
    blind_cols = [r[1] for r in con.execute("PRAGMA table_info(v_ai_coding_blind)")]
    leaks = [c for c in blind_cols if any(k in c.lower() for k in ("ev", "equity", "premium", "offer", "price", "value"))]
    chk.append({"view": "v_ai_coding_blind (no valuation columns)", "rows_sql": con.execute("SELECT COUNT(*) FROM v_ai_coding_blind").fetchone()[0],
                "rows_pandas_waterfall": np.nan, "match": len(leaks) == 0})
    con.commit()
    con.close()
    pd.DataFrame(chk).to_csv(root / "results" / "sql_view_check.csv", index=False)


def main(root: Path) -> None:
    d, terms, fin, desc = load_inputs(root)
    companies = U.read_csv_safe(root / "data_clean" / "companies.csv")
    companies["company_id"] = companies["company_id"].astype(int)
    for c in ("target_id", "buyer_id"):
        d[c] = pd.to_numeric(d[c]).astype("Int64")
    bids = pd.read_csv(root / "data_clean" / "deal_bids_history.csv") if (root / "data_clean" / "deal_bids_history.csv").stat().st_size > 5 else pd.DataFrame(columns=["deal_id"])

    x = build_deals(d, terms)
    f = build_financials(x, fin)
    x = add_ratios_and_flags(x, f)
    x = ai_screen(x, desc)

    wf, excl, masks = run_waterfalls(x)
    (root / "results").mkdir(exist_ok=True)
    wf.to_csv(root / "results" / "sample_waterfall_phase2.csv", index=False)
    excl.to_csv(root / "data_clean" / "exclusions_log.csv", index=False)

    x["in_primary_sample_evrev"] = x.index.isin(masks["EV/Revenue"][masks["EV/Revenue"]].index).astype(int)
    x["in_primary_sample_ebitda"] = x.index.isin(masks["EV/EBITDA"][masks["EV/EBITDA"]].index).astype(int)
    x["in_primary_sample_premium"] = x.index.isin(masks["Takeover premium"][masks["Takeover premium"]].index).astype(int)

    drop = ["ai_flag"]
    text_cols = ["target_description", "announcement_description", "website_description", "filing_description",
                 "historical_description", "snapshot_announcement", "snapshot_minus_12m"]   # kept in DB / raw file, not in the flat deal table
    out = x.drop(columns=[c for c in drop + text_cols if c in x.columns])
    out.to_csv(root / "data_clean" / "deals_stage2.csv", index=False)
    f.to_csv(root / "data_clean" / "financials_stage2.csv", index=False)
    (x["ai_candidate_flag"].fillna(-1).map({1.0: "candidate", 0.0: "non_candidate", -1.0: "no_description_text"})
     .value_counts().rename_axis("keyword_screen_result").rename("deals").reset_index()
     .to_csv(root / "results" / "candidate_screen_counts.csv", index=False))

    build_blind_file(x, desc, root)
    coverage_tables(x, masks, root)
    missingness_report(x, terms, fin, root)
    load_sqlite(x, f, desc, companies, bids, root, masks)
    print(wf.groupby("outcome").tail(2)[["outcome", "step", "total_N"]].to_string(index=False))
    print(f"deals: {len(x)} | EV/Rev sample: {int(masks['EV/Revenue'].sum())} | EBITDA: {int(masks['EV/EBITDA'].sum())} "
          f"| premium: {int(masks['Takeover premium'].sum())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    main(U.project_root(ap.parse_args().root))
