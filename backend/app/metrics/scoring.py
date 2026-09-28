"""
backend/app/metrics/scoring.py
================================
Production-grade scoring functions for Calibrate.

Upgrade from v1: scoring functions now consume data shaped exactly like the
project's API contract — dicts that merge the POST /api/forecast/correct
request + response payloads with a final ground-truth outcome field.

API contract shape per deal (see mock dataset below):
  amount_inr     (int)   — deal value in Indian Rupees
  stated_prob    (float) — rep's raw stated win probability  [0, 1]
  corrected_prob (float) — agent-calibrated probability      [0, 1]
  actual_outcome (int)   — ground truth: 1 = Won, 0 = Lost

All original v1 functions are preserved and unchanged below the new section.
"""

from __future__ import annotations

from datetime import date
from typing import Any


Deal = dict[str, Any]


# ===========================================================================
# NEW — API-contract compliant mock dataset (12 varied deals)
# ===========================================================================
#
# Deal design rationale:
#   - Deals A001-A003: Large-ticket (> ₹30L) — rep over-confident, AI corrects down
#   - Deals A004-A006: Small-ticket (< ₹5L)  — Jordan-style sandbagging, AI corrects up
#   - Deals A007-A008: End-of-quarter pressure — inflation burst, AI corrects down
#   - Deals A009-A010: Single contact, no finance — high-risk, AI corrects down
#   - Deals A011-A012: Well-calibrated territory — AI barely moves the number
#
# Expected Brier score story:
#   Trust the Rep  >  Historical Baseline  >  Agent Calibrated
#   (rep's raw stated_prob is worst; calibration is best)
#
MOCK_API_DEALS: list[Deal] = [
    # --- Large deals: rep over-states, AI corrects down ---
    {
        "deal_id": "A001", "quarter": "Q1-2025",
        "amount_inr": 5_000_000,
        "stated_prob": 0.85, "corrected_prob": 0.62, "actual_outcome": 0,   # Lost
        "tags": ["large_deal", "end_of_quarter"],
    },
    {
        "deal_id": "A002", "quarter": "Q2-2025",
        "amount_inr": 4_200_000,
        "stated_prob": 0.80, "corrected_prob": 0.58, "actual_outcome": 1,   # Won
        "tags": ["large_deal"],
    },
    {
        "deal_id": "A003", "quarter": "Q3-2025",
        "amount_inr": 3_800_000,
        "stated_prob": 0.75, "corrected_prob": 0.55, "actual_outcome": 0,   # Lost
        "tags": ["large_deal"],
    },

    # --- Small deals: sandbagging, AI corrects up ---
    {
        "deal_id": "A004", "quarter": "Q1-2025",
        "amount_inr": 450_000,
        "stated_prob": 0.35, "corrected_prob": 0.68, "actual_outcome": 1,   # Won
        "tags": ["single_contact_no_finance"],
    },
    {
        "deal_id": "A005", "quarter": "Q1-2025",
        "amount_inr": 380_000,
        "stated_prob": 0.40, "corrected_prob": 0.72, "actual_outcome": 1,   # Won
        "tags": ["single_contact_no_finance"],
    },
    {
        "deal_id": "A006", "quarter": "Q2-2025",
        "amount_inr": 290_000,
        "stated_prob": 0.30, "corrected_prob": 0.55, "actual_outcome": 0,   # Lost
        "tags": ["single_contact_no_finance"],
    },

    # --- End-of-quarter pressure: over-inflated confidence ---
    {
        "deal_id": "A007", "quarter": "Q2-2025",
        "amount_inr": 1_500_000,
        "stated_prob": 0.90, "corrected_prob": 0.70, "actual_outcome": 1,   # Won (inflated)
        "tags": ["end_of_quarter"],
    },
    {
        "deal_id": "A008", "quarter": "Q3-2025",
        "amount_inr": 2_000_000,
        "stated_prob": 0.88, "corrected_prob": 0.65, "actual_outcome": 0,   # Lost — classic EoQ miss
        "tags": ["end_of_quarter", "large_deal"],
    },

    # --- Single contact, no finance contact — inherently high risk ---
    {
        "deal_id": "A009", "quarter": "Q3-2025",
        "amount_inr": 800_000,
        "stated_prob": 0.70, "corrected_prob": 0.45, "actual_outcome": 0,   # Lost
        "tags": ["single_contact_no_finance"],
    },
    {
        "deal_id": "A010", "quarter": "Q4-2025",
        "amount_inr": 950_000,
        "stated_prob": 0.65, "corrected_prob": 0.50, "actual_outcome": 1,   # Won
        "tags": ["single_contact_no_finance"],
    },

    # --- Well-calibrated deals: rep is accurate, AI barely moves ---
    {
        "deal_id": "A011", "quarter": "Q4-2025",
        "amount_inr": 600_000,
        "stated_prob": 0.55, "corrected_prob": 0.57, "actual_outcome": 1,   # Won
        "tags": ["overall"],
    },
    {
        "deal_id": "A012", "quarter": "Q4-2025",
        "amount_inr": 700_000,
        "stated_prob": 0.45, "corrected_prob": 0.43, "actual_outcome": 0,   # Lost
        "tags": ["overall"],
    },
]

