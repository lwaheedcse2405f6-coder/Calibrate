from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reps_lists_six():
    assert len(client.get("/api/reps").json()) == 6


def test_quarters_shape():
    row = client.get("/api/quarters?mode=on").json()[0]
    assert set(row) == {
        "quarter", "reps_forecast_inr", "agent_forecast_inr", "actual_inr"
    }


def test_scores_shape():
    row = client.get("/api/scores").json()[0]
    assert set(row) == {
        "quarter", "reps", "agent_off", "agent_on", "baseline_win_rate"
    }


def test_card_has_rules_with_evidence():
    card = client.get("/api/reps/priya/card?quarter=2017-Q3").json()
    assert card["rep_id"] == "priya"
    assert card["rules"][0]["evidence_count"] > 0


def test_eval_headline_fields():
    data = client.get("/api/eval").json()
    assert data["biases_found"] <= data["biases_total"]
    assert "headline" in data


def test_forecast_correct_returns_contract_fields():
    body = {
        "rep_id": "priya", "account": "Zenith Corp", "amount_inr": 6000000,
        "n_contacts": 1, "has_finance_contact": False, "has_champion": True,
        "competitor": False, "stage": "proposal", "stated_prob": 0.9,
    }
    data = client.post("/api/forecast/correct", json=body).json()
    assert {"corrected_prob", "confidence", "explanation", "evidence",
            "questions_to_ask", "memory_used"} <= set(data)


def test_forecast_correct_rejects_empty_body():
    assert client.post("/api/forecast/correct", json={}).status_code == 422


def test_ask_returns_answer():
    data = client.post("/api/ask", json={"question": "Q3?"}).json()
    assert "answer" in data and "based_on" in data