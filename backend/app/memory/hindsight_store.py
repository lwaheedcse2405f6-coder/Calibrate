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

from app import config  # noqa: F401 (loads .env)
from app.agent.card import TRAITS, build_card, empty_card, parse_card

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts live here so they're quick to tweak at 3 AM.
# ---------------------------------------------------------------------------

CARD_QUERY = (
    "Compare {rep_name}'s stated forecast confidence with actual outcomes, using only deals that "
    "have closed (won or lost). Group the deals by these traits: single_contact_no_finance, "
    "large_deal, end_of_quarter, and overall (all of the rep's closed deals). For each group give: "
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

SUMMARY_QUERY = (
    "In one or two plain sentences for a sales manager, say how reliable {rep_name}'s forecasts "
    "are and where to be careful. Use the measured track record given as context, quote its "
    "numbers and deal counts exactly, and mention if the pattern seems to be changing recently."
)

SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

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


def _tags(deal: dict, kind: str) -> list[str]:
    return [f"rep:{deal['rep_id']}", f"quarter:{deal['quarter']}", f"kind:{kind}"]


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
        # Exact numbers ride along with the memory, so the card can be measured from it.
        "metadata": {
            "deal_id": str(deal["deal_id"]),
            "rep_id": str(deal["rep_id"]),
            "stated_prob": str(float(deal["stated_prob"])),
            "outcome": str(deal["outcome"]),
            "traits": ";".join(_traits(deal)),
            "close_date": str(deal["close_date"]),
        },
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
    _TRACK_CACHE.clear()


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
    _TRACK_CACHE.clear()


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
# Track record: every closed deal the bank remembers, with exact numbers
# ---------------------------------------------------------------------------

_TRACK_CACHE: dict[str, dict[str, list[dict]]] = {}   # bank -> rep -> records; cleared on save
PAGE_SIZE = 100


def _all_outcome_records() -> dict[str, list[dict]]:
    """Read every outcome memory in the bank (paged), grouped by rep. One read per quarter."""
    bank = bank_id()
    if bank in _TRACK_CACHE:
        return _TRACK_CACHE[bank]
    client = get_client()
    by_rep: dict[str, dict[str, dict]] = {}
    offset = 0
    while True:
        page = client.list_memories(bank_id=bank, limit=PAGE_SIZE, offset=offset)
        items = page.items or []
        for m in items:
            meta = m.metadata or {}
            if "stated_prob" not in meta or meta.get("outcome") not in ("won", "lost"):
                continue
            # One saved outcome can become several facts: keep one record per deal.
            by_rep.setdefault(str(meta.get("rep_id")), {})[str(meta.get("deal_id"))] = {
                "deal_id": str(meta.get("deal_id")),
                "stated_prob": float(meta["stated_prob"]),
                "outcome": meta["outcome"],
                "traits": [t for t in str(meta.get("traits", "")).split(";") if t],
                "close_date": meta.get("close_date"),
            }
        offset += len(items)
        if not items or offset >= (page.total or 0):
            break
    _TRACK_CACHE[bank] = {rep: list(d.values()) for rep, d in by_rep.items()}
    return _TRACK_CACHE[bank]


def rep_track_record(rep_id: str) -> list[dict]:
    """A rep's closed deals as remembered in Hindsight: stated %, outcome, traits."""
    return _all_outcome_records().get(rep_id, [])


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


def reflect_calibration_card(rep_id: str, rep_name: str, quarter: str | None = None) -> dict:
    """Build a rep's calibration card. Never raises, so the replay can't crash here.

    1. Read the rep's track record back from Hindsight and measure the rules exactly.
    2. Ask reflect to explain them in plain words (it also sees observations and directives).
    If the track record isn't available (no metadata on the memories), fall back to asking
    reflect for the whole card.
    """
    try:
        records = rep_track_record(rep_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("track record read failed for %s: %s", rep_id, exc)
        records = []

    if records:
        card = build_card(records)
        if card["rules"]:
            card["summary"] = _explain_card(rep_id, rep_name, card) or \
                card["summary"].replace("Rep ", f"{rep_name} ", 1)
        return {"rep_id": rep_id, "quarter": quarter, "source": "track_record",
                "deals_remembered": len(records), **card}

    raw = None
    for attempt in (1, 2):
        try:
            raw = _reflect_card(CARD_QUERY.format(rep_name=rep_name), [f"rep:{rep_id}"])
            if raw:
                break
        except Exception as exc:  # noqa: BLE001
            log.warning("reflect failed for %s (attempt %d): %s", rep_id, attempt, exc)
    card = parse_card(raw) if raw else empty_card()
    return {"rep_id": rep_id, "quarter": quarter, "source": "reflect", **card}


def _explain_card(rep_id: str, rep_name: str, card: dict) -> str | None:
    """One reflect call: a plain-English summary of the measured card, in Hindsight's words."""
    measured = "; ".join(
        f"{r['condition']}: says {r['stated_avg']:.0%} on average, wins {r['actual_rate']:.0%} "
        f"({r['evidence_count']} deals) -> {r['direction']}"
        for r in card["rules"]
    )
    try:
        resp = get_client().reflect(
            bank_id=bank_id(),
            query=SUMMARY_QUERY.format(rep_name=rep_name),
            context=f"Measured track record for {rep_name}: {measured}",
            tags=[f"rep:{rep_id}"],
            tags_match="all_strict",
            budget="low",
            response_schema=SUMMARY_SCHEMA,
        )
        text = (resp.structured_output or {}).get("summary") or resp.text
        return str(text).strip() or None
    except Exception as exc:  # noqa: BLE001 (the measured summary is a fine fallback)
        log.warning("summary reflect failed for %s: %s", rep_id, exc)
        return None


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
