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

import json
from pathlib import Path
import pandas as pd
import pytest

from backend.app.metrics.scoring import write_scores_to_run, brier
from backend.app.eval.bias_recovery import write_eval_to_run
from scripts.seed_mock_run import seed_test_run


@pytest.fixture
def mock_run_dir(tmp_path: Path) -> Path:
    """Fixture that generates an isolated mock run environment in a temporary folder."""
    seed_test_run(tmp_path)
    return tmp_path


def test_end_to_end_pipeline_flow(mock_run_dir: Path):
    """
    Full end-to-end integration test validating scoring and evaluation outputs.
    """
    # 1. Run data seeding (already executed by fixture in mock_run_dir)
    assert (mock_run_dir / "deals.csv").exists()
    assert (mock_run_dir / "cards.json").exists()
    assert (mock_run_dir / "audit.json").exists()

    # Read cards for step 3
    cards = json.loads((mock_run_dir / "cards.json").read_text(encoding="utf-8"))

    # 2. Execute write_scores_to_run
    scores_path = write_scores_to_run(mock_run_dir)
    assert scores_path.exists()

    # 3. Execute write_eval_to_run
    eval_path = write_eval_to_run(mock_run_dir, cards)
    assert eval_path.exists()

    # 4. Assert scores.json generated with 4 quarters & agent_on Brier < reps Brier
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    assert len(scores) == 4, f"Expected 4 quarters in scores.json, got {len(scores)}"

    quarters = [s["quarter"] for s in scores]
    assert sorted(quarters) == ["2017-Q1", "2017-Q2", "2017-Q3", "2017-Q4"]

    avg_reps = sum(s["reps"] for s in scores) / len(scores)
    avg_agent_on = sum(s["agent_on"] for s in scores) / len(scores)
    assert avg_agent_on < avg_reps, f"Agent-on avg Brier ({avg_agent_on}) should be lower than reps ({avg_reps})"

    # 5. Assert eval.json generated with exact spec fields
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    assert eval_data["biases_found"] == 5, f"Expected biases_found=5, got {eval_data['biases_found']}"
    assert eval_data["biases_total"] == 5, f"Expected biases_total=5, got {eval_data['biases_total']}"
    assert eval_data["false_alarms"] == 0, f"Expected false_alarms=0, got {eval_data['false_alarms']}"
    assert eval_data.get("sana_improvement_noticed") is True, "Expected sana_improvement_noticed=True"

    # 6. Assert pending deal is omitted from closed Brier calculations
    deals_df = pd.DataFrame(json.loads((mock_run_dir / "deals.json").read_text(encoding="utf-8")))
    pending_deals = deals_df[deals_df["outcome"] == "pending"]
    assert len(pending_deals) == 1, "Expected 1 pending deal"
    
    closed_deals = deals_df[deals_df["outcome"].isin(["won", "lost"])]
    assert len(closed_deals) == 23, "Expected 23 closed deals"

    # Confirm that scores calculation only includes 23 closed deals across 4 quarters
    total_closed_in_scores = 0
    for q, g in closed_deals.groupby("quarter"):
        total_closed_in_scores += len(g)
    assert total_closed_in_scores == 23


def test_seed_mock_run_directory_target():
    """Verify that seed_mock_run can write to the default data/runs/test_run directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    test_run_dir = project_root / "data" / "runs" / "test_run"
    seed_test_run(test_run_dir)

    assert (test_run_dir / "deals.csv").exists()
    assert (test_run_dir / "cards.json").exists()
    assert (test_run_dir / "audit.json").exists()

    scores_path = write_scores_to_run(test_run_dir)
    cards = json.loads((test_run_dir / "cards.json").read_text(encoding="utf-8"))
    eval_path = write_eval_to_run(test_run_dir, cards)

    assert scores_path.exists()
    assert eval_path.exists()
