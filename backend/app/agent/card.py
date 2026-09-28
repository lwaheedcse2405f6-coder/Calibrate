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
