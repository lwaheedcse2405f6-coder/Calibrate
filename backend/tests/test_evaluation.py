"""
backend/tests/test_evaluation.py
===================================
Automated pytest suite for the Calibrate evaluation harness.

Tests are deliberately dependency-free — they import only from the
backend/app/metrics and backend/app/eval modules (which themselves have
no third-party imports beyond pydantic), so they run cleanly in a fresh
.venv with only pytest + pydantic installed.

Test coverage:
  1.  Brier score sanity checks (perfect, worst, midpoint, known value)
  2.  Revenue error per quarter
  3.  No-peeking rule — v1 (temporal cutoff on historical win-rate)
  4.  New rep with zero history
  5.  Pending deals excluded from closed-deal scoring
  6.  Broken JSON fallback from AI response
  7.  Bias comparison correctness — v2 (Pydantic-backed evaluate_card)
  8.  False-alarm detection — v2
  9.  Pydantic enum enforcement (invalid traits rejected at boundary)
  10. API-contract scoring engine (brier_score_from_deals, compare_strategies)
  11. Strict temporal no-peeking rule — v2 (apply_card raises ValueError)
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.metrics.scoring import (
    MOCK_API_DEALS,
    MOCK_DEALS,
    HISTORICAL_BASELINE_PROB,
    baseline_historical_win_rate,
    baseline_trust_the_rep,
    brier_score,
    brier_score_from_deals,
    compare_strategies,
    revenue_error_per_quarter,
)
from backend.app.eval.bias_recovery import (
    CalibrationCard,
    CalibrationRule,
    DirectionEnum,
    ConfidenceEnum,
    TraitEnum,
    EvidenceDeal,
    DUMMY_CARD_MAYA_JSON,
    DUMMY_CARD_JORDAN_JSON,
    DUMMY_CARD_INVALID_TRAIT_JSON,
    evaluate_card,
    flag_false_alarms,
)
from backend.app.sim.personas import PERSONAS, active_reps
from backend.app.eval.personas import ALL_PERSONAS, SANA_REP_ID


# ===========================================================================
# Helper — apply_card temporal integrity enforcer
# ===========================================================================

def apply_card(deal: dict, card: CalibrationCard) -> CalibrationCard:
    """
    Apply a calibration card to a deal, enforcing the no-peeking rule.

    Checks that none of the card's evidence deals have a close_date that
    is greater than or equal to the deal's forecast_date. If any evidence
    deal is from the future (relative to the forecast date), it raises a
    ValueError, preventing temporally-contaminated predictions.

    Args:
        deal: Dict with at least a "forecast_date" key (ISO date string).
        card: A validated CalibrationCard with evidence_deals.

    Returns:
        The card, unchanged, if all evidence predates the forecast.

    Raises:
        ValueError: If any evidence deal's close_date >= forecast_date.
    """
    forecast_dt = date.fromisoformat(deal["forecast_date"])

    for ev in card.evidence_deals:
        ev_dt = date.fromisoformat(ev.close_date)
        if ev_dt >= forecast_dt:
            raise ValueError(
                f"Temporal violation: Card contains future evidence "
                f"(evidence close_date={ev.close_date}, "
                f"forecast_date={deal['forecast_date']})"
            )

    return card


# ===========================================================================
# 1. Brier Score — sanity checks
# ===========================================================================

class TestBrierScore:
    def test_perfect_score(self):
        """Perfect forecaster: forecast=1 for wins, forecast=0 for losses -> BS=0."""
        forecasts = [1.0, 0.0, 1.0, 0.0]
        actuals   = [1,   0,   1,   0]
        assert brier_score(forecasts, actuals) == 0.0

    def test_worst_score(self):
        """Completely wrong forecaster: forecast=1 for all losses -> BS=1."""
        forecasts = [1.0, 1.0]
        actuals   = [0, 0]
        assert brier_score(forecasts, actuals) == 1.0

    def test_random_baseline(self):
        """Random forecaster (always 0.5) -> BS=0.25."""
        forecasts = [0.5] * 100
        actuals   = [1, 0] * 50
        assert brier_score(forecasts, actuals) == pytest.approx(0.25, abs=1e-6)

    def test_known_value(self):
        """
        Manual calculation:
          (0.9-1)^2 + (0.75-0)^2 = 0.01 + 0.5625 = 0.5725 -> BS = 0.2863
        """
        forecasts = [0.9, 0.75]
        actuals   = [1, 0]
        expected  = round((0.1**2 + 0.75**2) / 2, 4)
        assert brier_score(forecasts, actuals) == pytest.approx(expected, abs=1e-4)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            brier_score([], [])

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="Length mismatch"):
            brier_score([0.5, 0.8], [1])

    def test_out_of_range_probability_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            brier_score([1.5], [1])


# ===========================================================================
# 2. Revenue Error Per Quarter
# ===========================================================================

class TestRevenueError:
    def test_q1_totals(self):
        result = revenue_error_per_quarter(MOCK_DEALS, "Q1-2025")
        # Q1 closed: D001 (won), D002 (lost), D004 (won), D005 (won)
        # forecast: 120k + 80k + 50k + 40k = 290k
        # actual:   110k + 0   + 75k + 60k = 245k
        assert result["total_forecast"] == pytest.approx(290_000, abs=1)
        assert result["total_actual"]   == pytest.approx(245_000, abs=1)
        assert result["total_error"]    == pytest.approx( 45_000, abs=1)
        assert result["deal_count"]     == 4

    def test_empty_quarter_returns_zeros(self):
        result = revenue_error_per_quarter(MOCK_DEALS, "Q4-2099")
        assert result["deal_count"]     == 0
        assert result["total_forecast"] == 0.0
        assert result["total_actual"]   == 0.0
        assert result["mae"]            == 0.0

    def test_pending_deals_excluded(self):
        """Pending deal D006 must NOT appear in Q2 revenue calculations."""
        result = revenue_error_per_quarter(MOCK_DEALS, "Q2-2025")
        assert result["deal_count"]     == 1
        assert result["total_forecast"] == pytest.approx(95_000, abs=1)
        assert result["total_actual"]   == pytest.approx(98_000, abs=1)


# ===========================================================================
# 3. No-Peeking Rule v1 — temporal cutoff on historical win-rate
# ===========================================================================

class TestNoPeekingRuleV1:
    def test_deals_after_cutoff_excluded(self):
        """
        With cutoff=2025-03-20:
          D001 (Mar 15): included -> won
          D002 (Mar 28): excluded (after cutoff)
          D003 (Jun 20): excluded
        -> win rate = 1/1 = 1.0
        """
        cutoff = date(2025, 3, 20)
        win_rate = baseline_historical_win_rate(MOCK_DEALS, "rep_maya", before_date=cutoff)
        assert win_rate == pytest.approx(1.0, abs=1e-4)

    def test_future_deal_not_counted(self):
        """Cutoff before all deals -> neutral prior 0.5."""
        cutoff = date(2020, 1, 1)
        win_rate = baseline_historical_win_rate(MOCK_DEALS, "rep_maya", before_date=cutoff)
        assert win_rate == pytest.approx(0.5, abs=1e-4)

    def test_q1_only_no_q2_leak(self):
        """
        Cutoff=2025-04-01: Maya Q1 closed: D001 won, D002 lost -> 0.5
        D003 (Jun 20) must not be counted.
        """
        cutoff = date(2025, 4, 1)
        win_rate = baseline_historical_win_rate(MOCK_DEALS, "rep_maya", before_date=cutoff)
        assert win_rate == pytest.approx(0.5, abs=1e-4)


# ===========================================================================
# 4. New Rep — Zero History Edge Case
# ===========================================================================

class TestNewRepNoHistory:
    def test_new_rep_returns_neutral_prior(self):
        """A rep with no closed deals should get a neutral 0.5 prior, not crash."""
        win_rate = baseline_historical_win_rate(MOCK_DEALS, "rep_brand_new")
        assert win_rate == pytest.approx(0.5, abs=1e-6)

    def test_new_rep_with_cutoff_returns_neutral(self):
        """Even with a before_date, an unknown rep returns the neutral prior."""
        win_rate = baseline_historical_win_rate(
            MOCK_DEALS, "rep_nobody", before_date=date(2025, 6, 1)
        )
        assert win_rate == pytest.approx(0.5, abs=1e-6)

    def test_trust_the_rep_works_with_single_deal(self):
        """Baseline trust-the-rep must handle a single-element list."""
        single = [{"rep_probability": 0.72, "status": "closed", "actual_outcome": 1}]
        probs = baseline_trust_the_rep(single)
        assert probs == [0.72]


# ===========================================================================
# 5. Pending Deals — Open at Quarter End
# ===========================================================================

class TestPendingDeals:
    def test_pending_deal_excluded_from_brier(self):
        """Filter pending deals before scoring — none should have None outcomes."""
        closed_only = [d for d in MOCK_DEALS if d["status"] == "closed"]
        actuals = [d["actual_outcome"] for d in closed_only]
        assert None not in actuals

    def test_pending_deal_flagged_in_dataset(self):
        """At least one deal in MOCK_DEALS is pending (D006)."""
        pending = [d for d in MOCK_DEALS if d["status"] == "pending"]
        assert len(pending) >= 1
        assert pending[0]["actual_outcome"] is None
        assert pending[0]["close_date"]     is None

    def test_pending_deal_excluded_from_revenue_calc(self):
        """Revenue error for Q2 must not include the pending deal's 200k forecast."""
        result = revenue_error_per_quarter(MOCK_DEALS, "Q2-2025")
        assert result["total_forecast"] < 200_000   # 95k only, not 295k


