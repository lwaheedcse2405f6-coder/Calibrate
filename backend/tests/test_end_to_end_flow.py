"""
backend/tests/test_end_to_end_flow.py
======================================
Integration Test for Role 5 End-to-End Mock Run Pipeline.

# SYNTHETIC MOCK TEST FIXTURE — ISOLATED PIPELINE INTEGRATION
This test executes the full end-to-end evaluation flow:
  1. Seed mock data in data/runs/test_run/ (deals.csv, deals.json, cards.json, audit.json)
  2. Compute and write per-quarter Brier scores (write_scores_to_run -> scores.json)
  3. Evaluate hidden bias recovery metrics (write_eval_to_run -> eval.json)
  4. Assert pipeline integrity, score improvements, bias detection, and pending deal exclusion.
"""

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

try:
    from app.eval.bias_recovery import write_eval_to_run
    from app.metrics.scoring import write_scores_to_run
except ModuleNotFoundError:
    from backend.app.eval.bias_recovery import write_eval_to_run
    from backend.app.metrics.scoring import write_scores_to_run


def seed_test_run(run_dir: Path) -> None:
    """Populate an isolated mock run directory with deals, cards, and audit snapshot."""
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. audit.json
    audit_data = {
        "2017-Q1": "2016-12-28",
        "2017-Q2": "2017-03-29",
        "2017-Q3": "2017-06-30",
        "2017-Q4": "2017-09-28",
    }
    (run_dir / "audit.json").write_text(json.dumps(audit_data, indent=2), encoding="utf-8")

    # 2. cards.json
    cards_data = {
        "2017-Q1": {
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "over", "confidence": "medium", "adjustment": 0.65}
                ]
            },
            "karan": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "low", "adjustment": 1.0}
                ]
            },
        },
        "2017-Q2": {
            "priya": {
                "rules": [
                    {"trait": "single_contact_no_finance", "direction": "over", "confidence": "high", "adjustment": 0.65}
                ]
            },
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "karan": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "low", "adjustment": 1.0}
                ]
            },
        },
        "2017-Q3": {
            "priya": {
                "rules": [
                    {"trait": "single_contact_no_finance", "direction": "over", "confidence": "high", "adjustment": 0.65}
                ]
            },
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "high", "adjustment": 1.0}
                ]
            },
            "karan": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "low", "adjustment": 1.0}
                ]
            },
        },
        "2017-Q4": {
            "priya": {
                "rules": [
                    {"trait": "single_contact_no_finance", "direction": "over", "confidence": "high", "adjustment": 0.65}
                ]
            },
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "high", "adjustment": 1.0}
                ]
            },
            "karan": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "low", "adjustment": 1.0}
                ]
            },
        },
    }
    (run_dir / "cards.json").write_text(json.dumps(cards_data, indent=2), encoding="utf-8")

    # 3. deals.csv & deals.json
    deals = [
        {"deal_id": "D001", "rep_id": "priya", "quarter": "2017-Q1", "forecast_date": "2017-01-15", "close_date": "2017-03-15", "amount_inr": 1200000, "stated_prob": 0.88, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D002", "rep_id": "arjun", "quarter": "2017-Q1", "forecast_date": "2017-01-20", "close_date": "2017-03-20", "amount_inr": 500000,  "stated_prob": 0.40, "corrected_prob": 0.75, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D003", "rep_id": "meera", "quarter": "2017-Q1", "forecast_date": "2017-01-25", "close_date": "2017-03-25", "amount_inr": 3500000, "stated_prob": 0.85, "corrected_prob": 0.35, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D004", "rep_id": "rahul", "quarter": "2017-Q1", "forecast_date": "2017-02-01", "close_date": "2017-03-28", "amount_inr": 800000,  "stated_prob": 0.82, "corrected_prob": 0.28, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D005", "rep_id": "sana",  "quarter": "2017-Q1", "forecast_date": "2017-02-10", "close_date": "2017-03-30", "amount_inr": 950000,  "stated_prob": 0.86, "corrected_prob": 0.32, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D006", "rep_id": "priya", "quarter": "2017-Q2", "forecast_date": "2017-04-10", "close_date": "2017-06-15", "amount_inr": 1500000, "stated_prob": 0.89, "corrected_prob": 0.25, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D007", "rep_id": "arjun", "quarter": "2017-Q2", "forecast_date": "2017-04-15", "close_date": "2017-06-18", "amount_inr": 600000,  "stated_prob": 0.38, "corrected_prob": 0.80, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D008", "rep_id": "meera", "quarter": "2017-Q2", "forecast_date": "2017-04-20", "close_date": "2017-06-22", "amount_inr": 4000000, "stated_prob": 0.84, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D009", "rep_id": "rahul", "quarter": "2017-Q2", "forecast_date": "2017-05-01", "close_date": "2017-06-28", "amount_inr": 1100000, "stated_prob": 0.85, "corrected_prob": 0.35, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D010", "rep_id": "sana",  "quarter": "2017-Q2", "forecast_date": "2017-05-15", "close_date": "2017-06-30", "amount_inr": 700000,  "stated_prob": 0.80, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D011", "rep_id": "priya", "quarter": "2017-Q3", "forecast_date": "2017-07-05", "close_date": "2017-09-10", "amount_inr": 1300000, "stated_prob": 0.87, "corrected_prob": 0.28, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D012", "rep_id": "arjun", "quarter": "2017-Q3", "forecast_date": "2017-07-12", "close_date": "2017-09-15", "amount_inr": 450000,  "stated_prob": 0.42, "corrected_prob": 0.78, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D013", "rep_id": "meera", "quarter": "2017-Q3", "forecast_date": "2017-07-18", "close_date": "2017-09-20", "amount_inr": 3800000, "stated_prob": 0.80, "corrected_prob": 0.32, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D014", "rep_id": "rahul", "quarter": "2017-Q3", "forecast_date": "2017-08-01", "close_date": "2017-09-27", "amount_inr": 900000,  "stated_prob": 0.83, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D015", "rep_id": "sana",  "quarter": "2017-Q3", "forecast_date": "2017-08-10", "close_date": "2017-09-29", "amount_inr": 850000,  "stated_prob": 0.65, "corrected_prob": 0.65, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D016", "rep_id": "karan", "quarter": "2017-Q3", "forecast_date": "2017-08-15", "close_date": "2017-09-30", "amount_inr": 600000,  "stated_prob": 0.70, "corrected_prob": 0.70, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D017", "rep_id": "priya", "quarter": "2017-Q4", "forecast_date": "2017-10-05", "close_date": "2017-12-10", "amount_inr": 1400000, "stated_prob": 0.88, "corrected_prob": 0.25, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D018", "rep_id": "arjun", "quarter": "2017-Q4", "forecast_date": "2017-10-10", "close_date": "2017-12-15", "amount_inr": 550000,  "stated_prob": 0.39, "corrected_prob": 0.82, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D019", "rep_id": "meera", "quarter": "2017-Q4", "forecast_date": "2017-10-15", "close_date": "2017-12-18", "amount_inr": 4200000, "stated_prob": 0.82, "corrected_prob": 0.35, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D020", "rep_id": "rahul", "quarter": "2017-Q4", "forecast_date": "2017-11-01", "close_date": "2017-12-24", "amount_inr": 1000000, "stated_prob": 0.86, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D021", "rep_id": "sana",  "quarter": "2017-Q4", "forecast_date": "2017-11-10", "close_date": "2017-12-28", "amount_inr": 900000,  "stated_prob": 0.60, "corrected_prob": 0.60, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D022", "rep_id": "karan", "quarter": "2017-Q4", "forecast_date": "2017-11-15", "close_date": "2017-12-29", "amount_inr": 650000,  "stated_prob": 0.40, "corrected_prob": 0.40, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D023", "rep_id": "karan", "quarter": "2017-Q4", "forecast_date": "2017-11-20", "close_date": "2017-12-30", "amount_inr": 750000,  "stated_prob": 0.72, "corrected_prob": 0.72, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D024", "rep_id": "priya", "quarter": "2017-Q4", "forecast_date": "2017-12-01", "close_date": "",           "amount_inr": 2000000, "stated_prob": 0.88, "corrected_prob": 0.40, "baseline_prob": 0.63, "outcome": "pending"},
    ]

    fieldnames = ["deal_id", "rep_id", "quarter", "forecast_date", "close_date", "amount_inr", "stated_prob", "corrected_prob", "baseline_prob", "outcome"]
    with open(run_dir / "deals.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deals)

    (run_dir / "deals.json").write_text(json.dumps(deals, indent=2), encoding="utf-8")


@pytest.fixture
def mock_run_dir(tmp_path: Path) -> Path:
    """Fixture that generates an isolated mock run environment in a temporary folder."""
    seed_test_run(tmp_path)
    return tmp_path


def test_end_to_end_pipeline_flow(mock_run_dir: Path):
    """
    Full end-to-end integration test validating scoring and evaluation outputs.
    """
    assert (mock_run_dir / "deals.csv").exists()
    assert (mock_run_dir / "cards.json").exists()
    assert (mock_run_dir / "audit.json").exists()

    cards = json.loads((mock_run_dir / "cards.json").read_text(encoding="utf-8"))

    scores_path = write_scores_to_run(mock_run_dir)
    assert scores_path.exists()

    eval_path = write_eval_to_run(mock_run_dir, cards)
    assert eval_path.exists()

    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert len(scores) == 4, f"Expected 4 quarters in scores.json, got {len(scores)}"

    quarters = [s["quarter"] for s in scores]
    assert sorted(quarters) == ["2017-Q1", "2017-Q2", "2017-Q3", "2017-Q4"]

    avg_reps = sum(s["reps"] for s in scores) / len(scores)
    avg_agent_on = sum(s["agent_on"] for s in scores) / len(scores)
    assert avg_agent_on < avg_reps, f"Agent-on avg Brier ({avg_agent_on}) should be lower than reps ({avg_reps})"

    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    assert eval_data["biases_found"] == 5, f"Expected biases_found=5, got {eval_data['biases_found']}"
    assert eval_data["biases_total"] == 5, f"Expected biases_total=5, got {eval_data['biases_total']}"
    assert eval_data["false_alarms"] == 0, f"Expected false_alarms=0, got {eval_data['false_alarms']}"
    assert eval_data.get("sana_improvement_noticed") is True, "Expected sana_improvement_noticed=True"

    deals_df = pd.DataFrame(json.loads((mock_run_dir / "deals.json").read_text(encoding="utf-8")))
    pending_deals = deals_df[deals_df["outcome"] == "pending"]
    assert len(pending_deals) == 1, "Expected 1 pending deal"

    closed_deals = deals_df[deals_df["outcome"].isin(["won", "lost"])]
    assert len(closed_deals) == 23, "Expected 23 closed deals"

    total_closed_in_scores = 0
    for _q, g in closed_deals.groupby("quarter"):
        total_closed_in_scores += len(g)
    assert total_closed_in_scores == 23


def test_seed_mock_run_directory_target(tmp_path: Path):
    """Verify that seed_mock_run can write to an arbitrary target directory."""
    test_run_dir = tmp_path / "custom_test_run"
    seed_test_run(test_run_dir)

    assert (test_run_dir / "deals.csv").exists()
    assert (test_run_dir / "cards.json").exists()
    assert (test_run_dir / "audit.json").exists()

    scores_path = write_scores_to_run(test_run_dir)
    cards = json.loads((test_run_dir / "cards.json").read_text(encoding="utf-8"))
    eval_path = write_eval_to_run(test_run_dir, cards)

    assert scores_path.exists()
    assert eval_path.exists()
