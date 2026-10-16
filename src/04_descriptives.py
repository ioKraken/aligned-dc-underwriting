"""Phase 4: data cleaning checks, analysis dataset, descriptive and diagnostic valuation statistics.

DESCRIPTIVE AND DIAGNOSTIC ONLY. No headline regression, no AI-premium claim. Every AI-vs-non-AI number is labelled
UNADJUSTED. The only regression-type model is the influence pre-check (section 48), whose AI coefficient is never reported
as a finding.

Hard gate: the Phase 3 treatment must be frozen and its checksum must verify, otherwise this script refuses to run
(valuation outcomes may not be looked at before the treatment is frozen).

Inputs : data_clean/deals_stage2.csv (Phase 2), data_clean/ai_treatment_frozen_V1.csv + docs/AI_CLASSIFICATION_V1_*.json (Phase 3),
         optional data_raw/market_data.csv (date, nasdaq_ret_12m, software_index_ev_rev, ust10y, fed_funds, vix)
Outputs: data_raw/deals_master_raw_v1.csv (+ .manifest.json), data_clean/deals_analysis_v1.csv, analysis_winsor_1_99.csv,
         analysis_outcome_winsor.csv, analysis_trimmed.csv, matching_input_v1.csv, exclusions_log_phase4.csv,
         docs/ANALYSIS_V1_PHASE4.json, results/p4_*.csv, results/charts/chart_*.png, results/phase4_report.md
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import shutil
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa: E402

warnings.filterwarnings("ignore")
SEED = U.SEED
DATA_VERSION = "ANALYSIS_V1_PHASE4"
GENAI_DATE = pd.Timestamp("2022-11-30")
BLUE, GREY = "#2a6fbb", "#8a8f98"
REQUIRED_COLS = ["deal_id", "target_name", "buyer_name", "announcement_date", "sector", "subsector", "region", "public_private",
                 "buyer_type", "enterprise_value", "ltm_revenue", "ltm_ebitda", "revenue_growth", "ebitda_margin", "ev_revenue",
                 "ev_ebitda", "premium_1d", "ai_flag_strict", "ai_flag_broad", "ai_intensity", "ai_subsector", "quality_flag",
                 "financial_stale_flag"]
OUT: list[tuple[str, pd.DataFrame]] = []


# ------------------------------------------------------------------------------------------------ helpers
def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save(df: pd.DataFrame, root: Path, name: str, index: bool = False) -> pd.DataFrame:
    (root / "results").mkdir(exist_ok=True)
    df.to_csv(root / "results" / f"{name}.csv", index=index)
    OUT.append((name, df))
    return df


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def desc(s: pd.Series) -> dict:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return {k: np.nan for k in ["N", "mean", "median", "sd", "min", "p1", "p5", "p25", "p75", "p95", "p99", "max"]}
    q = s.quantile([.01, .05, .25, .75, .95, .99])
    return {"N": len(s), "mean": s.mean(), "median": s.median(), "sd": s.std(), "min": s.min(), "p1": q[.01], "p5": q[.05],
            "p25": q[.25], "p75": q[.75], "p95": q[.95], "p99": q[.99], "max": s.max()}


def three_way(df: pd.DataFrame, col: str, label: str, ai="ai_flag_strict") -> pd.DataFrame:
    rows = []
    for g, m in (("full", pd.Series(True, index=df.index)), ("strict_AI", df[ai] == 1), ("non_AI", df[ai] == 0)):
        rows.append({"variable": label, "group": g, **desc(df.loc[m, col])})
    return pd.DataFrame(rows)


def welch(a, b):
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    if len(a) < 3 or len(b) < 3:
        return dict(diff=np.nan, t=np.nan, p=np.nan, ci_low=np.nan, ci_high=np.nan, n_ai=len(a), n_non=len(b))
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    se = np.sqrt(va + vb)
    dfree = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1)) if se > 0 else np.nan
    t, p = stats.ttest_ind(a, b, equal_var=False)
    crit = stats.t.ppf(.975, dfree)
    d = a.mean() - b.mean()
    return dict(diff=d, t=t, p=p, ci_low=d - crit * se, ci_high=d + crit * se, n_ai=len(a), n_non=len(b))


def mwu(a, b):
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    if len(a) < 3 or len(b) < 3:
        return dict(U=np.nan, p=np.nan, rank_biserial=np.nan)
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return dict(U=u, p=p, rank_biserial=2 * u / (len(a) * len(b)) - 1)


def cohens_d(a, b):
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    if len(a) < 3 or len(b) < 3:
        return np.nan
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return (a.mean() - b.mean()) / sp if sp > 0 else np.nan


def smd(a, b):
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return (a.mean() - b.mean()) / sd if sd > 0 else np.nan


def ols_diag(y: np.ndarray, X: np.ndarray, j: int):
    """OLS with leverage, Cook's D, scaled DFBETA for column j. numpy only; used for influence diagnostics, never as a result."""
    n, p = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    h = np.einsum("ij,jk,ik->i", X, xtx_inv, X)
    s2 = e @ e / (n - p)
    cook = e ** 2 / (p * s2) * h / (1 - h) ** 2
    s2_i = ((n - p) * s2 - e ** 2 / (1 - h)) / (n - p - 1)
    dfb = (xtx_inv @ X.T * (e / (1 - h))).T[:, j]
    dfbetas = dfb / (np.sqrt(np.maximum(s2_i, 1e-12)) * np.sqrt(xtx_inv[j, j]))
    return beta, h, cook, dfbetas, np.sqrt(s2)