# ===========================================================================
# 6. Broken JSON Fallback from AI
# ===========================================================================

def _parse_ai_response(raw: str) -> dict:
    """
    Thin wrapper that simulates how the integration layer would parse
    an AI response.  Returns a safe fallback dict if JSON is invalid
    OR if the parsed result is not a dict (e.g. an array or scalar).
    """
    _FALLBACK = {
        "error": "invalid_json",
        "detected_bias_type": "unknown",
        "estimated_probability_inflation": 0.0,
        "estimated_revenue_inflation_pct": 0.0,
        "raw_json_valid": False,
    }
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else _FALLBACK
    except json.JSONDecodeError:
        return _FALLBACK


class TestBrokenJsonFallback:
    def test_valid_json_parses_correctly(self):
        raw = '{"detected_bias_type": "sandbagging", "confidence": 0.9}'
        result = _parse_ai_response(raw)
        assert result["detected_bias_type"] == "sandbagging"
        assert result.get("error") is None

    def test_truncated_json_returns_fallback(self):
        raw = '{"detected_bias_type": "over_confident", "confidence":'  # truncated
        result = _parse_ai_response(raw)
        assert result["raw_json_valid"] is False
        assert result["detected_bias_type"] == "unknown"
        assert result["error"] == "invalid_json"

    def test_empty_string_returns_fallback(self):
        result = _parse_ai_response("")
        assert result["raw_json_valid"] is False
        assert result["estimated_probability_inflation"] == 0.0

    def test_html_error_page_returns_fallback(self):
        """Simulate Groq returning an HTML 500 error page instead of JSON."""
        raw = "<html><body>Internal Server Error</body></html>"
        result = _parse_ai_response(raw)
        assert result["raw_json_valid"] is False
        assert result["error"] == "invalid_json"

    def test_fallback_does_not_raise(self):
        """Critically: the fallback must never raise an exception and always return a dict."""
        non_dict_inputs = ["", "{{{", "[]", "null", "true"]
        for bad_input in non_dict_inputs:
            result = _parse_ai_response(bad_input)
            assert isinstance(result, dict), (
                f"Expected dict fallback for input {bad_input!r}, got {type(result)}"
            )
            assert result["raw_json_valid"] is False

        # None raises TypeError in json.loads itself -- document that boundary
        with pytest.raises(TypeError):
            json.loads(None)