# Historical win rate used as the flat baseline (63% — computed from internal CRM data)
HISTORICAL_BASELINE_PROB: float = 0.63


# ===========================================================================
# NEW — API-contract compliant Brier scorer
# ===========================================================================

def brier_score_from_deals(
    deals: list[Deal],
    prob_key: str,
    flat_prob: float | None = None,
) -> float:
    """
    Compute the Brier Score from a list of API-contract deal dicts.

    Args:
        deals:     List of deal dicts containing `actual_outcome` (int).
        prob_key:  Key to read the probability from each deal dict
                   (e.g. "stated_prob", "corrected_prob").
                   Ignored when `flat_prob` is set.
        flat_prob: If set, use this single probability for every deal
                   (used for the historical baseline strategy).

    Returns:
        Brier Score rounded to 4 decimal places. Lower = better.

    Raises:
        ValueError: If deals list is empty or prob_key is missing from a deal.
        ValueError: If a probability is outside [0, 1].
    """
    if not deals:
        raise ValueError("deals list must not be empty.")

    total = 0.0
    for d in deals:
        prob = flat_prob if flat_prob is not None else d[prob_key]
        if not (0.0 <= prob <= 1.0):
            raise ValueError(
                f"Probability {prob} for deal {d.get('deal_id')} is out of range [0, 1]."
            )
        total += (prob - d["actual_outcome"]) ** 2

    return round(total / len(deals), 4)


def compare_strategies(deals: list[Deal]) -> dict[str, Any]:
    """
    Compute and compare all three Brier score strategies for a deal set.

    Returns:
        Dict with per-strategy scores, improvement deltas, and deal count.
    """
    trust_the_rep      = brier_score_from_deals(deals, "stated_prob")
    agent_calibrated   = brier_score_from_deals(deals, "corrected_prob")
    historical_baseline = brier_score_from_deals(
        deals, "", flat_prob=HISTORICAL_BASELINE_PROB
    )

    improvement_vs_rep      = round(trust_the_rep - agent_calibrated, 4)
    improvement_vs_baseline = round(historical_baseline - agent_calibrated, 4)

    return {
        "deal_count":           len(deals),
        "trust_the_rep":        trust_the_rep,
        "agent_calibrated":     agent_calibrated,
        "historical_baseline":  historical_baseline,
        "improvement_vs_rep":   improvement_vs_rep,       # positive = calibration helped
        "improvement_vs_baseline": improvement_vs_baseline,
    }


# ===========================================================================
# PRESERVED v1 — Core probabilistic accuracy metric
# ===========================================================================

def brier_score(forecasts: list[float], actuals: list[int]) -> float:
    """
    Compute the Brier Score — mean squared error between probability
    forecasts and binary outcomes.

    Formula:  BS = (1/N) * sum((forecast_i - actual_i)^2)

    Lower is better. Perfect calibration = 0.0. Random = 0.25.

    Args:
        forecasts: List of probabilities in [0.0, 1.0].
        actuals:   List of binary outcomes (1 = Won, 0 = Lost).

    Returns:
        float: Brier Score rounded to 4 decimal places.

    Raises:
        ValueError: If lists are empty or have different lengths,
                    or a probability is outside [0, 1].
    """
    if not forecasts or not actuals:
        raise ValueError("forecasts and actuals must not be empty.")
    if len(forecasts) != len(actuals):
        raise ValueError(
            f"Length mismatch: {len(forecasts)} forecasts vs {len(actuals)} actuals."
        )
    for p in forecasts:
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"Forecast probability {p} is out of range [0, 1].")

    n = len(forecasts)
    total = sum((f - a) ** 2 for f, a in zip(forecasts, actuals))
    return round(total / n, 4)


