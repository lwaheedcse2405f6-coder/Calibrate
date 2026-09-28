from fastapi import APIRouter
from pydantic import BaseModel

from app.api import mock_data

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
    stated_prob: float


class AskRequest(BaseModel):
    question: str


@router.get("/reps")
def list_reps():
    return mock_data.REPS


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
    return mock_data.CORRECTION


@router.post("/ask")
def ask(body: AskRequest):
    return mock_data.ASK_ANSWER


@router.get("/eval")
def get_eval():
    return mock_data.EVAL