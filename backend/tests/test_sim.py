"""Tests for the data generator. Uses a small fake Maven dataset, so no downloads needed."""
import numpy as np
import pandas as pd
import pytest

from app.sim import generate, prepare
from app.sim.personas import PERSONAS, QUARTERS, REP_ORDER, active_reps
from app.sim.sanity import report

PRODUCTS = [("GTXPro", "GTX", 4821), ("GTK 500", "GTK", 26768), ("MG Special", "MG", 55),
            ("MG Advanced", "MG", 3393), ("GTX Basic", "GTX", 550)]


@pytest.fixture(scope="module")
def raw(tmp_path_factory):
    d = tmp_path_factory.mktemp("maven")
    rng = np.random.default_rng(0)
    pd.DataFrame([("GTX Pro" if p == "GTXPro" else p, s, v) for p, s, v in PRODUCTS],
                 columns=["product", "series", "sales_price"]).to_csv(d / "products.csv", index=False)
    rows = []
    for i in range(6000):
        stage = rng.choice(["Won", "Lost", "Engaging", "Prospecting"], p=[0.42, 0.26, 0.16, 0.16])
        eng = pd.Timestamp("2016-10-20") + pd.Timedelta(days=int(rng.integers(0, 430)))
        close = eng + pd.Timedelta(days=int(rng.integers(5, 90)))
        if stage in ("Won", "Lost") and close > pd.Timestamp("2017-12-31"):
            close = pd.Timestamp("2017-12-31")
        rows.append({
            "opportunity_id": f"OPP{i:05d}", "sales_agent": f"Agent {i % 8}",
            "product": PRODUCTS[i % 5][0],
            "account": None if i % 9 == 0 else f"Acct {i % 40}",
            "deal_stage": stage,
            "engage_date": None if stage == "Prospecting" else eng.strftime("%Y-%m-%d"),
            "close_date": close.strftime("%Y-%m-%d") if stage in ("Won", "Lost") else None,
            "close_value": 0})
    pd.DataFrame(rows).to_csv(d / "sales_pipeline.csv", index=False)
    return d


@pytest.fixture(scope="module")
def deals(raw):
    return generate.build(raw)


def test_columns_are_the_contract(deals):
    assert list(deals.columns) == generate.COLUMNS


def test_same_seed_same_output(raw, deals):
    pd.testing.assert_frame_equal(deals, generate.build(raw))


def test_cleaning(raw):
    sp = prepare.load(raw)
    assert "GTXPro" not in set(sp["product"])
    assert not sp["account"].isna().any()
    assert (sp["amount_inr"] == sp["sales_price"] * 83).all()


def test_outcomes_dates_and_probabilities(deals):
    assert set(deals["outcome"]) <= {"won", "lost", "pending"}
    pend = deals[deals["outcome"] == "pending"]
    assert len(pend) > 0 and (pend["close_date"] == "").all()
    closed = deals[deals["outcome"] != "pending"]
    assert (closed["close_date"] >= closed["forecast_date"]).all()
    assert deals["stated_prob"].between(0.05, 0.97).all()
    assert deals["forecast_date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert deals["quarter"].isin(QUARTERS).all()


def test_trait_words_are_exact(deals):
    words = {t for s in deals["traits"] for t in s.split(";") if t}
    assert words <= {"single_contact_no_finance", "large_deal", "end_of_quarter"}


def test_karan_has_no_history_before_q3(deals):
    karan = deals[deals["rep_id"] == "karan"]
    assert len(karan) > 0
    assert (karan["forecast_date"] >= "2017-07-01").all()
    assert active_reps("2017-Q2") == REP_ORDER[:5]


def test_planted_biases_show_up(deals):
    d = deals.assign(t=deals["traits"].str.split(";"))

    def gap(rep, on):  # stated on the trait minus stated off it
        r = d[d["rep_id"] == rep]
        return r[on(r)]["stated_prob"].mean() - r[~on(r)]["stated_prob"].mean()

    assert gap("priya", lambda r: r["t"].apply(lambda t: "single_contact_no_finance" in t)) > 0.2
    assert gap("meera", lambda r: r["t"].apply(lambda t: "large_deal" in t)) > 0.15
    sana = d[(d["rep_id"] == "sana") & (d["outcome"] != "pending")]
    assert sana[sana["quarter"] <= "2017-Q2"]["stated_prob"].mean() > \
        sana[sana["quarter"] >= "2017-Q3"]["stated_prob"].mean() + 0.15


def test_sana_bias_uses_forecast_quarter_not_close_quarter(raw):
    deals = generate.build(raw)
    _, base = prepare.prepare(raw)
    sana = deals[deals["rep_id"] == "sana"].copy()
    dates = pd.to_datetime(sana["forecast_date"])
    sana["forecast_quarter"] = dates.dt.year.astype(str) + "-Q" + dates.dt.quarter.astype(str)
    series = prepare.load(raw).drop_duplicates("product").set_index("product")["series"]
    sana["unbiased_residual"] = sana["stated_prob"] - sana["product"].map(series).map(base)
    before_improvement = sana[sana["forecast_quarter"] <= "2017-Q2"]
    after_improvement = sana[sana["forecast_quarter"] >= "2017-Q3"]
    assert before_improvement["unbiased_residual"].mean() > 0.15
    assert abs(after_improvement["unbiased_residual"].mean()) < 0.08


def test_sanity_report_runs(deals):
    assert {"rep", "group", "n", "stated", "actual", "gap"} <= set(report(deals).columns)
    assert set(PERSONAS) == set(REP_ORDER)
