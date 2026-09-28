"""Chronologically replay forecast and outcome events without future leakage.

The engine owns event ordering and durable run files. Hindsight operations are
injected through ``ReplayServices`` so the replay does not own Role 2's client.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from app.sim.personas import PERSONAS, QUARTERS, active_reps

DATA = Path(__file__).resolve().parents[2] / "data"
RUNS = DATA / "runs"
RETAIN_BATCH_SIZE = 25


class ReplayServices(Protocol):
    """Role 2 boundary required for a memory-on replay."""

    def reflect_calibration_card(self, rep_id: str, rep_name: str, quarter: str) -> dict[str, Any]: ...
    def apply_card(self, deal: dict[str, Any], card: dict[str, Any]) -> tuple[float, dict[str, Any] | None]: ...
    def forecast_item(self, deal: dict[str, Any]) -> dict[str, Any]: ...
    def outcome_item(self, deal: dict[str, Any]) -> dict[str, Any]: ...
    def self_check_item(self, deal: dict[str, Any], prediction: float, was_right: bool) -> dict[str, Any]: ...
    def retain_many(self, items: list[dict[str, Any]]) -> None: ...
    def wait_for_memory_processing(self) -> None: ...
    def snapshot_beliefs(self, rep_id: str, quarter: str, card: dict[str, Any]) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class ReplayResult:
    run_id: str
    mode: str
    output_dir: Path
    completed_quarters: tuple[str, ...]


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


def _write_json(path: Path, value: Any) -> None:
    """Atomically replace a JSON file so interrupted runs keep the last checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        try:
            os.replace(tmp_name, path)
        except PermissionError:
            # OneDrive placeholders can reject an atomic replacement while
            # still permitting an in-place update. Keep that compatibility
            # path limited to the checkpoint files stored in synced folders.
            with path.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
            os.unlink(tmp_name)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return str(value).strip().lower() in {"true", "yes", "1"}


def _deal_record(row: pd.Series) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in row.to_dict().items()}


def _events(deals: pd.DataFrame) -> dict[str, list[tuple[pd.Timestamp, int, str, dict[str, Any]]]]:
    """Group by event quarter; on a shared date forecasts precede outcomes."""
    events: dict[str, list[tuple[pd.Timestamp, int, str, dict[str, Any]]]] = {q: [] for q in QUARTERS}
    for _, row in deals.iterrows():
        deal = _deal_record(row)
        forecast_day = pd.Timestamp(deal["forecast_date"])
        forecast_q = f"{forecast_day.year}-Q{forecast_day.quarter}"
        if forecast_q not in events:
            raise ValueError(f"forecast date {deal['forecast_date']} is outside replay quarters")
        events[forecast_q].append((forecast_day, 0, "forecast", deal))
        close_date = deal.get("close_date")
        if close_date:
            outcome_day = pd.Timestamp(close_date)
            outcome_q = f"{outcome_day.year}-Q{outcome_day.quarter}"
            if outcome_q not in events:
                raise ValueError(f"close date {close_date} is outside replay quarters")
            events[outcome_q].append((outcome_day, 1, "outcome", deal))
    for rows in events.values():
        rows.sort(key=lambda event: (event[0], event[1], event[3]["deal_id"]))
    return events


def _audit_before(quarter: str, closed_deals: dict[str, dict[str, Any]]) -> str | None:
    qstart = pd.Period(quarter, freq="Q").start_time
    prior = [d["close_date"] for d in closed_deals.values() if pd.Timestamp(d["close_date"]) < qstart]
    return max(prior) if prior else None


def _is_right(stated: float, corrected: float, outcome: str) -> bool:
    actual = 1.0 if outcome == "won" else 0.0
    return abs(corrected - actual) <= abs(stated - actual)


def _quarter_totals(
    deals: list[dict[str, Any]], predictions: dict[str, float]
) -> dict[str, dict[str, int]]:
    by_close_q: dict[str, dict[str, int]] = {}
    for deal in deals:
        if deal["outcome"] == "pending" or not deal.get("close_date"):
            continue
        q = str(deal["quarter"])
        totals = by_close_q.setdefault(q, {"reps_forecast_inr": 0, "agent_forecast_inr": 0, "actual_inr": 0})
        amount = int(deal["amount_inr"])
        totals["reps_forecast_inr"] += round(float(deal["stated_prob"]) * amount)
        totals["agent_forecast_inr"] += round(float(predictions.get(deal["deal_id"], deal["stated_prob"])) * amount)
        if deal["outcome"] == "won":
            totals["actual_inr"] += amount
    return by_close_q


