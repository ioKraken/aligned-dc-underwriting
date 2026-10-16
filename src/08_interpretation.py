"""Phase 7 - economic interpretation of the FROZEN Phase 6 classification. Estimates nothing new beyond the pre-listed decompositions;
never changes the classification; refuses without Phase 4/5/6 freezes. Association language only; mechanisms are labelled HYPOTHESIS.
Outputs results/p7_*.csv, results/charts/p7_chart_*.png, results/Phase7_Economic_Interpretation.md, docs/FINAL_EMPIRICAL_CONCLUSION_V1.json."""
from __future__ import annotations
import argparse, json, traceback
from datetime import date
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
import p5_common as C

AI = "ai_flag_strict"
STATUS: list[dict] = []


def sec(name):
    def deco(fn):
        def w(*a, **k):
            try:
                r = fn(*a, **k); STATUS.append({"section": name, "status": "done"}); return r
            except SkipSection as e:
                STATUS.append({"section": name, "status": f"skipped: {e}"})
            except Exception as e:
                STATUS.append({"section": name, "status": f"ERROR: {type(e).__name__}: {str(e)[:80]}"}); traceback.print_exc()
        return w
    return deco


class SkipSection(Exception):
    pass


def need(cond, msg):
    if not cond: raise SkipSection(msg)


def combo(r, i, j):
    v = r["V"]; b = r["b"][i] + r["b"][j]; se = float(np.sqrt(max(v[i, i] + v[j, j] + 2 * v[i, j], 0)))
    return b, b - 1.96 * se, b + 1.96 * se


def strength(lo, hi, beta, n_ai):
    if n_ai < 8 or not np.isfinite(lo): return "Unsupported (too few observations)"
    if lo > 0 and beta >= C.THRESH: return "Strong" if lo > 0.05 else "Moderate"
    if lo > 0: return "Moderate"
    if beta > 0: return "Weak"
    return "Unsupported"