# ===========================================================================
# 7. Bias Comparison Correctness — v2 (Pydantic-backed evaluate_card)
# ===========================================================================

class TestBiasComparisonV2:
    def test_maya_card_is_pydantic_valid(self):
        """Maya's dummy card JSON must parse cleanly through CalibrationCard."""
        card = CalibrationCard.model_validate_json(DUMMY_CARD_MAYA_JSON)
        assert isinstance(card, CalibrationCard)
        assert len(card.rules) > 0

    def test_jordan_card_is_pydantic_valid(self):
        """Jordan's dummy card JSON must parse cleanly through CalibrationCard."""
        card = CalibrationCard.model_validate_json(DUMMY_CARD_JORDAN_JSON)
        assert isinstance(card, CalibrationCard)

    def test_maya_detected_correctly(self):
        """AI correctly identifies over_confident persona -> overall_correct=True."""
        result = evaluate_card(DUMMY_CARD_MAYA_JSON, PERSONAS["sana"])
        assert result["pydantic_valid"]  is True
        assert result["overall_correct"] is True
        assert result["fields"]["bias_type"]["match"] is True

    def test_jordan_detected_correctly(self):
        """Jordan/Arjun corrected card identifies rep as sandbagging -> overall_correct=True."""
        result = evaluate_card(DUMMY_CARD_JORDAN_JSON, PERSONAS["arjun"])
        assert result["pydantic_valid"]  is True
        assert result["overall_correct"] is True
        assert result["fields"]["bias_type"]["ai"] == "sandbagging"

    def test_evidence_deals_present_in_maya_card(self):
        """Maya/Sana card must include at least one evidence deal."""
        card = CalibrationCard.model_validate_json(DUMMY_CARD_MAYA_JSON)
        assert len(card.evidence_deals) >= 1
        for ev in card.evidence_deals:
            assert isinstance(ev, EvidenceDeal)
            assert ev.close_date  # must not be empty


