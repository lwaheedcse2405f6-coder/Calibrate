"""Simulated fields + each rep's stated forecast -> backend/data/deals.csv.

Run:  python -m app.sim.generate      (fixed seed: identical output every time)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.sim import prepare as prep
from app.sim.personas import PERSONAS

SEED = 42
OUT = Path(__file__).resolve().parents[2] / "data" / "deals.csv"
COLUMNS = ["deal_id", "rep_id", "rep_name", "account", "product", "amount_inr",
           "forecast_date", "close_date", "quarter", "n_contacts", "has_finance_contact",
           "has_champion", "competitor", "stated_prob", "outcome", "traits"]


def stated_prob(base: float, rep: dict, traits: list[str], quarter: str,
                rng: np.random.Generator) -> float:
    p = base
    for b in rep["biases"]:
        applies = b["trait"] == "overall" or b["trait"] in traits
        active = "until" not in b or quarter <= b["until"]
        if applies and active:
            p += b["shift"]
    p += rng.normal(0, 0.05)
    return float(min(0.97, max(0.05, p)))


def _sample(d: pd.DataFrame, per_quarter: int, pending: int, seed: int) -> pd.DataFrame:
    """~per_quarter closed deals per rep per quarter, plus up to `pending` pending ones."""
    parts = []
    for is_pending, cap in ((False, per_quarter), (True, pending)):
        sub = d[(d["outcome"] == "pending") == is_pending]
        for _, g in sub.groupby(["rep_id", "quarter"], sort=True):
            parts.append(g.sample(n=min(cap, len(g)), random_state=seed))
    return pd.concat(parts)


def build(raw: Path = prep.RAW, seed: int = SEED, per_quarter: int = 25,
          pending: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    deals, base = prep.prepare(raw)
    d = _sample(deals, per_quarter, pending, seed)
    d = d.sort_values("deal_id").reset_index(drop=True)  # fixed order => fixed random draws
    n = len(d)

    # 1. simulated fields Maven lacks
    d["n_contacts"] = rng.choice([1, 2, 3, 4], size=n, p=[0.35, 0.30, 0.20, 0.15])
    d["has_finance_contact"] = rng.random(n) < 0.5
    d["has_champion"] = rng.random(n) < 0.5
    d["competitor"] = rng.random(n) < 0.5

    # 2. traits (exact words shared with Roles 2 and 5; do not rename)
    single = (d["n_contacts"] == 1) & (~d["has_finance_contact"])
    d["traits"] = [
        ";".join(t for t, on in (("single_contact_no_finance", s), ("large_deal", lg),
                                 ("end_of_quarter", eq)) if on)
        for s, lg, eq in zip(single, d["large_deal"], d["end_of_quarter"])
    ]

    # 3-4. stated probability = base rate + bias shift + noise
    d["stated_prob"] = [
        # Bias is applied using information available when the rep forecast,
        # never the later quarter in which the deal happened to close.
        round(stated_prob(base[r.series], PERSONAS[r.rep_id], r.traits.split(";"), r.forecast_quarter, rng), 4)
        for r in d.itertuples()
    ]

    # 5. outcome stays exactly as Maven says. Dates as YYYY-MM-DD strings.
    d["forecast_date"] = d["forecast_date"].dt.strftime("%Y-%m-%d")
    d["close_date"] = d["close_date"].dt.strftime("%Y-%m-%d").fillna("")
    d = d.sort_values(["forecast_date", "deal_id"]).reset_index(drop=True)
    return d[COLUMNS]


def main() -> None:
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"wrote {len(df)} deals to {OUT}")
    print(df.groupby(["rep_id", "quarter"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
