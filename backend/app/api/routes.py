from fastapi import APIRouter

from app.api import mock_data

router = APIRouter(prefix="/api")


@router.get("/reps")
def list_reps():
    return mock_data.REPS


@router.get("/quarters")
def get_quarters(mode: str = "on"):
    return mock_data.QUARTERS


@router.get("/scores")
def get_scores():
    return mock_data.SCORES


@router.get("/eval")
def get_eval():
    return mock_data.EVAL