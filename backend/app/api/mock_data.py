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
    {"quarter": "2017-Q3", "reps_forecast_inr": 47000000,
     "agent_forecast_inr": 34800000, "actual_inr": 33900000},
    {"quarter": "2017-Q4", "reps_forecast_inr": 46000000,
     "agent_forecast_inr": 34500000, "actual_inr": 33600000},
]

SCORES = [
    {"quarter": "2017-Q1", "reps": 0.31, "agent_off": 0.29,
     "agent_on": 0.29, "baseline_win_rate": 0.27},
    {"quarter": "2017-Q2", "reps": 0.31, "agent_off": 0.30,
     "agent_on": 0.24, "baseline_win_rate": 0.26},
    {"quarter": "2017-Q3", "reps": 0.30, "agent_off": 0.29,
     "agent_on": 0.20, "baseline_win_rate": 0.25},
    {"quarter": "2017-Q4", "reps": 0.30, "agent_off": 0.28,
     "agent_on": 0.17, "baseline_win_rate": 0.24},
]

EVAL = {
    "headline": "Found 5 of 5 hidden biases; noticed Sana improve in Q3; 0 false alarms",
    "biases_found": 5,
    "biases_total": 5,
    "false_alarms": 0,
    "sana_improvement_noticed": True,
    "per_rep": [
        {"rep_id": "priya", "hidden_trait": "single_contact_no_finance",
         "hidden_direction": "over", "found": True,
         "first_found_quarter": "2017-Q2",
         "agent_rule": "1 contact AND no finance contact: adjust x0.5"},
    ],
    "brier_by_quarter": SCORES,
    "revenue_error_pct": [
        {"quarter": "2017-Q4", "reps": 38.0, "agent_on": 9.0},
    ],
}

CARD = {
    "rep_id": "priya",
    "quarter": "2017-Q3",
    "summary": "Priya is overconfident on deals with a single contact and no finance person.",
    "rules": [
        {"trait": "single_contact_no_finance",
         "direction": "over",
         "condition": "1 contact AND no finance contact",
         "stated_avg": 0.88,
         "actual_rate": 0.44,
         "adjustment": 0.5,
         "evidence_count": 9,
         "confidence": "high"},
    ],
}

BELIEFS = [
    {"quarter": "2017-Q1", "belief": "Not enough history yet.",
     "evidence_count": 0, "confidence": "low"},
    {"quarter": "2017-Q2", "belief": "Sana overestimates mid-size deals by ~25 points.",
     "evidence_count": 11, "confidence": "medium"},
    {"quarter": "2017-Q4",
     "belief": "Sana's recent forecasts are close to reality; earlier bias has faded.",
     "evidence_count": 23, "confidence": "medium"},
]

DEALS = [
    {"deal_id": "D-0142", "rep_id": "priya", "account": "Arvind Textiles",
     "quarter": "2017-Q2", "stated_prob": 0.9, "corrected_prob": 0.5,
     "outcome": "lost"},
    {"deal_id": "D-0187", "rep_id": "priya", "account": "Kestrel Foods",
     "quarter": "2017-Q3", "stated_prob": 0.6, "corrected_prob": 0.6,
     "outcome": "won"},
    {"deal_id": "D-0203", "rep_id": "priya", "account": "Zenith Corp",
     "quarter": "2017-Q4", "stated_prob": 0.85, "corrected_prob": 0.5,
     "outcome": "pending"},
]

CORRECTION = {
    "corrected_prob": 0.5,
    "confidence": "high",
    "explanation": "Priya's deals with one contact and no finance person closed 4 of 9 times.",
    "evidence": [
        {"deal_id": "D-0142", "account": "Arvind Textiles",
         "stated": 0.9, "outcome": "lost"},
    ],
    "questions_to_ask": ["Who controls the budget at Zenith Corp?"],
    "memory_used": True,
}

ASK_ANSWER = {
    "answer": ("About ₹3.4 Cr, not ₹4.6 Cr. The gap is mostly Priya's "
               "single-contact deals and Rahul's end-of-quarter calls."),
    "based_on": ["Priya: 9 single-contact deals, 4 closed",
                 "Rahul: end-of-quarter deals over-called"],
}