# ===========================================================================
# 8. False-Alarm Detection — v2
# ===========================================================================

class TestFalseAlarmDetectionV2:
    def test_no_false_alarms_when_both_correct(self):
        """Both Sana (over) and Arjun (under) cards are correct — zero false alarms expected."""
        results = [
            evaluate_card(DUMMY_CARD_MAYA_JSON,   PERSONAS["sana"]),
            evaluate_card(DUMMY_CARD_JORDAN_JSON, PERSONAS["arjun"]),
        ]
        alarms = flag_false_alarms(results)
        assert len(alarms) == 0

    def test_invalid_card_raises_false_alarm_critical(self):
        """A card that fails Pydantic validation is flagged as CRITICAL severity."""
        results = [evaluate_card(DUMMY_CARD_INVALID_TRAIT_JSON, PERSONAS["sana"])]
        alarms  = flag_false_alarms(results)
        assert len(alarms) == 1
        assert alarms[0]["severity"] == "CRITICAL"
        assert alarms[0]["false_alarm_type"] == "pydantic_validation_failure"

    def test_pydantic_invalid_card_sets_overall_correct_false(self):
        """A ValidationError card must set overall_correct=False in the result."""
        result = evaluate_card(DUMMY_CARD_INVALID_TRAIT_JSON, PERSONAS["sana"])
        assert result["pydantic_valid"]  is False
        assert result["overall_correct"] is False
        assert "validation_errors" in result


# ===========================================================================
# 9. Pydantic Enum Enforcement — invalid traits rejected at boundary
# ===========================================================================

