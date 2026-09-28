"""One-time bank setup: missions, hard rules (directives), one summary page per rep.

Run from the backend folder (safe to run again; it skips what already exists):
    python scripts/setup_bank.py            # dev bank: summary pages refresh only when asked
    python scripts/setup_bank.py --final    # demo bank: summary pages refresh automatically
"""

import sys
from pathlib import Path

AUTO_REFRESH = "--final" in sys.argv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from app.memory import hindsight_store as hs  # noqa: E402

REPS = [("priya", "Priya"), ("arjun", "Arjun"), ("meera", "Meera"),
        ("rahul", "Rahul"), ("sana", "Sana"), ("karan", "Karan")]

DIRECTIVES = {
    "Evidence only": ("Never adjust a forecast based on a rep's personal traits such as gender, "
                      "age or background. Use only deal evidence and the rep's forecasting "
                      "track record."),
    "Show evidence": "Always state how many past deals a belief or adjustment is based on.",
}

client = hs.get_client()
bank = hs.bank_id()
hs.ensure_bank()

client.update_bank_config(
    bank,
    retain_mission=("Track sales forecasts and outcomes. For every forecast note the rep, stated "
                    "probability, product, deal size, number of contacts, finance contact, and "
                    "the deal traits listed."),
    observations_mission=("Form beliefs about each rep's forecasting bias by deal trait: where "
                          "their stated confidence is higher or lower than actual results, and "
                          "whether that is changing over time."),
    reflect_mission=("You are a sales forecast calibration analyst. Compare what reps said with "
                     "what happened, and always give numbers and deal counts."),
)
print("missions set")

existing = {getattr(d, "name", None) for d in (client.list_directives(bank).items or [])}
for name, content in DIRECTIVES.items():
    if name in existing:
        print(f"directive exists: {name}")
        continue
    client.create_directive(bank_id=bank, name=name, content=content)
    print(f"directive added: {name}")

for rep_id, name in REPS:
    try:
        client.create_mental_model(
            bank_id=bank,
            id=f"profile-{rep_id}",
            name=f"{name} calibration profile",
            source_query=f"How reliable are {name}'s forecasts, by deal trait? Give deal counts.",
            tags=[f"rep:{rep_id}"],
            # Auto-refresh costs $0.05 each time; only turn it on for the final demo bank.
            trigger=({"refresh_after_consolidation": True, "tags_match": "all_strict"}
                     if AUTO_REFRESH else None),
        )
        print(f"summary page added: {name}")
    except Exception as exc:
        print(f"summary page for {name} skipped ({str(exc)[:100]})")
