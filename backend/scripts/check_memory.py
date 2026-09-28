"""Check which Hindsight bank this environment uses, and what it remembers.

Run from the backend folder with the same settings as the server:
    python scripts/check_memory.py

Prints the bank, how many closed deals it remembers per rep, and one test answer.
If the counts are 0, the server is pointed at the wrong bank or API key.
"""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(BACKEND))
    from app.agent.calibrator import ask
    from app.memory import hindsight_store as hs

    print("HINDSIGHT_BASE_URL:", os.environ.get("HINDSIGHT_BASE_URL") or "(default)")
    print("HINDSIGHT_API_KEY set:", bool(os.environ.get("HINDSIGHT_API_KEY")))
    print("HINDSIGHT_BANK_ID:", os.environ.get("HINDSIGHT_BANK_ID") or "(NOT SET)")
    records = hs._all_outcome_records()
    print("closed deals remembered per rep:",
          {rep: len(r) for rep, r in sorted(records.items())} or "NONE")
    out = ask("What bias has Priya shown?")
    print("\nask('What bias has Priya shown?'):\n ", out["answer"])
    print("based_on:", *out["based_on"][:3], sep="\n  - ")
    hs.get_client().close()


if __name__ == "__main__":
    main()
