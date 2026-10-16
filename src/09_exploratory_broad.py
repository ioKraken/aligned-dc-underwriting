"""Exploratory add-on (D-026). NOT the pre-registered test. Uses BROAD AI (intensity >= 1) because strict-AI N is too small, plus a growth-adjusted
precedent-multiple regression that needs no AI label. Gated on the frozen analysis file. Reports estimates with CIs and permutation p-values;
never assigns a Phase 6 classification and never uses the words 'premium found'."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd
import p5_common as C


def main(root: Path, B: int) -> int:
    res = root / "results"; man = C.load_frozen(root, "ANALYSIS_V1_PHASE4.json", "PHASE 9")
    A = pd.read_csv(root / "data_clean" / man["file"], low_memory=False); E = A[A["in_evrev_final"] == 1]
    D = E.dropna(subset=["ln_ev_revenue", "revenue_growth", "ebitda_margin", "ln_revenue"]).reset_index(drop=True)
    D["per"] = C.period(D)
    # A. growth-adjusted precedent regression (no AI)
    X = pd.concat([pd.Series(1.0, index=D.index, name="const"), D[["revenue_growth", "ebitda_margin", "ln_revenue"]].astype(float)], axis=1)
    o = C.ols(D["ln_ev_revenue"], X.to_numpy(), list(X.columns), 3)
    pd.DataFrame({"term": o["names"], "beta": o["b"], "hc3_se": o["se"], "p": o["p"], "ci_lo": o["lo"], "ci_hi": o["hi"]}).assign(N=o["n"], adj_r2=o["adj_r2"]).to_csv(res / "p9_precedent_growth_regression.csv", index=False)
    pred = np.exp(X.to_numpy() @ o["b"]) * np.mean(np.exp(o["resid"]))
    D.assign(predicted_ev_revenue=pred, residual_log=o["resid"])[["deal_id", "target_name", "ev_revenue", "predicted_ev_revenue", "residual_log", "revenue_growth", "ebitda_margin", "ai_flag_broad", "ai_flag_strict"]].to_csv(res / "p9_precedent_residuals.csv", index=False)
    # B. broad AI, progressive (small-N specifications)
    out = []; ai = "ai_flag_broad"
    D["strategic"] = D["strategic"].astype(float); D["public"] = D["public"].astype(float)
    pdm = pd.get_dummies(D["per"], prefix="per", drop_first=True, dtype=float)
    specs = {"(1) broad AI only": None, "(2) + growth, margin, size": ["revenue_growth", "ebitda_margin", "ln_revenue"],
             "(3) + period, strategic": ["revenue_growth", "ebitda_margin", "ln_revenue", "strategic"]}
    for nm, cols in specs.items():
        parts = [pd.Series(1.0, index=D.index, name="const"), D[ai].astype(float)]
        if cols: parts += [D[cols].astype(float)]
        if nm.startswith("(3)"): parts += [pdm]
        Xm = pd.concat(parts, axis=1); r = C.ols(D["ln_ev_revenue"], Xm.to_numpy(), list(Xm.columns), 3)
        # permutation test via FWL
        Z = Xm.drop(columns=[ai]).to_numpy(); Q, _ = np.linalg.qr(Z); My = D["ln_ev_revenue"].to_numpy() - Q @ (Q.T @ D["ln_ev_revenue"].to_numpy()); a0 = D[ai].to_numpy(float)
        rng = np.random.default_rng(C.SEED); A_ = np.column_stack([rng.permutation(a0) for _ in range(B)]); MA = A_ - Q @ (Q.T @ A_); nullb = (MA * My[:, None]).sum(0) / (MA ** 2).sum(0)
        p2 = float((1 + (np.abs(nullb) >= abs(r["b"][1])).sum()) / (B + 1))
        out.append({"model": nm, "treatment": ai, "beta": r["b"][1], "pct": C.pct(r["b"][1]), "ci_lo": r["lo"][1], "ci_hi": r["hi"][1], "hc3_p": r["p"][1], "perm_p_two_sided": p2,
                    "N": r["n"], "AI_N": int(a0.sum()), "label": "EXPLORATORY - broad AI, tiny sample, not the pre-registered test"})
    pd.DataFrame(out).to_csv(res / "p9_broad_ai_models.csv", index=False)
    # C. descriptive premium comparison (public sample)
    P = A[A["in_premium_final"] == 1]
    rows = [{"group": g, "N": int((P[c] == v).sum()), "median_premium_1d": P.loc[P[c] == v, "premium_1d"].median()} for g, c, v in (("broad AI", "ai_flag_broad", 1), ("non-AI", "ai_flag_broad", 0))]
    pd.DataFrame(rows).to_csv(res / "p9_premium_descriptive.csv", index=False)
    print("Phase 9 exploratory done:", pd.DataFrame(out)[["model", "beta", "ci_lo", "ci_hi", "perm_p_two_sided", "N", "AI_N"]].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent)); ap.add_argument("--perm", type=int, default=5000)
    a = ap.parse_args(); raise SystemExit(main(Path(a.root), a.perm))