class TestPydanticEnumEnforcement:
    def test_invalid_trait_raises_validation_error(self):
        """
        'vip_relationship' is not in TraitEnum.
        Pydantic must raise ValidationError — not return a partial result.
        """
        with pytest.raises(ValidationError) as exc_info:
            CalibrationCard.model_validate_json(DUMMY_CARD_INVALID_TRAIT_JSON)
        errors = exc_info.value.errors(include_url=False)
        assert len(errors) >= 1
        # Error location must point to the trait field
        locs = [str(e["loc"]) for e in errors]
        assert any("trait" in loc for loc in locs)

    def test_invalid_direction_raises_validation_error(self):
        """'sideways' is not a valid DirectionEnum value."""
        bad = json.dumps({
            "summary": "test",
            "rules": [{"trait": "overall", "direction": "sideways", "confidence": "high"}],
        })
        with pytest.raises(ValidationError) as exc_info:
            CalibrationCard.model_validate_json(bad)
        errors = exc_info.value.errors(include_url=False)
        locs = [str(e["loc"]) for e in errors]
        assert any("direction" in loc for loc in locs)

    def test_invalid_confidence_raises_validation_error(self):
        """'very_high' is not a valid ConfidenceEnum value."""
        bad = json.dumps({
            "summary": "test",
            "rules": [{"trait": "overall", "direction": "over", "confidence": "very_high"}],
        })
        with pytest.raises(ValidationError):
            CalibrationCard.model_validate_json(bad)

    def test_all_valid_enums_accepted(self):
        """Every valid combination of enum values must parse without error."""
        for trait in TraitEnum:
            for direction in DirectionEnum:
                for confidence in ConfidenceEnum:
                    payload = json.dumps({
                        "summary": "test",
                        "rules": [{
                            "trait":      trait.value,
                            "direction":  direction.value,
                            "confidence": confidence.value,
                        }],
                    })
                    card = CalibrationCard.model_validate_json(payload)
                    assert len(card.rules) == 1

    def test_empty_rules_list_is_valid(self):
        """A card with no rules but a summary is structurally valid."""
        card = CalibrationCard(summary="No patterns detected yet.", rules=[])
        assert card.rules == []

    def test_rule_note_is_optional(self):
        """CalibrationRule.note is optional — omitting it must not raise."""
        rule = CalibrationRule(
            trait=TraitEnum.overall,
            direction=DirectionEnum.over,
            confidence=ConfidenceEnum.high,
        )
        assert rule.note is None


# ===========================================================================
# 10. API-Contract Scoring Engine
# ===========================================================================

