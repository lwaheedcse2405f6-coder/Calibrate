import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    return mock_data.QUARTERS


@router.get("/scores")
def get_scores():
    return mock_data.SCORES


@router.get("/reps/{rep_id}/card")
def get_card(rep_id: str, quarter: str = "2017-Q3"):
    return {**mock_data.CARD, "rep_id": rep_id, "quarter": quarter}


@router.get("/reps/{rep_id}/beliefs")
def get_beliefs(rep_id: str):
    return mock_data.BELIEFS


@router.get("/reps/{rep_id}/deals")
def get_deals(rep_id: str):
    return [d for d in mock_data.DEALS if d["rep_id"] == rep_id]


@router.post("/forecast/correct")
def correct_forecast(body: CorrectRequest):
    deals_by_id = {d["deal_id"]: d for d in mock_data.DEALS}

    return correct(
        body.model_dump(),
        mock_data.CARD,
        deals_by_id=deals_by_id,
    )


@router.post("/ask")
def ask(body: AskRequest):
    return mock_data.ASK_ANSWER


@router.get("/eval")
def get_eval():
    return mock_data.EVAL
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
async def replay_events(mode: str):
    for item in REPLAY:
        yield f"data: {json.dumps(item)}\n\n"
        await asyncio.sleep(1.5)


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