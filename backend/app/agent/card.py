"""The calibration card: what the agent believes about one rep, as checkable rules.

Owner: Role 2. Role 4 shows it on the rep page; Role 5's checker compares ``trait`` + ``direction``
with the hidden biases in ``sim/personas.py``.

Every card that comes out of the AI goes through ``parse_card`` before we use it. It fixes the
things an AI tends to get wrong, instead of trusting it:
- drops rules with an unknown trait or broken fields
- recomputes ``adjustment`` and ``direction`` from the numbers when both are given
- clips ``adjustment`` to 0.3-2.0
- caps ``confidence`` by how many deals the rule is based on
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger(__name__)

TRAITS = ["single_contact_no_finance", "large_deal", "end_of_quarter", "overall", "other"]

MIN_EVIDENCE = 3          # fewer similar deals than this = no big adjustments
ACCURATE_BAND = 0.05      # within 5 points = accurate
ADJ_MIN, ADJ_MAX = 0.3, 2.0

Confidence = Literal["low", "medium", "high"]
_RANK = {"low": 0, "medium": 1, "high": 2}


class Rule(BaseModel):
    trait: Literal["single_contact_no_finance", "large_deal", "end_of_quarter", "overall", "other"]
    direction: Literal["over", "under", "accurate"]
    condition: str = ""
    stated_avg: float | None = Field(default=None, ge=0, le=1)
    actual_rate: float | None = Field(default=None, ge=0, le=1)
    adjustment: float = 1.0
    evidence_count: int = Field(default=0, ge=0)
    confidence: Confidence = "low"


class Card(BaseModel):
    summary: str = "Not enough history yet."
    rules: list[Rule] = []


def empty_card() -> dict:
    return Card().model_dump()


def confidence_for(evidence_count: int) -> Confidence:
    """The most confidence this much evidence can support."""
    if evidence_count < MIN_EVIDENCE:
        return "low"
    if evidence_count < 8:
        return "medium"
    return "high"


def _as_rate(v):
    """Accept 0.88 or 88 (the AI sometimes answers in percent)."""
    if v is None:
        return None
    v = float(v)
    return v / 100 if 1 < v <= 100 else v


def _fix_rule(raw: dict) -> Rule | None:
    raw = dict(raw)
    raw["stated_avg"] = _as_rate(raw.get("stated_avg"))
    raw["actual_rate"] = _as_rate(raw.get("actual_rate"))
    try:
        rule = Rule.model_validate(raw)
    except ValidationError as exc:
        log.info("dropping bad rule %s: %s", raw.get("trait"), exc.errors()[0]["msg"])
        return None

    # Don't trust the AI's arithmetic: recompute from its own numbers when we have them.
    if rule.stated_avg and rule.actual_rate is not None:
        rule.adjustment = rule.actual_rate / rule.stated_avg
        gap = rule.stated_avg - rule.actual_rate
        rule.direction = "over" if gap > ACCURATE_BAND else "under" if gap < -ACCURATE_BAND \
            else "accurate"

    rule.adjustment = round(min(ADJ_MAX, max(ADJ_MIN, rule.adjustment)), 3)
    if rule.direction == "accurate":
        rule.adjustment = 1.0

    cap = confidence_for(rule.evidence_count)
    if _RANK[rule.confidence] > _RANK[cap]:
        rule.confidence = cap
    return rule


def parse_card(raw: dict | None) -> dict:
    """Turn whatever reflect returned into a safe card dict. Never raises."""
    if not isinstance(raw, dict):
        return empty_card()
    rules = [r for r in (_fix_rule(x) for x in raw.get("rules") or [] if isinstance(x, dict)) if r]
    summary = str(raw.get("summary") or "").strip() or Card().summary
    return Card(summary=summary, rules=rules).model_dump()


# ---------------------------------------------------------------------------
# Cards measured from the track record (the numbers reflect can't do reliably)
# ---------------------------------------------------------------------------

# Tuned on deals.csv: memory ON beats OFF every quarter, finds 4/4 planted biases, few false
# alarms. A gap only counts as a bias if it's bigger than noise (z standard errors).
Z_OVERALL = 2.0
Z_TRAIT = 1.5
MIN_GROUP = 5

CONDITIONS = {
    "single_contact_no_finance": "1 contact and no finance person",
    "large_deal": "big-ticket products",
    "end_of_quarter": "deals opened in the last 2 weeks of a quarter",
    "overall": "all deals",
}


def _group_stats(records: list[dict]) -> tuple[float, float, int]:
    n = len(records)
    stated = sum(r["stated_prob"] for r in records) / n
    actual = sum(r["outcome"] == "won" for r in records) / n
    return stated, actual, n


def _is_real_gap(gap: float, actual: float, n: int, z: float) -> bool:
    se = (max(actual * (1 - actual), 0.05) / n) ** 0.5
    return abs(gap) > max(ACCURATE_BAND, z * se)


def _rule(trait: str, stated: float, actual: float, n: int, biased: bool) -> Rule:
    gap = stated - actual
    direction = ("over" if gap > 0 else "under") if biased else "accurate"
    adjustment = round(min(ADJ_MAX, max(ADJ_MIN, actual / stated)), 3) if biased and stated else 1.0
    return Rule(trait=trait, direction=direction, condition=CONDITIONS[trait],
                stated_avg=round(stated, 3), actual_rate=round(actual, 3), adjustment=adjustment,
                evidence_count=n, confidence=confidence_for(n))


def build_card(records: list[dict]) -> dict:
    """Measure a rep's calibration card from their closed deals (as remembered).

    ``records``: dicts with ``stated_prob`` (float), ``outcome`` ('won'/'lost') and ``traits``
    (list of trait names). A trait only gets its own bias if it differs from the rep's overall
    bias by more than noise, so e.g. a sandbagger isn't also flagged on every trait.
    """
    closed = [r for r in records if r.get("outcome") in ("won", "lost")]
    if len(closed) < MIN_GROUP:
        return empty_card()

    stated, actual, n = _group_stats(closed)
    overall_biased = _is_real_gap(stated - actual, actual, n, Z_OVERALL)
    rules = [_rule("overall", stated, actual, n, overall_biased)]
    overall_gap = stated - actual if overall_biased else 0.0

    for trait in ("single_contact_no_finance", "large_deal", "end_of_quarter"):
        group = [r for r in closed if trait in r["traits"]]
        if len(group) < MIN_GROUP:
            continue
        s, a, k = _group_stats(group)
        rules.append(_rule(trait, s, a, k, _is_real_gap((s - a) - overall_gap, a, k, Z_TRAIT)))

    biased = [r for r in rules if r.direction != "accurate"]
    if not biased:
        summary = f"Forecasts match reality within noise (based on {n} closed deals)."
    else:
        parts = [f"{r.direction}-calls {r.condition} (says {r.stated_avg:.0%}, wins "
                 f"{r.actual_rate:.0%}, {r.evidence_count} deals)" for r in biased]
        summary = "Rep " + "; ".join(parts) + "."
    return Card(summary=summary, rules=rules).model_dump()
