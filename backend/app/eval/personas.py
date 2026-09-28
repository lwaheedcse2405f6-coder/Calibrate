"""
backend/app/eval/personas.py
==============================
Ground-truth persona registry for evaluation.
Imports directly from app.sim.personas.
"""

from __future__ import annotations

from typing import Any
from backend.app.sim.personas import PERSONAS, active_reps

SANA_REP_ID: str = "sana"

Persona = dict[str, Any]

# List of official 6 personas for iteration across evaluation suite
ALL_PERSONAS: list[Persona] = [
    {"rep_id": rep_id, **data}
    for rep_id, data in PERSONAS.items()
]

__all__ = ["PERSONAS", "SANA_REP_ID", "active_reps", "Persona", "ALL_PERSONAS"]
