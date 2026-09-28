"""Do the planted biases jump out?  Run: python -m app.sim.sanity

Per rep and trait: average stated forecast vs actual win rate (closed deals only).
Expect e.g. Priya single_contact_no_finance ~0.88 stated vs ~0.6 actual.
"""
from __future__ import annotations

import pandas as pd

from app.sim.generate import OUT
from app.sim.personas import REP_ORDER

TRAITS = ["single_contact_no_finance", "large_deal", "end_of_quarter"]


def report(df: pd.DataFrame) -> pd.DataFrame:
    closed = df[df["outcome"] != "pending"].copy()
    closed["won"] = (closed["outcome"] == "won").astype(float)
    closed["trait_set"] = closed["traits"].fillna("").str.split(";")
    rows = []
    for rep in REP_ORDER:
        r = closed[closed["rep_id"] == rep]
        groups = {"all deals": r}
        groups.update({t: r[r["trait_set"].apply(lambda ts, t=t: t in ts)] for t in TRAITS})
        for name, g in groups.items():
            if len(g):
                rows.append({"rep": rep, "group": name, "n": len(g),
                             "stated": round(g["stated_prob"].mean(), 2),
                             "actual": round(g["won"].mean(), 2),
                             "gap": round(g["stated_prob"].mean() - g["won"].mean(), 2)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print(report(pd.read_csv(OUT)).to_string(index=False))
