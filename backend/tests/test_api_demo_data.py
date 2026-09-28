"""The dashboard endpoints must serve the committed demo run (backend/data/runs/demo/)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app

routes.REPLAY_DELAY_S = 0  # no waiting in tests

client = TestClient(app)
DEMO = Path(__file__).resolve().parents[1] / "data" / "runs" / "demo"


def test_scores_match_official_scores_file():
    assert client.get("/api/scores").json() == json.loads((DEMO / "scores.json").read_text())


def test_rep_deals_are_real_deal_rows():
    rows = client.get("/api/reps/priya/deals").json()
    assert rows and all(r["rep_id"] == "priya" and "corrected_prob" in r for r in rows)


def test_beliefs_have_confidence():
    rows = client.get("/api/reps/sana/beliefs").json()
    assert rows and all(r["confidence"] in ("low", "medium", "high") for r in rows)


def test_eval_is_the_real_checker_output():
    data = client.get("/api/eval").json()
    assert data["headline"].startswith("Found") and data["biases_total"] == 5


def test_live_correction_uses_real_card():
    body = {"rep_id": "priya", "account": "Zenith Corp", "amount_inr": 6000000,
            "n_contacts": 1, "has_finance_contact": False, "stated_prob": 0.9}
    out = client.post("/api/forecast/correct", json=body).json()
    assert out["corrected_prob"] < 0.9 and "24 deals" in out["explanation"]


def test_replay_stream_sends_real_quarters_then_done():
    with client.stream("GET", "/api/replay/stream?mode=on") as r:
        body = "".join(r.iter_text())
    frames = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: {\"quarter")]
    assert [f["quarter"] for f in frames] == ["2017-Q1", "2017-Q2", "2017-Q3", "2017-Q4"]
    assert any(f["belief_updates"] for f in frames)
    assert body.rstrip().endswith("event: done\ndata: {}")


def test_beliefs_show_the_correction_strength():
    rows = client.get("/api/reps/sana/beliefs").json()
    assert rows[-1]["adjustment"] == 0.746
