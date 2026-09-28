"""
backend/app/eval/bias_recovery.py
====================================
Production-grade Hidden-Bias Checker for Calibrate.

Fully rewritten around strict Pydantic v2 models with enum-enforced
fields for the CalibrationCard schema. The pipeline:

  1. Parse raw AI JSON through Pydantic — invalid traits, directions, or
     confidence values are rejected at the boundary with a ValidationError.
  2. Compare validated card against the rep's ground-truth bias persona.
  3. Flag false alarms (wrong bias direction detected).
  4. Export headline statistics to eval.json.

Run directly:
    python -m backend.app.eval.bias_recovery
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ValidationError

from backend.app.sim.personas import PERSONAS, active_reps
from backend.app.eval.personas import ALL_PERSONAS, Persona, SANA_REP_ID


# ===========================================================================
# Enums — enforce strict vocabulary at the API boundary
# ===========================================================================

class TraitEnum(str, Enum):
    """The deal-type categories the AI is allowed to reference."""
    single_contact_no_finance = "single_contact_no_finance"
    large_deal                = "large_deal"
    end_of_quarter            = "end_of_quarter"
    overall                   = "overall"
    other                     = "other"


class DirectionEnum(str, Enum):
    """Whether the rep over- or under-states probability for this trait."""
    over     = "over"
    under    = "under"
    accurate = "accurate"


class ConfidenceEnum(str, Enum):
    """The AI's confidence in its own bias detection for this rule."""
    low    = "low"
    medium = "medium"
    high   = "high"


# ===========================================================================
# Pydantic models
# ===========================================================================

class EvidenceDeal(BaseModel):
    """
    A single historical deal used as evidence in a calibration card.
    The `close_date` is checked against the forecast date to enforce
    the no-peeking / temporal integrity rule.
    """
    deal_id:    str
    close_date: str            # ISO date string "YYYY-MM-DD"
    outcome:    Optional[str] = None   # "won" | "lost" | None if still open


class CalibrationRule(BaseModel):
    """
    One bias observation for a specific deal-type trait.

    All three categorical fields are strictly enum-validated — an AI
    response containing an unknown trait (e.g. "vip_relationship") will
    raise a pydantic.ValidationError immediately.
    """
    trait:      TraitEnum
    direction:  DirectionEnum
    confidence: ConfidenceEnum
    note:       Optional[str] = None   # free-text explanation from the AI


class CalibrationCard(BaseModel):
    """
    The full AI-generated calibration card for one rep.

    `rules`          — list of bias rules (must all pass enum validation).
    `evidence_deals` — the historical deals the AI used; checked for
                       temporal integrity by apply_card() in tests.
    """
    summary:        str
    rules:          List[CalibrationRule]
    evidence_deals: List[EvidenceDeal] = []


# ===========================================================================
# Dummy AI calibration-card JSON strings
# (simulate what Groq / GPT would return over the wire)
# ===========================================================================

# --- Valid card for Maya Chen (over-confident) ---
DUMMY_CARD_MAYA_JSON: str = json.dumps({
    "summary": (
        "Maya over-states win probability on large deals and at end of quarter. "
        "Her overall stated confidence consistently runs ~20pp above actuals."
    ),
    "rules": [
        {
            "trait": "large_deal",
            "direction": "over",
            "confidence": "high",
            "note": "Deals above ₹30L: stated prob averages 85%, actual close rate 62%."
        },
        {
            "trait": "end_of_quarter",
            "direction": "over",
            "confidence": "medium",
            "note": "EoQ pressure inflates her stated probability by an additional 8pp."
        },
        {
            "trait": "overall",
            "direction": "over",
            "confidence": "high",
            "note": "Historical win rate 52% vs average stated prob 74%."
        },
    ],
    "evidence_deals": [
        {"deal_id": "D001", "close_date": "2025-03-15", "outcome": "won"},
        {"deal_id": "D002", "close_date": "2025-03-28", "outcome": "lost"},
        {"deal_id": "D003", "close_date": "2025-06-20", "outcome": "won"},
    ],
})