def main(root: Path) -> int:
    res = root / "results"; ch = res / "charts"; ch.mkdir(parents=True, exist_ok=True)
    cp = root / "docs" / "PHASE6_CLASSIFICATION_V1.json"
    if not cp.exists(): raise SystemExit("PHASE 7 REFUSED: docs/PHASE6_CLASSIFICATION_V1.json missing. Phase 6 must be run and frozen first.")
    cl = json.loads(cp.read_text()); man = C.load_frozen(root, "ANALYSIS_V1_PHASE4.json", "PHASE 7")
    if cl["analysis_sha256"] != man["sha256"]: raise SystemExit("PHASE 7 REFUSED: Phase 6 classification was produced on a different analysis file.")
    label = cl["classification"]; synthetic, pilot = cl["synthetic"], cl["pilot"]
    banner = "SYNTHETIC DATA - NOT FINDINGS. Code demonstration only." if synthetic else "PILOT / NON-SYSTEMATIC SAMPLE - NOT FINDINGS." if pilot else ""
    A = pd.read_csv(root / "data_clean" / man["file"], low_memory=False)
    raw_snap = root / "data_raw" / "deals_master_raw_v1.csv"
    for c in ("contested", "cross_border"):
        if c not in A.columns and raw_snap.exists():
            rr = pd.read_csv(raw_snap, usecols=lambda k: k in ("deal_id", c), low_memory=False)
            if c in rr.columns: A = A.merge(rr, on="deal_id", how="left")
    E = A[A["in_evrev_final"] == 1]; D = C.complete(E, AI).reset_index(drop=True); nA = int((D[AI] == 1).sum())
    assessable = cl["status"] == "ASSESSABLE"
    doc: dict[str, str] = {}
    M: dict = {}
    if assessable:
        pref = C.fit(D, AI, C.ORDER); raw = C.fit(D, AI, []); M.update(pref=pref, raw=raw)

        @sec("B. Raw vs adjusted bridge (Table 1) + survival ratio")
        def bridge():
            specs = {"Raw (AI only)": [], "+ Growth": ["growth"], "+ Fundamentals (growth, margin, size)": C.MODELS["(2) + growth, margin, size"],
                     "+ Year FE": C.MODELS["(3) + year FE"], "+ Sector FE": C.MODELS["(4) + sector FE"], "Preferred (+region, public, strategic)": C.ORDER}
            rows = [{"measure": "Raw median EV/Revenue gap (AI minus non-AI, x)", "gap": D.loc[D[AI] == 1, "ev_revenue"].median() - D.loc[D[AI] == 0, "ev_revenue"].median()}]
            for k, v in specs.items():
                r = C.fit(D, AI, v); rows.append({"measure": k, "gap": r["beta"], "ci_lo": r["lo_ai"], "ci_hi": r["hi_ai"], "pct": C.pct(r["beta"]), "N": r["n"]})
            t = pd.DataFrame(rows); t["survival_ratio"] = [np.nan] + [x / raw["beta"] if raw["beta"] > 0 and x > 0 else np.nan for x in t["gap"][1:]]
            t.to_csv(res / "p7_table1_raw_to_adjusted.csv", index=False); M["bridge"] = t
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(8, 4)); z = t.iloc[1:]
            a.errorbar(range(len(z)), z["gap"], yerr=[z["gap"] - z["ci_lo"], z["ci_hi"] - z["gap"]], fmt="o-", capsize=3); a.axhline(0, c="grey"); a.axhline(C.THRESH, c="red", ls=":")
            a.set_xticks(range(len(z))); a.set_xticklabels([s.split(" (")[0] for s in z["measure"]], rotation=25, ha="right", fontsize=7); a.set_ylabel("AI coefficient (log points)")
            a.set_title("Chart 1/2: raw vs adjusted AI gap - coefficient attenuation path\n" + banner, fontsize=8); f.tight_layout(); f.savefig(ch / "p7_chart_01_02_attenuation.png", dpi=120); plt.close(f)
        bridge()

        @sec("U. Gelbach decomposition (Table 2 / Chart 3)")
        def gel():
            t, s = C.gelbach(D, AI); t.to_csv(res / "p7_table2_gelbach.csv", index=False); pd.DataFrame([s]).to_csv(res / "p7_gelbach_check.csv", index=False); M["gel"], M["gelsum"] = t, s
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(7, 3.6)); a.barh(t["group"], t["contribution"]); a.axvline(0, c="grey"); a.set_xlabel("contribution to (raw beta - preferred beta)")
            a.set_title("Chart 3: control-group decomposition (association, not mediation)\n" + banner, fontsize=8); f.tight_layout(); f.savefig(ch / "p7_chart_03_gelbach.png", dpi=120); plt.close(f)
        gel()

        @sec("U. Oaxaca-Blinder (explained vs unexplained; unexplained is NOT 'AI value')")
        def oax():
            G = C.groups(D, AI); X = pd.concat([pd.Series(1.0, index=D.index, name="const")] + [G[k] for k in C.ORDER], axis=1)
            n0 = D[AI] == 0; need(n0.sum() > X.shape[1] and (D[AI] == 1).sum() >= 8, "insufficient observations")
            b0 = np.linalg.pinv(X[n0].to_numpy().T @ X[n0].to_numpy()) @ X[n0].to_numpy().T @ D.loc[n0, C.Y].to_numpy()
            dx = X[~n0].mean() - X[n0].mean(); expl = float(dx.to_numpy() @ b0); tot = float(D.loc[~n0, C.Y].mean() - D.loc[n0, C.Y].mean())
            pd.DataFrame([{"total_gap_log": tot, "explained": expl, "unexplained": tot - expl, "explained_share": expl / tot if tot else np.nan,
                           "note": "reference = non-AI coefficients; unexplained includes omitted variables, selection, model error"}]).to_csv(res / "p7_oaxaca.csv", index=False)
        oax()

        @sec("D/E. Profitability and size profile")
        def prof():
            rows = []
            for c in ["revenue_growth", "ebitda_margin", "ltm_revenue", "ev_revenue"]:
                a, b = D.loc[D[AI] == 1, c].dropna(), D.loc[D[AI] == 0, c].dropna(); p = stats.mannwhitneyu(a, b).pvalue if len(a) > 2 and len(b) > 2 else np.nan
                rows.append({"variable": c, "AI_median": a.median(), "nonAI_median": b.median(), "mwu_p": p})
            rows.append({"variable": "share EBITDA < 0", "AI_median": (D.loc[D[AI] == 1, "ebitda_margin"] < 0).mean(), "nonAI_median": (D.loc[D[AI] == 0, "ebitda_margin"] < 0).mean()})
            pd.DataFrame(rows).to_csv(res / "p7_profitability_size_profile.csv", index=False)
            j = list(pref["X"].columns)
            coef = {k: (pref["b"][j.index(k)], pref["se"][j.index(k)]) for k in ("revenue_growth", "ebitda_margin", "ln_revenue")}
            pd.DataFrame([{"term": k, "beta": v[0], "hc3_se": v[1]} for k, v in coef.items()]).to_csv(res / "p7_control_coefficients.csv", index=False)
            D["_size_t"] = pd.qcut(D["ln_revenue"].rank(method="first"), 3, labels=["small", "mid", "large"])
            D.groupby("_size_t", observed=True)[AI].agg(["mean", "sum", "count"]).rename(columns={"mean": "AI_share"}).reset_index().to_csv(res / "p7_ai_share_by_size.csv", index=False)
        prof()

        @sec("F/G. Market timing and sector composition")
        def timing():
            y = D.groupby("announce_year").agg(n=(AI, "size"), n_ai=(AI, "sum")); y["ai_share"] = y["n_ai"] / y["n"]
            y["median_evrev_AI"] = D[D[AI] == 1].groupby("announce_year")["ev_revenue"].median(); y["median_evrev_nonAI"] = D[D[AI] == 0].groupby("announce_year")["ev_revenue"].median()
            y["spread"] = y["median_evrev_AI"] - y["median_evrev_nonAI"]; y.reset_index().to_csv(res / "p7_timing_by_year.csv", index=False)
            s = D.groupby("sector").agg(n=(AI, "size"), n_ai=(AI, "sum"), median_evrev=("ev_revenue", "median")); s["ai_share"] = s["n_ai"] / s["n"]; s.reset_index().to_csv(res / "p7_sector_composition.csv", index=False)
            b3, b4 = C.fit(D, AI, C.MODELS["(2) + growth, margin, size"])["beta"], C.fit(D, AI, C.MODELS["(3) + year FE"])["beta"]; b5 = C.fit(D, AI, C.MODELS["(4) + sector FE"])["beta"]
            pd.DataFrame([{"vintage_change_(2)->(3)": b4 - b3, "sector_change_(3)->(4)": b5 - b4}]).to_csv(res / "p7_vintage_sector_attenuation.csv", index=False)
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6)); yy = y.reset_index()
            a1.plot(yy["announce_year"], yy["median_evrev_AI"], "o-", label="AI"); a1.plot(yy["announce_year"], yy["median_evrev_nonAI"], "s-", label="non-AI"); a1.legend(); a1.set_title("Median EV/Revenue by year (descriptive)", fontsize=8)
            a2.bar(yy["announce_year"], yy["n_ai"]); a2.set_title("Number of AI deals (quantity, not price)", fontsize=8); f.suptitle(banner, fontsize=7); f.tight_layout(); f.savefig(ch / "p7_chart_timing_quantity.png", dpi=120); plt.close(f)
        timing()

        @sec("H/I. AI intensity (0-3) and strict vs broad")
        def inten():
            x = D.copy(); x["_i"] = pd.to_numeric(x["ai_intensity"], errors="coerce"); need(x["_i"].notna().sum() > 30, "intensity not coded")
            for k in (1, 2, 3): x[f"int{k}"] = (x["_i"] == k).astype(float)
            ks = [k for k in (1, 2, 3) if x[f"int{k}"].sum() >= 8]; need(ks, "no intensity level with N>=8")
            r = C.fit(x, f"int{ks[0]}", C.ORDER, extra=x[[f"int{k}" for k in ks[1:]]]); nm = list(r["X"].columns); rows = []
            for k in ks:
                i = nm.index(f"int{k}"); rows.append({"level": k, "N": int(x[f"int{k}"].sum()), "beta_vs_nonAI": r["b"][i], "ci_lo": r["lo"][i], "ci_hi": r["hi"][i]})
            t = pd.DataFrame(rows); t.to_csv(res / "p7_table3_ai_intensity.csv", index=False); M["inten"] = t
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(5, 3.4)); a.errorbar(t["level"], t["beta_vs_nonAI"], yerr=[t["beta_vs_nonAI"] - t["ci_lo"], t["ci_hi"] - t["beta_vs_nonAI"]], fmt="o", capsize=3); a.axhline(0, c="grey"); a.set_xlabel("AI intensity (0 = non-AI)"); a.set_title("Chart 4: valuation by AI intensity\n" + banner, fontsize=8); f.tight_layout(); f.savefig(ch / "p7_chart_04_intensity.png", dpi=120); plt.close(f)
        inten()

        @sec("J/K. AI subsectors and GenAI vs traditional ML")
        def subs():
            p = res / "p5_subsector_groups.csv"; need(p.exists(), "Phase 5 subsector table missing"); pd.read_csv(p).to_csv(res / "p7_table4_subsector.csv", index=False)
            x = D.copy(); st = pd.to_numeric(x["ai_subsector"], errors="coerce"); x["gen"] = (st == 1).astype(float); x["ml"] = ((st > 1) & (x[AI] == 1)).astype(float)
            need(x["gen"].sum() >= 8 and x["ml"].sum() >= 8, f"GenAI N={int(x['gen'].sum())}, other-AI N={int(x['ml'].sum())}; need >=8 each")
            r = C.fit(x, "gen", C.ORDER, extra=x[["ml"]]); nm = list(r["X"].columns)
            pd.DataFrame([{"group": "Foundation/GenAI (subsector 1)", "N": int(x["gen"].sum()), "beta": r["b"][nm.index("gen")], "lo": r["lo"][nm.index("gen")], "hi": r["hi"][nm.index("gen")]},
                          {"group": "Other AI (traditional ML etc.)", "N": int(x["ml"].sum()), "beta": r["b"][nm.index("ml")], "lo": r["lo"][nm.index("ml")], "hi": r["hi"][nm.index("ml")]}]).to_csv(res / "p7_genai_vs_ml.csv", index=False)
        subs()

        @sec("L/M. Strategic vs sponsor; public vs private; pre vs post GenAI")
        def hetero():
            x = D.copy(); rows = []
            for nm, col, lab1, lab0, fy in (("Buyer type", "strategic", "Strategic", "Sponsor/other", True), ("Target status", "public", "Public", "Private/other", True),
                                              ("Regime", "post_genai", "Post-GenAI", "Pre-GenAI", False)):
                x["_i"] = x[AI] * pd.to_numeric(x[col], errors="coerce"); r = C.fit(x, AI, C.ORDER, extra=x[["_i"]], fe_year=fy); j = list(r["X"].columns).index("_i")
                b1, l1, h1 = combo(r, 1, j); rows += [{"table": nm, "group": lab1, "AI_effect": b1, "lo": l1, "hi": h1, "N_AI": int(((x[AI] == 1) & (pd.to_numeric(x[col], errors='coerce') == 1)).sum()), "interaction_p": r["p"][j]},
                                                      {"table": nm, "group": lab0, "AI_effect": r["b"][1], "lo": r["lo"][1], "hi": r["hi"][1], "N_AI": int(((x[AI] == 1) & (pd.to_numeric(x[col], errors='coerce') == 0)).sum()), "interaction_p": r["p"][j]}]
            t = pd.DataFrame(rows); t.to_csv(res / "p7_tables5_6_7_heterogeneity.csv", index=False); M["het"] = t
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(7, 3.6)); a.errorbar(range(len(t)), t["AI_effect"], yerr=[t["AI_effect"] - t["lo"], t["hi"] - t["AI_effect"]], fmt="o", capsize=3); a.axhline(0, c="grey")
            a.set_xticks(range(len(t))); a.set_xticklabels(t["group"], rotation=30, ha="right", fontsize=7); a.set_title("Charts 5/6: AI effect by buyer type, status, regime\n" + banner, fontsize=8); f.tight_layout(); f.savefig(ch / "p7_chart_05_06_heterogeneity.png", dpi=120); plt.close(f)
        hetero()

        @sec("N-P. Pre-deal valuation, takeover premium, case A-D, control vs AI premium")
        def predeal():
            P = A[(A["in_premium_final"] == 1)].copy(); P["lp"] = np.log1p(P["premium_1d"]); P["lpre"] = np.log(P["predeal_ev_revenue"].where(P["predeal_ev_revenue"] > 0))
            P["uplift"] = P["ev_revenue"] / P["predeal_ev_revenue"] - 1; need(len(P) >= 15 and P[AI].nunique() == 2 and (P[AI] == 1).sum() >= 5, f"public premium sample N={len(P)}")
            T = pd.DataFrame([{"measure": m, "AI_median": P.loc[P[AI] == 1, c].median(), "nonAI_median": P.loc[P[AI] == 0, c].median(), "N_AI": int(P.loc[P[AI] == 1, c].notna().sum())}
                              for m, c in (("Pre-deal EV/Revenue", "predeal_ev_revenue"), ("Deal EV/Revenue", "ev_revenue"), ("1-day takeover premium", "premium_1d"), ("Implied multiple uplift (deal / pre-deal - 1)", "uplift"))])
            T.to_csv(res / "p7_table8_predeal_premium.csv", index=False)
            def adj(y):
                z = P.dropna(subset=[y, "revenue_growth", "ebitda_margin", "ln_revenue", "strategic", "post_genai", "announce_year"]); G = C.groups(z, AI, fe_year=False)
                X = pd.concat([pd.Series(1.0, index=z.index, name="c"), z[AI].astype(float), G["growth"], G["profitability"], G["size"], G["year"], z[["strategic"]].astype(float)], axis=1); o = C.ols(z[y], X.to_numpy(), list(X.columns)); return o["b"][1], o["lo"][1], o["hi"][1], o["n"]
            (bp, lp, hp, np_), (bm, lm, hm, nm_) = adj("lpre"), adj("lp"); hi_pre, hi_prem = lp > 0, lm > 0
            case = "A" if hi_pre and not hi_prem else "B" if hi_pre and hi_prem else "C" if (not hi_pre) and hi_prem else "D"
            M["case"] = {"case": case, "pre_beta": bp, "pre_ci": [lp, hp], "prem_beta": bm, "prem_ci": [lm, hm], "N": np_}
            pd.DataFrame([M["case"]]).to_csv(res / "p7_case_A_to_D.csv", index=False)
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(5, 3.6)); a.errorbar([0, 1], [bp, bm], yerr=[[bp - lp, bm - lm], [hp - bp, hm - bm]], fmt="o", capsize=3); a.axhline(0, c="grey"); a.set_xticks([0, 1]); a.set_xticklabels(["ln pre-deal EV/Rev", "ln(1+premium)"]); a.set_title(f"Chart 7: pre-deal valuation vs premium (case {case})\n" + banner, fontsize=8); f.tight_layout(); f.savefig(ch / "p7_chart_07_predeal_premium.png", dpi=120); plt.close(f)
        predeal()

        @sec("Q-S. Contested, cross-border, buyer concentration, buyer FE, sector x year FE")
        def auction():
            rows = []
            for c in ("contested", "cross_border"):
                if c in D.columns and D[c].notna().sum() > 20:
                    t = pd.crosstab(D[AI], pd.to_numeric(D[c], errors="coerce")); p = stats.fisher_exact(t.to_numpy())[1] if t.shape == (2, 2) else np.nan
                    rows.append({"variable": c, "P_AI": D.loc[D[AI] == 1, c].astype(float).mean(), "P_nonAI": D.loc[D[AI] == 0, c].astype(float).mean(), "fisher_p": p, "label": "EXPLORATORY"})
            pd.DataFrame(rows or [{"variable": "none available"}]).to_csv(res / "p7_auction_crossborder.csv", index=False)
            tb = D[D[AI] == 1].groupby("buyer_name").size().sort_values(ascending=False).head(10).rename("AI_deals").reset_index(); tb.to_csv(res / "p7_top_buyers.csv", index=False)
            rep = D["buyer_name"].map(D["buyer_name"].value_counts()); R = D[rep >= 2]
            if R["buyer_name"].nunique() >= 5 and len(R) >= 60 and R[AI].nunique() == 2:
                bd = pd.get_dummies(R["buyer_name"], prefix="b", drop_first=True, dtype=float); r = C.fit(R, AI, C.ORDER, extra=bd.loc[:, bd.std() > 0])
                pd.DataFrame([{"beta_AI_within_buyer": r["beta"], "lo": r["lo_ai"], "hi": r["hi_ai"], "N": r["n"], "repeat_buyers": R["buyer_name"].nunique(), "label": "EXPLORATORY"}]).to_csv(res / "p7_buyer_fe.csv", index=False)
            else: pd.DataFrame([{"status": "skipped: insufficient repeat buyers"}]).to_csv(res / "p7_buyer_fe.csv", index=False)
            cells = D.groupby(["sector", "announce_year"]).size()
            if (cells >= 3).mean() > .5 and len(D) > 150:
                sy = pd.get_dummies(D["sector"].astype(str) + "|" + D["announce_year"].astype(str), prefix="sy", drop_first=True, dtype=float)
                r = C.fit(D, AI, ["growth", "profitability", "size", "region", "buyer_public"], extra=sy.loc[:, sy.std() > 0])
                pd.DataFrame([{"beta_AI_sector_x_year_FE": r["beta"], "lo": r["lo_ai"], "hi": r["hi_ai"], "N": r["n"], "label": "EXPLORATORY"}]).to_csv(res / "p7_sector_year_fe.csv", index=False)
            else: pd.DataFrame([{"status": "skipped: sector x year cells too thin; would destroy power"}]).to_csv(res / "p7_sector_year_fe.csv", index=False)
        auction()

        @sec("V. Relative valuation vs benchmark (Chart 10)")
        def rel():
            ext = root / "data_raw" / "external_benchmarks" / "sector_year_multiples.csv"; x = D.copy()
            if ext.exists():
                bm = pd.read_csv(ext); x = x.merge(bm[["sector", "announce_year", "benchmark_ev_revenue"]], on=["sector", "announce_year"], how="left"); x["_bm"] = np.log(x["benchmark_ev_revenue"]); src = "external benchmark file"
            else:
                non = x[x[AI] == 0]; x["_bm"] = [non.loc[(non["sector"] == s) & (non["announce_year"] == yv) & (non.index != i), C.Y].median() if ((non["sector"] == s) & (non["announce_year"] == yv) & (non.index != i)).sum() >= 3 else non.loc[(non["announce_year"] == yv) & (non.index != i), C.Y].median()
                                                 for i, s, yv in zip(x.index, x["sector"], x["announce_year"])]; src = "IN-SAMPLE non-AI same sector-year median (NOT external market data)"
            x["rel"] = x[C.Y] - x["_bm"]; z = x.dropna(subset=["rel"]); need(z[AI].nunique() == 2, "no contrast")
            X0 = np.column_stack([np.ones(len(z)), z[AI]]); r0 = C.ols(z["rel"], X0); G = C.groups(z, AI)
            X1 = np.column_stack([X0, z[["revenue_growth", "ebitda_margin", "ln_revenue"]]]); r1 = C.ols(z["rel"], X1)
            t = pd.DataFrame([{"spec": "relative multiple, no controls", "beta": r0["b"][1], "lo": r0["lo"][1], "hi": r0["hi"][1], "pct": C.pct(r0["b"][1]), "benchmark": src},
                              {"spec": "relative multiple + growth, margin, size", "beta": r1["b"][1], "lo": r1["lo"][1], "hi": r1["hi"][1], "pct": C.pct(r1["b"][1]), "benchmark": src}]); t.to_csv(res / "p7_relative_multiple.csv", index=False)
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(5, 3.4)); a.errorbar([0, 1], t["beta"], yerr=[t["beta"] - t["lo"], t["hi"] - t["beta"]], fmt="o", capsize=3); a.axhline(0, c="grey"); a.set_xticks([0, 1]); a.set_xticklabels(["no controls", "+fundamentals"]); a.set_title("Chart 10: AI multiple relative to benchmark\n" + banner, fontsize=7); f.tight_layout(); f.savefig(ch / "p7_chart_10_relative.png", dpi=120); plt.close(f)
        rel()

        @sec("Counterfactual multiples, dollar illustration, representative targets, residual cases (Chart 9)")
        def cf():
            X = pref["X"].copy(); nm = list(X.columns); X0 = X.copy(); X0[AI] = 0.0; smear = float(np.mean(np.exp(pref["resid"])))
            pn = np.exp(X0.to_numpy() @ pref["b"]) * smear; ai_m = (D[AI] == 1).to_numpy(); dM = pn[ai_m] * (np.exp(pref["beta"]) - 1)
            ds = pd.Series(dM).describe(); ds.to_csv(res / "p7_counterfactual_multiple_uplift_AI_deals.csv", header=["value"])
            R = 500e6; pd.DataFrame([{"revenue_usd": R, "median_uplift_x": float(np.median(dM)), "implied_EV_difference_usd": R * float(np.median(dM)), "label": "ILLUSTRATIVE; association-based; derived from preferred model"}]).to_csv(res / "p7_dollar_illustration.csv", index=False)
            q = D[["revenue_growth", "ebitda_margin", "ln_revenue"]].quantile([.25, .75]); mode = lambda s: s.mode().iloc[0]
            base = {c: float(X[c].mean()) for c in nm if c.startswith(("yr_", "sec_", "reg_"))}; ai_rows = D[D[AI] == 1]
            sec_ai = mode(ai_rows["sector"]); reps = []
            for name, g, m, s in (("Small high-growth AI target", .75, .25, .25), ("Mature profitable target", .25, .75, .75), ("Mid-scale balanced target", .5, .5, .5)):
                v = pd.Series(0.0, index=nm); v["const"] = 1; v["revenue_growth"] = D["revenue_growth"].quantile(g); v["ebitda_margin"] = D["ebitda_margin"].quantile(m); v["ln_revenue"] = D["ln_revenue"].quantile(s)
                for c, val in base.items(): v[c] = val
                v["strategic"] = 1.0; v["public"] = 0.0; p0 = float(np.exp(v.to_numpy() @ pref["b"]) * smear); v[AI] = 1.0; p1 = float(np.exp(v.to_numpy() @ pref["b"]) * smear)
                reps.append({"profile": name, "predicted_EV_Rev_nonAI": p0, "predicted_EV_Rev_AI": p1, "uplift_x": p1 - p0, "note": "hypothetical firm; sector/year/region at sample averages"})
            pd.DataFrame(reps).to_csv(res / "p7_representative_targets.csv", index=False)
            rs = pd.Series(pref["resid"], index=D.index); ai_res = D.loc[D[AI] == 1, ["deal_id", "target_name", "buyer_name", "sector", "announce_year", "revenue_growth", "ev_revenue"]].assign(residual=rs[D[AI] == 1])
            cases = pd.concat([ai_res.nlargest(3, "residual").assign(side="largest positive"), ai_res.nsmallest(3, "residual").assign(side="largest negative")])
            cases["public_context_review"] = "MANUAL REVIEW REQUIRED: buyer rationale, competitive process, stage, product (not auto-filled; do NOT re-specify the model afterwards)"; cases.to_csv(res / "p7_residual_cases.csv", index=False)
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            f, a = plt.subplots(figsize=(6, 3.4)); a.barh(range(len(cases)), cases["residual"], color=["tab:green" if s.startswith("largest p") else "tab:red" for s in cases["side"]]); a.set_yticks(range(len(cases))); a.set_yticklabels(cases["deal_id"].astype(str), fontsize=7); a.set_title("Chart 9: largest AI-deal residuals (preferred model)\n" + banner, fontsize=8); f.tight_layout(); f.savefig(ch / "p7_chart_09_residuals.png", dpi=120); plt.close(f)
        cf()

        @sec("42-45. Exploratory splits by size, growth, profitability, regime")
        def splits():
            rows = []
            def one(lab, z):
                if (z[AI] == 1).sum() >= 8 and (z[AI] == 0).sum() >= 8:
                    r = C.fit(z, AI, ["growth", "profitability", "size"], fe_year=False, extra=C.dummies(C.period(z), "per")); rows.append({"split": lab, "beta": r["beta"], "lo": r["lo_ai"], "hi": r["hi_ai"], "N": r["n"], "AI_N": int((z[AI] == 1).sum()), "label": "EXPLORATORY"})
                else: rows.append({"split": lab, "note": "suppressed: <8 AI or <8 non-AI"})
            for q, g in zip(("small", "mid", "large"), D.groupby(pd.qcut(D["ln_revenue"].rank(method="first"), 3, labels=False))): one(f"size: {q}", g[1])
            mg = D["revenue_growth"].median(); one("growth: below median", D[D["revenue_growth"] <= mg]); one("growth: above median", D[D["revenue_growth"] > mg])
            one("EBITDA positive", D[D["ebitda_margin"] > 0]); one("EBITDA negative", D[D["ebitda_margin"] <= 0])
            yr = pd.to_numeric(D["announce_year"]); one("2015-2018", D[yr <= 2018]); one("2019-2022 (pre-GenAI)", D[(yr >= 2019) & (pd.to_numeric(D["post_genai"]) == 0)]); one("Post-Nov-2022", D[pd.to_numeric(D["post_genai"]) == 1])
            pd.DataFrame(rows).to_csv(res / "p7_exploratory_splits.csv", index=False)
        splits()

    # ---------------------------------------------------------------- narrative, evidence matrix, freeze
    stories = {
        "Robust AI Acquisition Premium": "AI-native targets are associated with a statistically and economically meaningful acquisition revenue-multiple premium that survives the pre-specified controls, matching, bootstrap and placebo tests.",
        "Suggestive AI Premium": "AI targets show a positive conditional association with acquisition multiples, but the evidence falls short of the pre-specified robustness standard, so the premium is suggestive rather than established.",
        "Regime-Specific Premium": "No broad AI premium is evident over the full sample, but the post-generative-AI period shows a materially stronger conditional association.",
        "Strategic-Buyer Premium": "AI valuation differentiation appears concentrated among strategic buyers rather than financial sponsors, consistent with - but not proving - synergy, defensive or time-to-market value.",
        "Sector-Specific Premium": "A positive conditional AI association appears only in specific sectors and should not be generalised to all AI M&A.",
        "Growth / Composition Premium": "AI targets trade at higher raw acquisition multiples, but most of the gap is explained by growth, size and deal composition rather than a distinct AI premium.",
        "No Robust Premium": "No robust evidence of an AI acquisition valuation premium was found once targets are compared on observable characteristics.",
        "Negative Conditional Association": "Conditional on observable characteristics, AI targets are associated with LOWER acquisition multiples than comparable non-AI targets.",
        "NOT ASSESSABLE": "No empirical conclusion can be drawn: the sample does not meet the pre-specified power gates."}
    headline = stories[label]
    strengths = None
    if assessable:
        het = M.get("het"); gel = M.get("gel")
        strengths = pd.DataFrame([
            ("AI deals trade at higher raw multiples", "Descriptive", strength(M["raw"]["lo_ai"], M["raw"]["hi_ai"], M["raw"]["beta"], nA)),
            ("Difference survives fundamentals", "Regression", strength(M["pref"]["lo_ai"], M["pref"]["hi_ai"], M["pref"]["beta"], nA)),
            ("Difference survives matching", "CEM/PSM", "Strong" if (cl["cem_boot_ci"][0] or -1) > 0 else "Weak" if (cl["cem_beta"] or 0) > 0 else "Unsupported"),
            ("Difference survives bootstrap", "Bootstrap", "Strong" if cl["bootstrap_ci"][0] > 0 else "Weak" if cl["beta_preferred"] > 0 else "Unsupported"),
            ("Difference beats placebo", "Placebo", "Strong" if cl["placebo_p_one_sided"] < .01 else "Moderate" if cl["placebo_p_one_sided"] < .05 else "Unsupported"),
            ("Strategics pay more", "Interaction", "Not estimated" if het is None else ("Moderate" if het.query("table=='Buyer type'")["interaction_p"].iloc[0] < .05 and het.query("group=='Strategic'")["AI_effect"].iloc[0] > het.query("group=='Sponsor/other'")["AI_effect"].iloc[0] else "Unsupported")),
            ("PostGenAI stronger", "Interaction", "Unsupported" if het is None or het.query("group=='Post-GenAI'")["interaction_p"].iloc[0] >= .05 else "Moderate"),
            ("Takeover premium higher", "Public deals", "Not estimated" if "case" not in M else ("Moderate" if M["case"]["prem_ci"][0] > 0 else "Unsupported")),
            ("Pre-deal valuation higher", "Public deals", "Not estimated" if "case" not in M else ("Moderate" if M["case"]["pre_ci"][0] > 0 else "Unsupported"))], columns=["claim", "evidence", "strength"])
        strengths.to_csv(res / "p7_table9_evidence_strength.csv", index=False)
    pd.DataFrame(STATUS).to_csv(res / "p7_section_status.csv", index=False)

    ci = cl.get("pref_ci", [np.nan, np.nan]); tech = (f"N={cl['N']} (strict AI N={cl['strict_AI_N']}). Raw log gap {cl['beta_raw']:.3f}; preferred coefficient {cl['beta_preferred']:.3f} "
          f"({cl['pct_effect']:.1f}%), HC3 95% CI [{ci[0]:.3f}, {ci[1]:.3f}]; bootstrap CI [{cl['bootstrap_ci'][0]:.3f}, {cl['bootstrap_ci'][1]:.3f}]; CEM ATT {cl['cem_beta']}; PSM ATT {cl['psm_att']:.3f}; "
          f"placebo one-sided p={cl['placebo_p_one_sided']:.3f}; {cl['checks_same_sign']}/12 checks same sign, {cl['checks_half_magnitude']}/12 keep half magnitude. Classification: {label}.") if assessable else \
        f"Not assessable: {cl['status']}. No coefficient is reported."
    banker = {"Robust AI Acquisition Premium": "AI-native status may justify a separate precedent set where growth, sector and strategic scarcity resemble the deals driving the effect; do not add a mechanical AI uplift.",
              "Growth / Composition Premium": "Do not apply an AI premium; select precedents on growth, scale, margin, sector and regime. Treat the AI label as a screening attribute, not a multiple driver.",
              "No Robust Premium": "Pool AI targets with comparable software precedents matched on fundamentals; AI labelling alone does not justify a premium.",
              "NOT ASSESSABLE": "No change to precedent practice can be inferred from this project yet."}.get(label, "Use the AI association as supporting context only, within the subgroup where it was observed; ground valuation in comparable growth and economics.")
    freeze = {"DATA_VERSION": "FINAL_EMPIRICAL_CONCLUSION_V1", "phase6_classification": label, "headline": headline, "technical_conclusion": tech, "banker_conclusion": banker,
              "synthetic": synthetic, "pilot": pilot, "banner": banner, "analysis_sha256": man["sha256"], "created": str(date.today()),
              "rule": "Core conclusion may change only for a factual/model error; any change = V2 + deviations_log"}
    fp = root / "docs" / "FINAL_EMPIRICAL_CONCLUSION_V1.json"
    if fp.exists():
        o = json.loads(fp.read_text())
        if o["analysis_sha256"] == freeze["analysis_sha256"] and o["phase6_classification"] != label: raise SystemExit("PHASE 7: conclusion would change on identical frozen inputs. Create V2.")
    fp.write_text(json.dumps(freeze, indent=2))

    def tbl(name):
        p = res / name; return pd.read_csv(p).round(3).to_markdown(index=False) if p.exists() else "_not produced (see p7_section_status.csv)_"
    md = [f"# Phase 7 - Economic Interpretation\n", f"> **{banner}**\n" if banner else "", f"## A. Final Phase 6 evidence classification (carried forward unchanged)\n**{label}** - {cl['reason']}\n"]
    if assessable:
        md += ["## B. Raw vs adjusted bridge (coefficient attenuation path, not a causal decomposition)\n", tbl("p7_table1_raw_to_adjusted.csv"), "\n## C/U. Gelbach attenuation by control group\n", tbl("p7_table2_gelbach.csv"), tbl("p7_gelbach_check.csv"),
               "\nOaxaca-Blinder (the unexplained part is NOT 'AI value'):\n", tbl("p7_oaxaca.csv"), "\n## D/E. Profitability and size profile\n", tbl("p7_profitability_size_profile.csv"), tbl("p7_control_coefficients.csv"),
               "\n## F/G. Timing and sector composition\n", tbl("p7_timing_by_year.csv"), tbl("p7_vintage_sector_attenuation.csv"), "\n## H. AI intensity\n", tbl("p7_table3_ai_intensity.csv"), "\n## I. Strict vs broad\n", tbl("p5_strict_vs_broad.csv"),
               "\n## J/K. Subsectors; GenAI vs other AI\n", tbl("p7_table4_subsector.csv"), tbl("p7_genai_vs_ml.csv"), "\n## L/M. Buyer, status, regime\n", tbl("p7_tables5_6_7_heterogeneity.csv"),
               "\n## N-P. Pre-deal valuation, premium, case A-D\n", tbl("p7_table8_predeal_premium.csv"), tbl("p7_case_A_to_D.csv"), "\n## Q. Contested / cross-border (exploratory)\n", tbl("p7_auction_crossborder.csv"), tbl("p7_top_buyers.csv"), tbl("p7_buyer_fe.csv"), tbl("p7_sector_year_fe.csv"),
               "\n## V. Relative valuation\n", tbl("p7_relative_multiple.csv"), "\n## Counterfactual / illustration / representative targets (ILLUSTRATIVE)\n", tbl("p7_counterfactual_multiple_uplift_AI_deals.csv"), tbl("p7_dollar_illustration.csv"), tbl("p7_representative_targets.csv"),
               "\n## W. Residual cases (manual public-source review required)\n", tbl("p7_residual_cases.csv"), "\n## Exploratory splits\n", tbl("p7_exploratory_splits.csv"), "\n## AC. Evidence-strength matrix\n", tbl("p7_table9_evidence_strength.csv")]
    md += ["\n## Control premium vs AI premium (concept)\nControl premium = price over the unaffected trading value. AI valuation premium = difference in acquisition multiple versus comparable non-AI targets. They are not synonyms: a 20x EV/Revenue deal can carry a 10% bid premium if the stock already traded richly; a 5x business can carry a 50% premium.\n",
           "## R/S/T/X-AB. Frameworks (HYPOTHESES - not empirically identified)\n- Strategic-value sources: revenue synergy, cost synergy, time-to-market, defensive value, data/model value, talent (operating company vs excluded acqui-hires).\n- Build vs buy: a strategic may rationally pay if PV(time saved + synergies + option value) > acquisition premium.\n- Scarcity premium = valuation attributed to rare strategic assets with limited substitutes; no numeric estimate is made.\n- Growth vs scarcity: growth premium = higher multiple from faster growth; residual after controls is the only candidate AI-specific component, and it also contains omitted variables.\n",
           "- Precedent decision tree: is the target AI-native (intensity >= 2)? -> is the effect robust (Phase 6 label)? YES -> prioritise AI-native precedents; NO -> match on growth, scale, margin, regime, buyer type. Never add a mechanical % uplift.\n- Banker workflow: sector precedents -> AI intensity -> normalise growth/margin -> separate public/private -> timing -> buyer mix -> conditional AI effect -> judgement.\n",
           "## AD. Deal-team takeaways\n1. Do not compare AI targets on EV/Revenue alone.\n2. Growth, margin and size controls matter materially (see Gelbach).\n3. Do not pool AI-enabled (level 1) with AI-native (levels 2-3) automatically.\n4. Transaction multiple and takeover premium are different objects.\n5. Public-market valuation may already embed AI expectations (see case A-D).\n6. Strategic and sponsor buyers may value AI differently (see interaction).\n7. Match precedents on sector and year.\n8. Extreme early-stage revenue multiples need caution.\n9. Private-target disclosure is selective.\n10. Choose precedents for economic comparability, not labels.\n11. Treat any residual AI effect as context, not a standalone adjustment.\n12. Quantity of AI deals and price of AI deals are separate questions.\n",
           "## AE. Interview insights\n" + "\n".join(f"**{q}** {a}" for q, a in [
               ("What did you find?", headline), ("Did AI cause the premium?", "No causal claim; association conditional on observables, with selection into being acquired."), ("Why EV/Revenue?", "Many targets have negative EBITDA; revenue is the common denominator."),
               ("Why not EV/EBITDA?", "Undefined or extreme for loss-making targets; kept as a secondary outcome."), ("Why log the multiple?", "Right-skewed; log differences read as percentage gaps."), ("Why HC3?", "Small samples with high-leverage points; HC3 is conservative."),
               ("Why matching?", "To compare AI deals only with similar non-AI deals and test the regression's functional-form dependence."), ("Why bootstrap?", "Inference without relying on normal errors in small samples."),
               ("Why placebo?", "Randomly reassigning AI labels shows how large a coefficient arises by chance."), ("What explains the raw gap?", "See the Gelbach table: the share attributable to growth, margin, size, year, sector, region, buyer/public."),
               ("Why might strategics pay more?", "HYPOTHESES: synergies, time-to-market, defensive value, IP and talent; none identified here."), ("Why might takeover premium not differ?", "Public stocks may already price AI expectations; premium is measured against unaffected value."),
               ("How would a banker use it?", banker), ("Biggest limitation?", "No causal identification; selection into being acquired; private disclosure bias; treatment error."), ("What with Capital IQ?", "Systematic universe, more deals, pre-deal multiples, contested-process data, then repeat the frozen pipeline."),
               ("What was excluded?", "Acqui-hires, non-technology sectors, deals without disclosed EV/revenue; see the waterfall.")]),
           f"\n## AF. Final one-sentence conclusion\n{headline}\n\n## AG. Technical conclusion\n{tech}\n\n## AH. Banker conclusion\n{banker}\n",
           "\n## AI. Limitations\nNo causal identification; selection into being acquired; private disclosure bias; treatment (AI label) error; unobserved synergies; no bid-process data; earn-outs/retention in deal terms; small subgroup samples; exploratory splits are not corrected for multiplicity.\n",
           f"\n## AJ. Freeze\nFINAL_EMPIRICAL_CONCLUSION_V1 written to docs/ (created {date.today()}).\n\n## AK. Inputs required for Phase 8\nFrozen analysis, baseline, Phase 6 classification, this file, charts p7_chart_*.png, section status table.\n\n## Section status\n", pd.DataFrame(STATUS).to_markdown(index=False)]
    (res / "Phase7_Economic_Interpretation.md").write_text("\n".join(md))
    print(f"Phase 7 complete. Classification carried forward: {label}. Sections: {sum(s['status']=='done' for s in STATUS)} done, {sum(s['status']!='done' for s in STATUS)} skipped/error.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent)); a = ap.parse_args(); raise SystemExit(main(Path(a.root)))