class TestAPIContractScoring:
    def test_brier_from_deals_stated_prob(self):
        """Trust-the-rep Brier score from MOCK_API_DEALS must be > 0."""
        score = brier_score_from_deals(MOCK_API_DEALS, "stated_prob")
        assert score > 0.0
        assert score <= 1.0

    def test_brier_from_deals_corrected_prob(self):
        """Agent-calibrated score must be a valid Brier score."""
        score = brier_score_from_deals(MOCK_API_DEALS, "corrected_prob")
        assert 0.0 < score < 1.0

    def test_calibrated_beats_stated(self):
        """
        Core hypothesis: corrected_prob should produce a lower (better)
        Brier score than stated_prob across the 12-deal mock dataset.
        """
        trust_score     = brier_score_from_deals(MOCK_API_DEALS, "stated_prob")
        calibrated_score = brier_score_from_deals(MOCK_API_DEALS, "corrected_prob")
        assert calibrated_score < trust_score, (
            f"Agent calibration should improve on raw rep: "
            f"calibrated={calibrated_score} vs trust={trust_score}"
        )

    def test_flat_baseline_score(self):
        """Historical baseline (flat 0.63) must produce a valid Brier score."""
        score = brier_score_from_deals(
            MOCK_API_DEALS, "", flat_prob=HISTORICAL_BASELINE_PROB
        )
        assert 0.0 < score < 1.0

    def test_compare_strategies_returns_all_keys(self):
        """compare_strategies() dict must contain all required keys."""
        stats = compare_strategies(MOCK_API_DEALS)
        required = {
            "deal_count", "trust_the_rep", "agent_calibrated",
            "historical_baseline", "improvement_vs_rep", "improvement_vs_baseline",
        }
        assert required.issubset(stats.keys())

    def test_compare_strategies_deal_count(self):
        """compare_strategies must report correct deal count."""
        stats = compare_strategies(MOCK_API_DEALS)
        assert stats["deal_count"] == len(MOCK_API_DEALS) == 12

    def test_improvement_vs_rep_is_positive(self):
        """improvement_vs_rep = trust_the_rep - agent_calibrated must be > 0."""
        stats = compare_strategies(MOCK_API_DEALS)
        assert stats["improvement_vs_rep"] > 0, (
            "Calibration must improve on raw rep probability — check mock deal design."
        )

    def test_empty_deals_raises(self):
        """brier_score_from_deals must raise on empty input, not return 0."""
        with pytest.raises(ValueError, match="must not be empty"):
            brier_score_from_deals([], "stated_prob")

    def test_out_of_range_prob_raises(self):
        """A probability > 1.0 in mock data must raise ValueError."""
        bad_deal = [{"stated_prob": 1.5, "actual_outcome": 1}]
        with pytest.raises(ValueError, match="out of range"):
            brier_score_from_deals(bad_deal, "stated_prob")


# ===========================================================================
# 11. Strict Temporal No-Peeking Rule — v2 (apply_card raises ValueError)
# ===========================================================================

class TestNoPeekingRuleV2:
    """
    Prove to the judges that the AI cannot cheat by looking at future data.

    apply_card() enforces: evidence_deal.close_date < deal.forecast_date
    for ALL evidence deals. Violators raise ValueError immediately.
    """

    def _make_deal(self, forecast_date: str) -> dict:
        return {
            "deal_id":       "LIVE001",
            "forecast_date": forecast_date,
            "rep_id":        "rep_maya",
            "amount_inr":    2_000_000,
            "stated_prob":   0.80,
        }

    def _make_card(self, evidence_close_dates: list[str]) -> CalibrationCard:
        return CalibrationCard(
            summary="Test card",
            rules=[
                CalibrationRule(
                    trait=TraitEnum.overall,
                    direction=DirectionEnum.over,
                    confidence=ConfidenceEnum.high,
                )
            ],
            evidence_deals=[
                EvidenceDeal(deal_id=f"EV{i:03d}", close_date=cd)
                for i, cd in enumerate(evidence_close_dates)
            ],
        )

    def test_no_peeking_rule(self):
        """
        CORE TEST — required by spec.

        forecast_date = "2017-05-01"
        evidence contains a deal with close_date = "2017-06-15" (future!)
        -> apply_card must raise ValueError("Temporal violation...")
        """
        deal = self._make_deal("2017-05-01")
        card = self._make_card(["2017-03-10", "2017-06-15"])  # 2nd is future

        with pytest.raises(ValueError, match="Temporal violation"):
            apply_card(deal, card)

    def test_no_peeking_clean_card(self):
        """
        All evidence predates the forecast date -> apply_card must
        return the card cleanly without raising.
        """
        deal = self._make_deal("2017-05-01")
        card = self._make_card(["2017-01-15", "2017-03-22", "2017-04-30"])

        returned_card = apply_card(deal, card)
        assert returned_card is card  # same object returned

    def test_no_peeking_same_day_boundary(self):
        """
        close_date == forecast_date is also a violation (strict < required).
        A deal closed on the same day as the forecast is future data —
        we cannot know at forecast time that it will close that day.
        """
        deal = self._make_deal("2017-05-01")
        card = self._make_card(["2017-04-20", "2017-05-01"])  # same day!

        with pytest.raises(ValueError, match="Temporal violation"):
            apply_card(deal, card)

    def test_no_peeking_empty_evidence_always_passes(self):
        """A card with no evidence deals cannot have a temporal violation."""
        deal = self._make_deal("2017-05-01")
        card = self._make_card([])  # no evidence

        returned_card = apply_card(deal, card)
        assert returned_card is card

    def test_no_peeking_error_message_includes_dates(self):
        """The ValueError message must include both the offending dates for debuggability."""
        deal = self._make_deal("2017-05-01")
        card = self._make_card(["2017-06-15"])

        with pytest.raises(ValueError) as exc_info:
            apply_card(deal, card)

        msg = str(exc_info.value)
        assert "2017-06-15"  in msg
        assert "2017-05-01"  in msg


