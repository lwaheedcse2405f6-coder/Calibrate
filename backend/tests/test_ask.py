"""Tests for the ask box: evidence first, answer from it, and a clear message when memory is empty."""

from types import SimpleNamespace as NS

from app.agent import calibrator as cal
from app.memory import hindsight_store as hs

CARD = {"summary": "Priya over-calls 1 contact and no finance person (says 89%, wins 75%, 24 deals).",
        "rules": [{"trait": "single_contact_no_finance", "direction": "over"}]}


class ReflectClient:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def reflect(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("down")
        return NS(text="Priya is overconfident on single-contact deals.",
                  based_on=NS(memories=[NS(text="The Isdom deal was lost.")]))


def _setup(monkeypatch, card=CARD, hits=None, fail=False):
    client = ReflectClient(fail)
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "calibrate-demo")
    monkeypatch.setattr(hs, "get_client", lambda: client)
    monkeypatch.setattr(cal, "_latest_card", lambda rep_id: ("2017-Q4", card) if card else (None, None))
    monkeypatch.setattr(hs, "recall_rep_history", lambda rep_id, q, limit=4: hits or [])
    return client


def test_named_rep_evidence_goes_to_reflect_and_based_on(monkeypatch):
    hits = [{"deal_id": "Z1", "text": "Priya forecast Zenith at 90%; it was lost."}]
    client = _setup(monkeypatch, hits=hits)
    out = cal.ask("What bias has Priya shown?")
    assert out["answer"] == "Priya is overconfident on single-contact deals."
    assert "latest calibration card (2017-Q4)" in client.calls[0]["context"]
    assert "Zenith" in client.calls[0]["context"]
    assert out["based_on"][0].startswith("Priya's latest calibration card")
    assert "The Isdom deal was lost." in out["based_on"]
    assert out["memory_bank"] == "calibrate-demo"


def test_rep_missing_from_memory_names_the_bank(monkeypatch):
    client = _setup(monkeypatch, card=None, hits=[])
    out = cal.ask("What bias has Priya shown?")
    assert "no memories about Priya" in out["answer"] and "calibrate-demo" in out["answer"]
    assert client.calls == []


def test_reflect_down_still_answers_from_evidence(monkeypatch):
    _setup(monkeypatch, fail=True)
    out = cal.ask("How reliable is Priya?")
    assert out["answer"].startswith("Priya's latest calibration card")
    assert out["based_on"]


def test_question_without_a_rep_goes_straight_to_reflect(monkeypatch):
    client = _setup(monkeypatch)
    out = cal.ask("What's our realistic Q3 number?")
    assert "context" not in client.calls[0] and out["answer"]


def test_rep_names_are_matched_as_words():
    assert [r for r, _ in cal._reps_named("What about SANA and priya?")] == ["priya", "sana"]
    assert cal._reps_named("Hosanna") == []
