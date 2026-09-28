"""Every Hindsight call Calibrate makes: save (retain), look up (recall), think it over (reflect).

Owner: Role 2 (Agent & Memory).

Notes:
- The client is created lazily, so importing this file never needs API keys (CI stays green).
- Every rep's memories carry the tag ``rep:<rep_id>``; lookups use ``tags_match="all_strict"``
  so one rep's memories never leak into another's.
- Don't save and look up in the same step: Hindsight processes memories in the background.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from app.agent.card import TRAITS, empty_card, parse_card

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts live here so they're quick to tweak at 3 AM.
# ---------------------------------------------------------------------------

CARD_QUERY = (
    "Compare {rep_name}'s stated forecast confidence with actual outcomes using only closed deals "
    "from forecast cohort {forecast_quarter}. The tag forecast-quarter identifies when the rep "
    "made the forecast; do not use the close quarter as a substitute. Do not blend older forecast "
    "cohorts into these metrics. Group the deals by single_contact_no_finance, large_deal, "
    "end_of_quarter, and overall. For each group give: "
    "the average stated probability (stated_avg, 0-1), the actual win rate (actual_rate, 0-1), "
    "the number of closed deals (evidence_count), and adjustment = actual_rate / stated_avg. "
    "direction is 'over' if stated_avg is more than 5 points above actual_rate, 'under' if more "
    "than 5 points below, otherwise 'accurate'. If recent quarters differ from earlier ones, "
    "trust the recent quarters and say so in the summary. Only include a group if it has at "
    "least one closed deal."
)

TEAM_CARD_QUERY = (
    "Across all reps, compare stated forecast confidence with actual outcomes for closed deals. "
    "Group by: single_contact_no_finance, large_deal, end_of_quarter, and overall. For each "
    "group give stated_avg, actual_rate, evidence_count, adjustment = actual_rate / stated_avg, "
    "and direction (over / under / accurate, within 5 points = accurate)."
)

CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "trait": {"type": "string", "enum": TRAITS},
                    "direction": {"type": "string", "enum": ["over", "under", "accurate"]},
                    "condition": {"type": "string"},
                    "stated_avg": {"type": "number"},
                    "actual_rate": {"type": "number"},
                    "adjustment": {"type": "number"},
                    "evidence_count": {"type": "integer"},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["trait", "direction", "condition", "adjustment",
                             "evidence_count", "confidence"],
            },
        },
    },
    "required": ["summary", "rules"],
}


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def bank_id() -> str:
    return os.environ.get("HINDSIGHT_BANK_ID", "calibrate-dev")


@lru_cache(maxsize=1)
def get_client():
    """Create the Hindsight client the first time it's needed."""
    from hindsight_client import Hindsight

    return Hindsight(
        base_url=os.environ.get("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
        api_key=os.environ["HINDSIGHT_API_KEY"],
    )


def ensure_bank() -> None:
    """Create the bank if it doesn't exist yet. Safe to call many times."""
    try:
        get_client().create_bank(bank_id=bank_id(), name=bank_id())
    except Exception as exc:  # noqa: BLE001 (bank already exists, most likely)
        log.info("create_bank skipped (%s)", str(exc)[:120])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _traits(deal: dict) -> list[str]:
    """deals.csv stores traits as 'a;b'. Accept a string or a list."""
    raw = deal.get("traits") or []
    if isinstance(raw, str):
        raw = raw.split(";")
    return [t.strip() for t in raw if t and str(t).strip()]


def _pct(p: float) -> int:
    return round(float(p) * 100)


def _yes(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def _forecast_quarter(deal: dict) -> str | None:
    if deal.get("forecast_quarter"):
        return str(deal["forecast_quarter"])
    raw_date = str(deal.get("forecast_date") or "")
    try:
        year, month = int(raw_date[:4]), int(raw_date[5:7])
    except (TypeError, ValueError):
        return None
    return f"{year}-Q{(month - 1) // 3 + 1}"


def _tags(deal: dict, kind: str) -> list[str]:
    tags = [f"rep:{deal['rep_id']}", f"quarter:{deal['quarter']}", f"kind:{kind}"]
    forecast_quarter = _forecast_quarter(deal)
    if forecast_quarter:
        tags.append(f"forecast-quarter:{forecast_quarter}")
    return tags


# ---------------------------------------------------------------------------
# Memory items (plain dicts, so they work with retain and retain_batch)
# ---------------------------------------------------------------------------

def forecast_item(deal: dict) -> dict:
    traits = ", ".join(_traits(deal)) or "none"
    return {
        "content": (
            f"On {deal['forecast_date']}, {deal['rep_name']} forecast the {deal['account']} deal "
            f"({deal['product']}, ₹{int(float(deal['amount_inr'])):,}, "
            f"{int(float(deal['n_contacts']))} contact(s), "
            f"finance contact: {'yes' if _yes(deal['has_finance_contact']) else 'no'}) "
            f"at {_pct(deal['stated_prob'])}%. Deal traits: {traits}."
        ),
        "context": "sales forecast entered by a rep",
        "timestamp": f"{deal['forecast_date']}T10:00:00Z",
        "tags": _tags(deal, "forecast"),
        "document_id": f"forecast-{deal['deal_id']}",
    }


def outcome_item(deal: dict) -> dict:
    traits = ", ".join(_traits(deal)) or "none"
    return {
        "content": (
            f"The {deal['account']} deal ({deal['rep_name']}, {deal['product']}) was "
            f"{deal['outcome']} on {deal['close_date']}. {deal['rep_name']} had forecast "
            f"{_pct(deal['stated_prob'])}%. Deal traits: {traits}."
        ),
        "context": "deal outcome from CRM",
        "timestamp": f"{deal['close_date']}T18:00:00Z",
        "tags": _tags(deal, "outcome"),
        "document_id": f"outcome-{deal['deal_id']}",
    }


def self_check_item(deal: dict, corrected_prob: float, was_right: bool) -> dict:
    return {
        "content": (
            f"I adjusted {deal['rep_name']}'s {deal['account']} forecast from "
            f"{_pct(deal['stated_prob'])}% to {_pct(corrected_prob)}%. The deal was "
            f"{deal['outcome']}, so my correction was {'right' if was_right else 'wrong'}."
        ),
        "context": "the calibration agent's own correction and its result",
        "timestamp": f"{deal['close_date']}T18:05:00Z",
        "tags": _tags(deal, "self-check"),
        "document_id": f"selfcheck-{deal['deal_id']}",
    }


# ---------------------------------------------------------------------------
# Save (retain)
# ---------------------------------------------------------------------------

def _retain(item: dict) -> None:
    get_client().retain(bank_id=bank_id(), **item)


def retain_forecast(deal: dict) -> None:
    _retain(forecast_item(deal))


def retain_outcome(deal: dict) -> None:
    _retain(outcome_item(deal))


def retain_self_check(deal: dict, corrected_prob: float, was_right: bool) -> None:
    _retain(self_check_item(deal, corrected_prob, was_right))


def retain_many(items: list[dict], chunk: int = 25) -> None:
    """Save many items with a few calls instead of one per item (much faster for the replay).

    Build items with forecast_item / outcome_item / self_check_item.
    """
    client = get_client()
    for i in range(0, len(items), chunk):
        client.retain_batch(bank_id=bank_id(), items=items[i:i + chunk])


def correction_was_right(stated: float, corrected: float, outcome: str) -> bool:
    """Right = the correction moved the forecast closer to what happened."""
    actual = 1.0 if outcome == "won" else 0.0
    return abs(corrected - actual) <= abs(stated - actual)


# ---------------------------------------------------------------------------
# Look up (recall)
# ---------------------------------------------------------------------------

def recall_rep_history(rep_id: str, query: str, limit: int = 5) -> list[dict]:
    """A rep's closed-deal facts most similar to ``query``. Each has text and deal_id (if known)."""
    resp = get_client().recall(
        bank_id=bank_id(),
        query=query,
        types=["world"],
        tags=[f"rep:{rep_id}", "kind:outcome"],
        tags_match="all_strict",
        budget="mid",
    )
    hits = []
    for r in resp.results[:limit]:
        doc = r.document_id or ""
        hits.append({
            "deal_id": doc.removeprefix("outcome-") if doc.startswith("outcome-") else None,
            "text": r.text,
        })
    return hits


def recall_beliefs(rep_id: str, limit: int = 5) -> list[str]:
    """Hindsight's current beliefs (observations) about a rep, for the belief timeline."""
    resp = get_client().recall(
        bank_id=bank_id(),
        query="How accurate are this rep's forecasts, by deal type?",
        types=["observation"],
        tags=[f"rep:{rep_id}"],
        tags_match="all_strict",
    )
    return [r.text for r in resp.results[:limit]]


# ---------------------------------------------------------------------------
# Think it over (reflect) -> calibration card
# ---------------------------------------------------------------------------

def _reflect_card(query: str, tags: list[str] | None) -> dict | None:
    kwargs: dict[str, Any] = {"bank_id": bank_id(), "query": query, "budget": "mid",
                              "response_schema": CARD_SCHEMA}
    if tags:
        kwargs.update(tags=tags, tags_match="all_strict")
    resp = get_client().reflect(**kwargs)
    if resp.structured_output_error:
        log.warning("reflect structured output error: %s", resp.structured_output_error)
    return resp.structured_output


def _previous_quarter(quarter: str) -> str:
    year_text, q_text = quarter.split("-Q", maxsplit=1)
    year, q = int(year_text), int(q_text)
    return f"{year - 1}-Q4" if q == 1 else f"{year}-Q{q - 1}"


def reflect_calibration_card(rep_id: str, rep_name: str, quarter: str | None = None) -> dict:
    """Build a rep's calibration card. Tries twice, then falls back to an empty card.

    Never raises, so the replay can't crash here.
    """
    raw = None
    prior_forecast_quarter = _previous_quarter(quarter) if quarter else None
    query = CARD_QUERY.format(
        rep_name=rep_name,
        forecast_quarter=prior_forecast_quarter or "the latest completed forecast cohort",
    )
    tags = [f"rep:{rep_id}"]
    if prior_forecast_quarter:
        tags.append(f"forecast-quarter:{prior_forecast_quarter}")
    for attempt in (1, 2):
        try:
            raw = _reflect_card(query, tags)
            if raw:
                break
        except Exception as exc:  # noqa: BLE001
            log.warning("reflect failed for %s (attempt %d): %s", rep_id, attempt, exc)
    card = parse_card(raw) if raw else empty_card()
    if raw is None:
        card["reflection_failed"] = True
    return {"rep_id": rep_id, "quarter": quarter, **card}


def reflect_team_card(quarter: str | None = None) -> dict:
    """Team-wide patterns, for reps with no history yet (cold start)."""
    try:
        raw = _reflect_card(TEAM_CARD_QUERY, None)
    except Exception as exc:  # noqa: BLE001
        log.warning("team reflect failed: %s", exc)
        raw = None
    card = parse_card(raw) if raw else empty_card()
    return {"rep_id": "team", "quarter": quarter, **card}


def reflect_answer(question: str) -> tuple[str, list[str]]:
    """Free question over the whole bank. Returns (answer, the memories it was based on)."""
    resp = get_client().reflect(bank_id=bank_id(), query=question, budget="mid",
                                include_facts=True)
    based_on = []
    if resp.based_on and resp.based_on.memories:
        based_on = [m.text for m in resp.based_on.memories[:5]]
    return resp.text, based_on
