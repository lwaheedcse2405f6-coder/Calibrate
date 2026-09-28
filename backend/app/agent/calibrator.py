"""The calibrator: turns a calibration card into a corrected forecast, with a reason.

Owner: Role 2.

- ``apply_card(card, deal)``: pure Python. Fast, free, repeatable. The replay calls this per deal.
- ``correct(form, card)``: the live "correct this forecast" form (Role 1's POST /api/forecast/correct).
- ``ask(question)``: the ask box (Role 1's POST /api/ask).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from app.agent.card import MIN_EVIDENCE

log = logging.getLogger(__name__)

LARGE_DEAL_PRODUCTS = {"GTX Pro", "GTK 500"}
END_OF_QUARTER_DAYS = 14
# Calibration cards are estimates, not ground truth. Keep corrections partial
# even when Hindsight reports high confidence, so stale or noisy summaries do
# not move a forecast too far in one step.
STRENGTH = {"low": 0.125, "medium": 0.2, "high": 0.25}
PROB_MIN, PROB_MAX = 0.02, 0.98
IST = timezone(timedelta(hours=5, minutes=30))

EXPLAIN_SYSTEM = (
    "You explain a sales forecast correction to a sales manager in plain, simple English. "
    "Use only the facts given. Never mention the rep's gender, age or background. "
    'Return JSON: {"explanation": "<one sentence, must include the number of deals>", '
    '"questions_to_ask": ["<1 or 2 short questions the manager should ask the rep>"]}'
)


# ---------------------------------------------------------------------------
# Traits
# ---------------------------------------------------------------------------

def deal_traits(deal: dict) -> list[str]:
    raw = deal.get("traits") or []
    if isinstance(raw, str):
        raw = raw.split(";")
    return [t.strip() for t in raw if t and str(t).strip()]


def _quarter_end(d: date) -> date:
    q_end_month = ((d.month - 1) // 3 + 1) * 3
    nxt = date(d.year + (q_end_month == 12), q_end_month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def compute_traits(form: dict, today: date | None = None) -> list[str]:
    """The live form doesn't send traits, so work them out from its fields."""
    traits = []
    n_contacts = int(form.get("n_contacts") or 0)
    if n_contacts <= 1 and not form.get("has_finance_contact"):
        traits.append("single_contact_no_finance")
    if form.get("product") in LARGE_DEAL_PRODUCTS:
        traits.append("large_deal")
    d = today or datetime.now(IST).date()
    if (_quarter_end(d) - d).days < END_OF_QUARTER_DAYS:
        traits.append("end_of_quarter")
    return traits


# ---------------------------------------------------------------------------
# Apply a card (pure Python)
# ---------------------------------------------------------------------------

def pick_rule(card: dict | None, traits: list[str]) -> dict | None:
    """The rule that applies to this deal: a matching trait rule first, else the 'overall' rule.

    Rules based on fewer than MIN_EVIDENCE deals, or marked 'accurate', don't adjust anything.
    """
    rules = (card or {}).get("rules") or []
    usable = [r for r in rules
              if r.get("evidence_count", 0) >= MIN_EVIDENCE and r.get("direction") != "accurate"]
    specific = [r for r in usable if r.get("trait") in traits]
    overall = [r for r in usable if r.get("trait") == "overall"]
    return max(specific or overall, key=lambda r: r["evidence_count"], default=None)


def apply_card(card: dict | None, deal: dict) -> tuple[float, dict | None]:
    """Return (corrected probability, the rule used or None)."""
    stated = float(deal["stated_prob"])
    rule = pick_rule(card, deal_traits(deal))
    if rule is None:
        return stated, None
    strength = STRENGTH.get(rule.get("confidence", "low"), 0.5)
    factor = 1 + (float(rule["adjustment"]) - 1) * strength
    corrected = min(PROB_MAX, max(PROB_MIN, stated * factor))
    return round(corrected, 3), rule


def has_usable_rules(card: dict | None) -> bool:
    return any(r.get("evidence_count", 0) >= MIN_EVIDENCE for r in (card or {}).get("rules") or [])


# ---------------------------------------------------------------------------
# Live form: correct()
# ---------------------------------------------------------------------------

def _template_explanation(rep_name: str, rule: dict | None, stated: float, corrected: float,
                          cold_start: bool) -> str:
    if rule is None:
        return (f"No clear pattern in {rep_name}'s past forecasts for deals like this, "
                f"so the forecast stays at {round(stated * 100)}%.")
    who = "Across the team, deals" if cold_start else f"{rep_name}'s deals"
    cond = rule.get("condition") or rule["trait"].replace("_", " ")
    n = rule["evidence_count"]
    if rule.get("stated_avg") is not None and rule.get("actual_rate") is not None:
        return (f"{who} matching '{cond}' were forecast at {round(rule['stated_avg'] * 100)}% "
                f"on average but closed {round(rule['actual_rate'] * 100)}% of the time "
                f"(based on {n} deals). Adjusted from {round(stated * 100)}% to "
                f"{round(corrected * 100)}%.")
    return (f"{who} matching '{cond}' are usually {'over' if rule['direction'] == 'over' else 'under'}"
            f"-called (based on {n} deals). Adjusted from {round(stated * 100)}% to "
            f"{round(corrected * 100)}%.")


