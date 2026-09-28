"""Clean the Maven CRM data, pick six reps, mark the deal traits that need no simulation."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.sim.personas import MAVEN_AGENT, PERSONAS, REP_ORDER

RAW = Path(__file__).resolve().parents[2] / "data" / "maven"
INR_PER_USD = 83
LARGE_PRODUCTS = {"GTX Pro", "GTK 500"}
OUTCOME = {"Won": "won", "Lost": "lost", "Engaging": "pending"}


def load(raw: Path = RAW) -> pd.DataFrame:
    sp = pd.read_csv(raw / "sales_pipeline.csv")
    pr = pd.read_csv(raw / "products.csv")
    sp["product"] = sp["product"].replace({"GTXPro": "GTX Pro"})
    sp["account"] = sp["account"].fillna("Unknown")
    sp = sp.merge(pr, on="product", how="left")
    if sp["sales_price"].isna().any():
        bad = sp.loc[sp["sales_price"].isna(), "product"].unique().tolist()
        raise ValueError(f"products with no price in products.csv: {bad}")
    sp["amount_inr"] = (sp["sales_price"] * INR_PER_USD).round().astype(int)
    sp["engage_date"] = pd.to_datetime(sp["engage_date"])
    sp["close_date"] = pd.to_datetime(sp["close_date"])
    return sp


def load_accounts(raw: Path = RAW) -> pd.DataFrame:
    acc = pd.read_csv(raw / "accounts.csv")
    acc["sector"] = acc["sector"].replace({"technolgy": "technology"})
    return acc


def quarter_label(dates: pd.Series) -> pd.Series:
    return dates.dt.year.astype(str) + "-Q" + dates.dt.quarter.astype(str)


def is_end_of_quarter(engage: pd.Series) -> pd.Series:
    """True when engage_date is in the last 14 days of its calendar quarter."""
    qend = engage.dt.to_period("Q").dt.end_time.dt.normalize()
    return (qend - engage.dt.normalize()).dt.days <= 13


def pick_reps(sp: pd.DataFrame, n: int = 6) -> list[str]:
    """The n agents with the most closed deals (ties broken by name, so it is repeatable)."""
    closed = sp[sp["deal_stage"].isin(["Won", "Lost"])]
    counts = closed.groupby("sales_agent").size().reset_index(name="n")
    counts = counts.sort_values(["n", "sales_agent"], ascending=[False, True])
    return counts["sales_agent"].head(n).tolist()


def base_rates(sp: pd.DataFrame) -> dict[str, float]:
    """Win rate per product series over ALL closed Maven deals (about 0.6)."""
    closed = sp[sp["deal_stage"].isin(["Won", "Lost"])]
    return (closed["deal_stage"].eq("Won").groupby(closed["series"]).mean()).to_dict()


def prepare(raw: Path = RAW) -> tuple[pd.DataFrame, dict[str, float]]:
    """Return (deals of the six reps, base rate per series).

    Prospecting deals are dropped: Maven gives them no dates, so they cannot be placed
    in a quarter. "Pending" deals are the Engaging ones (they have an engage_date only).
    """
    sp = load(raw)
    agents = pick_reps(sp, len(REP_ORDER))
    MAVEN_AGENT.clear()
    MAVEN_AGENT.update(dict(zip(REP_ORDER, agents)))
    base = base_rates(sp)

    d = sp[sp["sales_agent"].isin(agents) & sp["deal_stage"].isin(OUTCOME)].copy()
    d = d.dropna(subset=["engage_date"])
    d["outcome"] = d["deal_stage"].map(OUTCOME)
    d = d[(d["outcome"] == "pending") | d["close_date"].notna()]
    d = d[(d["outcome"] == "pending") | (d["close_date"] >= d["engage_date"])]

    by_agent = {v: k for k, v in MAVEN_AGENT.items()}
    d["rep_id"] = d["sales_agent"].map(by_agent)
    d["rep_name"] = d["rep_id"].map(lambda r: PERSONAS[r]["name"])
    d["deal_id"] = d["opportunity_id"]
    d["forecast_date"] = d["engage_date"]
    # quarter = calendar quarter of close_date (of engage_date for pending deals)
    d["quarter"] = quarter_label(d["close_date"].where(d["outcome"] != "pending", d["engage_date"]))
    d["forecast_quarter"] = quarter_label(d["engage_date"])
    d["large_deal"] = d["product"].isin(LARGE_PRODUCTS)
    d["end_of_quarter"] = is_end_of_quarter(d["engage_date"])

    # A rep's deals from before they joined are left out (Karan appears from 2017-Q3).
    joins = d["rep_id"].map(lambda r: PERSONAS[r]["joins"])
    d = d[d["forecast_quarter"] >= joins]
    return d.sort_values("deal_id").reset_index(drop=True), base
