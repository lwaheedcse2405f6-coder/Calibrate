"""Adapter from the replay engine to Role 2's merged Hindsight APIs.

This imports Role 2 code lazily, so the memory-off replay and tests still work
in checkouts where that code has not yet been pulled from ``main``.
"""
from __future__ import annotations

import time
from typing import Any

from app.replay.engine import RETAIN_BATCH_SIZE

MEMORY_PAUSE_SECONDS = 30


class HindsightReplayServices:
    def __init__(self, store: Any, calibrator: Any) -> None:
        self.store = store
        self.calibrator = calibrator

    def reflect_calibration_card(self, rep_id: str, rep_name: str, quarter: str) -> dict[str, Any]:
        return self.store.reflect_calibration_card(rep_id, rep_name, quarter)

    def apply_card(self, deal: dict[str, Any], card: dict[str, Any]):
        # Role 2's public signature is apply_card(card, deal).
        return self.calibrator.apply_card(card, deal)

    def forecast_item(self, deal: dict[str, Any]) -> dict[str, Any]:
        return self.store.forecast_item(deal)

    def outcome_item(self, deal: dict[str, Any]) -> dict[str, Any]:
        return self.store.outcome_item(deal)

    def self_check_item(self, deal: dict[str, Any], prediction: float, was_right: bool) -> dict[str, Any]:
        return self.store.self_check_item(deal, prediction, was_right)

    def retain_many(self, items: list[dict[str, Any]]) -> None:
        # The engine has already split the queue; keep the store's own batch
        # size explicit as a second guard against one-at-a-time saves.
        self.store.retain_many(items, chunk=RETAIN_BATCH_SIZE)

    def wait_for_memory_processing(self) -> None:
        time.sleep(MEMORY_PAUSE_SECONDS)

    def snapshot_beliefs(self, rep_id: str, quarter: str, card: dict[str, Any]) -> dict[str, Any]:
        observations = self.store.recall_beliefs(rep_id, limit=5)
        rules = card.get("rules") or []
        strongest = max(rules, key=lambda row: row.get("evidence_count", 0), default={})
        belief = "; ".join(observations) or card.get("summary", "No belief formed yet.")
        return {
            "belief": belief,
            "evidence_count": int(strongest.get("evidence_count", 0)),
            "confidence": strongest.get("confidence", "low"),
        }


def build_services() -> HindsightReplayServices:
    """Create the adapter from the Role 2 modules merged in PR #4."""
    try:
        from app.agent import calibrator
        from app.memory import hindsight_store
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Role 2's merged memory/calibrator files are missing from this checkout; "
            "pull main before running memory-on"
        ) from exc
    hindsight_store.ensure_bank()
    return HindsightReplayServices(hindsight_store, calibrator)