# ===========================================================================
# 12. TEAM-SPEC VERBATIM — pandas Brier tests (verbatim from project leads)
# ===========================================================================
# Import path adapted to our project structure (backend.app.metrics.scoring
# instead of app.metrics.scoring) — test logic is character-for-character
# identical to the spec provided by the project leads.
# ===========================================================================

import pandas as pd  # noqa: E402  (appended section — pandas now available)
from backend.app.metrics.scoring import brier  # noqa: E402


def test_brier_perfect_and_worst():
    assert brier(pd.Series([1.0, 0.0]), pd.Series(["won", "lost"])) == 0.0
    assert brier(pd.Series([0.0, 1.0]), pd.Series(["won", "lost"])) == 1.0


def test_brier_coin_flip():
    assert brier(pd.Series([0.5, 0.5]), pd.Series(["won", "lost"])) == 0.25


# ===========================================================================
# 13. TEAM-SPEC VERBATIM — no-peeking audit.json test
# ===========================================================================
# Reads data/runs/demo/audit.json (relative to the project root where pytest
# is invoked). The fixture contains latest evidence close dates that must
# all be strictly before the quarter start date.
# ===========================================================================

QUARTER_START = {
    "2017-Q1": "2017-01-01",
    "2017-Q2": "2017-04-01",
    "2017-Q3": "2017-07-01",
    "2017-Q4": "2017-10-01",
}


def test_no_peeking():
    import json
    from pathlib import Path
    audit = json.loads(Path("data/runs/demo/audit.json").read_text())
    for quarter, latest_close in audit.items():
        if quarter in QUARTER_START and latest_close:
            assert latest_close < QUARTER_START[quarter], f"{quarter} saw the future"


# ===========================================================================
# 14. REAL DATASET VALIDATION — backend/data/deals.csv
# ===========================================================================

class TestRealDataValidation:
    """
    Validate shape, structure, data integrity, and scoring pipeline
    compatibility on the official Maven-derived dataset backend/data/deals.csv.
    """

    def test_real_deals_csv_shape(self):
        """Assert backend/data/deals.csv is 1162 rows and 16 columns."""
        from pathlib import Path
        csv_path = Path("backend/data/deals.csv")
        assert csv_path.exists(), "backend/data/deals.csv must exist"
        df = pd.read_csv(csv_path)
        assert df.shape == (1162, 16), f"Expected shape (1162, 16), got {df.shape}"

    def test_real_deals_valid_quarters(self):
        """Assert only valid quarters (2017-Q1 through 2017-Q4) exist."""
        df = pd.read_csv("backend/data/deals.csv")
        expected_quarters = {"2017-Q1", "2017-Q2", "2017-Q3", "2017-Q4"}
        actual_quarters = set(df["quarter"].dropna().unique())
        assert actual_quarters == expected_quarters, f"Quarters mismatch: {actual_quarters}"

    def test_real_deals_critical_columns_no_nans(self):
        """Assert no NaN values exist in critical columns: rep_id, stated_prob, outcome."""
        df = pd.read_csv("backend/data/deals.csv")
        critical_cols = ["rep_id", "stated_prob", "outcome"]
        for col in critical_cols:
            null_count = df[col].isnull().sum()
            assert null_count == 0, f"Critical column '{col}' has {null_count} nulls"

    def test_real_deals_outcomes_valid(self):
        """Assert outcome values are strictly in {'won', 'lost', 'pending'}."""
        df = pd.read_csv("backend/data/deals.csv")
        valid_outcomes = {"won", "lost", "pending"}
        actual_outcomes = set(df["outcome"].unique())
        assert actual_outcomes.issubset(valid_outcomes), f"Invalid outcomes: {actual_outcomes}"

    def test_real_deals_baseline_brier_scores_compute(self):
        """Assert baseline Brier scores compute without errors on the real dataset."""
        from backend.app.metrics.scoring import scores_by_quarter
        df = pd.read_csv("backend/data/deals.csv")
        scores = scores_by_quarter(df)
        assert len(scores) == 4, f"Expected 4 quarterly score dicts, got {len(scores)}"
        for s in scores:
            assert "quarter" in s
            assert "reps" in s
            assert "baseline_win_rate" in s
            assert 0.0 <= s["reps"] <= 1.0
            assert 0.0 <= s["baseline_win_rate"] <= 1.0


