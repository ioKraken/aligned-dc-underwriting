"""Stage 1: ingest the raw deal universe, normalise identities, apply the duplicate protocol.

Input : data_raw/deal_universe_raw.csv  (+ optional data_raw/company_aliases.csv: alias,canonical_name)
Output: data_clean/companies.csv
        data_clean/deals_stage1.csv
        data_clean/deal_bids_history.csv
        data_clean/duplicates_log.csv      (every merge / demotion is logged, nothing silently dropped)

This script NEVER selects deals. It only reads what is in the raw universe file, which is built from
systematic screens (see docs/universe_construction_protocol.md), not from a list of known AI deals.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils as U  # noqa: E402

REQUIRED = ["target_name", "buyer_name", "announcement_date", "close_date", "deal_status", "target_country",
            "buyer_country", "target_public_private", "buyer_type", "sector", "subsector",
            "headline_transaction_value", "source_universe", "source_url", "notes"]
OPTIONAL = ["deal_id", "deal_type", "ticker", "exchange", "website", "structural_exclusion",
            "headline_value_type", "offer_price", "mixed_consortium", "target_former_name"]


def load_aliases(root: Path) -> dict[str, str]:
    p = root / "data_raw" / "company_aliases.csv"
    if not p.exists():
        return {}
    a = U.read_csv_safe(p)
    return {U.normalize_name(r.alias): r.canonical_name for r in a.itertuples()}


def canonical(name: str, aliases: dict[str, str]) -> str:
    n = U.normalize_name(name)
    return U.normalize_name(aliases.get(n, name)) if n in aliases else n


def make_deal_id(key: str) -> str:
    return "D" + hashlib.sha1(key.encode()).hexdigest()[:10].upper()


def main(root: Path) -> None:
    raw_path = root / "data_raw" / "deal_universe_raw.csv"
    df = U.read_csv_safe(raw_path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"deal_universe_raw.csv is missing required columns: {missing}")
    for c in OPTIONAL:
        if c not in df.columns:
            df[c] = np.nan
    n_raw = len(df)
    if n_raw == 0:
        raise SystemExit("data_raw/deal_universe_raw.csv has no rows. Populate the universe first "
                         "(see README 'What you need to do next'); nothing was fabricated.")
    aliases = load_aliases(root)

    df["announcement_date"] = U.to_date(df["announcement_date"])
    df["close_date"] = U.to_date(df["close_date"])
    df["norm_target"] = df["target_name"].map(lambda x: canonical(x, aliases))
    df["norm_buyer"] = df["buyer_name"].map(lambda x: canonical(x, aliases))
    df["deal_status"] = df["deal_status"].str.strip().str.lower().str.replace(" ", "_")
    df["target_country"] = df["target_country"].map(U.iso2)
    df["buyer_country"] = df["buyer_country"].map(U.iso2)
    df["canonical_key"] = df["norm_target"] + "|" + df["announcement_date"].dt.strftime("%Y-%m-%d").fillna("NaT") + "|" + df["norm_buyer"]

    dup_log: list[dict] = []

    # --- 1. exact duplicates on canonical key: merge, keeping the most complete record ---------------
    df["_fill"] = df.notna().sum(axis=1)
    df = df.sort_values(["canonical_key", "_fill"], ascending=[True, False])
    merged_rows = []
    for key, g in df.groupby("canonical_key", sort=False):
        if len(g) > 1:
            base = g.iloc[0].copy()
            for _, other in g.iloc[1:].iterrows():
                for col in df.columns:
                    if pd.isna(base[col]) and pd.notna(other[col]):
                        base[col] = other[col]
            srcs = "; ".join(sorted({str(s) for s in g["source_universe"].dropna()}))
            base["source_universe"] = srcs
            dup_log.append({"type": "exact_duplicate_merged", "canonical_key": key, "n_records": len(g),
                            "deal_ids": ";".join(g["deal_id"].fillna("").astype(str)), "action": "merged; sources concatenated"})
            merged_rows.append(base)
        else:
            merged_rows.append(g.iloc[0])
    df = pd.DataFrame(merged_rows).drop(columns=["_fill"]).reset_index(drop=True)

    # --- 2. deal_id assignment ------------------------------------------------------------------
    df["deal_id"] = df.apply(lambda r: r["deal_id"] if isinstance(r["deal_id"], str) and r["deal_id"].strip()
                             else make_deal_id(r["canonical_key"]), axis=1)
    if df["deal_id"].duplicated().any():
        bad = df.loc[df["deal_id"].duplicated(keep=False), "deal_id"].unique().tolist()
        raise SystemExit(f"Duplicate deal_id values with different canonical keys: {bad[:10]} ... resolve manually.")

    # --- 3. competing / revised bids: cluster by target within 365 days -------------------------------
    df = df.sort_values(["norm_target", "announcement_date"]).reset_index(drop=True)
    df["contested"] = 0
    df["needs_review"] = 0
    df["duplicate_role"] = "primary"
    bids = []
    for tgt, g in df.groupby("norm_target", sort=False):
        if len(g) < 2 or not tgt:
            continue
        idx = g.index.tolist()
        dates = g["announcement_date"].tolist()
        cluster, clusters = [idx[0]], []
        for i in range(1, len(idx)):
            gap = (dates[i] - dates[i - 1]).days if pd.notna(dates[i]) and pd.notna(dates[i - 1]) else 9999
            if gap <= 365:
                cluster.append(idx[i])
            else:
                clusters.append(cluster)
                cluster = [idx[i]]
        clusters.append(cluster)
        for cl in clusters:
            if len(cl) < 2:
                continue
            sub = df.loc[cl]
            buyers = set(sub["norm_buyer"])
            completed = sub[sub["deal_status"] == "completed"]
            ambiguous = False
            if len(completed) == 1:
                winner = completed.index[0]
            elif len(completed) > 1 and completed["norm_buyer"].nunique() == 1:
                winner = completed["announcement_date"].idxmax()
            else:
                live = sub[~sub["deal_status"].isin(["withdrawn", "rejected", "terminated"])]
                pool = live if len(live) else sub
                winner = pool["announcement_date"].idxmax()
                ambiguous = len(completed) > 1 or len(live) != 1
            df.loc[winner, "contested"] = int(len(buyers) > 1)
            if ambiguous:
                df.loc[cl, "needs_review"] = 1
            for i in cl:
                if i == winner:
                    continue
                role = "competing_bid" if df.loc[i, "norm_buyer"] != df.loc[winner, "norm_buyer"] else "revised_bid"
                df.loc[i, "duplicate_role"] = role
                bids.append({"deal_id": df.loc[winner, "deal_id"], "bidder": df.loc[i, "buyer_name"],
                             "bid_date": df.loc[i, "announcement_date"],
                             "bid_price": df.loc[i, "offer_price"], "status": role,
                             "source": df.loc[i, "source_url"], "original_deal_id": df.loc[i, "deal_id"]})
                dup_log.append({"type": role + "_demoted_to_history", "canonical_key": df.loc[i, "canonical_key"],
                                "n_records": 1, "deal_ids": df.loc[i, "deal_id"],
                                "action": f"moved to deal_bids_history under winner {df.loc[winner, 'deal_id']}"
                                          + ("; NEEDS MANUAL REVIEW" if ambiguous else "")})
    history = pd.DataFrame(bids, columns=["deal_id", "bidder", "bid_date", "bid_price", "status", "source", "original_deal_id"])
    primary = df[df["duplicate_role"] == "primary"].copy()

    # --- 4. company identity normalisation ------------------------------------------------------------
    comp_rows: dict[str, dict] = {}

    def add_company(name, country, ticker=None, exch=None, web=None, pp=None, sector=None, sub=None, former=None):
        key = canonical(name, aliases)
        if not key:
            return None
        rec = comp_rows.setdefault(key, {"canonical_name": name, "former_name": former, "ticker": ticker,
                                         "exchange": exch, "country": country, "website": web,
                                         "public_private": pp, "sector": sector, "subsector": sub})
        for k, v in (("ticker", ticker), ("exchange", exch), ("website", web), ("country", country),
                     ("public_private", pp), ("sector", sector), ("subsector", sub), ("former_name", former)):
            if pd.isna(rec.get(k)) and isinstance(v, str) and v.strip():
                rec[k] = v
        return key

    for r in primary.itertuples():
        add_company(r.target_name, r.target_country, r.ticker, r.exchange, r.website,
                    str(r.target_public_private).strip().lower() if isinstance(r.target_public_private, str) else None,
                    r.sector, r.subsector, r.target_former_name)
        add_company(r.buyer_name, r.buyer_country)
    companies = pd.DataFrame.from_dict(comp_rows, orient="index").reset_index(names="norm_key")
    companies.insert(0, "company_id", np.arange(1, len(companies) + 1))
    id_of = dict(zip(companies["norm_key"], companies["company_id"]))
    primary["target_id"] = primary["norm_target"].map(id_of)
    primary["buyer_id"] = primary["norm_buyer"].map(id_of)

    # --- 5. write outputs -----------------------------------------------------------------------------
    out = root / "data_clean"
    out.mkdir(exist_ok=True)
    companies.drop(columns=["norm_key"]).to_csv(out / "companies.csv", index=False)
    keep = ["deal_id", "target_id", "buyer_id", "target_name", "buyer_name", "announcement_date", "close_date",
            "deal_status", "target_country", "buyer_country", "target_public_private", "buyer_type", "sector",
            "subsector", "headline_transaction_value", "headline_value_type", "deal_type", "structural_exclusion",
            "mixed_consortium", "contested", "needs_review", "source_universe", "source_url", "notes", "canonical_key"]
    primary[keep].to_csv(out / "deals_stage1.csv", index=False)
    history.to_csv(out / "deal_bids_history.csv", index=False)
    pd.DataFrame(dup_log, columns=["type", "canonical_key", "n_records", "deal_ids", "action"]).to_csv(
        out / "duplicates_log.csv", index=False)
    print(f"raw rows: {n_raw} | after exact-duplicate merge + deal-id: {len(df)} | primary deals: {len(primary)} "
          f"| bids in history: {len(history)} | companies: {len(companies)} | needs_review: {int(primary['needs_review'].sum())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="project root (default: parent of src/)")
    main(U.project_root(ap.parse_args().root))
