"""Phases 5-7 synthetic test. Builds standalone frozen Phase 4 fixtures (no Phase 3 needed): (a) planted AI effect, (b) pure growth confound with NO AI effect.
Checks estimator maths (OLS/HC3, Gelbach additivity, placebo), gates, classification behaviour, freeze rules and Phase 7 outputs. SYNTHETIC ONLY."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent; SRC = HERE.parent; sys.path.insert(0, str(SRC))
import p5_common as C


def make(root: Path, effect: float, seed: int, n=700, confound=True, universe="synthetic_test"):
    rng = np.random.default_rng(seed); (root / "data_clean").mkdir(parents=True); (root / "docs").mkdir(); (root / "results").mkdir(); (root / "data_raw").mkdir()
    ai = (rng.random(n) < .25).astype(int); yr = rng.integers(2015, 2026, n); post = (yr >= 2023).astype(int)
    sector = rng.choice(["AppSoft", "InfraSoft", "Semis", "Cyber", "Internet"], n); region = rng.choice(["US", "EU", "UK"], n, p=[.6, .25, .15])
    pub = (rng.random(n) < .4).astype(int); strat = (rng.random(n) < .7).astype(int)
    growth = np.clip(rng.normal(.15 + (.2 * ai if confound else 0), .15), -.3, 1.5); marg = np.clip(rng.normal(.1 - (.12 * ai if confound else 0), .15), -.8, .6)
    lnrev = rng.normal(np.log(80e6) - (.4 * ai if confound else 0), .8)
    lnm = np.log(3) + 1.1 * growth + .5 * marg - .08 * (lnrev - np.log(80e6)) + .1 * (sector == "Semis") + .03 * (yr - 2020) + effect * ai + rng.normal(0, .3, n)
    rev = np.exp(lnrev); evrev = np.exp(lnm); prem = np.clip(rng.normal(.3, .1, n), .02, .9)
    d = pd.DataFrame({"deal_id": [f"D{i}" for i in range(n)], "target_name": [f"T{i}" for i in range(n)], "buyer_name": rng.choice([f"B{i}" for i in range(25)], n),
                      "announcement_date": [f"{y}-06-30" for y in yr], "sector": sector, "subsector": "x", "region": region, "public_private": np.where(pub, "public", "private"),
                      "buyer_type": np.where(strat, "strategic", "sponsor"), "enterprise_value": rev * evrev, "ltm_revenue": rev, "ltm_ebitda": marg * rev, "revenue_growth": growth, "ebitda_margin": marg,
                      "ev_revenue": evrev, "ev_ebitda": np.nan, "premium_1d": np.where(pub, prem, np.nan), "ai_flag_strict": ai, "ai_flag_broad": np.maximum(ai, (rng.random(n) < .1).astype(int)),
                      "ai_intensity": np.where(ai, rng.choice([1, 2, 3], n, p=[.4, .4, .2]), 0), "ai_subsector": np.where(ai, rng.integers(1, 10, n), np.nan), "quality_flag": rng.choice(list("ABC"), n, p=[.5, .35, .15]),
                      "financial_stale_flag": 0, "announce_year": yr, "post_genai": post, "public_target": pub, "public": pub, "strategic": strat, "ln_revenue": lnrev, "ln_ev_revenue": lnm,
                      "predeal_ev_revenue": np.where(pub, evrev / 1.3, np.nan), "in_evrev_final": 1, "in_premium_final": pub, "in_ebitda_final": 0, "contested": (rng.random(n) < .1).astype(int), "cross_border": (rng.random(n) < .2).astype(int)})
    d["ai_subsector_group"] = d["ai_subsector"].map({1: "Core AI Platform / Infrastructure", 2: "Core AI Platform / Infrastructure", 8: "Core AI Platform / Infrastructure", 3: "AI Applications", 4: "AI Applications", 5: "AI Applications", 9: "AI Applications", 6: "Specialized AI", 7: "Specialized AI"})
    d["trim_p1_p99_exclude"] = 0; d["ln_ev_revenue_w"] = d["ln_ev_revenue"]; d["ev_revenue_w"] = d["ev_revenue"]
    d.to_csv(root / "data_clean" / "deals_analysis_v1.csv", index=False); d.to_csv(root / "data_clean" / "analysis_outcome_winsor.csv", index=False); d.to_csv(root / "data_clean" / "analysis_trimmed.csv", index=False)
    pd.DataFrame({"source_universe": [universe]}).to_csv(root / "data_clean" / "deals_stage2.csv", index=False)
    (root / "docs" / "ANALYSIS_V1_PHASE4.json").write_text(json.dumps({"file": "deals_analysis_v1.csv", "sha256": C.sha256(root / "data_clean" / "deals_analysis_v1.csv")}))


def run(script, root, *a, check=True):
    r = subprocess.run([sys.executable, str(SRC / script), "--root", str(root), *a], capture_output=True, text=True)
    if check and r.returncode: print(r.stdout, r.stderr); raise SystemExit(f"{script} failed")
    return r


def pipeline(root, extra=()):
    run("05_regressions.py", root, "--boot", "200"); run("06_matching.py", root, "--boot", "60"); return run("07_robustness.py", root, "--boot", "300", "--placebo", "1000", *extra)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="ai_p567_"))
    # ---- estimator maths ----
    rng = np.random.default_rng(1); n = 300; X = np.column_stack([np.ones(n), rng.normal(size=(n, 2))]); y = X @ [1, .5, -.3] + rng.normal(0, 1 + abs(X[:, 1]), n)
    o = C.ols(y, X); b = np.linalg.solve(X.T @ X, X.T @ y); assert np.allclose(o["b"], b)
    h = np.diag(X @ np.linalg.inv(X.T @ X) @ X.T); e = y - X @ b; V = np.linalg.inv(X.T @ X) @ (X.T * (e ** 2 / (1 - h) ** 2)) @ X @ np.linalg.inv(X.T @ X)
    assert np.allclose(o["se"], np.sqrt(np.diag(V))), "HC3 mismatch"; assert abs(h.sum() - 3) < 1e-8
    # ---- scenario A: planted effect ----
    A = tmp / "A"; make(A, .4, 11)
    D = pd.read_csv(A / "data_clean" / "deals_analysis_v1.csv"); t, s = C.gelbach(D, "ai_flag_strict"); assert s["max_abs_gap"] < 1e-9, "Gelbach must be exactly additive"
    pl = C.placebo(D, "ai_flag_strict", C.ORDER, 1000); assert pl["p_one_sided"] < .01 and abs(pl["null_mean"]) < .05
    # gates
    r = run("07_robustness.py", A, check=False); assert r.returncode and "REFUSED" in r.stdout + r.stderr
    r = run("08_interpretation.py", A, check=False); assert r.returncode and "REFUSED" in r.stdout + r.stderr
    r = run("06_matching.py", A, check=False); assert r.returncode and "REFUSED" in r.stdout + r.stderr
    pipeline(A); cA = json.loads((A / "docs" / "PHASE6_CLASSIFICATION_V1.json").read_text()); assert cA["synthetic"]
    prog = pd.read_csv(A / "results" / "p5_progressive_models.csv"); assert abs(prog.beta_AI.iloc[-1] - .4) < .12, prog.beta_AI.tolist()
    assert prog.beta_AI.iloc[0] > prog.beta_AI.iloc[-1], "raw (confounded) must exceed adjusted"
    assert cA["classification"] in ("Robust AI Acquisition Premium", "Suggestive AI Premium"), cA["classification"]
    pd.read_csv(A / "results" / "p6_robustness_12_checks.csv").shape[0] == 12
    # idempotent rerun and Phase 7
    pipeline(A); r = run("08_interpretation.py", A); print(r.stdout.strip())
    for f in ("p7_table1_raw_to_adjusted.csv", "p7_table2_gelbach.csv", "p7_table3_ai_intensity.csv", "p7_tables5_6_7_heterogeneity.csv", "p7_table8_predeal_premium.csv", "p7_residual_cases.csv", "p7_relative_multiple.csv", "Phase7_Economic_Interpretation.md"):
        assert (A / "results" / f).exists(), f
    st = pd.read_csv(A / "results" / "p7_section_status.csv"); assert not st["status"].str.startswith("ERROR").any(), st[st.status.str.startswith("ERROR")]
    md = (A / "results" / "Phase7_Economic_Interpretation.md").read_text(); assert "SYNTHETIC DATA" in md and cA["classification"] in md
    assert len(list((A / "results" / "charts").glob("p7_chart_*.png"))) >= 8
    fc = json.loads((A / "docs" / "FINAL_EMPIRICAL_CONCLUSION_V1.json").read_text()); assert fc["phase6_classification"] == cA["classification"]
    low = md.lower(); assert "causes" not in low.replace("did ai cause", "")
    # tampering analysis file after freeze -> refused
    T = tmp / "T"; shutil.copytree(A, T); p = T / "data_clean" / "deals_analysis_v1.csv"; p.write_text(p.read_text() + "\n")
    assert run("08_interpretation.py", T, check=False).returncode != 0
    # ---- scenario B: pure growth confound, NO AI effect ----
    B = tmp / "B"; make(B, 0.0, 22); pipeline(B); cB = json.loads((B / "docs" / "PHASE6_CLASSIFICATION_V1.json").read_text())
    pb = pd.read_csv(B / "results" / "p5_progressive_models.csv")
    assert pb.beta_AI.iloc[0] > .15 and abs(pb.beta_AI.iloc[-1]) < .12, pb.beta_AI.tolist()
    assert cB["classification"] != "Robust AI Acquisition Premium", cB["classification"]; print("scenario B ->", cB["classification"], "|", cB["reason"])
    # ---- scenario C: pilot-size sample -> NOT ASSESSABLE, no empirical claims ----
    Cc = tmp / "C"; make(Cc, .4, 5, n=40); pipeline(Cc); cC = json.loads((Cc / "docs" / "PHASE6_CLASSIFICATION_V1.json").read_text()); assert cC["classification"] == "NOT ASSESSABLE", cC
    run("08_interpretation.py", Cc); assert not (Cc / "results" / "p7_table1_raw_to_adjusted.csv").exists()
    assert "Not assessable" in json.loads((Cc / "docs" / "FINAL_EMPIRICAL_CONCLUSION_V1.json").read_text())["technical_conclusion"]
    print("ALL PHASE 5-7 TESTS PASSED (synthetic data only). A ->", cA["classification"], "| B ->", cB["classification"], "| C ->", cC["classification"])


main()
