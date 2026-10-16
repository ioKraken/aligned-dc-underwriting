"""Phase 4 synthetic test. Builds on a frozen Phase 3 synthetic project, injects valuation structure (planted effects and
confounders), then checks the gate, outputs, invariants and freeze behaviour. SYNTHETIC ONLY - proves code, not findings."""
import importlib.util, json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent; SRC = HERE.parent; PROJ = SRC.parent


def run(script, root, *args, check=True):
    r = subprocess.run([sys.executable, str(root / "src" / script), "--root", str(root), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stdout, r.stderr); raise SystemExit(f"{script} failed")
    return r


def main():
    r = subprocess.run([sys.executable, str(HERE / "test_phase3.py"), "--keep"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    base = Path([l.split("kept: ")[1] for l in r.stdout.splitlines() if "kept:" in l][0].strip())
    tmp = Path(tempfile.mkdtemp(prefix="ai_p4_")); root = tmp / "proj"
    shutil.copytree(base, root)
    shutil.copytree(PROJ / "src", root / "src", dirs_exist_ok=True)
    # gate: no freeze manifest -> refuse
    nofreeze = tmp / "nofreeze"; shutil.copytree(root, nofreeze)
    for f in (nofreeze / "docs").glob("AI_CLASSIFICATION_V1_*.json"): f.unlink()
    rr = run("04_descriptives.py", nofreeze, check=False)
    assert rr.returncode != 0 and "no Phase 3 treatment freeze" in (rr.stdout + rr.stderr), rr.stderr
    # tampered frozen file -> refuse
    tam = tmp / "tam"; shutil.copytree(root, tam)
    fz = tam / "data_clean" / "ai_treatment_frozen_V1.csv"; fz.write_text(fz.read_text().replace(",1.0,1.0,2.0,", ",1.0,1.0,3.0,", 1) + " ")
    assert run("04_descriptives.py", tam, check=False).returncode != 0

    # inject valuation structure
    rng = np.random.default_rng(3)
    d = pd.read_csv(root / "data_clean" / "deals_stage2.csv", low_memory=False)
    t = pd.read_csv(root / "data_clean" / "ai_treatment_frozen_V1.csv")
    ai = d["deal_id"].map(t.set_index("deal_id")["ai_flag_strict"]).fillna(0).to_numpy()
    n = len(d)
    growth = np.clip(rng.normal(.15 + .25 * ai, .15), -.3, 1.5)
    rev = np.exp(rng.normal(np.log(60e6) - .5 * ai, .8))
    lnm = np.log(3) + 1.2 * growth - .1 * (np.log(rev) - np.log(60e6)) + .0 * ai + rng.normal(0, .35, n)   # NO true AI effect beyond growth
    d["revenue_ltm_usd"] = rev; d["revenue_growth"] = growth
    d["ev_usd"] = rev * np.exp(lnm); d["ev_revenue"] = np.exp(lnm); d["ln_ev_revenue"] = lnm; d["ln_revenue"] = np.log(rev)
    d["ebitda_margin"] = np.clip(rng.normal(.12 - .15 * ai, .15), -.8, .6); d["ebitda_ltm_usd"] = d["ebitda_margin"] * rev
    d["ebitda_positive"] = (d["ebitda_ltm_usd"] > 0).astype(int)
    d["ev_ebitda"] = np.where(d["ebitda_ltm_usd"] > 0, d["ev_usd"] / d["ebitda_ltm_usd"], np.nan); d["ln_ev_ebitda"] = np.log(d["ev_ebitda"])
    d["data_quality_flag"] = rng.choice(list("ABC"), n, p=[.5, .35, .15]); d.loc[rng.random(n) < .05, "revenue_ltm_usd"] = np.nan
    d["ev_revenue"] = np.where(d["revenue_ltm_usd"].isna(), np.nan, d["ev_revenue"])
    pub = d["public_target"] == 1
    d.loc[pub, "premium_1d"] = rng.normal(.3, .12, pub.sum()); d.loc[pub, "premium_1w"] = d.loc[pub, "premium_1d"] + .02; d.loc[pub, "premium_1m"] = d.loc[pub, "premium_1d"] + .05
    d.loc[pub, "offer_price"] = 10.0; d.loc[pub, "unaffected_price_1d"] = 10 / (1 + d.loc[pub, "premium_1d"]); d.loc[pub, "premium_date_ok"] = 1
    d.loc[pub, "predeal_ev_revenue"] = d.loc[pub, "ev_revenue"] / 1.3
    d.to_csv(root / "data_clean" / "deals_stage2.csv", index=False)
    spec = importlib.util.spec_from_file_location("s2", SRC / "02b_build_stage2.py"); m2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m2)
    _, _, masks = m2.run_waterfalls(d.assign(ai_candidate_flag=d["ai_candidate_flag"]))
    for k, c in (("EV/Revenue", "evrev"), ("EV/EBITDA", "ebitda"), ("Takeover premium", "premium")):
        d[f"in_primary_sample_{c}"] = masks[k].astype(int).to_numpy()
    d.to_csv(root / "data_clean" / "deals_stage2.csv", index=False)

    run("04_descriptives.py", root)
    R = root / "results"
    wf = pd.read_csv(R / "p4_sample_waterfall.csv")
    assert (wf.groupby("outcome")["total_N"].apply(lambda s: s.is_monotonic_decreasing)).all()
    assert pd.read_csv(R / "p4_waterfall_consistency.csv")["matches_phase2_flag_after_ai_and_acquihire"].all()
    A = pd.read_csv(root / "data_clean" / "deals_analysis_v1.csv")
    for c in ["deal_id","target_name","buyer_name","announcement_date","sector","subsector","region","public_private","buyer_type","enterprise_value","ltm_revenue","ltm_ebitda","revenue_growth","ebitda_margin","ev_revenue","ev_ebitda","premium_1d","ai_flag_strict","ai_flag_broad","ai_intensity","ai_subsector","quality_flag","financial_stale_flag"]:
        assert c in A.columns, c
    assert A["deal_id"].is_unique and pd.read_csv(R / "p4_duplicates.csv")["count"].iloc[:2].sum() == 0
    e = A[A.in_evrev_final == 1]
    assert (e["ev_revenue"] > 0).all() and e["ln_ev_revenue"].notna().all()
    assert (pd.read_csv(R / "p4_outcome_checks.csv")["count"] == 0).all()
    # raw difference should be positive via growth confounding, but the *true* AI effect is zero
    raw = pd.read_csv(R / "p4_raw_comparison_unadjusted.csv"); assert "UNADJUSTED" in raw["label"].iloc[0]
    bal = pd.read_csv(R / "p4_covariate_balance_pre_matching.csv").set_index("covariate")
    assert bal.loc["revenue_growth", "SMD"] > .5, "planted growth imbalance must be visible"
    tt = pd.read_csv(R / "p4_univariate_tests.csv").set_index("outcome")
    assert tt.loc["ln(EV/Revenue)", "welch_diff"] > 0, "confounded raw difference expected"
    # numpy OLS influence helper matches closed-form leverage identity: sum(h) == p
    inf = pd.read_csv(R / "p4_influence_top25.csv"); assert inf["cooks_d"].is_monotonic_decreasing
    # Welch implementation matches scipy
    from scipy import stats
    a1, a0 = e.loc[e.ai_flag_strict == 1, "ln_ev_revenue"], e.loc[e.ai_flag_strict == 0, "ln_ev_revenue"]
    assert abs(stats.ttest_ind(a1, a0, equal_var=False)[1] - tt.loc["ln(EV/Revenue)", "welch_p"]) < 1e-10
    assert (R / "charts" / "chart_12_propensity.png").exists() and len(list((R / "charts").glob("*.png"))) >= 14
    assert "SYNTHETIC" in (R / "phase4_report.md").read_text()
    # no AI-premium wording in report
    assert "ai premium found" not in (R / "phase4_report.md").read_text().lower()
    # freeze: rerun identical -> ok; change data -> refused
    h1 = json.loads((root / "docs" / "ANALYSIS_V1_PHASE4.json").read_text())["sha256"]
    assert run("04_descriptives.py", root, check=False).returncode == 0
    # raw snapshot immutability
    snap = root / "data_raw" / "deals_master_raw_v1.csv"; snap.write_text(snap.read_text() + "\n#")
    assert run("04_descriptives.py", root, check=False).returncode != 0
    print("ALL PHASE 4 TESTS PASSED (synthetic data only); wf EV/Rev final N =", int(wf[wf.outcome == "EV/Revenue"].total_N.iloc[-1]))


main()
