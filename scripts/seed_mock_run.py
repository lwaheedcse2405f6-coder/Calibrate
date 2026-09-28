"""
scripts/seed_mock_run.py
==========================
Standalone Seed Script for Role 5 End-to-End Mock Run Environment.

# SYNTHETIC MOCK DATA — ISOLATED TEST FIXTURE
This file generates mock CRM deals, AI calibration cards, and audit snapshot dates
in data/runs/test_run/ for end-to-end evaluation pipeline verification.
This synthetic data is isolated and temporary, designed to be cleanly replaced
once production upstream outputs from Role 2 & Role 3 are available.

Usage:
    python scripts/seed_mock_run.py
"""

import csv
import json
from pathlib import Path


def seed_test_run(run_dir: Path | None = None) -> None:
    if run_dir is None:
        run_dir = Path(__file__).resolve().parent.parent / "data" / "runs" / "test_run"
    
    run_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------------------
    # 1. audit.json
    # ---------------------------------------------------------------------------
    audit_data = {
        "2017-Q1": "2016-12-28",
        "2017-Q2": "2017-03-29",
        "2017-Q3": "2017-06-30",
        "2017-Q4": "2017-09-28"
    }
    (run_dir / "audit.json").write_text(json.dumps(audit_data, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------------------
    # 2. cards.json
    # ---------------------------------------------------------------------------
    # Specs:
    # Priya: single_contact_no_finance, direction over, confidence high, adjustment 0.65, starting Q2
    # Arjun: overall, direction under, confidence high, adjustment 1.30
    # Meera: large_deal, direction over, confidence medium, adjustment 0.70
    # Rahul: end_of_quarter, direction over, confidence medium, adjustment 0.60
    # Sana: overall, direction over in Q1-Q2, switches to accurate (1.0) by Q4
    # Karan: no strong rules (accurate or empty)
    cards_data = {
        "2017-Q1": {
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "over", "confidence": "high", "adjustment": 0.60}
                ]
            },
            "priya": {"rules": []},
            "karan": {"rules": []},
        },
        "2017-Q2": {
            "priya": {
                "rules": [
                    {"trait": "single_contact_no_finance", "direction": "over", "confidence": "high", "adjustment": 0.65}
                ]
            },
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "over", "confidence": "high", "adjustment": 0.60}
                ]
            },
            "karan": {"rules": []},
        },
        "2017-Q3": {
            "priya": {
                "rules": [
                    {"trait": "single_contact_no_finance", "direction": "over", "confidence": "high", "adjustment": 0.65}
                ]
            },
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "high", "adjustment": 1.0}
                ]
            },
            "karan": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "low", "adjustment": 1.0}
                ]
            },
        },
        "2017-Q4": {
            "priya": {
                "rules": [
                    {"trait": "single_contact_no_finance", "direction": "over", "confidence": "high", "adjustment": 0.65}
                ]
            },
            "arjun": {
                "rules": [
                    {"trait": "overall", "direction": "under", "confidence": "high", "adjustment": 1.30}
                ]
            },
            "meera": {
                "rules": [
                    {"trait": "large_deal", "direction": "over", "confidence": "medium", "adjustment": 0.70}
                ]
            },
            "rahul": {
                "rules": [
                    {"trait": "end_of_quarter", "direction": "over", "confidence": "medium", "adjustment": 0.60}
                ]
            },
            "sana": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "high", "adjustment": 1.0}
                ]
            },
            "karan": {
                "rules": [
                    {"trait": "overall", "direction": "accurate", "confidence": "low", "adjustment": 1.0}
                ]
            },
        },
    }
    (run_dir / "cards.json").write_text(json.dumps(cards_data, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------------------
    # 3. deals.csv & deals.json
    # ---------------------------------------------------------------------------
    # ~24 rows across 4 quarters (2017-Q1 through 2017-Q4).
    # Priya stated_prob ~0.88, outcome lost, corrected_prob ~0.30
    # Arjun stated_prob ~0.40, outcome won, corrected_prob ~0.75
    # 1 pending deal in Q4
    deals = [
        # --- 2017-Q1 ---
        {"deal_id": "D001", "rep_id": "priya", "quarter": "2017-Q1", "forecast_date": "2017-01-15", "close_date": "2017-03-15", "amount_inr": 1200000, "stated_prob": 0.88, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D002", "rep_id": "arjun", "quarter": "2017-Q1", "forecast_date": "2017-01-20", "close_date": "2017-03-20", "amount_inr": 500000,  "stated_prob": 0.40, "corrected_prob": 0.75, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D003", "rep_id": "meera", "quarter": "2017-Q1", "forecast_date": "2017-01-25", "close_date": "2017-03-25", "amount_inr": 3500000, "stated_prob": 0.85, "corrected_prob": 0.35, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D004", "rep_id": "rahul", "quarter": "2017-Q1", "forecast_date": "2017-02-01", "close_date": "2017-03-28", "amount_inr": 800000,  "stated_prob": 0.82, "corrected_prob": 0.28, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D005", "rep_id": "sana",  "quarter": "2017-Q1", "forecast_date": "2017-02-10", "close_date": "2017-03-30", "amount_inr": 950000,  "stated_prob": 0.86, "corrected_prob": 0.32, "baseline_prob": 0.63, "outcome": "lost"},

        # --- 2017-Q2 ---
        {"deal_id": "D006", "rep_id": "priya", "quarter": "2017-Q2", "forecast_date": "2017-04-10", "close_date": "2017-06-15", "amount_inr": 1500000, "stated_prob": 0.89, "corrected_prob": 0.25, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D007", "rep_id": "arjun", "quarter": "2017-Q2", "forecast_date": "2017-04-15", "close_date": "2017-06-18", "amount_inr": 600000,  "stated_prob": 0.38, "corrected_prob": 0.80, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D008", "rep_id": "meera", "quarter": "2017-Q2", "forecast_date": "2017-04-20", "close_date": "2017-06-22", "amount_inr": 4000000, "stated_prob": 0.84, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D009", "rep_id": "rahul", "quarter": "2017-Q2", "forecast_date": "2017-05-01", "close_date": "2017-06-28", "amount_inr": 1100000, "stated_prob": 0.85, "corrected_prob": 0.35, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D010", "rep_id": "sana",  "quarter": "2017-Q2", "forecast_date": "2017-05-15", "close_date": "2017-06-30", "amount_inr": 700000,  "stated_prob": 0.80, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},

        # --- 2017-Q3 ---
        {"deal_id": "D011", "rep_id": "priya", "quarter": "2017-Q3", "forecast_date": "2017-07-05", "close_date": "2017-09-10", "amount_inr": 1300000, "stated_prob": 0.87, "corrected_prob": 0.28, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D012", "rep_id": "arjun", "quarter": "2017-Q3", "forecast_date": "2017-07-12", "close_date": "2017-09-15", "amount_inr": 450000,  "stated_prob": 0.42, "corrected_prob": 0.78, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D013", "rep_id": "meera", "quarter": "2017-Q3", "forecast_date": "2017-07-18", "close_date": "2017-09-20", "amount_inr": 3800000, "stated_prob": 0.80, "corrected_prob": 0.32, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D014", "rep_id": "rahul", "quarter": "2017-Q3", "forecast_date": "2017-08-01", "close_date": "2017-09-27", "amount_inr": 900000,  "stated_prob": 0.83, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D015", "rep_id": "sana",  "quarter": "2017-Q3", "forecast_date": "2017-08-10", "close_date": "2017-09-29", "amount_inr": 850000,  "stated_prob": 0.65, "corrected_prob": 0.65, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D016", "rep_id": "karan", "quarter": "2017-Q3", "forecast_date": "2017-08-15", "close_date": "2017-09-30", "amount_inr": 600000,  "stated_prob": 0.70, "corrected_prob": 0.70, "baseline_prob": 0.63, "outcome": "won"},

        # --- 2017-Q4 ---
        {"deal_id": "D017", "rep_id": "priya", "quarter": "2017-Q4", "forecast_date": "2017-10-05", "close_date": "2017-12-10", "amount_inr": 1400000, "stated_prob": 0.88, "corrected_prob": 0.25, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D018", "rep_id": "arjun", "quarter": "2017-Q4", "forecast_date": "2017-10-10", "close_date": "2017-12-15", "amount_inr": 550000,  "stated_prob": 0.39, "corrected_prob": 0.82, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D019", "rep_id": "meera", "quarter": "2017-Q4", "forecast_date": "2017-10-15", "close_date": "2017-12-18", "amount_inr": 4200000, "stated_prob": 0.82, "corrected_prob": 0.35, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D020", "rep_id": "rahul", "quarter": "2017-Q4", "forecast_date": "2017-11-01", "close_date": "2017-12-24", "amount_inr": 1000000, "stated_prob": 0.86, "corrected_prob": 0.30, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D021", "rep_id": "sana",  "quarter": "2017-Q4", "forecast_date": "2017-11-10", "close_date": "2017-12-28", "amount_inr": 900000,  "stated_prob": 0.60, "corrected_prob": 0.60, "baseline_prob": 0.63, "outcome": "won"},
        {"deal_id": "D022", "rep_id": "karan", "quarter": "2017-Q4", "forecast_date": "2017-11-15", "close_date": "2017-12-29", "amount_inr": 650000,  "stated_prob": 0.40, "corrected_prob": 0.40, "baseline_prob": 0.63, "outcome": "lost"},
        {"deal_id": "D023", "rep_id": "karan", "quarter": "2017-Q4", "forecast_date": "2017-11-20", "close_date": "2017-12-30", "amount_inr": 750000,  "stated_prob": 0.72, "corrected_prob": 0.72, "baseline_prob": 0.63, "outcome": "won"},

        # --- Pending deal in 2017-Q4 (Must be excluded from closed Brier score calculations) ---
        {"deal_id": "D024", "rep_id": "priya", "quarter": "2017-Q4", "forecast_date": "2017-12-01", "close_date": "",           "amount_inr": 2000000, "stated_prob": 0.88, "corrected_prob": 0.40, "baseline_prob": 0.63, "outcome": "pending"},
    ]

    # Write deals.csv
    fieldnames = ["deal_id", "rep_id", "quarter", "forecast_date", "close_date", "amount_inr", "stated_prob", "corrected_prob", "baseline_prob", "outcome"]
    with open(run_dir / "deals.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deals)

    # Write deals.json (required by write_scores_to_run)
    (run_dir / "deals.json").write_text(json.dumps(deals, indent=2), encoding="utf-8")

    print(f"[seed_mock_run] Populated mock run environment -> {run_dir}")


if __name__ == "__main__":
    seed_test_run()
