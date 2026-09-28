import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "calibrate.sqlite"
RUNS = Path(__file__).resolve().parents[1] / "data" / "runs"


def load_run(run_id: str = "demo") -> None:
    folder = RUNS / run_id

    con = sqlite3.connect(DB)

    con.execute("DROP TABLE IF EXISTS blobs")
    con.execute(
        "CREATE TABLE blobs (name TEXT PRIMARY KEY, body TEXT)"
    )

    for file in folder.glob("*.json"):
        con.execute(
            "INSERT INTO blobs VALUES (?, ?)",
            (file.stem, file.read_text(encoding="utf-8")),
        )

    con.commit()
    con.close()


def get(name: str):
    con = sqlite3.connect(DB)

    row = con.execute(
        "SELECT body FROM blobs WHERE name = ?",
        (name,),
    ).fetchone()

    con.close()

    return json.loads(row[0]) if row else None