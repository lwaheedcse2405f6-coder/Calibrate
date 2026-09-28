"""Offline tests for Role 2's code. No API keys needed: Hindsight and Groq are faked."""

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import calibrator as cal  # noqa: E402
from app.agent.card import parse_card  # noqa: E402
from app.memory import hindsight_store as hs  # noqa: E402

PRIYA_CARD = {
    "rep_id": "priya",
    "summary": "Priya is overconfident on single-contact deals with no finance person.",
    "rules": [
        {"trait": "single_contact_no_finance", "direction": "over", "condition": "1 contact, no finance",
         "stated_avg": 0.88, "actual_rate": 0.44, "adjustment": 0.5, "evidence_count": 9,
         "confidence": "high"},
        {"trait": "overall", "direction": "over", "condition": "all deals",
         "stated_avg": 0.75, "actual_rate": 0.62, "adjustment": 0.83, "evidence_count": 30,
         "confidence": "high"},
    ],
}

DEAL = {
    "deal_id": "Z063OYW0", "rep_id": "priya", "rep_name": "Priya", "account": "Isdom",
    "product": "GTX Basic", "amount_inr": "45650", "forecast_date": "2017-02-03",
    "close_date": "2017-03-01", "quarter": "2017-Q1", "n_contacts": "1",
    "has_finance_contact": "False", "stated_prob": "0.9", "outcome": "lost",
    "traits": "single_contact_no_finance",
}


# --- parse_card: never trust the AI blindly ---------------------------------

def test_parse_card_recomputes_adjustment_and_direction():
    raw = {"summary": "x", "rules": [
        {"trait": "overall", "direction": "over", "condition": "all", "stated_avg": 0.40,
         "actual_rate": 0.63, "adjustment": 0.9, "evidence_count": 12, "confidence": "high"}]}
    rule = parse_card(raw)["rules"][0]
    assert rule["direction"] == "under"          # AI said "over"; numbers say sandbagger
    assert rule["adjustment"] == round(0.63 / 0.40, 3)


def test_parse_card_drops_unknown_traits_and_clips():
    raw = {"summary": "x", "rules": [
        {"trait": "gender", "direction": "over", "condition": "c", "adjustment": 0.5,
         "evidence_count": 10, "confidence": "high"},
        {"trait": "large_deal", "direction": "over", "condition": "c", "adjustment": 0.05,
         "evidence_count": 10, "confidence": "high"}]}
    rules = parse_card(raw)["rules"]
    assert [r["trait"] for r in rules] == ["large_deal"]
    assert rules[0]["adjustment"] == 0.3


def test_parse_card_caps_confidence_by_evidence_and_accepts_percent():
    raw = {"summary": "x", "rules": [
        {"trait": "overall", "direction": "over", "condition": "c", "stated_avg": 90,
         "actual_rate": 50, "adjustment": 1, "evidence_count": 2, "confidence": "high"}]}
    rule = parse_card(raw)["rules"][0]
    assert rule["confidence"] == "low"
    assert rule["stated_avg"] == 0.9


def test_parse_card_garbage_gives_empty_card():
    assert parse_card(None)["rules"] == []
    assert parse_card({"rules": "nope"})["rules"] == []


# --- apply_card ---------------------------------------------------------------

def test_apply_card_prefers_specific_trait_rule():
    corrected, rule = cal.apply_card(PRIYA_CARD, DEAL)
    assert rule["trait"] == "single_contact_no_finance"
    assert corrected == 0.45


def test_apply_card_falls_back_to_overall():
    corrected, rule = cal.apply_card(PRIYA_CARD, {**DEAL, "traits": ""})
    assert rule["trait"] == "overall"
    assert corrected < 0.9


def test_apply_card_ignores_low_evidence_and_accurate_rules():
    card = {"rules": [
        {"trait": "overall", "direction": "over", "adjustment": 0.5, "evidence_count": 2,
         "confidence": "low"},
        {"trait": "overall", "direction": "accurate", "adjustment": 1.0, "evidence_count": 20,
         "confidence": "high"}]}
    assert cal.apply_card(card, DEAL) == (0.9, None)


def test_apply_card_empty_card_trusts_rep():
    assert cal.apply_card(None, DEAL) == (0.9, None)


def test_apply_card_stays_in_bounds():
    card = {"rules": [{"trait": "overall", "direction": "under", "adjustment": 2.0,
                       "evidence_count": 20, "confidence": "high"}]}
    corrected, _ = cal.apply_card(card, {**DEAL, "stated_prob": 0.9, "traits": ""})
    assert corrected == 0.98


