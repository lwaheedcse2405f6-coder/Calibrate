"""The six simulated reps and their hidden biases, written as data.

Role 5's hidden-bias checker reads PERSONAS directly, so keep this shape and
these trait names: single_contact_no_finance, large_deal, end_of_quarter, overall.
Quarter labels are calendar quarters like "2017-Q3" and compare correctly as strings.
"""

# Replay covers these quarters, in order (Maven data runs Oct 2016 - Dec 2017).
QUARTERS = ["2016-Q4", "2017-Q1", "2017-Q2", "2017-Q3", "2017-Q4"]

PERSONAS = {
    "priya": {"name": "Priya", "joins": "2017-Q1",
              "biases": [{"trait": "single_contact_no_finance", "direction": "over", "shift": 0.28}]},
    "arjun": {"name": "Arjun", "joins": "2017-Q1",
              "biases": [{"trait": "overall", "direction": "under", "shift": -0.23}]},
    "meera": {"name": "Meera", "joins": "2017-Q1",
              "biases": [{"trait": "large_deal", "direction": "over", "shift": 0.25}]},
    "rahul": {"name": "Rahul", "joins": "2017-Q1",
              "biases": [{"trait": "end_of_quarter", "direction": "over", "shift": 0.25}]},
    "sana": {"name": "Sana", "joins": "2017-Q1",
             "biases": [{"trait": "overall", "direction": "over", "shift": 0.25, "until": "2017-Q2"}]},
    "karan": {"name": "Karan", "joins": "2017-Q3", "biases": []},
}

REP_ORDER = list(PERSONAS)

# rep_id -> original Maven sales_agent name. Filled by prepare.prepare().
MAVEN_AGENT: dict[str, str] = {}


def active_reps(quarter: str) -> list[str]:
    """Reps who have joined by the start of `quarter` (Karan is absent before 2017-Q3)."""
    return [r for r in REP_ORDER if PERSONAS[r]["joins"] <= quarter]