# --- Valid card for Jordan Walsh (sandbagging) ---
DUMMY_CARD_JORDAN_JSON: str = json.dumps({
    "summary": (
        "Jordan systematically understates win probability across all deal types, "
        "most severely at the Negotiation stage on smaller tickets."
    ),
    "rules": [
        {
            "trait": "overall",
            "direction": "under",
            "confidence": "high",
            "note": "True win rate 78% vs average stated prob 38%."
        },
        {
            "trait": "single_contact_no_finance",
            "direction": "under",
            "confidence": "medium",
            "note": "Jordan sandbangs hardest when there is no finance contact."
        },
    ],
    "evidence_deals": [
        {"deal_id": "D004", "close_date": "2025-03-10", "outcome": "won"},
        {"deal_id": "D005", "close_date": "2025-03-25", "outcome": "won"},
    ],
})

# --- INVALID card — contains an unknown trait to prove Pydantic rejects it ---
DUMMY_CARD_INVALID_TRAIT_JSON: str = json.dumps({
    "summary": "This card has a made-up trait that should never pass validation.",
    "rules": [
        {
            "trait": "vip_relationship",   # <-- NOT in TraitEnum — must raise ValidationError
            "direction": "over",
            "confidence": "high",
        }
    ],
    "evidence_deals": [],
})


# ===========================================================================
# Comparison logic
# ===========================================================================

# Mapping from DirectionEnum → bias type vocabulary used in personas.py
_DIRECTION_TO_BIAS: dict[str, str] = {
    "over":     "over_confident",
    "under":    "sandbagging",
    "accurate": "well_calibrated",
}

PROBABILITY_TOLERANCE = 0.10
REVENUE_TOLERANCE     = 0.08


def evaluate_card(
    raw_json: str,
    persona: Persona,
) -> dict[str, Any]:
    """
    Parse a raw AI JSON string through the Pydantic CalibrationCard model,
    then compare the validated card against the rep's ground-truth persona.

    Args:
        raw_json: Raw JSON string from the AI (may be invalid).
        persona:  The rep's ground-truth bias profile from personas.py.

    Returns:
        A comparison report dict.  On Pydantic failure, returns an error report.
    """
    rep_id   = persona.get("rep_id", persona.get("name", "unknown"))
    rep_name = persona.get("name", rep_id)

    if "true_bias" in persona:
        true_bias_type = persona["true_bias"]["type"]
    else:
        biases = persona.get("biases", [])
        if not biases:
            true_bias_type = "well_calibrated"
        else:
            primary_dir = biases[0].get("direction", "over")
            true_bias_type = _DIRECTION_TO_BIAS.get(primary_dir, "unknown")

    # --- Step 1: Pydantic validation at the boundary ---
    try:
        card = CalibrationCard.model_validate_json(raw_json)
    except ValidationError as exc:
        return {
            "rep_id":          rep_id,
            "rep_name":        rep_name,
            "pydantic_valid":  False,
            "overall_correct": False,
            "validation_errors": exc.errors(include_url=False),
            "fields":          {},
        }

    # --- Step 2: Find the "overall" rule for top-level bias direction ---
    overall_rule = next(
        (r for r in card.rules if r.trait == TraitEnum.overall),
        None,
    )

    detected_bias_type = (
        _DIRECTION_TO_BIAS.get(overall_rule.direction.value, "unknown")
        if overall_rule else "unknown"
    )
    bias_type_match = detected_bias_type == true_bias_type

    # Confidence tier of the overall detection
    detection_confidence = overall_rule.confidence.value if overall_rule else "low"

    # Traits the AI flagged
    flagged_traits = [r.trait.value for r in card.rules]

    overall_correct = bias_type_match

    return {
        "rep_id":          rep_id,
        "rep_name":        rep_name,
        "pydantic_valid":  True,
        "overall_correct": overall_correct,
        "detected_bias_type":    detected_bias_type,
        "true_bias_type":        true_bias_type,
        "detection_confidence":  detection_confidence,
        "flagged_traits":        flagged_traits,
        "card_summary":          card.summary,
        "evidence_deal_count":   len(card.evidence_deals),
        "fields": {
            "bias_type": {
                "ai":    detected_bias_type,
                "true":  true_bias_type,
                "match": bias_type_match,
            },
        },
    }


# ===========================================================================
# False-alarm flagging
# ===========================================================================