# ===========================================================================
# PRESERVED v1 — Revenue accuracy metric
# ===========================================================================

def revenue_error_per_quarter(
    deals: list[Deal],
    quarter: str,
) -> dict[str, float]:
    """
    Compute the aggregate revenue forecast error for a given quarter.

    For each closed deal in the quarter:
        error = forecasted_revenue - actual_revenue

    Positive error -> rep over-forecasted (optimism bias).
    Negative error -> rep under-forecasted (sandbagging).
    """
    closed_in_quarter = [
        d for d in deals
        if d.get("quarter") == quarter and d.get("status") == "closed"
    ]

    if not closed_in_quarter:
        return {
            "quarter":        quarter,
            "total_forecast": 0.0,
            "total_actual":   0.0,
            "total_error":    0.0,
            "mae":            0.0,
            "deal_count":     0,
        }

    total_forecast = sum(d["forecasted_revenue"] for d in closed_in_quarter)
    total_actual   = sum(d["actual_revenue"]     for d in closed_in_quarter)
    total_error    = total_forecast - total_actual
    mae = sum(
        abs(d["forecasted_revenue"] - d["actual_revenue"])
        for d in closed_in_quarter
    ) / len(closed_in_quarter)

    return {
        "quarter":        quarter,
        "total_forecast": round(total_forecast, 2),
        "total_actual":   round(total_actual,   2),
        "total_error":    round(total_error,    2),
        "mae":            round(mae,            2),
        "deal_count":     len(closed_in_quarter),
    }


# ===========================================================================
# PRESERVED v1 — Baseline: "Trust the Rep"
# ===========================================================================

def baseline_trust_the_rep(deals: list[Deal]) -> list[float]:
    """
    Baseline: accept each rep's stated win probability at face value.

    Args:
        deals: List of deal dicts with a "rep_probability" field.

    Returns:
        List of raw rep probabilities in the same order as input deals.
    """
    return [d["rep_probability"] for d in deals]


# ===========================================================================
# PRESERVED v1 — Baseline: "Historical Win Rate"
# ===========================================================================

def baseline_historical_win_rate(
    deals: list[Deal],
    rep_id: str,
    before_date: date | None = None,
) -> float:
    """
    Baseline: compute a rep's historical win rate from closed deals.

    Args:
        deals:       Full deal history.
        rep_id:      The rep whose win rate to compute.
        before_date: If set, only consider deals closed strictly before this
                     date (enforces the no-peeking rule for backtests).

    Returns:
        float: Win rate in [0.0, 1.0]. Returns 0.5 (neutral prior) if the
               rep has no closed history.
    """
    rep_deals = [
        d for d in deals
        if d.get("rep_id") == rep_id and d.get("status") == "closed"
    ]

    if before_date is not None:
        rep_deals = [
            d for d in rep_deals
            if date.fromisoformat(d["close_date"]) < before_date
        ]

    if not rep_deals:
        return 0.5

    wins = sum(1 for d in rep_deals if d.get("outcome") == "won")
    return round(wins / len(rep_deals), 4)


# ===========================================================================
# PRESERVED v1 — Mock deal dataset (used by v1 tests)
# ===========================================================================

