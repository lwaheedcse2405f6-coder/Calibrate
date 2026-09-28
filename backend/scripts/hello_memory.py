"""v0 "does Hindsight work?" test, and the delay measurement Role 3 needs.

Run from the backend folder:
    python scripts/hello_memory.py

It prints two numbers. Post both in the team chat:
    1. seconds until a saved fact can be looked up
    2. seconds until a belief (observation) appears
Role 3 uses the second one as the pause between quarters.
"""

import sys
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
TIMEOUT_S = 240


def main() -> None:
    sys.path.insert(0, str(BACKEND))  # so "import app" works
    from dotenv import load_dotenv

    load_dotenv(BACKEND.parent / ".env")
    from app.memory import hindsight_store as hs

    run = uuid.uuid4().hex[:6]
    tags = ["rep:hello", f"run:{run}"]
    client = hs.get_client()
    bank = hs.bank_id()

    print(f"bank: {bank}   run: {run}")
    hs.ensure_bank()

    # Five closed deals with the same pattern, so Hindsight has something to form a belief from.
    facts = [
        f"Test rep Hello{run} forecast deal {i} at 90% with one contact and no finance contact. "
        f"The deal was lost."
        for i in range(1, 5)
    ] + [f"Test rep Hello{run} forecast deal 5 at 90% with three contacts. The deal was won."]

    t0 = time.time()
    client.retain_batch(bank_id=bank, items=[
        {"content": f, "context": "hello memory test", "tags": tags,
         "timestamp": f"2017-01-0{i + 1}T10:00:00Z", "document_id": f"hello-{run}-{i}"}
        for i, f in enumerate(facts)
    ])
    print(f"saved {len(facts)} facts in {time.time() - t0:.1f}s")

    start = time.time()
    found_at = belief_at = None
    while time.time() - start < TIMEOUT_S and (found_at is None or belief_at is None):
        if found_at is None:
            hits = client.recall(bank_id=bank, query=f"How did Hello{run}'s deals go?",
                                 types=["world"], tags=tags, tags_match="all_strict").results
            if hits:
                found_at = time.time() - start
                print(f"[lookup] found after {found_at:.1f}s: {hits[0].text}")
        if belief_at is None:
            obs = client.recall(bank_id=bank, query=f"Is Hello{run} overconfident?",
                                types=["observation"], tags=tags,
                                tags_match="all_strict").results
            if obs:
                belief_at = time.time() - start
                print(f"[belief] appeared after {belief_at:.1f}s: {obs[0].text}")
        time.sleep(3)

    print("\n--- post this in the team chat ---")
    print(f"lookup delay: {f'{found_at:.0f}s' if found_at is not None else f'>{TIMEOUT_S}s'}")
    print(f"belief delay: {f'{belief_at:.0f}s' if belief_at is not None else f'>{TIMEOUT_S}s'}")
    if belief_at is None:
        print("No belief yet. Check the bank in ui.hindsight.vectorize.io, then try reflect:")
        r = client.reflect(bank_id=bank, query=f"Is Hello{run} overconfident?",
                           tags=tags, tags_match="all_strict")
        print("reflect says:", r.text[:300])

    client.close()


if __name__ == "__main__":
    main()