def flag_false_alarms(
    comparison_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Identify reps where the AI made a critical bias-direction misclassification.

    A false alarm here means the AI's overall bias direction is wrong,
    so any correction applied would move the probability the wrong way.
    """
    flags: list[dict[str, Any]] = []

    for result in comparison_results:
        if not result.get("pydantic_valid", False):
            flags.append({
                "rep_id":           result["rep_id"],
                "rep_name":         result["rep_name"],
                "false_alarm_type": "pydantic_validation_failure",
                "ai_detected":      None,
                "true_bias":        None,
                "impact":           "Card rejected at validation boundary — no correction applied.",
                "severity":         "CRITICAL",
            })
            continue

        bias_field = result["fields"].get("bias_type", {})
        if not bias_field.get("match", True):
            flags.append({
                "rep_id":           result["rep_id"],
                "rep_name":         result["rep_name"],
                "false_alarm_type": "misclassified_bias_direction",
                "ai_detected":      bias_field["ai"],
                "true_bias":        bias_field["true"],
                "impact": (
                    "AI correction would move forecast probability in the WRONG direction. "
                    f"Rep is actually '{bias_field['true']}' "
                    f"but AI thinks '{bias_field['ai']}'."
                ),
                "severity": "HIGH",
            })

    return flags


# ===========================================================================
# Results export
# ===========================================================================

def export_eval_results(
    comparison_results: list[dict[str, Any]],
    false_alarms: list[dict[str, Any]],
    output_path: str | None = None,
) -> dict[str, Any]:
    """
    Assemble headline statistics and write them to eval.json.
    """
    total   = len(comparison_results)
    valid   = sum(1 for r in comparison_results if r.get("pydantic_valid"))
    correct = sum(1 for r in comparison_results if r.get("overall_correct"))

    headline = {
        "run_timestamp": datetime.utcnow().isoformat() + "Z",
        "model":         "dummy_ai_v1 (Pydantic-validated, no real model connected)",
        "summary": {
            "total_reps_evaluated":   total,
            "pydantic_valid_cards":   valid,
            "pydantic_invalid_cards": total - valid,
            "correct_bias_detections": correct,
            "accuracy_pct": round((correct / total) * 100, 1) if total else 0.0,
            "false_alarm_count": len(false_alarms),
        },
        "false_alarms":     false_alarms,
        "per_rep_results":  comparison_results,
    }

    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "eval.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(headline, f, indent=2)

    print(f"[bias_recovery] eval.json written -> {output_path}")
    return headline


# ===========================================================================
# Entry point
# ===========================================================================

def run_bias_check() -> dict[str, Any]:
    """
    Run the full hidden-bias check pipeline and return results.

    Also demonstrates Pydantic catching an invalid trait — this is NOT
    included in the main comparison results (no matching persona) but
    is printed to prove the boundary enforcement works.
    """
    # --- Prove Pydantic rejects an invalid trait ---
    print("\n[bias_recovery] Testing invalid trait rejection...")
    try:
        CalibrationCard.model_validate_json(DUMMY_CARD_INVALID_TRAIT_JSON)
        print("  [ERROR] Pydantic did NOT reject invalid trait — this is a bug!")
    except ValidationError as exc:
        first_err = exc.errors(include_url=False)[0]
        print(
            f"  [OK] ValidationError raised as expected: "
            f"field='{first_err['loc']}' msg='{first_err['msg']}'"
        )

    # --- Main pipeline: Maya + Jordan ---
    card_map = {
        "rep_maya":   DUMMY_CARD_MAYA_JSON,
        "rep_jordan": DUMMY_CARD_JORDAN_JSON,
    }

    comparison_results: list[dict[str, Any]] = []
    for persona in ALL_PERSONAS:
        raw = card_map.get(persona["rep_id"])
        if raw is None:
            print(f"[WARN] No AI card for rep {persona['rep_id']}, skipping.")
            continue
        result = evaluate_card(raw, persona)
        comparison_results.append(result)

    false_alarms = flag_false_alarms(comparison_results)
    return export_eval_results(comparison_results, false_alarms)


if __name__ == "__main__":
    results = run_bias_check()
    print("\n=== HEADLINE RESULTS ===")
    print(json.dumps(results["summary"], indent=2))

    if results["false_alarms"]:
        print("\n=== FALSE ALARMS ===")
        for fa in results["false_alarms"]:
            print(f"  [WARN] {fa['rep_name']}: {fa['impact']}")
    else:
        print("\n[OK] No false alarms detected.")


# ===========================================================================
# TEAM-SPEC v3 — Hidden-bias checker (verbatim from project leads)
# ===========================================================================
# These functions are the canonical implementation agreed across all roles.
# Do not modify the function signatures or core logic without team sign-off.
#
# Differences from v2 evaluate_card() approach:
#   - Operates on raw card dicts (not Pydantic objects) for cross-role compat
#   - Tracks first quarter a bias was found (temporal surfacing)
#   - Deduplicates false alarms per (rep_id, trait, direction)
#   - Applies the Sana exception for improvement detection
# ===========================================================================

import json as _json
from pathlib import Path as _Path

from backend.app.sim.personas import PERSONAS


def is_strong(rule: dict) -> bool:
    """
    Determine whether a calibration rule is strong enough to act on.

    VERBATIM team-spec implementation — do not alter.

    A rule is "strong" when all three conditions hold:
      1. Confidence is "medium" or "high" (not "low")
      2. Direction is not "accurate" (i.e. a real bias exists)
      3. Adjustment factor deviates from neutral (1.0) by >= 15%

    Args:
        rule: Raw rule dict with keys: confidence, direction, adjustment.

    Returns:
        bool: True if the rule clears all three thresholds.
    """
    return (
        rule["confidence"] in ("medium", "high")
        and rule["direction"] != "accurate"
        and abs(rule["adjustment"] - 1) >= 0.15
    )


def check(cards: dict) -> dict:
    """
    Evaluate AI-generated calibration cards against the PERSONAS ground truth.

    VERBATIM team-spec implementation with two additions:
      - False alarms deduplicated per (rep_id, trait, direction) across quarters.
      - Sana exception: if Sana's latest card no longer has a strong overall/over
        rule, inject "sana_improvement_noticed": True into the result.

    Args:
        cards: Nested dict of shape:
               { quarter: { rep_id: { "rules": [ rule_dict, ... ] } } }
               where each rule_dict has: trait, direction, confidence, adjustment.

    Returns:
        dict with keys:
            biases_found          — int: correctly detected planted biases
            biases_total          — int: total planted biases across all reps
            false_alarms          — int: deduplicated false alarm count
            per_rep               — list[dict]: per-rep detection detail
            sana_improvement_noticed — bool (only present when condition is met)
    """
    quarters = sorted(cards)

    # Track false alarms as a set to avoid double-counting the same
    # (rep_id, trait, direction) across multiple quarters.
    seen_false_alarms: set[tuple] = set()

    per_rep, found = [], 0

    for rep_id, persona in PERSONAS.items():
        planted = {(b["trait"], b["direction"]) for b in persona["biases"]}
        first_found = None

        for q in quarters:
            rules = cards[q].get(rep_id, {}).get("rules", [])
            for r in rules:
                if not is_strong(r):
                    continue
                key = (r["trait"], r["direction"])
                if key in planted:
                    first_found = first_found or q
                else:
                    # Deduplicate: only count a new (rep, trait, direction) once
                    fa_key = (rep_id, r["trait"], r["direction"])
                    seen_false_alarms.add(fa_key)

        if planted:
            found += first_found is not None

        per_rep.append({
            "rep_id":              rep_id,
            "hidden":              sorted(planted),
            "found":               first_found is not None,
            "first_found_quarter": first_found,
        })

    result = {
        "biases_found":  found,
        "biases_total":  sum(1 for p in PERSONAS.values() if p["biases"]),
        "false_alarms":  len(seen_false_alarms),
        "per_rep":       per_rep,
    }

    # --- Sana exception ---
    # If Sana's latest card no longer shows a strong overall/over rule, she
    # has demonstrably improved — surface this as a positive signal.
    if quarters:
        latest_q = quarters[-1]
        sana_rules = cards[latest_q].get(SANA_REP_ID, {}).get("rules", [])
        sana_still_biased = any(
            is_strong(r)
            and r.get("trait") == "overall"
            and r.get("direction") == "over"
            for r in sana_rules
        )
        if not sana_still_biased:
            result["sana_improvement_noticed"] = True

    return result


# ---------------------------------------------------------------------------
# File I/O wrapper
# ---------------------------------------------------------------------------

def write_eval_to_run(run_dir: _Path, cards: dict) -> _Path:
    """
    Run the team-spec bias check and write the result to ``eval.json``
    inside the given run directory.

    Args:
        run_dir: Path to the run directory (e.g. Path("data/runs/demo")).
        cards:   Nested cards dict as expected by check().

    Returns:
        Path to the written eval.json file.
    """
    result   = check(cards)
    out_path = run_dir / "eval.json"
    out_path.write_text(_json.dumps(result, indent=2), encoding="utf-8")
    print(f"[bias_recovery] eval.json written -> {out_path}")
    return out_path