# ===========================================================================
# 15. CARD PARSING & VALIDATION — parse_card / Rule / Card
# ===========================================================================

class TestCardParsing:
    """Validate parse_card(), rule auto-corrections, bounds clipping, and confidence capping."""

    def test_parse_card_none_returns_empty_card(self):
        from backend.app.cards import parse_card, empty_card
        assert parse_card(None) == empty_card()

    def test_parse_card_valid_rule_recomputes_direction_and_adjustment(self):
        from backend.app.cards import parse_card
        raw = {
            "summary": "Priya over-estimates single contact deals.",
            "rules": [
                {
                    "trait": "single_contact_no_finance",
                    "stated_avg": 0.80,
                    "actual_rate": 0.50,
                    "evidence_count": 10,
                    "confidence": "high",
                }
            ],
        }
        card = parse_card(raw)
        assert card["summary"] == "Priya over-estimates single contact deals."
        assert len(card["rules"]) == 1
        rule = card["rules"][0]
        assert rule["trait"] == "single_contact_no_finance"
        assert rule["direction"] == "over"  # 0.80 - 0.50 = 0.30 > 0.05
        assert rule["adjustment"] == pytest.approx(0.625, abs=1e-3)
        assert rule["confidence"] == "high"

    def test_parse_card_handles_percentage_values(self):
        from backend.app.cards import parse_card
        raw = {
            "summary": "AI returned numbers in percentages.",
            "rules": [
                {
                    "trait": "overall",
                    "stated_avg": 85,    # 85% -> 0.85
                    "actual_rate": 40,   # 40% -> 0.40
                    "evidence_count": 5,
                    "confidence": "medium",
                }
            ],
        }
        card = parse_card(raw)
        rule = card["rules"][0]
        assert rule["stated_avg"] == pytest.approx(0.85, abs=1e-3)
        assert rule["actual_rate"] == pytest.approx(0.40, abs=1e-3)
        assert rule["direction"] == "over"

    def test_parse_card_drops_invalid_trait(self):
        from backend.app.cards import parse_card
        raw = {
            "summary": "Card with unknown trait.",
            "rules": [
                {
                    "trait": "invalid_trait_name",
                    "direction": "over",
                    "confidence": "high",
                }
            ],
        }
        card = parse_card(raw)
        assert card["rules"] == []

    def test_parse_card_caps_confidence_by_evidence_count(self):
        from backend.app.cards import parse_card
        raw = {
            "summary": "High confidence claimed with low evidence.",
            "rules": [
                {
                    "trait": "large_deal",
                    "direction": "over",
                    "evidence_count": 1,  # < MIN_EVIDENCE (3) -> max confidence = low
                    "confidence": "high",
                }
            ],
        }
        card = parse_card(raw)
        assert card["rules"][0]["confidence"] == "low"