def run(
    mode: str,
    run_id: str,
    deals_path: Path = DATA / "deals.csv",
    output_root: Path = RUNS,
    services: ReplayServices | None = None,
    *,
    rep_id: str | None = None,
    forecast_quarter: str | None = None,
    resume: bool = True,
) -> ReplayResult:
    """Replay all or a selected subset of forecasts in calendar-quarter order.

    ``mode='off'`` trusts each rep's stated probability. ``mode='on'`` requires
    Role 2's Hindsight services; a run never silently degrades to memory off.
    Quarter progress is committed only after events and snapshots finish.
    """
    if mode not in {"on", "off"}:
        raise ValueError("mode must be 'on' or 'off'")
    if mode == "on" and services is None:
        raise RuntimeError(
            "memory-on replay needs Role 2's Hindsight ReplayServices adapter "
            "(reflect/apply/retain/snapshot); no adapter is available in this checkout"
        )
    deals = pd.read_csv(deals_path, keep_default_na=False)
    required = {"deal_id", "rep_id", "rep_name", "amount_inr", "forecast_date", "close_date", "quarter", "stated_prob", "outcome", "traits"}
    missing = required - set(deals.columns)
    if missing:
        raise ValueError(f"deals.csv missing required columns: {sorted(missing)}")
    if rep_id is not None:
        deals = deals[deals["rep_id"] == rep_id].copy()
        if deals.empty:
            raise ValueError(f"no deals found for rep_id={rep_id!r}")
    if forecast_quarter is not None:
        deals = deals[
            deals["forecast_date"].map(lambda s: f"{pd.Timestamp(s).year}-Q{pd.Timestamp(s).quarter}") == forecast_quarter
        ].copy()
        if deals.empty:
            raise ValueError(f"no deals found for forecast quarter={forecast_quarter!r}")

    records = [_deal_record(row) for _, row in deals.iterrows()]
    event_map = _events(deals)
    replay_quarters = list(QUARTERS)
    if forecast_quarter is not None:
        event_quarters = [q for q in QUARTERS if event_map[q]]
        quarter_index = QUARTERS.index(forecast_quarter)
        later_events = [q for q in event_quarters if QUARTERS.index(q) >= quarter_index]
        replay_quarters = later_events
    outdir = output_root / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    progress_file = outdir / "progress.json"
    progress = _read_json(progress_file, {"on": {"completed_quarters": []}, "off": {"completed_quarters": []}})
    mode_progress = progress.setdefault(mode, {"completed_quarters": []})
    done = set(mode_progress.get("completed_quarters", [])) if resume else set()

    data_file = outdir / "deals.json"
    stored = _read_json(data_file, {"deals": {}})
    stored.setdefault("deals", {})
    cards = _read_json(outdir / "cards.json", {})
    beliefs = _read_json(outdir / "beliefs.json", {})
    belief_updates = _read_json(outdir / "belief_updates.json", {})
    audit = _read_json(outdir / "audit.json", {})
    timings = _read_json(outdir / "timings.json", {"retain_batches": [], "first_25_batch_seconds": None})
    quarter_cards: dict[str, Any] = cards
    quarter_beliefs: dict[str, Any] = beliefs
    quarter_updates: dict[str, Any] = belief_updates
    closed_seen: dict[str, dict[str, Any]] = {}
    completed_now = list(mode_progress.get("completed_quarters", [])) if resume else []
    if not resume:
        for q in replay_quarters:
            quarter_cards.pop(q, None)
            quarter_updates.pop(q, None)
            audit.pop(q, None)
        for rep_rows in quarter_beliefs.values():
            if isinstance(rep_rows, list):
                rep_rows[:] = [row for row in rep_rows if row.get("quarter") not in QUARTERS]
        prediction_key = "memory_off_prob" if mode == "off" else "corrected_prob"
        for deal_row in stored["deals"].values():
            deal_row.pop(prediction_key, None)
            if mode == "on":
                deal_row.pop("rule", None)
        if mode == "on":
            timings = {"retain_batches": [], "first_25_batch_seconds": None, "memories_saved": 0}

    for quarter in replay_quarters:
        if quarter in done:
            # Reconstruct outcome history needed for auditing subsequent checkpoints.
            for deal in records:
                if deal.get("close_date") and str(deal["close_date"]) < str(pd.Period(quarter, freq="Q").start_time.date()):
                    closed_seen[deal["deal_id"]] = deal
            continue

        audit[quarter] = _audit_before(quarter, closed_seen)
        if mode == "on":
            quarter_cards[quarter] = {}
        forecast_reps = {
            event[3]["rep_id"]
            for event in event_map[quarter]
            if event[2] == "forecast"
        }
        if mode == "on":
            assert services is not None
            for active_rep in active_reps(quarter):
                if rep_id and active_rep != rep_id:
                    continue
                if active_rep not in forecast_reps:
                    continue
                rep_deals = [d for d in records if d["rep_id"] == active_rep]
                if not rep_deals:
                    continue
                card = services.reflect_calibration_card(active_rep, rep_deals[0]["rep_name"], quarter)
                if not isinstance(card, dict):
                    raise TypeError(f"Role 2 returned a non-object card for {active_rep} in {quarter}")
                if card.get("reflection_failed"):
                    quarter_idx = QUARTERS.index(quarter)
                    for prior_quarter in reversed(QUARTERS[:quarter_idx]):
                        prior_card = quarter_cards.get(prior_quarter, {}).get(active_rep)
                        if prior_card and prior_card.get("rules"):
                            card = {
                                **prior_card,
                                "rep_id": active_rep,
                                "quarter": quarter,
                                "fallback_from": prior_quarter,
                            }
                            print(
                                f"using {prior_quarter} calibration card for {active_rep} "
                                f"after reflection failed in {quarter}"
                            )
                            break
                quarter_cards[quarter][active_rep] = card

        memories: list[dict[str, Any]] = []
        for event_day, _, kind, deal in event_map[quarter]:
            deal_id = deal["deal_id"]
            stored["deals"][deal_id] = deal
            if kind == "forecast":
                stated = float(deal["stated_prob"])
                corrected, rule = stated, None
                if mode == "on":
                    card = quarter_cards[quarter].get(deal["rep_id"], {})
                    corrected, rule = services.apply_card(deal, card)  # type: ignore[union-attr]
                    corrected = float(corrected)
                    memories.append(services.forecast_item(deal))  # type: ignore[union-attr]
                stored["deals"][deal_id]["forecast_quarter"] = quarter
                if mode == "on":
                    stored["deals"][deal_id]["corrected_prob"] = corrected
                    stored["deals"][deal_id]["rule"] = rule
                else:
                    stored["deals"][deal_id]["memory_off_prob"] = corrected
            else:
                closed_seen[deal_id] = deal
                if mode == "on":
                    prediction = float(stored["deals"].get(deal_id, {}).get("corrected_prob", deal["stated_prob"]))
                    was_right = _is_right(float(deal["stated_prob"]), prediction, deal["outcome"])
                    memories.append(services.outcome_item(deal))  # type: ignore[union-attr]
                    memories.append(services.self_check_item(deal, prediction, was_right))  # type: ignore[union-attr]

        if mode == "on":
            assert services is not None
            for offset in range(0, len(memories), RETAIN_BATCH_SIZE):
                batch = memories[offset:offset + RETAIN_BATCH_SIZE]
                started = time.perf_counter()
                services.retain_many(batch)
                elapsed = time.perf_counter() - started
                timings["retain_batches"].append({"quarter": quarter, "count": len(batch), "seconds": round(elapsed, 3)})
                timings["memories_saved"] = int(timings.get("memories_saved", 0)) + len(batch)
                if len(batch) == RETAIN_BATCH_SIZE and timings.get("first_25_batch_seconds") is None:
                    timings["first_25_batch_seconds"] = round(elapsed, 3)
                    timings["first_25_batch_quarter"] = quarter
                    print(f"first retain_many batch ({RETAIN_BATCH_SIZE} memories): {elapsed:.2f}s in {quarter}")
                _write_json(outdir / "timings.json", timings)
            if memories:
                print(f"waiting 30s for Hindsight after {quarter}")
                services.wait_for_memory_processing()
            quarter_updates[quarter] = []
            for active_rep in active_reps(quarter):
                if rep_id and active_rep != rep_id:
                    continue
                snapshot = services.snapshot_beliefs(
                    active_rep, quarter, quarter_cards[quarter].get(active_rep, {})
                )
                if snapshot is not None:
                    rows = quarter_beliefs.setdefault(active_rep, [])
                    rows[:] = [row for row in rows if row.get("quarter") != quarter]
                    rows.append({"quarter": quarter, **snapshot})
                    quarter_updates[quarter].append({"rep_id": active_rep, **snapshot})

        completed_now.append(quarter)
        mode_progress["completed_quarters"] = completed_now
        # Each quarter is a recoverable transaction boundary.
        prediction_key = "corrected_prob" if mode == "on" else "memory_off_prob"
        predictions = {
            deal_id: deal.get(prediction_key, deal["stated_prob"])
            for deal_id, deal in stored["deals"].items()
        }
        totals = _quarter_totals(records, predictions)
        _write_json(data_file, stored)
        _write_json(outdir / f"quarters_{mode}.json", totals)
        _write_json(outdir / "cards.json", cards)
        _write_json(outdir / "beliefs.json", beliefs)
        _write_json(outdir / "belief_updates.json", belief_updates)
        _write_json(outdir / "audit.json", audit)
        _write_json(progress_file, progress)

    rep_rows = []
    for rep_key, info in PERSONAS.items():
        rep_rows.append({"rep_id": rep_key, "name": info["name"], "joins": info["joins"]})
    _write_json(outdir / "reps.json", rep_rows)
    return ReplayResult(run_id, mode, outdir, tuple(completed_now))
