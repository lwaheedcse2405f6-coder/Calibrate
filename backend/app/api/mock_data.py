"""Mock data for the API contract (section 6 of the Team Build Plan).
The numbers are made-up examples, not results."""

REPS = [
    {"rep_id": "priya", "name": "Priya"},
    {"rep_id": "arjun", "name": "Arjun"},
    {"rep_id": "meera", "name": "Meera"},
    {"rep_id": "rahul", "name": "Rahul"},
    {"rep_id": "sana", "name": "Sana"},
    {"rep_id": "karan", "name": "Karan"},
]

QUARTERS = [
    {"quarter": "2017-Q1", "reps_forecast_inr": 42000000,
     "agent_forecast_inr": 38500000, "actual_inr": 29800000},
    {"quarter": "2017-Q2", "reps_forecast_inr": 45500000,
     "agent_forecast_inr": 34100000, "actual_inr": 31900000},
]

SCORES = [
    {"quarter": "2017-Q1", "reps": 0.31, "agent_off": 0.29,
     "agent_on": 0.29, "baseline_win_rate": 0.27},
    {"quarter": "2017-Q4", "reps": 0.30, "agent_off": 0.28,
     "agent_on": 0.17, "baseline_win_rate": 0.24},
]

EVAL = {
    "headline": "Found 5 of 5 hidden biases; noticed Sana improve in Q3; 0 false alarms",
    "biases_found": 5,
    "biases_total": 5,
    "false_alarms": 0,
    "per_rep": [
        {"rep_id": "priya", "hidden_trait": "single_contact_no_finance",
         "hidden_direction": "over", "found": True,
         "first_found_quarter": "2017-Q2",
         "agent_rule": "1 contact AND no finance contact: adjust x0.5"}
    ],
    "brier_by_quarter": SCORES,
}