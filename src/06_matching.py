"""Phase 6a - matching (CEM primary; PSM nearest-neighbour check) on the frozen analysis file. Gated on the Phase 5 baseline freeze."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd
import p5_common as C


def smd(x, ai, cols, w=None):
    rows = []
    for c in cols:
        a, b = x[x[ai] == 1], x[x[ai] == 0]; wa = np.ones(len(a)) if w is None else a["w"].to_numpy(); wb = np.ones(len(b)) if w is None else b["w"].to_numpy()
        if w is not None: a, b = a[wa > 0], b[wb > 0]; wa, wb = wa[wa > 0], wb[wb > 0]
        ma = np.average(a[c], weights=wa) if len(a) else np.nan; mb = np.average(b[c], weights=wb) if len(b) else np.nan
        sd = np.sqrt((a[c].var() + b[c].var()) / 2) if len(a) > 1 and len(b) > 1 else np.nan
        rows.append({"covariate": c, "mean_AI": ma, "mean_nonAI": mb, "SMD": (ma - mb) / sd if sd else np.nan})
    return pd.DataFrame(rows)


def main(root: Path, B: int) -> int:
    res = root / "results"
    import json
    bp = root / "docs" / "BASELINE_V1_PHASE5.json"
    if not bp.exists(): raise SystemExit("PHASE 6 REFUSED: Phase 5 baseline freeze (docs/BASELINE_V1_PHASE5.json) not found.")
    man = C.load_frozen(root, "ANALYSIS_V1_PHASE4.json", "PHASE 6")
    if json.loads(bp.read_text()).get("estimable") is False:
        print("Phase 6 matching skipped: baseline not estimable."); return 0
    A = pd.read_csv(root / "data_clean" / man["file"], low_memory=False); ai = "ai_flag_strict"
    D = C.complete(A[A["in_evrev_final"] == 1], ai).reset_index(drop=True)
    if D[ai].sum() < 3 or (D[ai] == 0).sum() < 3: raise SystemExit("PHASE 6 matching: too few treated or control deals; not assessable.")
    x, n1, n0 = C.cem(D, ai); r = C.wls_att(x, ai); lo, hi, nb = C.cem_boot(D, ai, B)
    pd.DataFrame([{"method": "CEM (sector x period x public x growth/margin/size terciles)", "ATT_log": r["beta"] if r else np.nan, "hc3_ci_lo": r["lo"] if r else np.nan,
                   "hc3_ci_hi": r["hi"] if r else np.nan, "boot_ci_lo": lo, "boot_ci_hi": hi, "boot_reps": nb, "matched_AI": n1, "matched_nonAI": n0,
                   "AI_total": int((D[ai] == 1).sum()), "share_AI_matched": n1 / max(int((D[ai] == 1).sum()), 1)}]).to_csv(res / "p6_cem.csv", index=False)
    cols = ["revenue_growth", "ebitda_margin", "ln_revenue", "public", "strategic"]
    pd.concat([smd(D, ai, cols).assign(stage="before"), smd(x, ai, cols, w=True).assign(stage="after CEM")]).to_csv(res / "p6_balance_cem.csv", index=False)
    p = C.psm(D, ai); plo, phi, pb = C.psm_boot(D, ai, max(B // 2, 100))
    pd.DataFrame([{"method": "PSM 1:3 NN with replacement, caliper 0.25 SD(logit)", "ATT_log": p["att"], "boot_ci_lo": plo, "boot_ci_hi": phi, "boot_reps": pb,
                   "matched_treated": p["n_matched_treated"], "dropped_by_caliper": p["dropped_caliper"], "controls_used": p["n_controls_used"],
                   "common_support_lo": p["common_support"][0], "common_support_hi": p["common_support"][1]}]).to_csv(res / "p6_psm.csv", index=False)
    print(f"Phase 6 matching done: CEM matched AI {n1}/{int((D[ai]==1).sum())}, PSM ATT {p['att']:.3f}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent)); ap.add_argument("--boot", type=int, default=300)
    a = ap.parse_args(); raise SystemExit(main(Path(a.root), a.boot))