# --- traits for the live form --------------------------------------------------

def test_compute_traits():
    form = {"n_contacts": 1, "has_finance_contact": False, "product": "GTK 500"}
    assert cal.compute_traits(form, date(2017, 3, 25)) == [
        "single_contact_no_finance", "large_deal", "end_of_quarter"]
    assert cal.compute_traits({"n_contacts": 3, "has_finance_contact": True},
                              date(2017, 12, 1)) == []
    assert "end_of_quarter" in cal.compute_traits({"n_contacts": 3}, date(2017, 12, 20))


# --- correct(): the live form --------------------------------------------------

FORM = {"rep_id": "priya", "account": "Zenith Corp", "amount_inr": 6000000, "n_contacts": 1,
        "has_finance_contact": False, "has_champion": True, "competitor": False,
        "stage": "proposal", "stated_prob": 0.9}


def test_correct_with_history(monkeypatch):
    monkeypatch.setattr(hs, "recall_rep_history",
                        lambda rep_id, q, limit=3: [{"deal_id": "Z063OYW0", "text": "lost"}])
    out = cal.correct(FORM, PRIYA_CARD, rep_name="Priya", deals_by_id={"Z063OYW0": DEAL},
                      today=date(2017, 5, 1), use_llm=False)
    assert out["corrected_prob"] == 0.45
    assert out["memory_used"] is True
    assert "9 deals" in out["explanation"]
    assert out["evidence"][0] == {"deal_id": "Z063OYW0", "account": "Isdom", "stated": 0.9,
                                  "outcome": "lost"}
    assert set(out) == {"corrected_prob", "confidence", "explanation", "evidence",
                        "questions_to_ask", "memory_used"}


def test_correct_cold_start_uses_team_card_and_says_so():
    team = {"rules": [{"trait": "overall", "direction": "over", "adjustment": 0.8,
                       "evidence_count": 100, "confidence": "high"}]}
    out = cal.correct({**FORM, "rep_id": "karan"}, {"rules": []}, rep_name="Karan",
                      team_card=team, today=date(2017, 8, 1), use_llm=False)
    assert out["memory_used"] is False
    assert out["explanation"].startswith("Not enough history for Karan")
    assert out["corrected_prob"] < 0.9


# --- hindsight_store with a fake client ----------------------------------------

class FakeClient:
    def __init__(self, structured):
        self.structured = structured
        self.calls = []

    def reflect(self, **kw):
        self.calls.append(kw)
        if isinstance(self.structured, Exception):
            raise self.structured
        return SimpleNamespace(structured_output=self.structured, structured_output_error=None,
                               text="", based_on=None)

    def retain(self, **kw):
        self.calls.append(kw)


def test_reflect_card_validates_and_uses_strict_tags(monkeypatch):
    fake = FakeClient({"summary": "s", "rules": PRIYA_CARD["rules"]})
    monkeypatch.setattr(hs, "get_client", lambda: fake)
    card = hs.reflect_calibration_card("priya", "Priya", "2017-Q2")
    assert card["rep_id"] == "priya" and card["quarter"] == "2017-Q2"
    assert len(card["rules"]) == 2
    assert fake.calls[0]["tags"] == ["rep:priya"]
    assert fake.calls[0]["tags_match"] == "all_strict"


def test_reflect_card_never_crashes(monkeypatch):
    fake = FakeClient(RuntimeError("rate limited"))
    monkeypatch.setattr(hs, "get_client", lambda: fake)
    card = hs.reflect_calibration_card("priya", "Priya")
    assert card["rules"] == [] and len(fake.calls) == 2   # tried twice, then empty card


def test_memory_items():
    f = hs.forecast_item(DEAL)
    assert "at 90%" in f["content"] and "single_contact_no_finance" in f["content"]
    assert f["tags"] == ["rep:priya", "quarter:2017-Q1", "kind:forecast"]
    assert f["timestamp"] == "2017-02-03T10:00:00Z"
    o = hs.outcome_item(DEAL)
    assert o["document_id"] == "outcome-Z063OYW0" and "was lost" in o["content"]
    s = hs.self_check_item(DEAL, 0.45, True)
    assert "from 90% to 45%" in s["content"] and "right" in s["content"]


def test_correction_was_right():
    assert hs.correction_was_right(0.9, 0.45, "lost") is True
    assert hs.correction_was_right(0.9, 0.45, "won") is False