def _default_questions(traits: list[str], rule: dict | None) -> list[str]:
    if rule and rule["trait"] == "single_contact_no_finance":
        return ["Who controls the budget at this account?"]
    if rule and rule["trait"] == "large_deal":
        return ["Has the customer confirmed budget for a purchase this size?"]
    if rule and rule["trait"] == "end_of_quarter":
        return ["What has to happen for this to close this quarter, and is it scheduled?"]
    if rule and rule["direction"] == "under":
        return ["What's making you cautious here? Is anything actually blocking it?"]
    return ["What's the next concrete step, and when is it?"]


def _evidence(rep_id: str, traits: list[str], deals_by_id: dict | None) -> list[dict]:
    from app.memory import hindsight_store as hs

    query = (f"closed deals with traits {', '.join(traits)}" if traits
             else "closed deals and how they turned out")
    try:
        hits = hs.recall_rep_history(rep_id, query, limit=3)
    except Exception as exc:  # noqa: BLE001
        log.warning("recall failed: %s", exc)
        return []
    out = []
    for h in hits:
        d = (deals_by_id or {}).get(h["deal_id"]) if h["deal_id"] else None
        if d:
            out.append({"deal_id": h["deal_id"], "account": d.get("account"),
                        "stated": float(d.get("stated_prob")), "outcome": d.get("outcome")})
        else:
            out.append({"deal_id": h["deal_id"], "text": h["text"]})
    return out


def correct(form: dict, card: dict | None, *, rep_name: str | None = None,
            team_card: dict | None = None, deals_by_id: dict | None = None,
            today: date | None = None, use_llm: bool = True) -> dict:
    """Correct one new forecast from the live form. Returns the shape in the API contract.

    card        the rep's latest calibration card (from cards.json, or reflect fresh)
    team_card   team-wide card, used when the rep has no usable history (cold start)
    deals_by_id optional {deal_id: deal row} so evidence can show account/stated/outcome
    """
    rep_id = form["rep_id"]
    rep_name = rep_name or rep_id.title()
    traits = compute_traits(form, today)
    deal = {**form, "traits": traits}
    stated = float(form["stated_prob"])

    cold_start = not has_usable_rules(card)
    use_card = team_card if cold_start and team_card else card
    corrected, rule = apply_card(use_card, deal)

    explanation = _template_explanation(rep_name, rule, stated, corrected, cold_start)
    questions = _default_questions(traits, rule)
    if use_llm and rule is not None:
        try:
            from app.llm.groq_client import ask_json

            facts = (f"Rep: {rep_name}. Account: {form.get('account')}. Stated: "
                     f"{round(stated * 100)}%. Corrected: {round(corrected * 100)}%. "
                     f"Deal traits: {', '.join(traits) or 'none'}. Rule used: {rule}. "
                     f"{'Rep has no history; rule is team-wide.' if cold_start else ''}")
            out = ask_json(EXPLAIN_SYSTEM, facts)
            if isinstance(out.get("explanation"), str) and out["explanation"].strip():
                explanation = out["explanation"].strip()
            qs = [q for q in out.get("questions_to_ask") or [] if isinstance(q, str) and q.strip()]
            if qs:
                questions = qs[:2]
        except Exception as exc:  # noqa: BLE001 (template text is the fallback)
            log.warning("explanation LLM call failed, using template: %s", exc)

    if cold_start:
        explanation = (f"Not enough history for {rep_name} yet; using team-wide patterns. "
                       + explanation)

    return {
        "corrected_prob": corrected,
        "confidence": rule["confidence"] if rule else "low",
        "explanation": explanation,
        "evidence": [] if cold_start else _evidence(rep_id, traits, deals_by_id),
        "questions_to_ask": questions,
        "memory_used": not cold_start and rule is not None,
    }


# ---------------------------------------------------------------------------
# Ask box
# ---------------------------------------------------------------------------

def ask(question: str) -> dict:
    from app.memory import hindsight_store as hs

    try:
        answer, based_on = hs.reflect_answer(question)
    except Exception as exc:  # noqa: BLE001
        log.warning("ask failed: %s", exc)
        return {"answer": "Sorry, memory isn't reachable right now. Try again in a minute.",
                "based_on": []}
    return {"answer": answer, "based_on": based_on}
