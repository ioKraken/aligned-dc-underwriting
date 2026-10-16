"""Phase 6b - robustness, bootstrap, placebo, wild-cluster bootstrap, Holm, evidence matrix and FINAL CLASSIFICATION (frozen).
Evidence standard (Phase 1): beta>0; HC3 and bootstrap CIs exclude 0; beta>=0.15; 12/12 checks same sign; >=9/12 retain >=half magnitude;
strict AI used; matched CI excludes 0; placebo p<0.05. Classification is rule-based and is written to docs/PHASE6_CLASSIFICATION_V1.json.
If power gates fail the result is NOT ASSESSABLE - no label is forced."""
from __future__ import annotations
import argparse, json
from datetime import date
from pathlib import Path
import numpy as np, pandas as pd
import p5_common as C

LABELS = ["Robust AI Acquisition Premium", "Suggestive AI Premium", "Regime-Specific Premium", "Strategic-Buyer Premium", "Sector-Specific Premium",
          "Growth / Composition Premium", "No Robust Premium", "Negative Conditional Association"]


def quantile_beta(D, ai, keep):
    from sklearn.linear_model import QuantileRegressor
    X = C.design(D, ai, keep); cols = list(X.columns); Xv = X.drop(columns=["const"]).to_numpy()
    m = QuantileRegressor(quantile=.5, alpha=0, solver="highs").fit(Xv, D[C.Y].to_numpy())
    return float(m.coef_[cols.index(ai) - 1])


def wild_cluster_p(D, ai, keep, cluster, B=999, seed=C.SEED):
    """Wild cluster bootstrap-t, Rademacher weights, null imposed (WCR). Returns two-sided p; unreliable with <10 clusters (flagged)."""
    X = C.design(D, ai, keep); Xv = X.to_numpy(); i = list(X.columns).index(ai); y = D[C.Y].to_numpy(); g = D[cluster].astype(str).to_numpy()
    ids = pd.unique(g); gi = {k: np.where(g == k)[0] for k in ids}
    def tstat(yv, Xm):
        XtXi = np.linalg.pinv(Xm.T @ Xm); b = XtXi @ Xm.T @ yv; e = yv - Xm @ b; S = np.zeros((Xm.shape[1],) * 2)
        for k in ids:
            s = Xm[gi[k]].T @ e[gi[k]]; S += np.outer(s, s)
        V = XtXi @ S @ XtXi; return b[i] / np.sqrt(max(V[i, i], 1e-18)), b
    t0, _ = tstat(y, Xv); Xr = np.delete(Xv, i, 1); br = np.linalg.pinv(Xr.T @ Xr) @ Xr.T @ y; fr = Xr @ br; er = y - fr
    rng = np.random.default_rng(seed); cnt = 0; n = 0
    for _ in range(B):
        w = np.ones(len(y)); 
        for k in ids: w[gi[k]] = rng.choice([-1., 1.])
        ys = fr + er * w
        try: tb, _ = tstat(ys, Xv)
        except Exception: continue
        n += 1; cnt += abs(tb) >= abs(t0)
    return {"p": (cnt + 1) / (n + 1), "clusters": len(ids), "reliable": len(ids) >= 10}