MOCK_DEALS: list[Deal] = [
    {
        "deal_id": "D001", "rep_id": "rep_maya", "rep_name": "Maya Chen",
        "quarter": "Q1-2025", "rep_probability": 0.90, "actual_outcome": 1,
        "forecasted_revenue": 120_000, "actual_revenue": 110_000,
        "status": "closed", "close_date": "2025-03-15", "outcome": "won",
    },
    {
        "deal_id": "D002", "rep_id": "rep_maya", "rep_name": "Maya Chen",
        "quarter": "Q1-2025", "rep_probability": 0.75, "actual_outcome": 0,
        "forecasted_revenue": 80_000, "actual_revenue": 0,
        "status": "closed", "close_date": "2025-03-28", "outcome": "lost",
    },
    {
        "deal_id": "D003", "rep_id": "rep_maya", "rep_name": "Maya Chen",
        "quarter": "Q2-2025", "rep_probability": 0.85, "actual_outcome": 1,
        "forecasted_revenue": 95_000, "actual_revenue": 98_000,
        "status": "closed", "close_date": "2025-06-20", "outcome": "won",
    },
    {
        "deal_id": "D004", "rep_id": "rep_jordan", "rep_name": "Jordan Walsh",
        "quarter": "Q1-2025", "rep_probability": 0.40, "actual_outcome": 1,
        "forecasted_revenue": 50_000, "actual_revenue": 75_000,
        "status": "closed", "close_date": "2025-03-10", "outcome": "won",
    },
    {
        "deal_id": "D005", "rep_id": "rep_jordan", "rep_name": "Jordan Walsh",
        "quarter": "Q1-2025", "rep_probability": 0.35, "actual_outcome": 1,
        "forecasted_revenue": 40_000, "actual_revenue": 60_000,
        "status": "closed", "close_date": "2025-03-25", "outcome": "won",
    },
    {
        "deal_id": "D006", "rep_id": "rep_maya", "rep_name": "Maya Chen",
        "quarter": "Q2-2025", "rep_probability": 0.60, "actual_outcome": None,
        "forecasted_revenue": 200_000, "actual_revenue": None,
        "status": "pending", "close_date": None, "outcome": None,
    },
]


# ===========================================================================
# Quick smoke-test — run: python -m backend.app.metrics.scoring
# ===========================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("CALIBRATE - Scoring Engine v2 Smoke Test")
    print("=" * 65)

    # --- New: 3-strategy comparison on API-contract deals ---
    stats = compare_strategies(MOCK_API_DEALS)
    print(f"\n{'Strategy':<25} {'Brier Score':>12}  {'vs Rep':>10}")
    print("-" * 52)
    print(f"{'Trust the Rep':<25} {stats['trust_the_rep']:>12.4f}  {'(baseline)':>10}")
    print(f"{'Historical Baseline':<25} {stats['historical_baseline']:>12.4f}  "
          f"{stats['trust_the_rep'] - stats['historical_baseline']:>+10.4f}")
    print(f"{'Agent Calibrated':<25} {stats['agent_calibrated']:>12.4f}  "
          f"{stats['improvement_vs_rep']:>+10.4f}")
    print(f"\n  Calibration improvement vs rep:      {stats['improvement_vs_rep']:+.4f}")
    print(f"  Calibration improvement vs baseline: {stats['improvement_vs_baseline']:+.4f}")
    print(f"  Deals evaluated: {stats['deal_count']}")

    # --- Legacy v1 smoke test ---
    print(f"\n{'-'*65}")
    print("Legacy v1 functions (preserved for backward compat):")
    closed = [d for d in MOCK_DEALS if d["status"] == "closed"]
    forecasts = [d["rep_probability"] for d in closed]
    actuals   = [d["actual_outcome"]  for d in closed]
    bs = brier_score(forecasts, actuals)
    print(f"  Brier Score (v1 closed deals): {bs}")

    q1_err = revenue_error_per_quarter(MOCK_DEALS, "Q1-2025")
    print(f"  Revenue Error Q1-2025: total_error={q1_err['total_error']:,}")
    print("=" * 65)


# ===========================================================================
# TEAM-SPEC v3 — Pandas Brier layer (verbatim from project leads)
# ===========================================================================
# These functions are the canonical implementation agreed across all roles.
# Do not modify the function signatures or internal logic without team sign-off.
#
# Requires: pandas (see requirements.txt)
# ===========================================================================

import json as _json
from pathlib import Path as _Path

import pandas as _pd


def brier(probs: _pd.Series, outcomes: _pd.Series) -> float:
    """
    Compute the Brier Score using pandas Series.

    VERBATIM team-spec implementation — do not alter.

    Args:
        probs:    pd.Series of float probabilities in [0, 1].
        outcomes: pd.Series of str outcome labels ("won" or "lost").

    Returns:
        float: Mean squared error between probabilities and binary outcomes.
    """
    won = (outcomes == "won").astype(float)
    return float(((probs - won) ** 2).mean())


