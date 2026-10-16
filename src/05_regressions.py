"""Phase 5 - baseline regressions on the FROZEN Phase 4 analysis file (frozen Phase 1 specification, no new specs).
Gate: docs/ANALYSIS_V1_PHASE4.json + checksum. Outputs results/p5_*.csv and docs/BASELINE_V1_PHASE5.json.
Primary (confirmatory) = H1 only; H2,H4,H5 + subsector tests form the secondary Holm family. Association language only."""
from __future__ import annotations
import argparse, json
from datetime import date
from pathlib import Path
import numpy as np, pandas as pd
import p5_common as C


def row(label, r, extra=None):
    d = {"model": label, "beta_AI": r["beta"], "hc3_se": r["se_ai"], "p": r["p_ai"], "ci_lo": r["lo_ai"], "ci_hi": r["hi_ai"],
         "pct_effect": C.pct(r["beta"]), "pct_lo": C.pct(r["lo_ai"]), "pct_hi": C.pct(r["hi_ai"]), "N": r["n"], "adj_r2": r["adj_r2"]}
    d.update(extra or {}); return d


def main(root: Path, B: int) -> int:
    res = root / "results"; res.mkdir(exist_ok=True)
    man = C.load_frozen(root, "ANALYSIS_V1_PHASE4.json", "PHASE 5")
    A = pd.read_csv(root / "data_clean" / man["file"], low_memory=False)
    uni = pd.read_csv(root / "data_clean" / "deals_stage2.csv", usecols=["source_universe"], low_memory=False)["source_universe"].astype(str)
    synthetic = bool(uni.str.contains("synthetic", case=False).any()); pilot = bool(uni.str.contains("pilot", case=False).any())
    E = A[A["in_evrev_final"] == 1]
    ai = "ai_flag_strict"; D = C.complete(E, ai)
    nA = int((D[ai] == 1).sum())
    if nA < 5 or int((D[ai] == 0).sum()) < 5:
        pd.DataFrame([{"status": f"NOT ESTIMABLE: strict AI N={nA}, non-AI N={int((D[ai]==0).sum())}; models not fitted (need >=5 each)"}]).to_csv(res / "p5_h1_primary.csv", index=False)
        (root / "docs" / "BASELINE_V1_PHASE5.json").write_text(json.dumps({"DATA_VERSION": "BASELINE_V1_PHASE5", "analysis_sha256": man["sha256"], "estimable": False, "N": int(len(D)), "strict_AI_N": nA,
            "H1_beta": None, "created": str(date.today()), "synthetic": synthetic, "pilot": pilot}, indent=2))
        print(f"Phase 5: NOT ESTIMABLE (strict AI N={nA}); baseline stub frozen."); return 0
    out = []
    for name, keep in C.MODELS.items():
        out.append(row(name, C.fit(D, ai, keep)))
    prog = pd.DataFrame(out)
    prog["pct_change_in_beta_vs_model1"] = prog["beta_AI"] / prog["beta_AI"].iloc[0] - 1
    prog.to_csv(res / "p5_progressive_models.csv", index=False)
    pref = C.fit(D, ai, C.ORDER)
    # H3: attenuation (1)->(2) with bootstrap CI on the difference
    rng = np.random.default_rng(C.SEED); diffs = []
    for _ in range(B):
        s = D.iloc[rng.integers(0, len(D), len(D))].reset_index(drop=True)
        if s[ai].nunique() < 2: continue
        try:
            diffs.append(C.fit(s, ai, [], hc=1)["beta"] - C.fit(s, ai, C.MODELS["(2) + growth, margin, size"], hc=1)["beta"])
        except Exception:
            continue
    dd = np.array(diffs); h3 = {"beta_m1": prog.beta_AI[0], "beta_m2": prog.beta_AI[1], "attenuation": prog.beta_AI[0] - prog.beta_AI[1],
                                "ci_lo": float(np.percentile(dd, 2.5)), "ci_hi": float(np.percentile(dd, 97.5)), "B": len(dd)}
    pd.DataFrame([h3]).to_csv(res / "p5_h3_growth_attenuation.csv", index=False)
    full_tab = pd.DataFrame({"term": pref["names"], "beta": pref["b"], "hc3_se": pref["se"], "p": pref["p"], "ci_lo": pref["lo"], "ci_hi": pref["hi"]})
    full_tab.to_csv(res / "p5_preferred_model_full_coefficients.csv", index=False)
    # strict vs broad, preferred
    D2 = C.complete(E, "ai_flag_broad"); br = C.fit(D2, "ai_flag_broad", C.ORDER)
    pd.DataFrame([row("preferred, strict AI", pref), row("preferred, broad AI", br)]).to_csv(res / "p5_strict_vs_broad.csv", index=False)

    # interactions (period dummies instead of year FE for AI x PostGenAI)
    inter = []; secondary = {}
    S = D.copy(); S["ai_x_strategic"] = S[ai] * S["strategic"]
    r4 = C.fit(S, ai, C.ORDER, extra=S[["ai_x_strategic"]]); names = list(r4["X"].columns); j = names.index("ai_x_strategic")
    inter.append({"term": "AI x Strategic (H4)", "beta": r4["b"][j], "se": r4["se"][j], "p": r4["p"][j], "ci_lo": r4["lo"][j], "ci_hi": r4["hi"][j], "N": r4["n"],
                  "effect_strategic": r4["b"][1] + r4["b"][j], "effect_sponsor_other": r4["b"][1]}); secondary["H4 AI x Strategic"] = r4["p"][j]
    S["ai_x_post"] = S[ai] * pd.to_numeric(S["post_genai"], errors="coerce")
    r5 = C.fit(S, ai, C.ORDER, extra=S[["ai_x_post"]], fe_year=False); names = list(r5["X"].columns); j = names.index("ai_x_post")
    inter.append({"term": "AI x PostGenAI (H5, two-sided reported)", "beta": r5["b"][j], "se": r5["se"][j], "p": r5["p"][j], "ci_lo": r5["lo"][j], "ci_hi": r5["hi"][j], "N": r5["n"],
                  "effect_post": r5["b"][1] + r5["b"][j], "effect_pre": r5["b"][1]}); secondary["H5 AI x PostGenAI"] = r5["p"][j]
    S["ai_x_public"] = S[ai] * S["public"]
    r6 = C.fit(S, ai, C.ORDER, extra=S[["ai_x_public"]]); j = list(r6["X"].columns).index("ai_x_public")
    inter.append({"term": "AI x Public (exploratory, not in Holm family)", "beta": r6["b"][j], "se": r6["se"][j], "p": r6["p"][j], "ci_lo": r6["lo"][j], "ci_hi": r6["hi"][j], "N": r6["n"],
                  "effect_public": r6["b"][1] + r6["b"][j], "effect_private": r6["b"][1]})
    pd.DataFrame(inter).to_csv(res / "p5_interactions.csv", index=False)

    # H2 takeover premium (public sample): ln(1+premium_1d); period dummies, fundamentals, strategic; no sector FE (small N)
    Pm = A[A["in_premium_final"] == 1].copy(); Pm["ln1p_premium_1d"] = np.log1p(Pm["premium_1d"]); h2 = {}
    P = Pm.dropna(subset=["ln1p_premium_1d", ai, "revenue_growth", "ebitda_margin", "ln_revenue", "strategic", "announce_year", "post_genai"])
    if len(P) >= 15 and P[ai].nunique() == 2:
        G = C.groups(P, ai, fe_year=False); X = pd.concat([pd.Series(1.0, index=P.index, name="const"), P[ai].astype(float), G["growth"], G["profitability"], G["size"], G["year"], P[["strategic"]].astype(float)], axis=1)
        o = C.ols(P["ln1p_premium_1d"], X.to_numpy(), list(X.columns), 3)
        h2 = {"beta_AI": o["b"][1], "se": o["se"][1], "p": o["p"][1], "ci_lo": o["lo"][1], "ci_hi": o["hi"][1], "N": o["n"], "AI_N": int((P[ai] == 1).sum())}
        secondary["H2 takeover premium"] = o["p"][1]
        raw_gap = P.loc[P[ai] == 1, "premium_1d"].median() - P.loc[P[ai] == 0, "premium_1d"].median(); h2["raw_median_gap"] = raw_gap
    pd.DataFrame([h2] if h2 else [{"status": "not estimable (public premium sample too small or no AI/non-AI contrast)", "N": len(P)}]).to_csv(res / "p5_premium_model.csv", index=False)

    # EV/EBITDA secondary (positive EBITDA only)
    Bd = A[A["in_ebitda_final"] == 1].copy(); Bd = C.complete(Bd, ai, "ln_ev_ebitda") if len(Bd) else Bd
    if len(Bd) >= 15 and Bd[ai].nunique() == 2:
        rb = C.fit(Bd, ai, C.ORDER, y="ln_ev_ebitda"); pd.DataFrame([row("EV/EBITDA preferred", rb)]).to_csv(res / "p5_ev_ebitda_model.csv", index=False)

    # subsector groups vs non-AI (preferred controls)
    sub = []
    for g in sorted(D["ai_subsector_group"].dropna().unique()):
        s = D[(D[ai] == 0) | (D["ai_subsector_group"] == g)].copy(); s["g"] = (s["ai_subsector_group"] == g).astype(int)
        n_g = int(s["g"].sum())
        if n_g >= 8:
            r = C.fit(s, "g", C.ORDER); sub.append(row(g, r, {"group_N": n_g})); secondary[f"Subsector {g}"] = r["p_ai"]
        else:
            sub.append({"model": g, "group_N": n_g, "note": "suppressed: below minimum cell size 8"})
    pd.DataFrame(sub).to_csv(res / "p5_subsector_groups.csv", index=False)
    hp = C.holm(secondary) if secondary else {}
    pd.DataFrame([{"test": k, "raw_p": v, "holm_p": hp[k]} for k, v in secondary.items()]).to_csv(res / "p5_secondary_family_holm.csv", index=False)

    # H1 statement (one-sided, confirmatory)
    from scipy import stats
    p1 = float(stats.t.sf(pref["t"][1], max(pref["n"] - pref["k"], 1)))
    h1 = {"H1_beta": pref["beta"], "H1_pct": C.pct(pref["beta"]), "ci_lo": pref["lo_ai"], "ci_hi": pref["hi_ai"], "one_sided_p": p1, "N": pref["n"], "strict_AI_N": nA,
          "meets_min_effect_0.15": bool(pref["beta"] >= C.THRESH), "note": "ASSOCIATION; not causal"}
    pd.DataFrame([h1]).to_csv(res / "p5_h1_primary.csv", index=False)
    (root / "results" / "phase5_report.md").write_text(
        ("# SYNTHETIC DATA - NOT FINDINGS\n\n" if synthetic else "# PILOT / NON-SYSTEMATIC DATA - NOT FINDINGS\n\n" if pilot else "# Phase 5 baseline regressions\n\n")
        + f"Preferred model N={pref['n']}, strict AI N={nA}. H1 beta={pref['beta']:.3f} (HC3 95% CI {pref['lo_ai']:.3f}, {pref['hi_ai']:.3f}). Association only.\n\n"
        + prog.round(3).to_markdown(index=False) + "\n")
    mf = root / "docs" / "BASELINE_V1_PHASE5.json"
    ref = {"DATA_VERSION": "BASELINE_V1_PHASE5", "analysis_sha256": man["sha256"], "H1_beta": round(float(pref["beta"]), 8), "N": int(pref["n"]), "strict_AI_N": nA,
           "created": str(date.today()), "synthetic": synthetic, "pilot": pilot}
    if mf.exists():
        old = json.loads(mf.read_text())
        if old["analysis_sha256"] == man["sha256"] and abs(old["H1_beta"] - ref["H1_beta"]) > 1e-6:
            raise SystemExit("PHASE 5: baseline H1 changed on identical frozen data - model error. Create BASELINE_V2 with deviations_log entry.")
    else:
        mf.write_text(json.dumps(ref, indent=2))
    print(f"Phase 5 complete. N={pref['n']} strictAI={nA} beta={pref['beta']:.3f}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent)); ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args(); raise SystemExit(main(Path(a.root), a.boot))
