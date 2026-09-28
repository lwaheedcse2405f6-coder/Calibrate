import json

import pandas as pd
import pytest

from app.replay.engine import run


class FakeServices:
    def __init__(self):
        self.calls = []

    def reflect_calibration_card(self, rep_id, rep_name, quarter):
        self.calls.append(("reflect", quarter, rep_id))
        return {"rules": []}

    def apply_card(self, deal, card):
        self.calls.append(("apply", deal["deal_id"]))
        return float(deal["stated_prob"]), None

    def forecast_item(self, deal):
        self.calls.append(("forecast_item", deal["deal_id"]))
        return {"kind": "forecast", "deal_id": deal["deal_id"]}

    def outcome_item(self, deal):
        self.calls.append(("outcome_item", deal["deal_id"], deal["close_date"]))
        return {"kind": "outcome", "deal_id": deal["deal_id"]}

    def self_check_item(self, deal, prediction, was_right):
        self.calls.append(("self_check_item", deal["deal_id"], was_right))
        return {"kind": "self_check", "deal_id": deal["deal_id"]}

    def retain_many(self, items):
        self.calls.append(("batch", [item["deal_id"] for item in items]))
        assert len(items) <= 25

    def wait_for_memory_processing(self):
        self.calls.append(("wait",))

    def snapshot_beliefs(self, rep_id, quarter, card):
        return {"belief": "No material bias yet", "evidence_count": 1, "confidence": "low"}


@pytest.fixture
def deals_file(tmp_path):
    df = pd.DataFrame([
        {"deal_id": "D1", "rep_id": "priya", "rep_name": "Priya", "account": "A",
         "product": "GTX Pro", "amount_inr": 1000, "forecast_date": "2017-03-28",
         "close_date": "2017-04-20", "quarter": "2017-Q2", "n_contacts": 1,
         "has_finance_contact": False, "has_champion": True, "competitor": False,
         "stated_prob": 0.9, "outcome": "won", "traits": "single_contact_no_finance"},
        {"deal_id": "D2", "rep_id": "priya", "rep_name": "Priya", "account": "B",
         "product": "MG Basic", "amount_inr": 2000, "forecast_date": "2017-07-05",
         "close_date": "2017-08-01", "quarter": "2017-Q3", "n_contacts": 2,
         "has_finance_contact": True, "has_champion": False, "competitor": True,
         "stated_prob": 0.6, "outcome": "lost", "traits": ""},
        {"deal_id": "D3", "rep_id": "priya", "rep_name": "Priya", "account": "C",
         "product": "MG Basic", "amount_inr": 3000, "forecast_date": "2017-09-01",
         "close_date": "", "quarter": "2017-Q3", "n_contacts": 1,
         "has_finance_contact": False, "has_champion": False, "competitor": False,
         "stated_prob": 0.5, "outcome": "pending", "traits": "single_contact_no_finance"},
    ])
    path = tmp_path / "deals.csv"
    df.to_csv(path, index=False)
    return path


def test_off_replay_outputs_contract_and_resumes(deals_file, tmp_path):
    output_root = tmp_path / "runs"
    first = run("off", "test", deals_file, output_root)
    assert len(first.completed_quarters) == 5
    second = run("off", "test", deals_file, output_root)
    assert second.completed_quarters == first.completed_quarters

    out = output_root / "test"
    deals = json.loads((out / "deals.json").read_text(encoding="utf-8"))["deals"]
    assert deals["D1"]["memory_off_prob"] == 0.9
    assert deals["D1"]["forecast_quarter"] == "2017-Q1"
    assert "corrected_prob" not in deals["D1"]
    assert json.loads((out / "progress.json").read_text(encoding="utf-8"))["off"]["completed_quarters"] == list(first.completed_quarters)
    totals = json.loads((out / "quarters_off.json").read_text(encoding="utf-8"))
    assert totals["2017-Q2"] == {"reps_forecast_inr": 900, "agent_forecast_inr": 900, "actual_inr": 1000}


def test_on_replay_orders_events_and_audits_prior_outcomes(deals_file, tmp_path):
    services = FakeServices()
    out = run("on", "test", deals_file, tmp_path / "runs", services)
    assert len(out.completed_quarters) == 5
    calls = services.calls
    assert calls.index(("forecast_item", "D1")) < calls.index(("outcome_item", "D1", "2017-04-20"))
    assert ("reflect", "2017-Q3", "priya") in calls

    folder = tmp_path / "runs" / "test"
    audit = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    assert audit["2017-Q1"] is None
    assert audit["2017-Q2"] is None
    assert audit["2017-Q3"] == "2017-04-20"
    output = json.loads((folder / "deals.json").read_text(encoding="utf-8"))["deals"]
    assert output["D1"]["corrected_prob"] == 0.9
    assert output["D3"]["outcome"] == "pending"
    assert output["D3"]["close_date"] == ""
    cards = json.loads((folder / "cards.json").read_text(encoding="utf-8"))
    assert cards["2017-Q1"]["priya"]["rules"] == []
    beliefs = json.loads((folder / "beliefs.json").read_text(encoding="utf-8"))
    assert beliefs["priya"][-1]["quarter"] == "2017-Q4"


def test_on_requires_hindsight_services(deals_file, tmp_path):
    with pytest.raises(RuntimeError, match="Role 2's Hindsight ReplayServices"):
        run("on", "test", deals_file, tmp_path / "runs")


def test_hindsight_adapter_reports_missing_api_key(monkeypatch):
    from app import config
    from app.replay.hindsight_services import build_services

    monkeypatch.setattr(config, "HINDSIGHT_API_KEY", "")
    with pytest.raises(RuntimeError, match="HINDSIGHT_API_KEY is missing"):
        build_services()


def test_one_rep_one_quarter_smoke_includes_later_outcome(deals_file, tmp_path):
    result = run("off", "smoke", deals_file, tmp_path / "runs", rep_id="priya", forecast_quarter="2017-Q1")
    assert result.completed_quarters == ("2017-Q1", "2017-Q2")


def test_on_flushes_in_batches_of_25_and_records_first_batch_time(tmp_path):
    rows = []
    for i in range(31):
        rows.append({"deal_id": f"P{i:02}", "rep_id": "priya", "rep_name": "Priya",
                     "account": f"Acct {i}", "product": "GTX Pro", "amount_inr": 1000,
                     "forecast_date": "2017-02-01", "close_date": "", "quarter": "2017-Q1",
                     "n_contacts": 1, "has_finance_contact": False, "has_champion": True,
                     "competitor": False, "stated_prob": 0.8, "outcome": "pending", "traits": ""})
    path = tmp_path / "pending.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    services = FakeServices()
    result = run("on", "batch", path, tmp_path / "runs", services)
    batches = [call for call in services.calls if call[0] == "batch"]
    assert [len(call[1]) for call in batches] == [25, 6]
    timings = json.loads((result.output_dir / "timings.json").read_text(encoding="utf-8"))
    assert timings["first_25_batch_seconds"] is not None
    assert timings["first_25_batch_quarter"] == "2017-Q1"
    assert timings["memories_saved"] == 31