def vif_table(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    d = df[cols].dropna()
    rows = []
    for c in cols:
        if len(d) < len(cols) + 3:
            rows.append({"variable": c, "VIF": np.nan, "flag_gt_5": np.nan, "N": len(d)})
            continue
        X = np.column_stack([np.ones(len(d)), d.drop(columns=c).to_numpy(float)])
        y = d[c].to_numpy(float)
        b = np.linalg.pinv(X.T @ X) @ X.T @ y
        r2 = 1 - ((y - X @ b) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        v = 1 / (1 - r2) if r2 < 1 else np.inf
        rows.append({"variable": c, "VIF": v, "flag_gt_5": int(v > 5), "N": len(d)})
    return pd.DataFrame(rows)


def mde(sd, n1, n0, alpha=.05, power=.8):
    if min(n1, n0) < 2 or not np.isfinite(sd):
        return np.nan
    return (stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * sd * np.sqrt(1 / n1 + 1 / n0)


def pct(a, b):
    return a / b if b else np.nan


# ------------------------------------------------------------------------------------------------ gate
def verify_phase3_freeze(root: Path) -> dict:
    mans = sorted(glob.glob(str(root / "docs" / "AI_CLASSIFICATION_V1_*.json")))
    if not mans:
        raise SystemExit("PHASE 4 REFUSED: no Phase 3 treatment freeze manifest (docs/AI_CLASSIFICATION_V1_*.json). "
                         "Valuation outcomes may not be analysed before the AI treatment is frozen.")
    man = json.loads(Path(mans[-1]).read_text())
    fp = root / "data_clean" / man["frozen_file"]
    if not fp.exists() or sha256(fp) != man["frozen_file_sha256"]:
        raise SystemExit("PHASE 4 REFUSED: frozen treatment file is missing or its checksum does not match the manifest.")
    return man


# ------------------------------------------------------------------------------------------------ main
def main(root: Path) -> int:
    for sub in ("results", "results/charts", "docs", "data_raw", "data_clean"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    man = verify_phase3_freeze(root)
    src = root / "data_clean" / "deals_stage2.csv"
    if not src.exists() or src.stat().st_size < 50:
        raise SystemExit("PHASE 4 REFUSED: deals_stage2.csv missing or empty (universe not populated).")

    # ---- 1. immutable raw snapshot -------------------------------------------------------------------
    snap = root / "data_raw" / "deals_master_raw_v1.csv"
    snap_man = root / "data_raw" / "deals_master_raw_v1.manifest.json"
    if snap.exists():
        rec = json.loads(snap_man.read_text())
        if sha256(snap) != rec["sha256"]:
            raise SystemExit("deals_master_raw_v1.csv was modified after freeze. Restore it or create a documented v2.")
    else:
        shutil.copyfile(src, snap)
        raw = pd.read_csv(snap, low_memory=False)
        snap_man.write_text(json.dumps({"file": snap.name, "sha256": sha256(snap), "created": str(date.today()),
                                        "rows": int(len(raw)), "columns": int(raw.shape[1])}, indent=2))
    x = pd.read_csv(snap, low_memory=False, parse_dates=["announcement_date", "close_date"])
    tr = pd.read_csv(root / "data_clean" / man["frozen_file"], low_memory=False)
    keep_t = [c for c in ["deal_id", "ai_flag_strict", "ai_flag_broad", "ai_intensity", "ai_subsector", "ai_subsector_group",
                          "ai_class_confidence", "ai_class_source", "ai_label_is_assumed", "acquihire_ai_flag",
                          "ai_conservative_intensity", "ai_liberal_intensity", "ai_company_vintage"] if c in tr.columns]
    x = x.merge(tr[keep_t], on="deal_id", how="left", validate="one_to_one")
    synthetic = bool(x["source_universe"].astype(str).str.contains("synthetic", case=False).any())
    x["acquihire_ai_flag"] = pd.to_numeric(x["acquihire_ai_flag"], errors="coerce").fillna(0)

    # ---- 2. analysis dataset (raw columns preserved; transforms added as new columns) -------------------
    a = pd.DataFrame({
        "deal_id": x["deal_id"], "target_name": x["target_name"], "buyer_name": x["buyer_name"],
        "announcement_date": x["announcement_date"].dt.strftime("%Y-%m-%d"), "sector": x["sector_primary"], "subsector": x["subsector"],
        "region": x["target_region"], "public_private": x["target_public_private"], "buyer_type": x["buyer_type"],
        "enterprise_value": x["ev_usd"], "ltm_revenue": x["revenue_ltm_usd"], "ltm_ebitda": x["ebitda_ltm_usd"],
        "revenue_growth": x["revenue_growth"], "ebitda_margin": x["ebitda_margin"], "ev_revenue": x["ev_revenue"],
        "ev_ebitda": x["ev_ebitda"], "premium_1d": x["premium_1d"], "ai_flag_strict": x["ai_flag_strict"],
        "ai_flag_broad": x["ai_flag_broad"], "ai_intensity": x["ai_intensity"], "ai_subsector": x["ai_subsector"],
        "quality_flag": x["data_quality_flag"], "financial_stale_flag": x["financials_stale_flag"]})
    a["_ann"] = x["announcement_date"]
    for c in ["announce_year", "post_genai", "public_target", "strategic_buyer", "sponsor_buyer", "staleness_days", "ev_quality",
              "financials_quality", "premium_1w", "premium_1m", "premium_vwap30", "ln1p_premium_1d", "predeal_ev_revenue",
              "ev_recon_diff_pct", "ev_reported", "ev_calculated", "ebitda_positive", "ev_disclosed", "financials_disclosed",
              "contingent_consideration", "ev_basis", "ev_disclosed_in", "target_country", "revenue_period_end", "cash_pct",
              "stock_pct", "ai_subsector_group", "acquihire_ai_flag", "ai_class_source", "ai_label_is_assumed", "close_date"]:
        a[c] = x[c] if c in x.columns else np.nan
    a["ln_revenue"] = np.log(a["ltm_revenue"].where(a["ltm_revenue"] > 0))
    a["ln_ev_revenue"] = np.log(a["ev_revenue"].where(a["ev_revenue"] > 0))
    a["ln_ev_ebitda"] = np.log(a["ev_ebitda"].where(a["ev_ebitda"] > 0))
    a["evrev_gt_100"] = (a["ev_revenue"] > 100).astype(int)
    a["strategic"] = (a["strategic_buyer"] == 1).astype(int)
    a["public"] = (a["public_target"] == 1).astype(int)
    a["disclosure_flag"] = ((a["ev_disclosed"] == 1) & (a["financials_disclosed"].astype(str).isin(["1", "1.0", "True"]))).astype(int)

    # ---- 3. waterfalls (Phase 2 step definitions, re-run programmatically) + AI-coded + acqui-hire -----
    m2 = load_module(Path(__file__).resolve().parent / "02b_build_stage2.py", "stage2mod")
    steps = m2.waterfall_steps(x)
    wf_rows, excl_rows, masks = [], [], {}
    for outcome, st in steps.items():
        cur = pd.Series(True, index=x.index)
        full = list(st[:-1]) if st and st[-1][2] == "ai_coding_pending" else list(st)
        coded = x["ai_flag_strict"].notna()
        full += [("AI classification available (frozen Phase 3)", coded, "no_ai_classification"),
                 ("Not acqui-hire / licence (acquihire_ai_flag = 0)", x["acquihire_ai_flag"] != 1, "acquihire_ai_flag")]
        for i, (label, mask, reason) in enumerate(full):
            keep = cur & mask.fillna(False)
            for idx in x.index[cur & ~keep]:
                excl_rows.append({"deal_id": x.at[idx, "deal_id"], "target": x.at[idx, "target_name"], "exclusion_stage": f"{outcome}: {label}",
                                  "exclusion_reason": reason, "rule_source": "phase1_design;" + ("phase3_rubric_s5" if reason == "acquihire_ai_flag" else "phase2_waterfall"),
                                  "manual_or_automatic": "automatic", "notes": ""})
            cur = keep
            wf_rows.append({"outcome": outcome, "stage": i + 1, "step": label, "total_N": int(cur.sum()),
                            "strict_AI_N": int((cur & (x["ai_flag_strict"] == 1)).sum()),
                            "non_AI_N": int((cur & (x["ai_flag_strict"] == 0)).sum()),
                            "AI_enabled_N(intensity=1)": int((cur & (x["ai_intensity"] == 1)).sum())})
        masks[outcome] = cur
    wf = save(pd.DataFrame(wf_rows), root, "p4_sample_waterfall")
    excl = pd.DataFrame(excl_rows)
    # one row per deal per outcome is large; keep the first-failing stage per deal and outcome
    excl.to_csv(root / "data_clean" / "exclusions_log_phase4.csv", index=False)
    chk = {k: bool((masks[k].astype(int) == x[f"in_primary_sample_{c}"].astype(int) * (x["ai_flag_strict"].notna() & (x["acquihire_ai_flag"] != 1))).all())
           for k, c in (("EV/Revenue", "evrev"), ("EV/EBITDA", "ebitda"), ("Takeover premium", "premium"))}
    save(pd.DataFrame([{"outcome": k, "matches_phase2_flag_after_ai_and_acquihire": v} for k, v in chk.items()]), root, "p4_waterfall_consistency")
    a["in_evrev_final"] = masks["EV/Revenue"].astype(int)
    a["in_ebitda_final"] = masks["EV/EBITDA"].astype(int)
    a["in_premium_final"] = masks["Takeover premium"].astype(int)
    E = a[a["in_evrev_final"] == 1].copy()
    B = a[a["in_ebitda_final"] == 1].copy()
    P = a[a["in_premium_final"] == 1].copy()

    # ---- 5. duplicates ---------------------------------------------------------------------------------
    dup = pd.DataFrame([
        {"check": "duplicate deal_id", "count": int(a["deal_id"].duplicated().sum())},
        {"check": "duplicate target|announcement|buyer", "count": int(a.duplicated(["target_name", "announcement_date", "buyer_name"]).sum())},
        {"check": "same target, multiple completed deals within 365d", "count": int(
            a.sort_values("_ann").groupby("target_name")["_ann"].diff().dt.days.le(365).sum())}])
    save(dup, root, "p4_duplicates")

    # ---- 6. impossible values ----------------------------------------------------------------------------
    def scale(s):
        s = pd.to_numeric(s, errors="coerce")
        return s / 100 if s.max() > 1.5 else s
    imp = {"EV <= 0": a["enterprise_value"] <= 0, "Revenue <= 0": a["ltm_revenue"] <= 0,
           "EBITDA > revenue (margin > 100%)": a["ebitda_margin"] > 1, "Revenue growth < -100%": a["revenue_growth"] < -1,
           "Cash consideration > 100%": scale(a["cash_pct"]) > 1.0001, "Stock consideration > 100%": scale(a["stock_pct"]) > 1.0001,
           "Premium < -100%": a["premium_1d"] < -1,
           "Financial period end after announcement": pd.to_datetime(a["revenue_period_end"], errors="coerce") > a["_ann"],
           "Announcement after close": pd.to_datetime(a["close_date"], errors="coerce") < a["_ann"]}
    impt = pd.DataFrame([{"check": k, "N_flagged": int(v.fillna(False).sum()),
                          "deal_ids": ";".join(a.loc[v.fillna(False), "deal_id"].head(25))} for k, v in imp.items()])
    save(impt, root, "p4_impossible_values")

    # ---- 7. EV reconciliation ---------------------------------------------------------------------------
    rec = a[["deal_id", "ev_reported", "ev_calculated", "ev_recon_diff_pct"]].dropna(subset=["ev_reported", "ev_calculated"]).copy()
    rec["abs_diff_pct"] = (rec["ev_reported"] - rec["ev_calculated"]).abs() / rec["ev_reported"]
    rec["flag_gt_5pct"] = (rec["abs_diff_pct"] > .05).astype(int)
    save(rec, root, "p4_ev_reconciliation_deals")
    save(pd.DataFrame([{"N_with_components": len(rec), **desc(rec["abs_diff_pct"]), "N_flagged_gt_5pct": int(rec["flag_gt_5pct"].sum()),
                        "tolerance": "5% of reported EV"}]), root, "p4_ev_reconciliation_summary")

    # ---- 8. staleness -------------------------------------------------------------------------------------
    sd_ = a["staleness_days"]
    a["staleness_bucket"] = pd.cut(sd_, [-np.inf, 90, 180, 365, np.inf], labels=["0-90", "91-180", "181-365", ">365"])
    sb = a.assign(group=a["ai_flag_strict"].map({1: "strict_AI", 0: "non_AI"})).groupby(["group", "staleness_bucket"], observed=False).size().unstack(0).fillna(0)
    save(sb.reset_index(), root, "p4_staleness_buckets")
    stl = pd.DataFrame([{**desc(a.loc[a["ai_flag_strict"] == v, "staleness_days"]), "group": g} for v, g in ((1, "strict_AI"), (0, "non_AI"))])
    stl["mannwhitney_p_AI_vs_nonAI"] = mwu(a.loc[a["ai_flag_strict"] == 1, "staleness_days"], a.loc[a["ai_flag_strict"] == 0, "staleness_days"])["p"]
    save(stl, root, "p4_staleness_by_ai")

    # ---- 9. LTM validation sample (manual step; cannot be computed from final data) ----------------------------
    pubE = E[E["public"] == 1]
    k = max(1, int(np.ceil(.10 * len(pubE)))) if len(pubE) else 0
    smp = pubE.sample(n=k, random_state=SEED)[["deal_id", "target_name", "ltm_revenue"]].copy() if k else pd.DataFrame(columns=["deal_id", "target_name", "ltm_revenue"])
    for c in ("fy_revenue", "current_ytd", "prior_ytd", "recalculated_ltm", "difference_pct", "auditor_initials"):
        smp[c] = ""
    save(smp, root, "p4_ltm_audit_sample")
    save(E.groupby(["public_private", "financials_quality"], dropna=False).size().rename("N").reset_index(), root, "p4_financial_source_quality")

    # ---- 10-13 outcomes ---------------------------------------------------------------------------------
    outcome_checks = pd.DataFrame([
        {"check": "EV/Revenue zero or negative in EV/Revenue sample", "count": int((E["ev_revenue"] <= 0).sum())},
        {"check": "ln(EV/Revenue) NaN introduced in sample", "count": int((E["ln_ev_revenue"].isna() & E["ev_revenue"].notna()).sum())},
        {"check": "EV/EBITDA assigned to EBITDA <= 0", "count": int(((B["ltm_ebitda"] <= 0) & B["ev_ebitda"].notna()).sum())},
        {"check": "premium_1d <= -100% in premium sample", "count": int((P["premium_1d"] <= -1).sum())}])
    save(outcome_checks, root, "p4_outcome_checks")
    save(pd.DataFrame([{"group": g, "N_ebitda_known": int(m.sum()), "N_positive": int((m & (E["ebitda_positive"] == 1)).sum()),
                        "P(EBITDA>0)": pct(int((m & (E["ebitda_positive"] == 1)).sum()), int(m.sum()))}
                       for g, m in (("strict_AI", (E["ai_flag_strict"] == 1) & E["ltm_ebitda"].notna()),
                                    ("non_AI", (E["ai_flag_strict"] == 0) & E["ltm_ebitda"].notna()))]), root, "p4_ebitda_positive_share")

    # ---- 14 distributions -----------------------------------------------------------------------------------
    dist = pd.concat([three_way(E, "ev_revenue", "EV/Revenue"), three_way(E, "ln_ev_revenue", "ln(EV/Revenue)"),
                      three_way(B, "ev_ebitda", "EV/EBITDA"), three_way(P, "premium_1d", "Premium 1D"),
                      three_way(P, "premium_1w", "Premium 1W"), three_way(P, "premium_1m", "Premium 1M"),
                      three_way(P, "premium_vwap30", "Premium VWAP30")])
    save(dist, root, "p4_outcome_distributions")

    # ---- 16-20 raw comparison and tests (UNADJUSTED) -------------------------------------------------------------
    A1, A0 = E[E["ai_flag_strict"] == 1], E[E["ai_flag_strict"] == 0]
    med1, med0 = A1["ev_revenue"].median(), A0["ev_revenue"].median()
    raw = pd.DataFrame([
        ("Median EV/Revenue", med1, med0, med1 - med0, "UNADJUSTED difference (turns of revenue)"),
        ("Median EV/Revenue ratio-1", med1, med0, pct(med1, med0) - 1 if med0 else np.nan, "UNADJUSTED percentage difference"),
        ("Mean ln(EV/Revenue)", A1["ln_ev_revenue"].mean(), A0["ln_ev_revenue"].mean(), A1["ln_ev_revenue"].mean() - A0["ln_ev_revenue"].mean(), "UNADJUSTED log-point difference"),
        ("Median EV/EBITDA", B.loc[B.ai_flag_strict == 1, "ev_ebitda"].median(), B.loc[B.ai_flag_strict == 0, "ev_ebitda"].median(),
         B.loc[B.ai_flag_strict == 1, "ev_ebitda"].median() - B.loc[B.ai_flag_strict == 0, "ev_ebitda"].median(), "UNADJUSTED"),
        ("Median premium 1D", P.loc[P.ai_flag_strict == 1, "premium_1d"].median(), P.loc[P.ai_flag_strict == 0, "premium_1d"].median(),
         P.loc[P.ai_flag_strict == 1, "premium_1d"].median() - P.loc[P.ai_flag_strict == 0, "premium_1d"].median(), "UNADJUSTED"),
        ("Median revenue growth", A1["revenue_growth"].median(), A0["revenue_growth"].median(), A1["revenue_growth"].median() - A0["revenue_growth"].median(), "descriptive"),
        ("Median EBITDA margin", A1["ebitda_margin"].median(), A0["ebitda_margin"].median(), A1["ebitda_margin"].median() - A0["ebitda_margin"].median(), "descriptive"),
        ("Median LTM revenue (USD)", A1["ltm_revenue"].median(), A0["ltm_revenue"].median(), A1["ltm_revenue"].median() - A0["ltm_revenue"].median(), "descriptive")],
        columns=["metric", "AI", "non_AI", "difference", "label"])
    save(raw, root, "p4_raw_comparison_unadjusted")

    tests = []
    for lab, df, col in (("ln(EV/Revenue)", E, "ln_ev_revenue"), ("EV/Revenue (raw)", E, "ev_revenue"), ("Revenue growth", E, "revenue_growth"),
                         ("EBITDA margin", E, "ebitda_margin"), ("Premium 1D", P, "premium_1d")):
        a1, a0 = df.loc[df.ai_flag_strict == 1, col], df.loc[df.ai_flag_strict == 0, col]
        w, m_ = welch(a1, a0), mwu(a1, a0)
        tests.append({"outcome": lab, "AI_mean": a1.mean(), "nonAI_mean": a0.mean(), "AI_median": a1.median(), "nonAI_median": a0.median(),
                      "welch_diff": w["diff"], "welch_t": w["t"], "welch_p": w["p"], "welch_ci_low": w["ci_low"], "welch_ci_high": w["ci_high"],
                      "mwu_p": m_["p"], "rank_biserial": m_["rank_biserial"], "cohens_d": cohens_d(a1, a0), "n_AI": w["n_ai"], "n_nonAI": w["n_non"],
                      "label": "descriptive / unadjusted - not an AI premium"})
    save(pd.DataFrame(tests), root, "p4_univariate_tests")

    # ---- 21 intensity ---------------------------------------------------------------------------------------------
    it = E.groupby("ai_intensity").agg(N=("deal_id", "count"), median_ev_revenue=("ev_revenue", "median"), median_growth=("revenue_growth", "median"),
                                       median_margin=("ebitda_margin", "median"), median_revenue=("ltm_revenue", "median")).reset_index()
    save(it, root, "p4_intensity_descriptives")
    gi = E[["ai_intensity", "revenue_growth", "ln_ev_revenue"]].dropna()
    if len(gi) > 10 and gi["ai_intensity"].nunique() > 1:
        save(pd.DataFrame([{"check": "Spearman(intensity, growth)", "rho": stats.spearmanr(gi.ai_intensity, gi.revenue_growth)[0]},
                           {"check": "Spearman(growth, ln EV/Rev)", "rho": stats.spearmanr(gi.revenue_growth, gi.ln_ev_revenue)[0]}]), root, "p4_intensity_growth_mechanical_check")

    # ---- 22-23 year and GenAI -----------------------------------------------------------------------------------------
    yr = E.groupby(["announce_year", "ai_flag_strict"]).agg(N=("deal_id", "count"), median_ev_revenue=("ev_revenue", "median")).unstack("ai_flag_strict")
    yr.columns = [f"{a_}_{'AI' if b_ == 1 else 'nonAI'}" for a_, b_ in yr.columns]
    yr = yr.reset_index()
    for c in ("N_AI", "N_nonAI"):
        if c not in yr:
            yr[c] = 0
    yr["AI_share_of_year"] = yr["N_AI"].fillna(0) / (yr["N_AI"].fillna(0) + yr["N_nonAI"].fillna(0))
    save(yr, root, "p4_year_distribution")
    gp = []
    for g, mk in (("Pre-Nov 2022", E["_ann"] <= GENAI_DATE), ("Post-Nov 2022", E["_ann"] > GENAI_DATE)):
        gp.append({"period": g, "AI_N": int((mk & (E.ai_flag_strict == 1)).sum()), "nonAI_N": int((mk & (E.ai_flag_strict == 0)).sum()),
                   "AI_median_EV_Rev": E.loc[mk & (E.ai_flag_strict == 1), "ev_revenue"].median(),
                   "nonAI_median_EV_Rev": E.loc[mk & (E.ai_flag_strict == 0), "ev_revenue"].median(),
                   "note": "descriptive; not a causal difference-in-differences"})
    save(pd.DataFrame(gp), root, "p4_pre_post_genai")

    # ---- 24-30 composition -----------------------------------------------------------------------------------------------
    def comp(col, name):
        t = pd.crosstab(E[col].fillna("missing"), E["ai_flag_strict"].map({1: "AI", 0: "nonAI"}))
        for c in ("AI", "nonAI"):
            if c not in t:
                t[c] = 0
        t["AI_pct_of_AI"], t["nonAI_pct_of_nonAI"] = t["AI"] / max(t["AI"].sum(), 1), t["nonAI"] / max(t["nonAI"].sum(), 1)
        save(t.reset_index(), root, name)
        return t
    comp("sector", "p4_sector_composition"); comp("region", "p4_region_composition"); comp("public_private", "p4_public_private_composition")
    comp("buyer_type", "p4_buyer_composition")
    pp = []
    for g, mk in (("public", E["public"] == 1), ("private", E["public"] == 0)):
        for lab, m2_ in (("strict_AI", E.ai_flag_strict == 1), ("non_AI", E.ai_flag_strict == 0)):
            pp.append({"target_type": g, "group": lab, "N": int((mk & m2_).sum()), "median_ev_revenue": E.loc[mk & m2_, "ev_revenue"].median()})
    save(pd.DataFrame(pp), root, "p4_public_private_multiples")
    for col, nm in (("ltm_revenue", "size"), ("revenue_growth", "growth"), ("ebitda_margin", "margin")):
        save(pd.concat([three_way(E, col, col), three_way(E.assign(ln_rev=E["ln_revenue"]), "ln_rev", "ln_revenue")]) if nm == "size" else three_way(E, col, col), root, f"p4_{nm}_comparison")

    # ---- 31-35 correlations, VIF -----------------------------------------------------------------------------------------------
    cc = ["ln_ev_revenue", "revenue_growth", "ebitda_margin", "ln_revenue", "predeal_ev_revenue", "premium_1d"]
    D = a[(a["in_evrev_final"] == 1) | (a["in_premium_final"] == 1)][cc]
    save(D.corr(method="pearson").reset_index(), root, "p4_corr_pearson")
    save(D.corr(method="spearman").reset_index(), root, "p4_corr_spearman")
    E["_pub"], E["_str"] = E["public"], E["strategic"]
    save(vif_table(E, ["revenue_growth", "ebitda_margin", "ln_revenue", "_pub", "_str"]).replace({"_pub": "public", "_str": "strategic"}), root, "p4_vif")

    # ---- 36-39 missingness ---------------------------------------------------------------------------------------------------------
    uni = a[a["ai_flag_strict"].notna()].copy()
    core = {"EV": "enterprise_value", "Revenue": "ltm_revenue", "Growth": "revenue_growth", "EBITDA": "ltm_ebitda", "Margin": "ebitda_margin",
            "Premium (public only)": "premium_1d"}
    mrows, avail = [], pd.DataFrame(index=uni.index)
    for lab, c in core.items():
        base = uni[uni["public"] == 1] if "public only" in lab else uni
        for g, m_ in (("all", base.index == base.index), ("AI", (base.ai_flag_strict == 1).to_numpy()), ("nonAI", (base.ai_flag_strict == 0).to_numpy())):
            sub = base[m_]
            mrows.append({"variable": lab, "group": g, "available": int(sub[c].notna().sum()), "missing": int(sub[c].isna().sum()), "pct_missing": sub[c].isna().mean() if len(sub) else np.nan})
        avail[lab] = uni[c].notna().astype(int)
    save(pd.DataFrame(mrows), root, "p4_missingness")
    ft = []
    for lab in ("EV", "Revenue", "Growth", "EBITDA", "Margin"):
        t = pd.crosstab(avail[lab], uni["ai_flag_strict"]).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
        p_chi = stats.chi2_contingency(t, correction=False)[1] if (t.to_numpy().sum() and (t.sum(axis=0) > 0).all() and (t.sum(axis=1) > 0).all()) else np.nan
        p_f = stats.fisher_exact(t.to_numpy())[1] if t.to_numpy().sum() else np.nan
        ft.append({"availability": lab, "AI_available_rate": uni.loc[uni.ai_flag_strict == 1, core[lab] if lab in core else lab].notna().mean(),
                   "nonAI_available_rate": uni.loc[uni.ai_flag_strict == 0, core[lab]].notna().mean(), "chi2_p": p_chi, "fisher_p": p_f})
    save(pd.DataFrame(ft), root, "p4_missingness_tests")
    uni["rev_avail"] = uni["ltm_revenue"].notna().astype(int)
    save(uni.groupby(["ai_flag_strict", "public_private"], dropna=False).agg(N=("deal_id", "count"), revenue_available=("rev_avail", "sum"),
                                                                           ev_available=("enterprise_value", lambda s: int(s.notna().sum()))).reset_index(), root, "p4_missingness_ai_x_public")
    save(uni.groupby("ai_flag_strict").agg(N=("deal_id", "count"), disclosure_rate=("disclosure_flag", "mean")).reset_index(), root, "p4_disclosure_rate")

    # ---- 40 selection model (descriptive; not used to correct anything) ------------------------------------------------------------------
    from sklearn.linear_model import LogisticRegression
    pre = (x["in_period"] == 1) & (x["primary_geography"] == 1) & (x["primary_sector"] == 1) & (x["control_deal"] == 1) & (x["status_primary_sample"] == 1) & x["structural_exclusion"].isna() & x["ai_flag_strict"].notna()
    S = a[pre.to_numpy()].copy()
    S["in_sample"] = S["in_evrev_final"]
    if S["in_sample"].nunique() == 2 and len(S) > 30:
        Z = pd.get_dummies(S[["announce_year", "sector", "region"]].astype(str), drop_first=True).astype(float)
        Z["public"], Z["ai_flag_strict"] = S["public"].astype(float), S["ai_flag_strict"].astype(float)
        mdl = LogisticRegression(C=1e4, max_iter=2000).fit(Z, S["in_sample"])
        S["p_in"] = mdl.predict_proba(Z)[:, 1]
        z0, z1 = Z.copy(), Z.copy(); z0["ai_flag_strict"], z1["ai_flag_strict"] = 0., 1.
        save(pd.DataFrame([{"N_universe_for_selection_model": len(S), "raw_inclusion_rate_AI": S.loc[S.ai_flag_strict == 1, "in_sample"].mean(),
                            "raw_inclusion_rate_nonAI": S.loc[S.ai_flag_strict == 0, "in_sample"].mean(),
                            "ai_coefficient_log_odds": float(mdl.coef_[0][list(Z.columns).index("ai_flag_strict")]),
                            "avg_pred_inclusion_if_AI": float(mdl.predict_proba(z1)[:, 1].mean()),
                            "avg_pred_inclusion_if_nonAI": float(mdl.predict_proba(z0)[:, 1].mean()),
                            "note": "diagnostic only; not used to correct the main regression"}]), root, "p4_selection_model")
    else:
        save(pd.DataFrame([{"note": "selection model not estimable (no variation in inclusion or N too small)"}]), root, "p4_selection_model")

    # ---- 41-42 quality, source tiers -----------------------------------------------------------------------------------------------------------
    uq = a[a["ai_flag_strict"].notna()]
    save(pd.crosstab(uq["quality_flag"].fillna("missing"), uq["ai_flag_strict"].map({1: "AI", 0: "nonAI"})).reset_index(), root, "p4_quality_by_ai")
    tiercol = "ev_disclosed_in" if a["ev_disclosed_in"].notna().any() else "ev_basis"
    save(pd.crosstab(uq[tiercol].fillna("missing"), uq["ai_flag_strict"].map({1: "AI", 0: "nonAI"})).reset_index(), root, "p4_source_tier_by_ai")

    # ---- 43-44 outliers (identify, never remove) --------------------------------------------------------------------------------------------------------
    def tag(df):
        df = df.copy()
        df["suggested_category"] = np.select(
            [df["contingent_consideration"].fillna(0) == 1, df["staleness_days"] > 270, df["ltm_revenue"] < 10e6], ["contingent consideration distortion",
             "stale denominator", "early-stage low-revenue company"], "needs_review (true extreme or data error)")
        df["verified_source"], df["verified_revenue_denominator"], df["verified_ev"], df["final_category"] = "", "", "", ""
        return df[["deal_id", "target_name", "ai_flag_strict", "ev_revenue", "revenue_growth", "ebitda_margin", "ltm_revenue", "enterprise_value",
                   "staleness_days", "quality_flag", "suggested_category", "verified_source", "verified_revenue_denominator", "verified_ev", "final_category"]]
    out = pd.concat([tag(E.nlargest(10, "ev_revenue")).assign(list="top10_ev_revenue"), tag(E.nsmallest(10, "ev_revenue")).assign(list="bottom10_ev_revenue"),
                     tag(E.nlargest(10, "revenue_growth")).assign(list="largest_growth"), tag(E.nsmallest(10, "ebitda_margin")).assign(list="most_negative_margin")])
    save(out, root, "p4_outlier_validation_queue")

    # ---- 45-47 winsorised / trimmed / >100x versions ---------------------------------------------------------------------------------------------------------
    def wins(s, lo=.01, hi=.99):
        return s.clip(s.quantile(lo), s.quantile(hi))
    a["revenue_growth_w"], a["ebitda_margin_w"] = a["revenue_growth"], a["ebitda_margin"]
    e_idx = a["in_evrev_final"] == 1
    a.loc[e_idx, "revenue_growth_w"] = wins(a.loc[e_idx, "revenue_growth"])
    a.loc[e_idx, "ebitda_margin_w"] = wins(a.loc[e_idx, "ebitda_margin"])
    a["ev_revenue_w"] = a["ev_revenue"]
    a.loc[e_idx, "ev_revenue_w"] = wins(a.loc[e_idx, "ev_revenue"])
    a["ln_ev_revenue_w"] = np.log(a["ev_revenue_w"].where(a["ev_revenue_w"] > 0))
    lo_, hi_ = E["ev_revenue"].quantile(.01), E["ev_revenue"].quantile(.99)
    a["trim_p1_p99_exclude"] = (e_idx & ((a["ev_revenue"] < lo_) | (a["ev_revenue"] > hi_))).astype(int)
    save(a.loc[a["evrev_gt_100"] == 1, ["deal_id", "target_name", "ev_revenue", "ai_flag_strict", "in_evrev_final"]], root, "p4_evrev_gt_100_verification_queue")

    # ---- 48-50 influence (diagnostic regression, AI coefficient NOT reported) ---------------------------------------------------------------------------------------
    M = E[["deal_id", "ln_ev_revenue", "ai_flag_strict", "revenue_growth", "ebitda_margin", "ln_revenue"]].dropna()
    if len(M) > 12 and M["ai_flag_strict"].nunique() == 2:
        X = np.column_stack([np.ones(len(M)), M[["ai_flag_strict", "revenue_growth", "ebitda_margin", "ln_revenue"]].to_numpy(float)])
        _, h, cook, dfb, _ = ols_diag(M["ln_ev_revenue"].to_numpy(float), X, 1)
        inf = M[["deal_id"]].copy()
        inf["leverage"], inf["cooks_d"], inf["dfbetas_ai"] = h, cook, dfb
        inf["flag_cooks_gt_4n"] = (cook > 4 / len(M)).astype(int)
        inf["flag_dfbeta_gt_2sqrtn"] = (np.abs(dfb) > 2 / np.sqrt(len(M))).astype(int)
        inf = inf.merge(E[["deal_id", "target_name", "ev_revenue", "ai_flag_strict"]], on="deal_id").sort_values("cooks_d", ascending=False)
        save(inf.head(25), root, "p4_influence_top25")
        save(pd.DataFrame([{"N": len(M), "cooks_threshold_4_over_N": 4 / len(M), "N_cooks_flagged": int(inf.flag_cooks_gt_4n.sum()),
                            "dfbeta_threshold_2_over_sqrtN": 2 / np.sqrt(len(M)), "N_dfbeta_flagged": int(inf.flag_dfbeta_gt_2sqrtn.sum()),
                            "note": "diagnostic model only; AI coefficient intentionally not reported"}]), root, "p4_influence_summary")
    else:
        save(pd.DataFrame([{"note": "influence diagnostics not estimable"}]), root, "p4_influence_summary")

    # ---- 51-54 support, propensity, balance ----------------------------------------------------------------------------------------------------------------------------
    for c1, c2, nm in (("announce_year", "sector", "year_x_sector"), ("region", "sector", "region_x_sector"), ("public_private", "sector", "public_x_sector")):
        t = E.groupby([c1, c2, "ai_flag_strict"]).size().unstack("ai_flag_strict").reindex(columns=[0, 1]).fillna(0).astype(int).reset_index()
        t.columns = [c1, c2, "nonAI_N", "AI_N"]
        t["sparse_AI_lt3"] = (t["AI_N"] < 3).astype(int)
        t["no_support_one_group_empty"] = ((t["AI_N"] == 0) | (t["nonAI_N"] == 0)).astype(int)
        save(t, root, f"p4_support_{nm}")
    PS = E[["deal_id", "ai_flag_strict", "announce_year", "sector", "region", "revenue_growth", "ln_revenue", "ebitda_margin"]].dropna()
    ps_pct = np.nan
    if PS["ai_flag_strict"].nunique() == 2 and PS["ai_flag_strict"].value_counts().min() >= 5:
        Z = pd.get_dummies(PS[["announce_year", "sector", "region"]].astype(str), drop_first=True).astype(float)
        for c in ("revenue_growth", "ln_revenue", "ebitda_margin"):
            Z[c] = (PS[c] - PS[c].mean()) / PS[c].std()
        pm = LogisticRegression(C=1.0, max_iter=3000).fit(Z, PS["ai_flag_strict"])
        PS["pscore"] = pm.predict_proba(Z)[:, 1]
        lo = max(PS.loc[PS.ai_flag_strict == 1, "pscore"].min(), PS.loc[PS.ai_flag_strict == 0, "pscore"].min())
        hi = min(PS.loc[PS.ai_flag_strict == 1, "pscore"].max(), PS.loc[PS.ai_flag_strict == 0, "pscore"].max())
        ai_ps = PS.loc[PS.ai_flag_strict == 1, "pscore"]
        ps_pct = float(((ai_ps < lo) | (ai_ps > hi)).mean())
        save(pd.DataFrame([{"N": len(PS), "N_AI": int(PS.ai_flag_strict.sum()), "support_low": lo, "support_high": hi, "pct_AI_outside_common_support": ps_pct,
                            "covariates": "year, sector, region, growth, ln revenue, margin (no outcome)"}]), root, "p4_common_support")
    else:
        save(pd.DataFrame([{"note": "propensity model not estimable (too few AI or non-AI with complete covariates)"}]), root, "p4_common_support")
    bal = []
    for c in ("revenue_growth", "ebitda_margin", "ln_revenue"):
        s_ = smd(A1[c], A0[c])
        bal.append({"covariate": c, "AI_mean": A1[c].mean(), "nonAI_mean": A0[c].mean(), "SMD": s_, "abs_SMD_ge_0.10": int(abs(s_) >= .10) if np.isfinite(s_) else np.nan})
    for c, v in (("public", 1), ("strategic", 1), ("post_genai", 1)):
        s_ = smd(A1[c].eq(v).astype(float) if c != "post_genai" else A1[c], A0[c].eq(v).astype(float) if c != "post_genai" else A0[c])
        bal.append({"covariate": c, "AI_mean": A1[c].mean(), "nonAI_mean": A0[c].mean(), "SMD": s_, "abs_SMD_ge_0.10": int(abs(s_) >= .10) if np.isfinite(s_) else np.nan})
    save(pd.DataFrame(bal), root, "p4_covariate_balance_pre_matching")

    # ---- 55-57 public premium, pre-deal ------------------------------------------------------------------------------------------------------------------------------------
    pr = []
    for c in ("premium_1d", "premium_1w", "premium_1m", "premium_vwap30", "predeal_ev_revenue", "ev_revenue"):
        a1, a0 = P.loc[P.ai_flag_strict == 1, c], P.loc[P.ai_flag_strict == 0, c]
        pr.append({"variable": c, "N_AI": int(a1.notna().sum()), "N_nonAI": int(a0.notna().sum()), "AI_median": a1.median(), "nonAI_median": a0.median(),
                   "unadjusted_median_difference": a1.median() - a0.median(), "mwu_p": mwu(a1, a0)["p"]})
    save(pd.DataFrame(pr), root, "p4_public_premium_and_predeal")
    cr = P[["premium_1d", "ev_revenue", "predeal_ev_revenue"]].dropna(subset=["premium_1d"])
    save(pd.DataFrame([{"pair": "premium_1d vs deal EV/Revenue", "spearman": stats.spearmanr(cr.dropna(subset=['ev_revenue']).premium_1d, cr.dropna(subset=['ev_revenue']).ev_revenue)[0] if cr["ev_revenue"].notna().sum() > 5 else np.nan},
                       {"pair": "premium_1d vs pre-deal EV/Revenue", "spearman": stats.spearmanr(cr.dropna(subset=['predeal_ev_revenue']).premium_1d, cr.dropna(subset=['predeal_ev_revenue']).predeal_ev_revenue)[0] if cr["predeal_ev_revenue"].notna().sum() > 5 else np.nan}]), root, "p4_premium_vs_multiple")

    # ---- 58-60 FE motivation, regime -------------------------------------------------------------------------------------------------------------------------------------------------------
    save(E.groupby("announce_year")["ev_revenue"].agg(["count", "median"]).reset_index(), root, "p4_year_median_multiple")
    save(E.groupby("sector")["ev_revenue"].agg(["count", "median"]).reset_index(), root, "p4_sector_median_multiple")
    reg = E.assign(period=np.where(E["_ann"] <= GENAI_DATE, "pre", "post")).groupby("period").agg(N=("deal_id", "count"), median_ev_revenue=("ev_revenue", "median")).reset_index()
    save(reg, root, "p4_genai_regime_deals")

    # ---- 61 market data alignment ------------------------------------------------------------------------------------------------------------------------------------------------------------
    mk = root / "data_raw" / "market_data.csv"
    if mk.exists():
        md = pd.read_csv(mk, parse_dates=["date"]).sort_values("date")
        mm = pd.merge_asof(a[["deal_id", "_ann"]].sort_values("_ann"), md, left_on="_ann", right_on="date", direction="backward")
        mm["market_data_lag_days"] = (mm["_ann"] - mm["date"]).dt.days
        mm.drop(columns=["_ann"]).to_csv(root / "data_clean" / "market_data_aligned.csv", index=False)
        save(pd.DataFrame([{"status": "aligned (backward, no look-ahead)", "max_lag_days": mm["market_data_lag_days"].max(), "N_unmatched": int(mm["date"].isna().sum())}]), root, "p4_market_alignment")
    else:
        save(pd.DataFrame([{"status": "data_raw/market_data.csv not supplied; market alignment not performed", "max_lag_days": np.nan, "N_unmatched": np.nan}]), root, "p4_market_alignment")

    # ---- 62-65 power, interactions, subsectors -----------------------------------------------------------------------------------------------------------------------------------------------------------
    nA, n0 = len(A1), len(A0)
    sd_ln = E["ln_ev_revenue"].std()
    mde_ln = mde(sd_ln, nA, n0)
    nP1, nP0 = int((P.ai_flag_strict == 1).sum()), int((P.ai_flag_strict == 0).sum())
    sd_p = P["premium_1d"].std()
    mde_p = mde(sd_p, nP1, nP0)
    save(pd.DataFrame([
        {"model": "EV/Revenue (log)", "N_AI": nA, "N_nonAI": n0, "outcome_sd": sd_ln, "MDE_log_points": mde_ln,
         "MDE_percent": np.exp(mde_ln) - 1 if np.isfinite(mde_ln) else np.nan, "note": "unconditional SD (conservative; covariates will reduce it); alpha .05, power .80"},
        {"model": "Takeover premium 1D", "N_AI": nP1, "N_nonAI": nP0, "outcome_sd": sd_p, "MDE_log_points": np.nan,
         "MDE_percent": mde_p, "note": "MDE in premium percentage points (fraction)"}]), root, "p4_power_mde")
    save(pd.DataFrame([{"N_AI_strict": nA, "reduced_power_flag_N_AI_lt_60": int(nA < 60), "note": "treatment definition is not broadened to improve power"}]), root, "p4_strict_ai_n")
    ic = []
    for lab, mkk in (("Strategic", E["strategic"] == 1), ("Non-strategic", E["strategic"] == 0), ("Post-GenAI", E["_ann"] > GENAI_DATE),
                     ("Pre-GenAI", E["_ann"] <= GENAI_DATE), ("Public", E["public"] == 1), ("Private", E["public"] == 0)):
        n1_, n0_ = int((mkk & (E.ai_flag_strict == 1)).sum()), int((mkk & (E.ai_flag_strict == 0)).sum())
        ic.append({"cell": f"AI x {lab}", "AI_N": n1_, "nonAI_N": n0_, "label": "STRONGLY EXPLORATORY (cell N<15)" if min(n1_, n0_) < 15 else "estimable"})
    save(pd.DataFrame(ic), root, "p4_interaction_cells")
    sg = E[E.ai_flag_strict == 1].groupby(E["ai_subsector_group"].fillna("unassigned")).size().rename("N_AI").reset_index()
    sg["formal_subsector_coefficient_allowed_N_ge_8"] = (sg["N_AI"] >= 8).astype(int)
    save(sg, root, "p4_subsector_power")

    # ---- 66 Tables 1-3, 77-79 -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    t1 = []
    for lab, df, c in (("EV (USD)", E, "enterprise_value"), ("Revenue (USD)", E, "ltm_revenue"), ("EV/Revenue", E, "ev_revenue"), ("Growth", E, "revenue_growth"),
                       ("EBITDA margin", E, "ebitda_margin"), ("EV/EBITDA", B, "ev_ebitda"), ("Premium 1D", P, "premium_1d")):
        a1, a0 = df.loc[df.ai_flag_strict == 1, c], df.loc[df.ai_flag_strict == 0, c]
        t1.append({"variable": lab, "N_AI": int(a1.notna().sum()), "N_nonAI": int(a0.notna().sum()), "AI_mean": a1.mean(), "AI_median": a1.median(),
                   "nonAI_mean": a0.mean(), "nonAI_median": a0.median(), "unadjusted_difference_of_means": a1.mean() - a0.mean()})
    save(pd.DataFrame(t1), root, "p4_table1_sample_characteristics")
    t2 = []
    for lab, f in (("Public %", lambda d_: d_["public"]), ("Strategic buyer %", lambda d_: d_["strategic"]), ("Post-GenAI %", lambda d_: (d_["_ann"] > GENAI_DATE).astype(float)),
                   ("US %", lambda d_: (d_["region"] == "US").astype(float)),
                   ("Software %", lambda d_: d_["sector"].astype(str).str.contains("Software", case=False).astype(float)),
                   ("Semiconductor %", lambda d_: d_["sector"].astype(str).str.contains("Semiconductor", case=False).astype(float)),
                   ("EBITDA positive %", lambda d_: (d_["ebitda_positive"] == 1).astype(float).where(d_["ltm_ebitda"].notna()))):
        t2.append({"characteristic": lab, "AI": f(A1).mean(), "non_AI": f(A0).mean()})
    save(pd.DataFrame(t2), root, "p4_table2_sample_composition")
    # model sample counts
    m1 = E[["ln_ev_revenue", "ai_flag_strict"]].dropna()
    m2d = E[["ln_ev_revenue", "ai_flag_strict", "revenue_growth", "ebitda_margin", "ln_revenue"]].dropna()
    m3 = m2d.join(E["announce_year"]).dropna()
    m4 = m3.join(E["sector"]).dropna()
    m5 = m4.join(E[["region", "public", "strategic"]]).dropna()
    rows = []
    for nm, mm_ in (("Unconditional", m1), ("Fundamentals", m2d), ("+ Year FE", m3), ("+ Sector FE", m4), ("Preferred (+ region, public, strategic)", m5)):
        rows.append({"model": nm, "N": len(mm_), "AI_N": int((mm_.ai_flag_strict == 1).sum()), "nonAI_N": int((mm_.ai_flag_strict == 0).sum())})
    save(pd.DataFrame(rows), root, "p4_model_sample_attrition")
    mi = E[["deal_id", "ai_flag_strict", "announce_year", "sector", "region", "revenue_growth", "ln_revenue", "ebitda_margin"]].copy()
    mi["year_bucket"] = pd.cut(mi["announce_year"], [2014, 2017, 2020, 2022, 2100], labels=["2015-17", "2018-20", "2021-22", "2023+"])
    for c, nm in (("revenue_growth", "growth_tercile"), ("ln_revenue", "size_tercile")):
        try:
            mi[nm] = pd.qcut(mi[c], 3, labels=["T1", "T2", "T3"])
        except ValueError:
            mi[nm] = np.nan
    mi.to_csv(root / "data_clean" / "matching_input_v1.csv", index=False)
    save(mi.isna().sum().rename("N_missing").reset_index().rename(columns={"index": "variable"}), root, "p4_matching_input_missingness")

    # ---- charts ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    make_charts(root, wf, E, B, P, yr, it, PS if "pscore" in PS else None, uni, core, synthetic)

    # ---- 80 freeze analysis dataset ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    final = a.drop(columns=["_ann"]).copy()
    for c in ("ai_flag_strict", "ai_flag_broad", "ai_intensity"):
        final[c] = final[c]
    cp = root / "data_clean" / "deals_analysis_v1.csv"
    tmp = root / "data_clean" / "_deals_analysis_tmp.csv"
    final.to_csv(tmp, index=False)
    newh = sha256(tmp)
    mf = root / "docs" / "ANALYSIS_V1_PHASE4.json"
    if mf.exists() and json.loads(mf.read_text())["sha256"] != newh:
        tmp.unlink()
        raise SystemExit("deals_analysis_v1.csv would change after freeze. Any correction must create ANALYSIS_V2 with a deviations_log entry.")
    tmp.replace(cp)
    final.loc[:, :].assign(**{"_note": "winsorised growth/margin (1/99) on EV/Revenue sample"}).drop(columns=["_note"]).to_csv(root / "data_clean" / "analysis_winsor_1_99.csv", index=False)
    final.assign(ev_revenue=final["ev_revenue_w"], ln_ev_revenue=final["ln_ev_revenue_w"]).to_csv(root / "data_clean" / "analysis_outcome_winsor.csv", index=False)
    final[final["trim_p1_p99_exclude"] == 0].to_csv(root / "data_clean" / "analysis_trimmed.csv", index=False)
    if not mf.exists():
        mf.write_text(json.dumps({"DATA_VERSION": DATA_VERSION, "file": cp.name, "sha256": newh, "rows": int(len(final)), "columns": int(final.shape[1]),
                                  "created": str(date.today()), "treatment_version": man["version"], "treatment_sha256": man["frozen_file_sha256"],
                                  "raw_snapshot_sha256": json.loads(snap_man.read_text())["sha256"],
                                  "rule": "Any correction creates ANALYSIS_V2 and a deviations_log entry"}, indent=2))
    missing = [c for c in REQUIRED_COLS if c not in final.columns]
    assert not missing, missing

    write_report(root, wf, chk, synthetic, man)
    print(f"Phase 4 complete. EV/Revenue N={len(E)} (AI {nA}); EV/EBITDA N={len(B)}; premium N={len(P)}. Data version {DATA_VERSION}.")
    return 0


# ------------------------------------------------------------------------------------------------ charts & report
def make_charts(root, wf, E, B, P, yr, it, PS, uni, core, synthetic):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ch = root / "results" / "charts"
    tag = "SYNTHETIC DATA - NOT FINDINGS" if synthetic else "UNADJUSTED / DESCRIPTIVE"
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

    def fin(fig, ax, name, title):
        ax.set_title(f"{title}\n{tag}", fontsize=9, loc="left")
        fig.tight_layout()
        fig.savefig(ch / f"{name}.png", dpi=130)
        plt.close(fig)
    A1, A0 = E[E.ai_flag_strict == 1], E[E.ai_flag_strict == 0]
    f, ax = plt.subplots(figsize=(7, 4))
    w = wf[wf.outcome == "EV/Revenue"]
    ax.barh(range(len(w))[::-1], w["total_N"], color=GREY)
    ax.barh(range(len(w))[::-1], w["strict_AI_N"], color=BLUE)
    ax.set_yticks(range(len(w))[::-1]); ax.set_yticklabels(w["step"].str[:40])
    fin(f, ax, "chart_01_waterfall", "Sample waterfall, EV/Revenue (blue = strict AI)")
    f, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(yr["announce_year"] - .2, yr["N_AI"].fillna(0), .4, color=BLUE, label="AI"); ax.bar(yr["announce_year"] + .2, yr["N_nonAI"].fillna(0), .4, color=GREY, label="Non-AI"); ax.legend(frameon=False)
    fin(f, ax, "chart_02_deals_by_year", "Deals by year")
    f, ax = plt.subplots(figsize=(6, 3.5))
    if len(E):
        bins = np.logspace(np.log10(max(E.ev_revenue.min(), .01)), np.log10(E.ev_revenue.max()), 25)
        ax.hist(A0.ev_revenue, bins=bins, alpha=.6, color=GREY, label="Non-AI"); ax.hist(A1.ev_revenue, bins=bins, alpha=.7, color=BLUE, label="AI"); ax.set_xscale("log"); ax.legend(frameon=False)
    fin(f, ax, "chart_03_evrev_hist", "EV/Revenue (log axis)")
    f, ax = plt.subplots(figsize=(6, 3.5))
    ax.boxplot([A0.ln_ev_revenue.dropna(), A1.ln_ev_revenue.dropna()], tick_labels=["Non-AI", "AI"]) if len(E) else None
    fin(f, ax, "chart_04_ln_evrev_box", "ln(EV/Revenue) by group")
    f, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(yr["announce_year"], yr["median_ev_revenue_AI"], color=BLUE, marker="o", label="AI") if "median_ev_revenue_AI" in yr else None
    ax.plot(yr["announce_year"], yr["median_ev_revenue_nonAI"], color=GREY, marker="o", label="Non-AI") if "median_ev_revenue_nonAI" in yr else None
    ax.legend(frameon=False); fin(f, ax, "chart_05_median_by_year", "Median EV/Revenue by year")
    for nm, xc, ttl in (("chart_06_growth_scatter", "revenue_growth", "Growth vs ln(EV/Revenue)"), ("chart_06b_size_scatter", "ln_revenue", "ln revenue vs ln(EV/Revenue)"),
                        ("chart_06c_margin_scatter", "ebitda_margin", "EBITDA margin vs ln(EV/Revenue)")):
        f, ax = plt.subplots(figsize=(6, 4))
        for df_, c, lb in ((A0, GREY, "Non-AI"), (A1, BLUE, "AI")):
            d_ = df_[[xc, "ln_ev_revenue"]].dropna()
            ax.scatter(d_[xc], d_["ln_ev_revenue"], s=12, color=c, alpha=.6, label=lb)
            if len(d_) > 5:
                b = np.polyfit(d_[xc], d_["ln_ev_revenue"], 1); xs = np.linspace(d_[xc].min(), d_[xc].max(), 20); ax.plot(xs, np.polyval(b, xs), color=c)
        ax.legend(frameon=False); ax.set_xlabel(xc); ax.set_ylabel("ln(EV/Revenue)")
        fin(f, ax, nm, ttl)
    f, ax = plt.subplots(figsize=(5, 3.5))
    ax.bar(it["ai_intensity"].astype(str), it["median_ev_revenue"], color=BLUE); ax.set_xlabel("AI intensity")
    fin(f, ax, "chart_07_intensity", "Median EV/Revenue by AI intensity")
    f, ax = plt.subplots(figsize=(5, 3.5))
    if len(P):
        ax.boxplot([P[P.ai_flag_strict == 0].premium_1d.dropna(), P[P.ai_flag_strict == 1].premium_1d.dropna()], tick_labels=["Non-AI", "AI"])
    fin(f, ax, "chart_08_premium", "1-day takeover premium (public targets)")
    f, ax = plt.subplots(figsize=(5, 3.5))
    if len(P):
        ax.boxplot([P[P.ai_flag_strict == 0].predeal_ev_revenue.dropna(), P[P.ai_flag_strict == 1].predeal_ev_revenue.dropna()], tick_labels=["Non-AI", "AI"]); ax.set_yscale("log")
    fin(f, ax, "chart_09_predeal", "Pre-deal EV/Revenue (public targets, log axis)")
    A1_, A0_ = E[E.ai_flag_strict == 1], E[E.ai_flag_strict == 0]
    f, ax = plt.subplots(figsize=(5, 3.2))
    sm = [(c, smd(A1_[c], A0_[c])) for c in ("revenue_growth", "ebitda_margin", "ln_revenue")]
    ax.barh([c for c, _ in sm], [v for _, v in sm], color=BLUE); ax.axvline(.1, color="k", lw=.5); ax.axvline(-.1, color="k", lw=.5)
    fin(f, ax, "chart_10_smd", "Standardized mean differences (AI minus non-AI)")
    f, ax = plt.subplots(figsize=(6, 3))
    mat = pd.DataFrame({lab: [uni.loc[uni.ai_flag_strict == g, c].isna().mean() for g in (1, 0)] for lab, c in core.items()}, index=["AI", "Non-AI"])
    im = ax.imshow(mat.to_numpy(float), cmap="Blues", vmin=0, vmax=1); ax.set_xticks(range(mat.shape[1])); ax.set_xticklabels(mat.columns, rotation=30, ha="right"); ax.set_yticks([0, 1]); ax.set_yticklabels(mat.index)
    f.colorbar(im, ax=ax, label="share missing")
    fin(f, ax, "chart_11_missingness", "Missingness by group")
    f, ax = plt.subplots(figsize=(6, 3.5))
    if PS is not None:
        ax.hist(PS.loc[PS.ai_flag_strict == 0, "pscore"], bins=20, alpha=.6, color=GREY, label="Non-AI"); ax.hist(PS.loc[PS.ai_flag_strict == 1, "pscore"], bins=20, alpha=.7, color=BLUE, label="AI"); ax.legend(frameon=False)
    fin(f, ax, "chart_12_propensity", "Propensity-score overlap (no outcome used)")


def write_report(root, wf, chk, synthetic, man):
    def tbl(name):
        p = root / "results" / f"{name}.csv"
        return p.read_text() if p.exists() else ""
    hdr = ("# Phase 4 report - SYNTHETIC DATA, NOT FINDINGS\n\nThis run used synthetic test data. Nothing below is an empirical result.\n\n" if synthetic
           else "# Phase 4 report - descriptive and diagnostic (UNADJUSTED)\n\nNo number below is an 'AI premium'. All AI vs non-AI differences are unadjusted.\n\n")
    parts = [hdr, f"Data version: {DATA_VERSION}. Treatment version: {man['version']}.\n"]
    for title, name in (("A. Sample waterfall", "p4_sample_waterfall"), ("Waterfall consistency with Phase 2", "p4_waterfall_consistency"), ("C. EV reconciliation", "p4_ev_reconciliation_summary"),
                        ("D. Staleness", "p4_staleness_by_ai"), ("H. Missingness", "p4_missingness"), ("Missingness tests", "p4_missingness_tests"),
                        ("K. Raw comparison (UNADJUSTED)", "p4_raw_comparison_unadjusted"), ("X. Univariate tests (descriptive)", "p4_univariate_tests"),
                        ("T. Intensity", "p4_intensity_descriptives"), ("U. Pre/post GenAI", "p4_pre_post_genai"), ("Z. VIF", "p4_vif"),
                        ("AB. Common support", "p4_common_support"), ("AC. Balance", "p4_covariate_balance_pre_matching"), ("AD. Power / MDE", "p4_power_mde"),
                        ("AE. Model sample sizes", "p4_model_sample_attrition"), ("Interaction cells", "p4_interaction_cells")):
        parts.append(f"## {title}\n\n```\n{tbl(name)}```\n")
    (root / "results" / "phase4_report.md").write_text("\n".join(parts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None)
    sys.exit(main(U.project_root(ap.parse_args().root)))
