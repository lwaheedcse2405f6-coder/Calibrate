import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.calibrator import ask as agent_ask
from app.agent.calibrator import correct
from app.api import mock_data
from app.db import get

router = APIRouter(prefix="/api")


class CorrectRequest(BaseModel):
    rep_id: str
    account: str
    amount_inr: int
    n_contacts: int
    has_finance_contact: bool
    has_champion: bool = False
    competitor: bool = False
    stage: str = "proposal"
    product: str | None = None
    stated_prob: float


class AskRequest(BaseModel):
    question: str


@router.get("/reps")
def list_reps():
    return get("reps") or []


@router.get("/quarters")
def get_quarters(mode: str = "on"):
    name = "quarters_on" if mode == "on" else "quarters_off"
    data = get(name) or {}

    return [
        {"quarter": quarter, **values}
        for quarter, values in sorted(data.items())
    ]


@router.get("/scores")
def get_scores():
    official = get("scores")  # Role 5's scores.json: the numbers in the README
    if official:
        return official

    deal_map = (get("deals") or {}).get("deals", {})
    data = list(deal_map.values())

    by_quarter = {}

    for deal in data:
        if deal.get("outcome") not in ("won", "lost"):
            continue  # still open: not a miss

        quarter = deal.get("forecast_quarter")
        if not quarter:
            continue

        if quarter not in by_quarter:
            by_quarter[quarter] = {
                "reps": [],
                "agent_on": [],
                "agent_off": [],
            }

        won = 1 if deal["outcome"] == "won" else 0

        stated_prob = deal.get("stated_prob")
        corrected_prob = deal.get("corrected_prob")

        if stated_prob is not None:
            by_quarter[quarter]["reps"].append(
                (stated_prob - won) ** 2
            )
            by_quarter[quarter]["agent_off"].append(
                (stated_prob - won) ** 2
            )

        if corrected_prob is not None:
            by_quarter[quarter]["agent_on"].append(
                (corrected_prob - won) ** 2
            )

    result = []

    for quarter in sorted(by_quarter):
        values = by_quarter[quarter]

        result.append(
            {
                "quarter": quarter,
                "reps": (
                    sum(values["reps"]) / len(values["reps"])
                    if values["reps"]
                    else 0
                ),
                "agent_off": (
                    sum(values["agent_off"]) / len(values["agent_off"])
                    if values["agent_off"]
                    else 0
                ),
                "agent_on": (
                    sum(values["agent_on"]) / len(values["agent_on"])
                    if values["agent_on"]
                    else 0
                ),
                "baseline_win_rate": 0,
            }
        )

    return result


@router.get("/reps/{rep_id}/card")
def get_card(rep_id: str, quarter: str | None = None):
    cards = get("cards") or {}

    if quarter:
        card = cards.get(quarter, {}).get(rep_id)
        if card:
            return {**card, "rep_id": rep_id, "quarter": quarter}

    for current_quarter in sorted(cards, reverse=True):
        card = cards.get(current_quarter, {}).get(rep_id)
        if card:
            return {
                **card,
                "rep_id": rep_id,
                "quarter": current_quarter,
            }

    return {}


@router.get("/reps/{rep_id}/beliefs")
def get_beliefs(rep_id: str):
    cards = get("cards") or {}
    result = []

    for quarter in sorted(cards):
        card = cards.get(quarter, {}).get(rep_id)

        if not card:
            continue

        rules = card.get("rules") or []

        strongest = max(
            rules,
            key=lambda rule: rule.get("evidence_count", 0),
            default={},
        )
        evidence_count = strongest.get("evidence_count", 0)
        biased = [r for r in rules if r.get("direction") not in (None, "accurate")]
        top_bias = max(biased, key=lambda r: abs(r.get("adjustment", 1.0) - 1), default={})

        result.append(
            {
                "quarter": quarter,
                "belief": card.get("summary", ""),
                "evidence_count": evidence_count,
                "confidence": strongest.get("confidence", "low"),
                "adjustment": top_bias.get("adjustment", 1.0),
            }
        )

    return result


@router.get("/reps/{rep_id}/deals")
def get_deals(rep_id: str):
    deals = (get("deals") or {}).get("deals", {})

    return [
        deal
        for deal in deals.values()
        if deal.get("rep_id") == rep_id
    ]


@router.post("/forecast/correct")
def correct_forecast(body: CorrectRequest):
    cards = get("cards") or {}

    card = next(
        (
            cards[quarter][body.rep_id]
            for quarter in sorted(cards, reverse=True)
            if body.rep_id in cards.get(quarter, {})
            and cards[quarter][body.rep_id].get("rules")
        ),
        None,
    )

    deals_by_id = (get("deals") or {}).get("deals", {})

    return correct(
        body.model_dump(),
        card,
        deals_by_id=deals_by_id,
    )


@router.post("/ask")
def ask(body: AskRequest):
    return agent_ask(body.question)


@router.get("/eval")
def get_eval():
    return get("eval") or mock_data.EVAL


REPLAY_DELAY_S = 1.5  # seconds between quarters on screen

REPLAY = [
    {
        "quarter": "2017-Q2",
        "reps_forecast_inr": 45500000,
        "agent_forecast_inr": 34100000,
        "actual_inr": 31900000,
        "belief_updates": [
            {
                "rep_id": "priya",
                "belief": "Overconfident on single-contact deals",
                "evidence_count": 9,
            }
        ],
    },
    {
        "quarter": "2017-Q3",
        "reps_forecast_inr": 42000000,
        "agent_forecast_inr": 35000000,
        "actual_inr": 33000000,
        "belief_updates": [],
    },
    {
        "quarter": "2017-Q4",
        "reps_forecast_inr": 48000000,
        "agent_forecast_inr": 39000000,
        "actual_inr": 37000000,
        "belief_updates": [],
    },
]


def replay_frames(mode: str) -> list[dict]:
    """One frame per quarter from the saved demo run, with the beliefs formed that quarter."""
    rows = get_quarters(mode)
    if not rows:
        return REPLAY  # no saved run: fall back to the sample frames
    cards = get("cards") or {}
    frames = []
    for row in rows:
        updates = []
        if mode == "on":
            for rep_id, card in sorted((cards.get(row["quarter"]) or {}).items()):
                rules = card.get("rules") or []
                if any(r.get("direction") not in (None, "accurate") for r in rules):
                    updates.append({
                        "rep_id": rep_id,
                        "belief": card.get("summary", ""),
                        "evidence_count": card.get("deals_remembered")
                        or max((r.get("evidence_count", 0) for r in rules), default=0),
                    })
        frames.append({**row, "belief_updates": updates})
    return frames


async def replay_events(mode: str):
    for item in replay_frames(mode):
        yield f"data: {json.dumps(item)}\n\n"
        await asyncio.sleep(REPLAY_DELAY_S)
    # The dashboard waits for this; without it the stream end looks like a disconnect.
    yield "event: done\ndata: {}\n\n"


@router.get("/replay/stream")
async def replay_stream(mode: str = "on"):
    return StreamingResponse(
        replay_events(mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )