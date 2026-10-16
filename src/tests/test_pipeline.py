"""End-to-end test of the Phase 2 pipeline on SYNTHETIC data (fictional companies, fictional numbers).

Run:  python src/tests/test_pipeline.py
The synthetic project is built in a temp directory; nothing is written into data_raw/ or data_clean/ of the real
project. These fixtures exist only to prove the plumbing (dedupe, EV bridge, FX, LTM alignment, waterfall, SQL views,
blind-file redaction, QC checks). They contain NO real deals and say nothing about AI valuations.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SRC = HERE.parent
PROJ = SRC.parent


def build_fixtures(root: Path) -> None:
    rng = np.random.default_rng(1)
    U, T, F, D = [], [], [], []

    def deal(did, target, buyer="SynthBuyer Corp", ann="2023-03-15", close="2023-06-30", status="completed",
             tc="US", bc="US", pp="private", bt="strategic", sector="Application Software", dtype="", ticker="", **_):
        U.append(dict(deal_id=did, target_name=target, buyer_name=buyer, announcement_date=ann, close_date=close,
                      deal_status=status, target_country=tc, buyer_country=bc, target_public_private=pp, buyer_type=bt,
                      sector=sector, subsector="synthetic", headline_transaction_value="ND", source_universe="synthetic_screen",
                      source_url="https://example.invalid/" + str(did), notes="", deal_type=dtype, ticker=ticker, exchange=""))

    def terms(did, ev="", eq="", debt="", cash="", pref="", mi="", cur="USD", fx="", **kw):
        T.append(dict(deal_id=did, currency_original=cur, fx_rate_announcement=fx, enterprise_value=ev, equity_value=eq,
                      debt_assumed=debt, cash_acquired=cash, preferred=pref, minority_interest=mi, cash_pct="100",
                      stock_pct="0", other_pct="0", ev_quality=kw.pop("evq", "A"), **kw))

    def fin(did, end="2022-12-31", rev="", prior="", ebitda="", cur="", q="A", disc="1"):
        F.append(dict(deal_id=did, revenue_period_end=end, revenue_ltm=rev, revenue_prior_ltm=prior, ebitda_ltm=ebitda,
                      ebitda_definition="reported", currency=cur, financials_quality=q, financials_disclosed=disc))

    def desc(did, text):
        D.append(dict(deal_id=did, target_description=text, announcement_description="", website_description="",
                      filing_description="", historical_description="", snapshot_announcement=text, snapshot_minus_12m=""))

    # T01 normal, T02 exact duplicate of T01
    deal("T01", "Alpha Systems Inc", ann="2023-03-15"); terms("T01", ev="300000000"); fin("T01", rev="50000000", prior="40000000", ebitda="5000000")
    desc("T01", "Alpha Systems sells workflow software. Acquired for $300 million, a 6.0x revenue multiple.")
    U.append({**U[0], "deal_id": "", "target_name": "ALPHA SYSTEMS, INC.", "source_universe": "synthetic_news"})
    # T03 public with prices -> 25% premium
    deal("T03", "Beta Cyber plc", tc="GB", pp="public", sector="Cybersecurity", ticker="BETA", ann="2024-02-01", close="2024-07-01")
    terms("T03", ev="900000000", eq="1000000000", debt="50000000", cash="150000000", pref="0", mi="0", offer_price="20", diluted_shares="50000000",
          unaffected_date="2024-01-10", unaffected_reason="no leak found; last close before announcement", unaffected_price_1d="16",
          price_1w="16.5", price_1m="15", vwap_30="15.5", price_90d="14", predeal_market_cap="800000000", cur="USD")
    fin("T03", end="2023-09-30", rev="200000000", prior="160000000", ebitda="30000000")
    desc("T03", "Beta Cyber provides network security using machine learning to detect threats.")
    # T04 competing bids (loser withdrawn, winner completed)
    deal("T04a", "Rival Target Inc", buyer="LoserCo", status="withdrawn", ann="2022-05-01", close="")
    deal("T04b", "Rival Target Inc", buyer="WinnerCo", ann="2022-06-10", close="2022-09-30")
    for i in ("T04a", "T04b"):
        terms(i, ev="150000000"); fin(i, end="2022-03-31", rev="30000000", prior="25000000", ebitda="1000000")
    desc("T04b", "Rival Target builds data pipelines.")
    # T22 revised bid same buyer
    deal("T22a", "Revise Me Ltd", buyer="SameBuyer", ann="2021-01-10", status="announced", close="")
    deal("T22b", "Revise Me Ltd", buyer="SameBuyer", ann="2021-03-01", close="2021-05-30")
    for i in ("T22a", "T22b"):
        terms(i, ev="80000000"); fin(i, end="2020-09-30", rev="20000000", prior="18000000", ebitda="2000000")
    # exclusions / edge cases
    edge = {
        "T05": dict(target="Japan Target KK", tc="JP"),
        "T06": dict(target="Health Co", sector="Healthcare"),
        "T07": dict(target="Minority Stake Co", dtype="minority"),
        "T15": dict(target="Subsidiary Unit", pp="subsidiary"),
        "T17": dict(target="Withdrawn Target", status="withdrawn", close=""),
        "T18": dict(target="Old Deal Inc", ann="2014-06-01", close="2014-09-01"),
    }
    for i, e in edge.items():
        end = "2013-12-31" if i == "T18" else "2022-12-31"
        deal(i, e.pop("target"), **e); terms(i, ev="100000000"); fin(i, end=end, rev="20000000", prior="15000000", ebitda="2000000")
    deal("T08", "Stale Fin Co"); terms("T08", ev="100000000"); fin("T08", end="2021-10-01", rev="20000000", prior="15000000", ebitda="1000000")
    deal("T09", "Misaligned Co"); terms("T09", ev="100000000"); fin("T09", end="2023-03-25", rev="20000000", prior="15000000", ebitda="1000000")
    deal("T10", "Euro Target SA", tc="FR", bc="DE", sector="IT Services"); terms("T10", ev="100000000", cur="EUR", fx="1.1")
    fin("T10", rev="20000000", prior="19000000", ebitda="2000000", cur="EUR")
    deal("T11", "Undisclosed Value Co"); terms("T11", eq="ND", ev="ND", debt="ND", cash="ND", pref="ND", mi="ND"); fin("T11", rev="20000000", prior="15000000", ebitda="1000000")
    deal("T12", "Tiny Revenue Co"); terms("T12", ev="60000000"); fin("T12", rev="3000000", prior="2000000", ebitda="-1000000")
    deal("T13", "Small Deal Co"); terms("T13", ev="20000000"); fin("T13", rev="8000000", prior="7000000", ebitda="1000000")
    deal("T14", "Quality D Co"); terms("T14", ev="100000000", evq="D"); fin("T14", rev="20000000", prior="15000000", ebitda="1000000", q="D")
    deal("T16", "Loss Maker Inc", tc="IL", bc="US", sector="Infrastructure Software"); terms("T16", ev="400000000")
    fin("T16", rev="40000000", prior="25000000", ebitda="-9000000")
    desc("T16", "Loss Maker develops deep learning models for computer vision and generative applications.")
    deal("T20", "Earnout Co"); terms("T20", ev="200000000", contingent_max="50000000", included_in_ev="1"); fin("T20", rev="30000000", prior="25000000", ebitda="3000000")
    deal("T21", "Bridge Gap Co", pp="public", ticker="BGAP"); terms("T21", ev="200000000", eq="130000000", debt="10000000", cash="0", pref="0", mi="0",
        offer_price="10", diluted_shares="13000000", unaffected_date="2023-02-01", unaffected_reason="no leak", unaffected_price_1d="8", price_90d="7")
    fin("T21", rev="30000000", prior="25000000", ebitda="3000000")
    # bulk: normal eligible deals
    sectors = ["Application Software", "Infrastructure Software", "Cybersecurity", "Internet / Digital Platform", "Semiconductors", "IT Services"]
    ai_txt = ["uses machine learning to forecast demand", "provides a generative AI copilot", "builds computer vision for inspection", "plain ERP software vendor"]
    for k in range(60):
        did = f"B{k:03d}"
        yr = 2016 + k % 10
        deal(did, f"Bulk Target {k:03d}", ann=f"{yr}-0{1 + k % 9}-12", close=f"{yr}-1{k % 3}-20", tc=["US", "CA", "GB", "DE", "IL"][k % 5],
             sector=sectors[k % 6], bt=["strategic", "sponsor"][k % 2])
        rev = float(rng.uniform(10e6, 300e6)); ev = rev * float(rng.uniform(1.5, 12))
        terms(did, ev=f"{ev:.0f}", evq="AB"[k % 2]); fin(did, end=f"{yr - 1}-12-31", rev=f"{rev:.0f}", prior=f"{rev * 0.85:.0f}", ebitda=f"{rev * 0.08:.0f}", q="AB"[k % 2])
        desc(did, f"Bulk Target {k:03d} " + ai_txt[k % 4] + ".")
    raw = root / "data_raw"
    pd.DataFrame(U).to_csv(raw / "deal_universe_raw.csv", index=False)
    pd.DataFrame(T).to_csv(raw / "deal_terms_raw.csv", index=False)
    pd.DataFrame(F).to_csv(raw / "financials_raw.csv", index=False)
    pd.DataFrame(D).to_csv(raw / "descriptions_raw.csv", index=False)


def run(script: str, root: Path, check=True) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, str(root / "src" / script), "--root", str(root)], capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"{script} failed")
    return r


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ai_premium_synth_"))
    try:
        for d in ("data_raw", "data_clean", "results", "docs"):
            (tmp / d).mkdir()
        shutil.copytree(SRC, tmp / "src", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        shutil.copytree(PROJ / "sql", tmp / "sql")
        build_fixtures(tmp)
        r1 = run("01_collect.py", tmp); print(r1.stdout.strip())
        r2 = run("02b_build_stage2.py", tmp); print(r2.stdout.strip())
        r3 = run("02_validate_raw.py", tmp, check=False); print(r3.stdout.strip())
        run("02c_coverage_audit.py", tmp)

        s1 = pd.read_csv(tmp / "data_clean" / "deals_stage1.csv")
        hist = pd.read_csv(tmp / "data_clean" / "deal_bids_history.csv")
        s2 = pd.read_csv(tmp / "data_clean" / "deals_stage2.csv").set_index("deal_id")
        dup = pd.read_csv(tmp / "data_clean" / "duplicates_log.csv")

        # ---- dedupe protocol -----------------------------------------------------------------------------------
        assert (dup["type"] == "exact_duplicate_merged").sum() == 1, "T01 duplicate should merge exactly once"
        assert len(hist) == 2 and set(hist["status"]) == {"competing_bid", "revised_bid"}, hist
        assert "T04a" not in s2.index and "T04b" in s2.index and s2.loc["T04b", "contested"] == 1
        assert "T22a" not in s2.index and "T22b" in s2.index and s2.loc["T22b", "contested"] == 0
        assert len(s1) == len(s2)

        # ---- flags & construction ------------------------------------------------------------------------------------
        assert s2.loc["T10", "ev_usd"] == 110_000_000 and abs(s2.loc["T10", "ev_revenue"] - 5.0) < 1e-9, "FX invariance / conversion"
        assert abs(s2.loc["T03", "premium_1d"] - 0.25) < 1e-12
        assert abs(s2.loc["T03", "ev_calculated"] - 900_000_000) < 1 and abs(s2.loc["T03", "ev_recon_diff_pct"]) < 1e-9
        assert abs(s2.loc["T03", "runup_90d"] - (16 / 14 - 1)) < 1e-12
        assert s2.loc["T21", "ev_recon_diff_pct"] > 0.05, "bridge gap should be detected"
        assert s2.loc["T11", "ev_usd"] != s2.loc["T11", "ev_usd"], "ND EV must stay missing (never imputed)"
        assert s2.loc["T09", "alignment_error"] == 1 and np.isnan(s2.loc["T09", "revenue_ltm_usd"])
        assert s2.loc["T08", "financials_stale_flag"] == 1
        assert s2.loc["T20", "contingent_review"] == 1
        assert s2.loc["T15", "structural_exclusion"] == "carveout_no_standalone"
        assert s2.loc["T07", "structural_exclusion"] == "minority"
        assert "ai_flag" not in s2.columns, "final ai_flag must not exist in Phase 2"
        assert s2.loc["T16", "ai_candidate_flag"] == 1 and s2.loc["T01", "ai_candidate_flag"] == 0

        # ---- sample membership ----------------------------------------------------------------------------------------
        ev = s2[s2["in_primary_sample_evrev"] == 1].index
        must_in = {"T01", "T03", "T04b", "T10", "T16", "T21", "T22b", "T20"}
        for i in must_in:
            assert i in ev, f"{i} should be in EV/Rev sample"
        for i in ("T05", "T06", "T07", "T08", "T09", "T11", "T12", "T13", "T14", "T15", "T17", "T18"):
            assert i not in ev, f"{i} should be excluded from EV/Rev sample"
        eb = s2[s2["in_primary_sample_ebitda"] == 1].index
        assert "T16" not in eb and "T01" in eb, "negative EBITDA excluded from EV/EBITDA only"
        pm = s2[s2["in_primary_sample_premium"] == 1].index
        assert set(pm) == {"T03", "T21"}, pm
        # nothing in the stage-2 build may filter on AI
        wf = pd.read_csv(tmp / "results" / "sample_waterfall_phase2.csv")
        assert wf.loc[wf["step"].str.contains("AI coded"), "AI_N"].isna().all()

        # ---- SQL views agree with pandas waterfall ----------------------------------------------------------------------
        vc = pd.read_csv(tmp / "results" / "sql_view_check.csv")
        assert vc["match"].all(), vc
        con = sqlite3.connect(tmp / "data_clean" / "ai_premium.db")
        assert con.execute("SELECT COUNT(*) FROM v_evrev_candidates").fetchone()[0] == len(ev)
        cols = [r[1].lower() for r in con.execute("PRAGMA table_info(v_ai_coding_blind)")]
        assert not any(k in c for c in cols for k in ("ev", "premium", "offer", "price", "equity", "value")), cols
        con.close()

        # ---- blind file -----------------------------------------------------------------------------------------------------
        b = pd.read_csv(tmp / "data_clean" / "ai_coding_blind.csv", dtype=str).fillna("")
        key = pd.read_csv(tmp / "data_clean" / "ai_coding_pool_key.csv")
        assert "coding_pool" not in b.columns and "ai_candidate_flag" not in b.columns
        assert "$300" not in " ".join(b["business_description"]) and "6.0x" not in " ".join(b["business_description"]), "valuation text leaked"
        n_non = ((s2["ai_candidate_flag"] == 0) & (s2["primary_sector"] == 1) & (s2["primary_geography"] == 1) & s2["structural_exclusion"].isna()
                 & (s2["status_primary_sample"] == 1) & (s2["in_period"] == 1)).sum()
        assert (key["coding_pool"] == "audit_random_20pct").sum() == int(np.ceil(0.2 * n_non))

        # ---- validator -----------------------------------------------------------------------------------------------------------
        q = pd.read_csv(tmp / "results" / "data_quality_report.csv")
        errs = q[q["severity"] == "ERROR"]
        assert set(errs["check"]) == {"financial_period_not_before_announcement"}, errs
        assert set(errs["deal_id"]) == {"T09"}
        assert "EV_reconciliation_gap" in set(q["check"]) and "stale_financials_over_365d" in set(q["check"])
        assert r3.returncode == 1

        # ---- data dictionary covers every output column -------------------------------------------------------------------
        sys.path.insert(0, str(SRC))
        import data_dictionary_spec as DD
        for f_ in ("deals_stage2", "financials_stage2"):
            cols_ = pd.read_csv(tmp / "data_clean" / f"{f_}.csv", nrows=1).columns
            miss_ = [c for c in cols_ if not DD.covered(c)]
            assert not miss_, f"undocumented columns in {f_}: {miss_}"

        # ---- determinism -----------------------------------------------------------------------------------------------------------
        k1 = pd.read_csv(tmp / "data_clean" / "ai_coding_pool_key.csv")
        run("02b_build_stage2.py", tmp)
        k2 = pd.read_csv(tmp / "data_clean" / "ai_coding_pool_key.csv")
        assert k1.equals(k2), "audit sample must be reproducible under the fixed seed"
        print("\nALL PIPELINE TESTS PASSED (synthetic data only)")
    finally:
        if "--keep" in sys.argv:
            print("kept:", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
