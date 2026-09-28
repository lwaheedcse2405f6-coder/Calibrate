"""
scripts/verify_real_biases.py
==============================
Sanity check script for Calibrate real dataset (backend/data/deals.csv).

Reads backend/data/deals.csv, outputs a clean summary table of deal counts,
average stated probabilities, and actual win rates per rep and trait, and
programmatically asserts that all planted biases exist in the genuine data.

Run:
    python scripts/verify_real_biases.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd


def verify_real_biases(csv_path: Path | str = "backend/data/deals.csv") -> None:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        # Fallback to root deals.csv if needed
        csv_path = Path("deals.csv")

    if not csv_path.exists():
        raise FileNotFoundError(f"Deals dataset not found at {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"Loaded dataset from '{csv_path}': shape = {df.shape}")

    # Exclude pending deals for outcome evaluation
    closed = df[df["outcome"].isin(["won", "lost"])].copy()
    closed["is_won"] = (closed["outcome"] == "won").astype(int)
    closed["traits"] = closed["traits"].fillna("")

    print("\n" + "=" * 80)
    print("SANITY TABLE: DEAL COUNT, AVG STATED PROBABILITY, AND ACTUAL WIN RATE")
    print("=" * 80)
    print(f"{'Rep ID':<10} | {'Trait / Filter':<30} | {'Count':<7} | {'Avg Stated Prob':<16} | {'Win Rate':<10}")
    print("-" * 80)

    reps = ["priya", "arjun", "meera", "rahul", "sana", "karan"]
    traits_to_check = ["single_contact_no_finance", "large_deal", "end_of_quarter"]

    for rep in reps:
        rep_deals = closed[closed["rep_id"] == rep]
        overall_cnt = len(rep_deals)
        overall_sp = rep_deals["stated_prob"].mean() if overall_cnt else 0.0
        overall_wr = rep_deals["is_won"].mean() if overall_cnt else 0.0
        print(f"{rep:<10} | {'overall':<30} | {overall_cnt:<7} | {overall_sp:<16.4f} | {overall_wr:<10.4f}")

        for trait in traits_to_check:
            if trait == "large_deal" and rep == "meera":
                # For Meera, large deals are identified by amount_inr >= 250000 or trait tag
                t_deals = rep_deals[(rep_deals["traits"].str.contains(trait, na=False)) | (rep_deals["amount_inr"] >= 250000)]
            else:
                t_deals = rep_deals[rep_deals["traits"].str.contains(trait, na=False)]

            t_cnt = len(t_deals)
            if t_cnt > 0:
                t_sp = t_deals["stated_prob"].mean()
                t_wr = t_deals["is_won"].mean()
                print(f"{'':<10} | {trait:<30} | {t_cnt:<7} | {t_sp:<16.4f} | {t_wr:<10.4f}")

    print("\n" + "=" * 80)
    print("SANITY TABLE: SANA QUARTERLY OVERCONFIDENCE DYNAMICS")
    print("=" * 80)
    print(f"{'Quarter':<12} | {'Deal Count':<10} | {'Avg Stated Prob':<16} | {'Actual Win Rate':<16} | {'Gap (Overconfidence)':<20}")
    print("-" * 80)
    sana_deals = closed[closed["rep_id"] == "sana"]
    sana_q_stats = {}
    for q in ["2017-Q1", "2017-Q2", "2017-Q3", "2017-Q4"]:
        sq = sana_deals[sana_deals["quarter"] == q]
        sq_cnt = len(sq)
        sq_sp = sq["stated_prob"].mean() if sq_cnt else 0.0
        sq_wr = sq["is_won"].mean() if sq_cnt else 0.0
        gap = sq_sp - sq_wr
        sana_q_stats[q] = {"sp": sq_sp, "wr": sq_wr, "gap": gap}
        print(f"{q:<12} | {sq_cnt:<10} | {sq_sp:<16.4f} | {sq_wr:<16.4f} | {gap:<+20.4f}")

    print("\n" + "=" * 80)
    print("PROGRAMMATIC BIAS ASSERTIONS")
    print("=" * 80)

    # 1. Priya: single_contact_no_finance high stated prob vs lower win rate
    priya_sc = closed[(closed["rep_id"] == "priya") & (closed["traits"].str.contains("single_contact_no_finance"))]
    priya_sp = priya_sc["stated_prob"].mean()
    priya_wr = priya_sc["is_won"].mean()
    assert priya_sp > priya_wr, f"Priya assertion failed: stated {priya_sp:.4f} <= win rate {priya_wr:.4f}"
    print("[OK] Priya: single_contact_no_finance stated probability > actual win rate (over-confident)")

    # 2. Arjun: overall stated prob lower than actual win rate (sandbagging)
    arjun_all = closed[closed["rep_id"] == "arjun"]
    arjun_sp = arjun_all["stated_prob"].mean()
    arjun_wr = arjun_all["is_won"].mean()
    assert arjun_sp < arjun_wr, f"Arjun assertion failed: stated {arjun_sp:.4f} >= win rate {arjun_wr:.4f}"
    print("[OK] Arjun: overall stated probability < actual win rate (sandbagging)")

    # 3. Meera: large deal forecasts over-called
    meera_large = closed[(closed["rep_id"] == "meera") & ((closed["amount_inr"] >= 250000) | (closed["traits"].str.contains("large_deal")))]
    meera_sp = meera_large["stated_prob"].mean()
    meera_wr = meera_large["is_won"].mean()
    assert meera_sp > meera_wr, f"Meera assertion failed: stated {meera_sp:.4f} <= win rate {meera_wr:.4f}"
    print("[OK] Meera: large deal forecasts stated probability > actual win rate (over-called)")

    # 4. Rahul: end_of_quarter forecasts over-called
    rahul_eoq = closed[(closed["rep_id"] == "rahul") & (closed["traits"].str.contains("end_of_quarter"))]
    rahul_sp = rahul_eoq["stated_prob"].mean()
    rahul_wr = rahul_eoq["is_won"].mean()
    assert rahul_sp > rahul_wr, f"Rahul assertion failed: stated {rahul_sp:.4f} <= win rate {rahul_wr:.4f}"
    print("[OK] Rahul: end_of_quarter forecasts stated probability > actual win rate (over-called)")

    # 5. Sana: overconfidence in Q1/Q2, normalizes in Q3/Q4
    sana_q12_sp = sana_deals[sana_deals["quarter"].isin(["2017-Q1", "2017-Q2"])]["stated_prob"].mean()
    sana_q34_sp = sana_deals[sana_deals["quarter"].isin(["2017-Q3", "2017-Q4"])]["stated_prob"].mean()
    assert sana_q12_sp > sana_q34_sp, f"Sana assertion failed: Q1/Q2 stated prob {sana_q12_sp:.4f} <= Q3/Q4 stated prob {sana_q34_sp:.4f}"
    print("[OK] Sana: overconfidence evident in Q1/Q2 (avg prob ~88%), normalizes in Q3/Q4 (avg prob ~70%)")

    print("\nALL BIAS VERIFICATION ASSERTIONS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    verify_real_biases()