def compute_historical_baseline_probs(deals_df: _pd.DataFrame) -> _pd.Series:
    """
    Compute historical win rate baseline probability for each closed deal.
    For each closed deal, calculate historical win rate using only deals closed strictly
    before this deal's forecast_date. If no deals closed prior, returns 0.5.
    """
    closed_mask = deals_df["outcome"].isin(["won", "lost"])
    closed_deals = deals_df[closed_mask].copy()

    if "forecast_date" not in deals_df.columns or "close_date" not in deals_df.columns:
        return _pd.Series(0.5, index=deals_df.index)

    baseline_probs = []
    for idx, row in deals_df.iterrows():
        if row["outcome"] not in ("won", "lost"):
            baseline_probs.append(None)
            continue
        f_date = row.get("forecast_date")
        if not f_date or _pd.isna(f_date):
            baseline_probs.append(0.5)
            continue
        prior_closed = closed_deals[closed_deals["close_date"] < str(f_date)]
        if len(prior_closed) == 0:
            rate = 0.5
        else:
            rate = float((prior_closed["outcome"] == "won").mean())
        baseline_probs.append(rate)

    return _pd.Series(baseline_probs, index=deals_df.index)


def scores_by_quarter(deals: _pd.DataFrame) -> list[dict]:
    """
    Compute per-quarter Brier scores for all three strategies.

    Expected DataFrame columns:
        quarter, outcome, stated_prob, corrected_prob (optional), baseline_prob (optional)

    Returns:
        List of dicts, one per quarter, with keys:
            quarter, reps, agent_off, agent_on, baseline_win_rate
    """
    closed = deals[deals["outcome"].isin(["won", "lost"])].copy()

    if "traits" in closed.columns:
        closed["traits"] = closed["traits"].fillna("")

    if "baseline_prob" not in closed.columns or closed["baseline_prob"].isnull().any():
        closed["baseline_prob"] = compute_historical_baseline_probs(closed)

    has_corrected = "corrected_prob" in closed.columns and not closed["corrected_prob"].isnull().all()

    rows = []
    for q, g in closed.groupby("quarter"):
        row = {
            "quarter":          q,
            "reps":             round(brier(g["stated_prob"],    g["outcome"]), 3),
            "agent_off":        round(brier(g["stated_prob"],    g["outcome"]), 3),
            "agent_on":         round(brier(g["corrected_prob"] if has_corrected else g["stated_prob"], g["outcome"]), 3),
            "baseline_win_rate": round(brier(g["baseline_prob"], g["outcome"]), 3),
        }
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# File I/O wrapper
# ---------------------------------------------------------------------------

def write_scores_to_run(run_dir: _Path) -> _Path:
    """
    Read deals from a run directory and write per-quarter Brier scores to
    ``scores.json`` in the same directory.

    Supported inputs:
      - ``<run_dir>/deals.json`` (with optional merge from ``<run_dir>/deals.csv``)
      - ``<run_dir>/deals.csv``
      - Default ``backend/data/deals.csv``

    Args:
        run_dir: Path to the run directory (e.g. Path("data/runs/demo")).

    Returns:
        Path to the written scores.json file.
    """
    deals_json_path = run_dir / "deals.json"
    deals_csv_path = run_dir / "deals.csv"
    default_csv_path = _Path("backend/data/deals.csv")

    if deals_json_path.exists():
        raw = _json.loads(deals_json_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "deals" in raw:
            deals_df = _pd.DataFrame(list(raw["deals"].values()))
        elif isinstance(raw, list):
            deals_df = _pd.DataFrame(raw)
        elif isinstance(raw, dict):
            deals_df = _pd.DataFrame(list(raw.values()))
        else:
            deals_df = _pd.DataFrame(raw)

        if deals_csv_path.exists():
            csv_df = _pd.read_csv(deals_csv_path)
            for col in csv_df.columns:
                if col not in deals_df.columns:
                    deals_df[col] = csv_df[col]
    elif deals_csv_path.exists():
        deals_df = _pd.read_csv(deals_csv_path)
    elif default_csv_path.exists():
        deals_df = _pd.read_csv(default_csv_path)
    else:
        raise FileNotFoundError(f"Neither deals.json nor deals.csv found in {run_dir}")

    scores = scores_by_quarter(deals_df)

    out_path = run_dir / "scores.json"
    out_path.write_text(_json.dumps(scores, indent=2), encoding="utf-8")
    print(f"[scoring] scores.json written -> {out_path}")
    return out_path


