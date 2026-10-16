"""Shared estimation library for Phases 5-7 (numpy only; statsmodels is not installed).
OLS with HC3, design builders for the frozen progressive models, pairs bootstrap, permutation placebo, Gelbach decomposition.
Everything here is method code: it proves nothing about AI valuation until run on real, frozen data."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import numpy as np, pandas as pd

SEED = 20261006
Y = "ln_ev_revenue"
FUND = {"growth": ["revenue_growth"], "profitability": ["ebitda_margin"], "size": ["ln_revenue"]}
THRESH = 0.15            # Phase 1: minimum economically meaningful beta (log points)
MIN_STRICT_AI, MIN_TOTAL = 30, 100      # Phase 6 power gate (override only in tests)


def sha256(p) -> str:
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()


def load_frozen(root: Path, manifest: str, label: str) -> dict:
    p = root / "docs" / manifest
    if not p.exists():
        raise SystemExit(f"{label} REFUSED: {manifest} not found. Upstream phase must be run and frozen first.")
    m = json.loads(p.read_text()); f = root / "data_clean" / m["file"]
    if not f.exists() or sha256(f) != m["sha256"]:
        raise SystemExit(f"{label} REFUSED: {m['file']} missing or checksum mismatch with {manifest}.")
    return m


def period(d: pd.DataFrame) -> pd.Series:
    yr = pd.to_numeric(d["announce_year"], errors="coerce")
    post = pd.to_numeric(d["post_genai"], errors="coerce")
    return pd.Series(np.where(post == 1, "post_genai", np.where(yr <= 2018, "2015_2018", "2019_pre_genai")), index=d.index)


def dummies(s: pd.Series, prefix: str) -> pd.DataFrame:
    D = pd.get_dummies(s.astype(str), prefix=prefix, drop_first=True, dtype=float)
    return D.loc[:, D.std() > 0]


def groups(d: pd.DataFrame, ai: str = "ai_flag_strict", fe_year: bool = True) -> dict[str, pd.DataFrame]:
    """Control groups in the order of the frozen progressive models. Returns {group: columns}."""
    g = {"growth": d[FUND["growth"]].astype(float), "profitability": d[FUND["profitability"]].astype(float), "size": d[FUND["size"]].astype(float)}
    g["year"] = dummies(d["announce_year"], "yr") if fe_year else dummies(period(d), "per")
    g["sector"] = dummies(d["sector"], "sec")
    g["region"] = dummies(d["region"], "reg")
    g["buyer_public"] = d[["public", "strategic"]].astype(float)
    return g


def ols(y, X, names=None, hc=3):
    """OLS with HC3 (default) / HC1 / classical. X must include a constant. Returns dict."""
    y = np.asarray(y, float); X = np.asarray(X, float); n, k = X.shape
    XtXi = np.linalg.pinv(X.T @ X); b = XtXi @ X.T @ y; e = y - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtXi, X)
    if hc == 3:
        w = e ** 2 / np.clip(1 - h, 1e-8, None) ** 2
    elif hc == 1:
        w = e ** 2 * n / max(n - k, 1)
    else:
        w = np.full(n, e @ e / max(n - k, 1))
    V = XtXi @ (X.T * w) @ X @ XtXi
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    from scipy import stats
    t = b / np.where(se > 0, se, np.nan); df = max(n - k, 1)
    p = 2 * stats.t.sf(np.abs(t), df)
    crit = stats.t.ppf(.975, df)
    ss_res = e @ e; ss_tot = ((y - y.mean()) ** 2).sum()
    return {"b": b, "se": se, "t": t, "p": p, "lo": b - crit * se, "hi": b + crit * se, "n": n, "k": k, "r2": 1 - ss_res / ss_tot if ss_tot > 0 else np.nan,
            "adj_r2": 1 - (1 - (1 - ss_res / ss_tot)) * (n - 1) / max(n - k, 1) if ss_tot > 0 else np.nan, "resid": e, "h": h, "names": names, "V": V}


def design(d: pd.DataFrame, ai: str, keep: list[str], extra: pd.DataFrame | None = None, fe_year: bool = True):
    G = groups(d, ai, fe_year)
    cols = [pd.Series(1.0, index=d.index, name="const"), d[ai].astype(float).rename(ai)]
    for k in keep:
        cols += [G[k][c] for c in G[k].columns]
    if extra is not None:
        cols += [extra[c] for c in extra.columns]
    X = pd.concat(cols, axis=1)
    return X


def complete(d: pd.DataFrame, ai: str, y: str = Y) -> pd.DataFrame:
    need = [y, ai, "revenue_growth", "ebitda_margin", "ln_revenue", "announce_year", "sector", "region", "public", "strategic", "post_genai"]
    x = d.dropna(subset=[c for c in need if c in d.columns]).copy()
    return x


ORDER = ["growth", "profitability", "size", "year", "sector", "region", "buyer_public"]
MODELS = {  # frozen progressive specifications (Phase 1 Section L)
    "(1) AI only": [],
    "(2) + growth, margin, size": ["growth", "profitability", "size"],
    "(3) + year FE": ["growth", "profitability", "size", "year"],
    "(4) + sector FE": ["growth", "profitability", "size", "year", "sector"],
    "(5) + region, public, strategic [PREFERRED]": ORDER,
}


def fit(d, ai, keep, y=Y, hc=3, extra=None, fe_year=True):
    X = design(d, ai, keep, extra, fe_year)
    r = ols(d[y].to_numpy(), X.to_numpy(), list(X.columns), hc)
    i = list(X.columns).index(ai)
    r.update(beta=r["b"][i], se_ai=r["se"][i], p_ai=r["p"][i], lo_ai=r["lo"][i], hi_ai=r["hi"][i], X=X)
    return r


def pct(b):  # log points -> percent
    return float(np.expm1(b) * 100)


def pairs_bootstrap(d, ai, keep, B=2000, seed=SEED, y=Y):
    rng = np.random.default_rng(seed); n = len(d); out = []
    X = design(d, ai, keep); Xv = X.to_numpy(); yv = d[y].to_numpy(); i = list(X.columns).index(ai)
    for _ in range(B):
        ix = rng.integers(0, n, n)
        if len(np.unique(Xv[ix, i])) < 2:
            continue
        b = np.linalg.pinv(Xv[ix].T @ Xv[ix]) @ Xv[ix].T @ yv[ix]; out.append(b[i])
    o = np.array(out); return {"mean": o.mean(), "lo": np.percentile(o, 2.5), "hi": np.percentile(o, 97.5), "B": len(o), "draws": o}


def placebo(d, ai, keep, B=5000, seed=SEED, strata: pd.Series | None = None, y=Y):
    """Permutation reassignment of the AI label (FWL: residualise once). Returns observed beta, null draws, one-sided p (>=)."""
    rng = np.random.default_rng(seed)
    X = design(d, ai, keep).drop(columns=[ai]).to_numpy(); yv = d[y].to_numpy(); a0 = d[ai].to_numpy(float)
    Q, _ = np.linalg.qr(X); My = yv - Q @ (Q.T @ yv)
    def beta(A):
        MA = A - Q @ (Q.T @ A); return (MA * My[:, None]).sum(0) / (MA ** 2).sum(0)
    obs = beta(a0[:, None])[0]
    A = np.empty((len(a0), B))
    if strata is None:
        for j in range(B):
            A[:, j] = rng.permutation(a0)
    else:
        idx = [np.where(strata.to_numpy() == s)[0] for s in pd.unique(strata)]
        for j in range(B):
            col = a0.copy()
            for ii in idx:
                col[ii] = rng.permutation(a0[ii])
            A[:, j] = col
    null = beta(A)
    return {"obs": float(obs), "null_mean": float(null.mean()), "null_sd": float(null.std()), "p_one_sided": float((1 + (null >= obs).sum()) / (B + 1)),
            "p_two_sided": float((1 + (np.abs(null) >= abs(obs)).sum()) / (B + 1)), "B": B, "draws": null}


def gelbach(d, ai, y=Y, order=ORDER):
    """Exact additive decomposition of beta_base - beta_full into control groups (Gelbach 2016, OLS with constant).
    beta_base = AI-only coefficient, beta_full = preferred model. Group contribution = gamma_g' delta_g where gamma_g is from
    regressing each control in group g on AI and delta_g its coefficient in the full model. Not causal mediation."""
    base = fit(d, ai, [], hc=3); full = fit(d, ai, order, hc=3)
    X = full["X"]; names = list(X.columns); G = groups(d, ai)
    a = np.column_stack([np.ones(len(d)), d[ai].to_numpy(float)]); A = np.linalg.pinv(a.T @ a) @ a.T
    rows = []
    for g in order:
        cols = list(G[g].columns)
        if not cols:
            rows.append({"group": g, "contribution": 0.0}); continue
        gam = (A @ G[g].to_numpy(float))[1]       # slope of each control on AI
        dl = np.array([full["b"][names.index(c)] for c in cols])
        rows.append({"group": g, "contribution": float(gam @ dl)})
    t = pd.DataFrame(rows); tot = t["contribution"].sum()
    t["share_of_raw_beta"] = t["contribution"] / base["beta"] if abs(base["beta"]) > 1e-12 else np.nan
    chk = base["beta"] - full["beta"]
    return t, {"beta_base": base["beta"], "beta_full": full["beta"], "attenuation": chk, "sum_contrib": tot, "max_abs_gap": abs(chk - tot)}


def holm(p: dict[str, float]) -> dict[str, float]:
    items = sorted(p.items(), key=lambda kv: kv[1]); m = len(items); adj = {}; run = 0
    for i, (k, v) in enumerate(items):
        run = max(run, min(1, (m - i) * v)); adj[k] = run
    return adj


# ----------------------------------------------------------------------------------------------- matching (Phase 6)
def cem(d, ai, y=Y, bins=3):
    """Coarsened exact matching: exact on sector x period x public; growth, margin, size coarsened into quantile bins.
    ATT-style weights: AI units weight 1; non-AI weight = (n_AI_stratum / n_nonAI_stratum) * (N_nonAI_matched / N_AI_matched)."""
    x = d.copy().reset_index(drop=True)
    for c, nm in (("revenue_growth", "g"), ("ebitda_margin", "m"), ("ln_revenue", "s")):
        x[f"_b_{nm}"] = pd.qcut(x[c].rank(method="first"), bins, labels=False, duplicates="drop")
    x["_per"] = period(x)
    keys = ["sector", "_per", "public", "_b_g", "_b_m", "_b_s"]
    st = x.groupby(keys, dropna=False)[ai].agg(["sum", "count"]); st["n0"] = st["count"] - st["sum"]
    ok = st[(st["sum"] > 0) & (st["n0"] > 0)]
    x = x.join(ok[["sum", "n0"]].rename(columns={"sum": "_n1", "n0": "_n0"}), on=keys)
    m = x["_n1"].notna()
    x["w"] = 0.0
    x.loc[m & (x[ai] == 1), "w"] = 1.0
    x.loc[m & (x[ai] == 0), "w"] = x["_n1"] / x["_n0"]
    nm1, nm0 = int(((x["w"] > 0) & (x[ai] == 1)).sum()), int(((x["w"] > 0) & (x[ai] == 0)).sum())
    if nm1 > 0 and nm0 > 0:
        x.loc[(x[ai] == 0) & (x["w"] > 0), "w"] *= nm1 / x.loc[(x[ai] == 0) & (x["w"] > 0), "w"].sum()
    return x, nm1, nm0


def wls_att(x, ai, y=Y):
    z = x[x["w"] > 0]
    if z[ai].nunique() < 2:
        return None
    X = np.column_stack([np.ones(len(z)), z[ai].to_numpy(float)]); sw = np.sqrt(z["w"].to_numpy())
    r = ols(sw * z[y].to_numpy(), X * sw[:, None], ["const", ai], 3)
    return {"beta": r["b"][1], "se": r["se"][1], "lo": r["lo"][1], "hi": r["hi"][1], "p": r["p"][1], "n": len(z)}


def cem_boot(d, ai, B=500, seed=SEED, y=Y):
    rng = np.random.default_rng(seed); out = []
    for _ in range(B):
        s = d.iloc[rng.integers(0, len(d), len(d))].reset_index(drop=True)
        if s[ai].nunique() < 2: continue
        x, a, b = cem(s, ai, y)
        if a and b:
            r = wls_att(x, ai, y)
            if r: out.append(r["beta"])
    o = np.array(out); return (float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5)), len(o)) if len(o) > 20 else (np.nan, np.nan, len(o))


def psm(d, ai, y=Y, k=3, caliper_sd=0.25, seed=SEED):
    """Logit propensity (growth, margin, size, public, strategic, period, sector), 1:k nearest neighbour WITH replacement, caliper = 0.25 SD of logit."""
    from sklearn.linear_model import LogisticRegression
    G = groups(d, ai, fe_year=False)
    X = pd.concat([G["growth"], G["profitability"], G["size"], G["year"], G["sector"], G["buyer_public"]], axis=1).to_numpy(float)
    mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1
    lr = LogisticRegression(C=1e6, max_iter=2000).fit((X - mu) / sd, d[ai].to_numpy(int))
    ps = np.clip(lr.predict_proba((X - mu) / sd)[:, 1], 1e-6, 1 - 1e-6); lg = np.log(ps / (1 - ps)); cal = caliper_sd * lg.std()
    t = np.where(d[ai].to_numpy() == 1)[0]; c = np.where(d[ai].to_numpy() == 0)[0]; yv = d[y].to_numpy(); diffs = []; used = set(); dropped = 0
    for i in t:
        dist = np.abs(lg[c] - lg[i]); o = np.argsort(dist)[:k]; o = o[dist[o] <= cal]
        if len(o) == 0:
            dropped += 1; continue
        used.update(c[o]); diffs.append(yv[i] - yv[c[o]].mean())
    # common support
    lo_s, hi_s = max(lg[t].min(), lg[c].min()), min(lg[t].max(), lg[c].max())
    return {"att": float(np.mean(diffs)) if diffs else np.nan, "n_treated": len(t), "n_matched_treated": len(diffs), "dropped_caliper": dropped,
            "n_controls_used": len(used), "caliper": float(cal), "common_support": (float(lo_s), float(hi_s)), "ps": ps, "logit": lg, "diffs": np.array(diffs)}


def psm_boot(d, ai, B=300, seed=SEED, y=Y):
    rng = np.random.default_rng(seed); out = []
    for _ in range(B):
        s = d.iloc[rng.integers(0, len(d), len(d))].reset_index(drop=True)
        if s[ai].nunique() < 2 or s[ai].sum() < 3: continue
        try:
            r = psm(s, ai, y)
        except Exception:
            continue
        if np.isfinite(r["att"]): out.append(r["att"])
    o = np.array(out); return (float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5)), len(o)) if len(o) > 20 else (np.nan, np.nan, len(o))