def main(root: Path, B: int, Bp: int, min_ai: int, min_total: int) -> int:
    res = root / "results"
    for need in ("BASELINE_V1_PHASE5.json",):
        if not (root / "docs" / need).exists(): raise SystemExit(f"PHASE 6 REFUSED: {need} missing (run Phase 5 first).")
    _b = json.loads((root / "docs" / "BASELINE_V1_PHASE5.json").read_text())
    if _b.get("estimable") is False:
        man0 = C.load_frozen(root, "ANALYSIS_V1_PHASE4.json", "PHASE 6")
        st = f"NOT ASSESSABLE (strict AI N={_b['strict_AI_N']}; models not estimable)"
        out = {"DATA_VERSION": "PHASE6_CLASSIFICATION_V1", "classification": "NOT ASSESSABLE", "reason": st, "status": st, "analysis_sha256": man0["sha256"], "N": _b["N"], "strict_AI_N": _b["strict_AI_N"],
               "synthetic": _b["synthetic"], "pilot": _b["pilot"], "created": str(date.today())}
        (root / "docs" / "PHASE6_CLASSIFICATION_V1.json").write_text(json.dumps(out, indent=2)); print("Phase 6 classification: NOT ASSESSABLE |", st); return 0
    for f in ("p6_cem.csv", "p6_psm.csv"):
        if not (res / f).exists(): raise SystemExit(f"PHASE 6 REFUSED: {f} missing (run 06_matching.py first).")
    man = C.load_frozen(root, "ANALYSIS_V1_PHASE4.json", "PHASE 6")
    base = json.loads((root / "docs" / "BASELINE_V1_PHASE5.json").read_text())
    if base["analysis_sha256"] != man["sha256"]: raise SystemExit("PHASE 6 REFUSED: baseline was estimated on a different analysis file.")
    uni = pd.read_csv(root / "data_clean" / "deals_stage2.csv", usecols=["source_universe"], low_memory=False)["source_universe"].astype(str)
    synthetic = bool(uni.str.contains("synthetic", case=False).any()); pilot = bool(uni.str.contains("pilot", case=False).any())
    A = pd.read_csv(root / "data_clean" / man["file"], low_memory=False); ai = "ai_flag_strict"
    E = A[A["in_evrev_final"] == 1]; D = C.complete(E, ai).reset_index(drop=True); nA = int((D[ai] == 1).sum())
    status = "ASSESSABLE"
    if nA < min_ai or len(D) < min_total or (D[ai] == 0).sum() < 10:
        status = f"NOT ASSESSABLE (strict AI N={nA} < {min_ai} or total N={len(D)} < {min_total})"
    pref = C.fit(D, ai, C.ORDER); raw = C.fit(D, ai, [])
    bt = C.pairs_bootstrap(D, ai, C.ORDER, B)
    # --- 12 formal checks ---
    chk = []
    def add(name, beta, n, note=""): chk.append({"check": name, "beta": beta, "N": n, "same_sign": bool(np.sign(beta) == np.sign(pref["beta"])) if np.isfinite(beta) else False,
                                                 "keeps_half_magnitude": bool(np.isfinite(beta) and np.sign(beta) == np.sign(pref["beta"]) and abs(beta) >= .5 * abs(pref["beta"])), "note": note})
    Db = C.complete(E, "ai_flag_broad"); add("C1 broad AI definition", C.fit(Db, "ai_flag_broad", C.ORDER)["beta"], len(Db))
    for nm, f in (("C2 outcome winsorised 1/99", "analysis_outcome_winsor.csv"), ("C3 trimmed 1/99", "analysis_trimmed.csv")):
        p = root / "data_clean" / f
        if p.exists():
            W = pd.read_csv(p, low_memory=False); W = C.complete(W[W["in_evrev_final"] == 1], ai); add(nm, C.fit(W, ai, C.ORDER)["beta"], len(W))
        else: add(nm, np.nan, 0, "file missing")
    def sub(nm, mask, note=""):
        s = D[mask]; 
        if s[ai].nunique() < 2 or len(s) < 12: add(nm, np.nan, len(s), "insufficient"); return
        add(nm, C.fit(s, ai, C.ORDER)["beta"], len(s), note)
    sub("C4 exclude low-quality (flag C)", D["quality_flag"].astype(str) != "C")
    sub("C5 exclude semiconductors", ~D["sector"].astype(str).str.contains("semi", case=False))
    sub("C6 exclude EV/Revenue > 100x", D["ev_revenue"] <= 100)
    sub("C7 exclude stale financials", pd.to_numeric(D["financial_stale_flag"], errors="coerce").fillna(0) != 1)
    try: add("C8 median (LAD) regression", quantile_beta(D, ai, C.ORDER), len(D))
    except Exception as e: add("C8 median (LAD) regression", np.nan, len(D), str(e)[:60])
    Mx, n1, n0 = C.cem(D, ai); cr = C.wls_att(Mx, ai); clo, chi, _ = C.cem_boot(D, ai, max(B // 4, 100))
    add("C9 CEM matched ATT", cr["beta"] if cr else np.nan, cr["n"] if cr else 0)
    pm = C.psm(D, ai); plo, phi, _ = C.psm_boot(D, ai, max(B // 6, 60)); add("C10 PSM matched ATT", pm["att"], pm["n_matched_treated"])
    def worst(col, nm):
        bs = []
        for v in D[col].astype(str).unique():
            s = D[D[col].astype(str) != v]
            if s[ai].nunique() == 2 and len(s) > 12:
                try: bs.append((C.fit(s, ai, C.ORDER)["beta"], v))
                except Exception: pass
        if bs:
            m = min(bs, key=lambda t: t[0]); add(nm, m[0], len(D), f"worst case when dropping {col}={m[1]}")
        else: add(nm, np.nan, 0, "insufficient")
    worst("sector", "C11 leave-one-sector-out (worst)"); worst("announce_year", "C12 leave-one-year-out (worst)")
    ck = pd.DataFrame(chk); ck.to_csv(res / "p6_robustness_12_checks.csv", index=False)
    # --- placebo ---
    pl = C.placebo(D, ai, C.ORDER, Bp); pls = C.placebo(D, ai, C.ORDER, max(Bp // 2, 500), strata=D["announce_year"].astype(str) + "|" + D["sector"].astype(str))
    pd.DataFrame([{"type": "unrestricted reassignment", **{k: v for k, v in pl.items() if k != "draws"}}, {"type": "within year x sector strata", **{k: v for k, v in pls.items() if k != "draws"}}]).to_csv(res / "p6_placebo.csv", index=False)
    # --- wild cluster ---
    wy, ws = wild_cluster_p(D, ai, C.ORDER, "announce_year"), wild_cluster_p(D, ai, C.ORDER, "sector")
    pd.DataFrame([{"cluster": "year", **wy}, {"cluster": "sector", **ws}]).to_csv(res / "p6_wild_cluster.csv", index=False)
    # --- subgroup effects used for non-robust classes ---
    S = D.copy(); S["axs"] = S[ai] * S["strategic"]; S["axp"] = S[ai] * pd.to_numeric(S["post_genai"], errors="coerce")
    r4 = C.fit(S, ai, C.ORDER, extra=S[["axs"]]); j = list(r4["X"].columns).index("axs")
    strat_eff = r4["b"][1] + r4["b"][j]; v = r4["V"]; se_s = float(np.sqrt(max(v[1, 1] + v[j, j] + 2 * v[1, j], 0)))
    r5 = C.fit(S, ai, C.ORDER, extra=S[["axp"]], fe_year=False); j5 = list(r5["X"].columns).index("axp"); v5 = r5["V"]
    post_eff = r5["b"][1] + r5["b"][j5]; se_p = float(np.sqrt(max(v5[1, 1] + v5[j5, j5] + 2 * v5[1, j5], 0)))
    sec = []
    for s_, g in D.groupby("sector"):
        if (g[ai] == 1).sum() >= 5 and (g[ai] == 0).sum() >= 8:
            X = np.column_stack([np.ones(len(g)), g[ai], g["revenue_growth"], g["ebitda_margin"], g["ln_revenue"]]); o = C.ols(g[C.Y], X); sec.append({"sector": s_, "beta": o["b"][1], "lo": o["lo"][1], "hi": o["hi"][1], "N": len(g)})
    sec = pd.DataFrame(sec); sec.to_csv(res / "p6_sector_specific_effects.csv", index=False)
    sub_tab = pd.DataFrame([{"subgroup": "Strategic buyers", "effect": strat_eff, "lo": strat_eff - 1.96 * se_s, "hi": strat_eff + 1.96 * se_s, "interaction_p": r4["p"][j]},
                            {"subgroup": "Sponsor/other buyers", "effect": r4["b"][1], "lo": r4["lo"][1], "hi": r4["hi"][1], "interaction_p": r4["p"][j]},
                            {"subgroup": "Post-GenAI", "effect": post_eff, "lo": post_eff - 1.96 * se_p, "hi": post_eff + 1.96 * se_p, "interaction_p": r5["p"][j5]},
                            {"subgroup": "Pre-GenAI", "effect": r5["b"][1], "lo": r5["lo"][1], "hi": r5["hi"][1], "interaction_p": r5["p"][j5]}])
    sub_tab.to_csv(res / "p6_subgroup_effects.csv", index=False)
    # --- evidence standard ---
    crit = {"1 beta > 0": bool(pref["beta"] > 0), "2 HC3 CI excludes 0": bool(pref["lo_ai"] > 0), "3 bootstrap CI excludes 0": bool(bt["lo"] > 0),
            "4 beta >= 0.15": bool(pref["beta"] >= C.THRESH), "5 same sign in 12/12 checks": bool(ck["same_sign"].all()),
            "6 >=9/12 keep half magnitude": bool(ck["keeps_half_magnitude"].sum() >= 9), "7 strict AI definition used": True,
            "8 matched (CEM) CI excludes 0": bool(np.isfinite(clo) and clo > 0), "9 placebo p < 0.05": bool(pl["p_one_sided"] < .05)}
    ev = pd.DataFrame([{"criterion": k, "met": v} for k, v in crit.items()]); ev.to_csv(res / "p6_evidence_standard.csv", index=False)
    # --- classification (fixed priority order; no discretion) ---
    sec_pos = sec[sec["lo"] > 0] if len(sec) else sec
    sigpos = pref["lo_ai"] > 0
    raw_sigpos = raw["lo_ai"] > 0
    if status != "ASSESSABLE": label, why = "NOT ASSESSABLE", status
    elif all(crit.values()): label, why = LABELS[0], "all nine criteria met"
    elif pref["hi_ai"] < 0: label, why = LABELS[7], "preferred beta negative with HC3 CI below 0"
    elif sigpos and pref["beta"] > 0: label, why = LABELS[1], "preferred CI excludes 0 but not every Phase 1 criterion met: " + "; ".join(k for k, v in crit.items() if not v)
    elif r5["p"][j5] < .05 and post_eff - 1.96 * se_p > 0: label, why = LABELS[2], "post-GenAI effect CI>0 and interaction p<0.05; pooled effect not significant"
    elif r4["p"][j] < .05 and strat_eff - 1.96 * se_s > 0: label, why = LABELS[3], "strategic-buyer effect CI>0 and interaction p<0.05; pooled effect not significant"
    elif len(sec_pos) and len(sec_pos) < len(sec): label, why = LABELS[4], "positive CI only in sectors: " + ", ".join(sec_pos["sector"])
    elif raw_sigpos and raw["beta"] > 0: label, why = LABELS[5], "raw gap positive with CI>0 but preferred-model CI includes 0"
    else: label, why = LABELS[6], "no raw or adjusted evidence of a positive association"
    surv = pref["beta"] / raw["beta"] if raw["beta"] > 0 and pref["beta"] > 0 else np.nan
    out = {"DATA_VERSION": "PHASE6_CLASSIFICATION_V1", "classification": label, "reason": why, "status": status, "analysis_sha256": man["sha256"],
           "N": int(len(D)), "strict_AI_N": nA, "beta_raw": float(raw["beta"]), "beta_preferred": float(pref["beta"]), "pref_ci": [float(pref["lo_ai"]), float(pref["hi_ai"])],
           "pct_effect": C.pct(pref["beta"]), "bootstrap_ci": [float(bt["lo"]), float(bt["hi"])], "cem_beta": float(cr["beta"]) if cr else None, "cem_boot_ci": [clo, chi],
           "psm_att": float(pm["att"]), "psm_boot_ci": [plo, phi], "placebo_p_one_sided": pl["p_one_sided"], "placebo_p_strata": pls["p_one_sided"], "survival_ratio": None if not np.isfinite(surv) else float(surv),
           "criteria": crit, "checks_same_sign": int(ck["same_sign"].sum()), "checks_half_magnitude": int(ck["keeps_half_magnitude"].sum()),
           "synthetic": synthetic, "pilot": pilot, "created": str(date.today()), "rule": "Phase 7 must carry this label unchanged; changes require PHASE6_CLASSIFICATION_V2 + deviations_log"}
    cp = root / "docs" / "PHASE6_CLASSIFICATION_V1.json"
    if cp.exists():
        o = json.loads(cp.read_text())
        if o["analysis_sha256"] == out["analysis_sha256"] and o["classification"] != out["classification"]:
            raise SystemExit("PHASE 6: classification would change on identical frozen data. Create V2 with a deviations_log entry.")
    cp.write_text(json.dumps(out, indent=2, default=float))
    (res / "phase6_report.md").write_text(("# SYNTHETIC DATA - NOT FINDINGS\n\n" if synthetic else "# PILOT DATA - NOT FINDINGS\n\n" if pilot else "# Phase 6 evidence classification\n\n")
        + f"**Classification: {label}** ({why})\n\n" + ev.to_markdown(index=False) + "\n\n" + ck.round(3).to_markdown(index=False) + "\n")
    print(f"Phase 6 classification: {label} | {why}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--boot", type=int, default=2000); ap.add_argument("--placebo", type=int, default=5000)
    ap.add_argument("--min-ai", type=int, default=C.MIN_STRICT_AI); ap.add_argument("--min-total", type=int, default=C.MIN_TOTAL)
    a = ap.parse_args(); raise SystemExit(main(Path(a.root), a.boot, a.placebo, a.min_ai, a.min_total))
