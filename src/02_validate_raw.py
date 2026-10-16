"""Quality-control validator. Run after 01_collect.py and 02b_build_stage2.py.

Writes results/data_quality_report.csv (one row per finding) and prints a severity summary.
Severity: ERROR = must be fixed before Phase 3; WARN = review and document; INFO = informational.
Exit status is 1 if any ERROR exists (use --strict to also fail on WARN).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa: E402

FINDINGS: list[dict] = []


def add(check: str, sev: str, ids, detail: str = "") -> None:
    if isinstance(ids, pd.Series):
        ids = ids.tolist()
    for i in ids:
        FINDINGS.append({"check": check, "severity": sev, "deal_id": i, "detail": detail})


def main(root: Path, strict: bool) -> int:
    dc = root / "data_clean"
    x = pd.read_csv(dc / "deals_stage2.csv", parse_dates=["announcement_date", "close_date", "unaffected_date"])
    comp = pd.read_csv(dc / "companies.csv")
    x = x.merge(comp[["company_id", "ticker"]].rename(columns={"company_id": "target_id", "ticker": "target_ticker"}),
                on="target_id", how="left")
    n = len(x)

    # ---- identity / duplicates -------------------------------------------------------------------------
    add("duplicate_deal_id", "ERROR", x.loc[x["deal_id"].duplicated(keep=False), "deal_id"], "deal_id appears more than once")
    add("duplicate_canonical_key", "ERROR", x.loc[x["canonical_key"].duplicated(keep=False), "deal_id"],
        "same target + announcement_date + buyer")
    add("needs_manual_review_competing_bids", "WARN", x.loc[x["needs_review"] == 1, "deal_id"],
        "ambiguous winner among competing/revised bids; confirm final bid manually")

    # ---- dates -------------------------------------------------------------------------------------------
    add("announcement_date_missing_or_impossible", "ERROR",
        x.loc[x["announcement_date"].isna() | (x["announcement_date"] < "1990-01-01"), "deal_id"])
    add("close_before_announcement", "ERROR", x.loc[x["close_date"].notna() & (x["close_date"] < x["announcement_date"]), "deal_id"],
        "close_date earlier than announcement_date")
    add("completed_without_close_date", "WARN", x.loc[(x["deal_status"] == "completed") & x["close_date"].isna(), "deal_id"])
    add("outside_study_period", "INFO", x.loc[x["in_period"] == 0, "deal_id"], "excluded by period rule")
    add("unaffected_date_not_before_announcement", "ERROR",
        x.loc[x["public_target"].eq(1) & x["unaffected_date"].notna() & (x["unaffected_date"] >= x["announcement_date"]), "deal_id"])

    # ---- value checks ------------------------------------------------------------------------------------
    add("negative_or_zero_EV", "ERROR", x.loc[x["ev_final"].notna() & (x["ev_final"] <= 0), "deal_id"])
    add("EV_missing_in_primary_structure", "INFO", x.loc[(x["in_period"] == 1) & x["ev_usd"].isna(), "deal_id"],
        "no EV; falls out at the EV-available step")
    add("EV_currency_unconverted", "ERROR", x.loc[x["ev_final"].notna() & x["ev_usd"].isna(), "deal_id"],
        "EV present but fx_rate_announcement missing for non-USD currency")
    rec = x["ev_recon_diff_pct"].abs()
    add("EV_reconciliation_gap", "WARN", x.loc[rec > U.EV_RECON_TOL, "deal_id"],
        f"|reported EV - bridge EV| / reported EV > {U.EV_RECON_TOL:.0%}; check leases, pensions, earn-outs, investments")
    add("equity_value_vs_offer_x_shares_gap", "WARN",
        x.loc[x["implied_equity_check"].abs() > U.PRICE_RECON_TOL, "deal_id"],
        "equity value differs from offer price x diluted shares; check RSUs/options/converts")
    add("contingent_included_in_EV_review", "WARN", x.loc[x["contingent_review"] == 1, "deal_id"],
        "reported EV flagged as including contingent consideration; primary EV should be firm upfront")
    add("quality_flag_missing_with_EV", "WARN", x.loc[x["ev_usd"].notna() & x["data_quality_flag"].isna(), "deal_id"])
    add("quality_D_present", "INFO", x.loc[x["data_quality_flag"] == "D", "deal_id"], "robustness-only observation")

    # ---- financials ----------------------------------------------------------------------------------------
    add("financial_period_not_before_announcement", "ERROR", x.loc[x["alignment_error"] == 1, "deal_id"],
        "financial period end >= announcement date (post-deal information)")
    add("zero_or_negative_revenue", "ERROR", x.loc[x["revenue_ltm"].notna() & (x["revenue_ltm"] <= 0), "deal_id"])
    add("stale_financials_over_365d", "WARN", x.loc[x["financials_stale_flag"] == 1, "deal_id"],
        "excluded from preferred sample; kept for robustness")
    add("revenue_missing_in_primary_structure", "INFO",
        x.loc[(x["in_period"] == 1) & (x["primary_sector"] == 1) & x["revenue_ltm_usd"].isna(), "deal_id"])
    add("revenue_below_5m_threshold", "INFO", x.loc[x["revenue_ltm_usd"].notna() & (x["revenue_ltm_usd"] < U.REV_MIN_USD), "deal_id"])
    add("EV_below_25m_threshold", "INFO", x.loc[x["ev_usd"].notna() & (x["ev_usd"] < U.EV_MIN_USD), "deal_id"])
    # EV/Revenue mismatch: recompute in original currency when currencies match
    same = x["ev_final"].notna() & x["revenue_ltm"].notna() & (x["revenue_ltm"] > 0) & (x["ev_final"] > 0)
    chk = x["ev_final"] / x["revenue_ltm"]
    fin = pd.read_csv(dc / "financials_stage2.csv")[["deal_id", "currency"]]
    x = x.merge(fin, on="deal_id", how="left")
    same &= x["currency"].fillna(x["currency_original"]) == x["currency_original"]
    mism = same & ((chk - x["ev_revenue"]).abs() / x["ev_revenue"].abs() > 1e-6)
    add("EV_revenue_mismatch_vs_recomputed", "ERROR", x.loc[mism, "deal_id"], "stored EV/Revenue != EV/Revenue in original currency")
    add("EV_revenue_extreme_flag", "WARN", x.loc[(x["ev_revenue"] > 100) | (x["ev_revenue"] < 0.1), "deal_id"],
        "extreme multiple FLAGGED ONLY; no removal before Phase 4 cleaning")
    add("EV_EBITDA_extreme_flag", "WARN", x.loc[(x["ev_ebitda"] > 200) | (x["ev_ebitda"] < 1), "deal_id"],
        "extreme multiple FLAGGED ONLY; no removal before Phase 4 cleaning")

    # ---- public targets / prices -----------------------------------------------------------------------------
    pub = x["public_target"] == 1
    add("public_target_missing_ticker", "WARN", x.loc[pub & x["target_ticker"].isna(), "deal_id"])
    add("offer_price_nonpositive", "ERROR", x.loc[x["offer_price"].notna() & (x["offer_price"] <= 0), "deal_id"])
    add("public_without_price_data", "INFO", x.loc[pub & (x["in_period"] == 1) & x["premium_1d"].isna(), "deal_id"])
    recomputed = x["offer_price"] / x["unaffected_price_1d"] - 1
    pm = pub & x["premium_1d"].notna() & ((recomputed - x["premium_1d"]).abs() > 1e-9)
    add("premium_mismatch_vs_recomputed", "ERROR", x.loc[pm, "deal_id"])
    add("premium_outside_plausible_range", "WARN", x.loc[x["premium_1d"].notna() & ((x["premium_1d"] < -0.1) | (x["premium_1d"] > 1.5)), "deal_id"],
        "1-day premium < -10% or > 150%; verify offer price and unaffected date (flag only)")
    add("unaffected_date_missing_for_premium", "WARN", x.loc[pub & x["premium_1d"].notna() & x["unaffected_date"].isna(), "deal_id"])
    add("public_without_unaffected_reason", "WARN", x.loc[pub & x["premium_1d"].notna() & x["unaffected_reason"].isna(), "deal_id"],
        "document leak/rumour search result in unaffected_reason")

    # ---- percentages -----------------------------------------------------------------------------------------
    for c in ("cash_pct", "stock_pct", "other_pct"):
        add(f"{c}_out_of_range", "ERROR", x.loc[x[c].notna() & ((x[c] > 100) | (x[c] < 0)), "deal_id"], "percent must be 0-100")
    bad_sum = x["consideration_sum"].notna() & ((x["consideration_sum"] < 99) | (x["consideration_sum"] > 101))
    add("consideration_mix_not_100", "WARN", x.loc[bad_sum, "deal_id"])

    # ---- Phase 2 boundary checks -------------------------------------------------------------------------------
    if "ai_flag" in x.columns:
        add("final_ai_flag_present_in_phase2", "ERROR", ["<file>"], "ai_flag must not exist before Phase 3")
    blind_p = dc / "ai_coding_blind.csv"
    if blind_p.exists():
        b = pd.read_csv(blind_p, dtype=str)
        leak_cols = [c for c in b.columns if re.search(r"ev|equity|premium|offer|price|multiple|value", c, re.I)]
        if leak_cols:
            add("blind_file_valuation_column", "ERROR", ["<file>"], f"coder-facing columns: {leak_cols}")
        txt = b.drop(columns=["coder_row", "company_id", "target_name", "announcement_date", "sector"], errors="ignore").fillna("").agg(" ".join, axis=1)
        leaks = txt.map(lambda s: bool(re.search(r"[$€£]\s?\d|\b\d[\d,\.]*\s?(million|billion|bn)\b|\bEV/", s, re.I)))
        if leaks.any():
            add("blind_file_money_text_leak", "ERROR", ["<file>"], f"{int(leaks.sum())} rows still contain money/multiple text")
    mr = root / "results" / "missingness_report.csv"
    if mr.exists():
        m = pd.read_csv(mr)
        un = m[m["missing_code"] == "UNEXPLAINED"]
        for r in un.itertuples():
            add("missing_value_without_reason_code", "WARN", ["<field:" + r.field + ">"], f"{r.N} deals missing without NA/ND/NF/NR code")

    rep = pd.DataFrame(FINDINGS, columns=["check", "severity", "deal_id", "detail"])
    (root / "results").mkdir(exist_ok=True)
    rep.to_csv(root / "results" / "data_quality_report.csv", index=False)
    summ = rep.groupby(["severity", "check"]).size().rename("n").reset_index() if len(rep) else rep
    print(f"deals checked: {n}")
    print(summ.to_string(index=False) if len(summ) else "no findings")
    n_err = int((rep["severity"] == "ERROR").sum()) if len(rep) else 0
    n_warn = int((rep["severity"] == "WARN").sum()) if len(rep) else 0
    print(f"\nERROR={n_err} WARN={n_warn}")
    return 1 if (n_err or (strict and n_warn)) else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    sys.exit(main(U.project_root(a.root), a.strict))
