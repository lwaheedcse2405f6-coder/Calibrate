"""Tests for measured calibration cards and reading the track record back from memory."""

import random
from types import SimpleNamespace as NS

from app.agent.card import build_card
from app.memory import hindsight_store as hs


def _deals(n, stated, win_rate, traits=(), seed=1):
    rng = random.Random(seed)
    return [{"stated_prob": stated, "outcome": "won" if rng.random() < win_rate else "lost",
             "traits": list(traits)} for _ in range(n)]


def _flagged(card):
    return {(r["trait"], r["direction"]) for r in card["rules"] if r["direction"] != "accurate"}


def test_too_little_history_gives_empty_card():
    assert build_card(_deals(3, 0.7, 0.7))["rules"] == []


def test_accurate_rep_has_no_biases():
    card = build_card(_deals(120, 0.65, 0.65))
    assert _flagged(card) == set()
    assert "within noise" in card["summary"]


def test_sandbagger_found_without_flagging_every_trait():
    records = _deals(100, 0.40, 0.65) + _deals(30, 0.40, 0.65, ["single_contact_no_finance"], 2)
    assert _flagged(build_card(records)) == {("overall", "under")}


def test_trait_bias_found_on_top_of_accurate_rep():
    records = _deals(100, 0.65, 0.65) + _deals(25, 0.88, 0.45, ["single_contact_no_finance"], 3)
    card = build_card(records)
    assert ("single_contact_no_finance", "over") in _flagged(card)
    rule = next(r for r in card["rules"] if r["trait"] == "single_contact_no_finance")
    assert rule["evidence_count"] == 25 and rule["adjustment"] < 1


def test_small_noisy_gap_is_not_a_bias():
    assert _flagged(build_card(_deals(12, 0.70, 0.55))) == set()


# --- reading the track record back from Hindsight -----------------------------

def _unit(deal_id, rep, stated, outcome, traits=""):
    return NS(metadata={"deal_id": deal_id, "rep_id": rep, "stated_prob": str(stated),
                        "outcome": outcome, "traits": traits, "close_date": "2017-05-01"})


class ListClient:
    def __init__(self, units):
        self.units, self.pages, self.reflects = units, 0, []

    def list_memories(self, bank_id, limit=100, offset=0, **kw):
        self.pages += 1
        return NS(items=self.units[offset:offset + limit], total=len(self.units))

    def reflect(self, **kw):
        self.reflects.append(kw)
        return NS(structured_output={"summary": "Priya over-calls single-contact deals."},
                  structured_output_error=None, text="")


def test_track_record_pages_dedupes_and_skips_non_outcomes(monkeypatch):
    units = [_unit(f"D{i}", "priya", 0.9, "won" if i % 2 else "lost") for i in range(150)]
    units += [_unit("D1", "priya", 0.9, "won"), NS(metadata=None), NS(metadata={"note": "x"}),
              _unit("P1", "priya", 0.9, "pending"), _unit("A1", "arjun", 0.4, "won")]
    client = ListClient(units)
    monkeypatch.setattr(hs, "get_client", lambda: client)
    hs._TRACK_CACHE.clear()
    records = hs.rep_track_record("priya")
    assert len(records) == 150 and client.pages == 2          # paged, one record per deal
    assert len(hs.rep_track_record("arjun")) == 1 and client.pages == 2   # cached
    hs._TRACK_CACHE.clear()


def test_card_measured_from_memory_and_explained_by_reflect(monkeypatch):
    units = [_unit(f"D{i}", "priya", 0.65, "won" if i % 20 < 13 else "lost") for i in range(100)]
    units += [_unit(f"S{i}", "priya", 0.9, "won" if i % 10 < 4 else "lost",
                    "single_contact_no_finance") for i in range(30)]
    client = ListClient(units)
    monkeypatch.setattr(hs, "get_client", lambda: client)
    hs._TRACK_CACHE.clear()
    card = hs.reflect_calibration_card("priya", "Priya", "2017-Q3")
    assert card["source"] == "track_record" and card["deals_remembered"] == 130
    assert ("single_contact_no_finance", "over") in _flagged(card)
    assert card["summary"].startswith("Priya ") and "over-calls 1 contact and no finance person" in card["summary"]
    assert card["hindsight_summary"] == "Priya over-calls single-contact deals."
    assert client.reflects[0]["tags"] == ["rep:priya"] and "30 deals" in client.reflects[0]["context"]
    hs._TRACK_CACHE.clear()


def test_saving_clears_the_cached_track_record(monkeypatch):
    client = ListClient([_unit("D1", "priya", 0.9, "won")])
    client.retain_batch = lambda **kw: None
    monkeypatch.setattr(hs, "get_client", lambda: client)
    hs._TRACK_CACHE.clear()
    hs.rep_track_record("priya")
    hs.retain_many([{"content": "x"}])
    assert hs._TRACK_CACHE == {}


def test_outcome_memory_carries_exact_numbers():
    deal = {"deal_id": "Z1", "rep_id": "priya", "rep_name": "Priya", "account": "A",
            "product": "GTX Pro", "close_date": "2017-03-01", "quarter": "2017-Q1",
            "stated_prob": 0.9, "outcome": "lost", "traits": "single_contact_no_finance"}
    meta = hs.outcome_item(deal)["metadata"]
    assert meta == {"deal_id": "Z1", "rep_id": "priya", "stated_prob": "0.9", "outcome": "lost",
                    "traits": "single_contact_no_finance", "close_date": "2017-03-01"}


def test_accurate_rep_summary_is_measured_not_invented(monkeypatch):
    units = [_unit(f"D{i}", "priya", 0.65, "won" if i % 20 < 13 else "lost") for i in range(100)]
    client = ListClient(units)
    monkeypatch.setattr(hs, "get_client", lambda: client)
    hs._TRACK_CACHE.clear()
    card = hs.reflect_calibration_card("priya", "Priya", "2017-Q2")
    assert client.reflects == []                      # nothing to explain: no reflect call
    assert card["summary"].startswith("Priya's forecasts match reality within noise")
    assert "hindsight_summary" not in card
    hs._TRACK_CACHE.clear()
