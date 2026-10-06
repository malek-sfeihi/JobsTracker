"""Which emails to label by hand, to build the "gold" dataset."""
import random
import sqlite3

LABELS = ["confirmation", "rejection", "assessment", "interview", "offer", "not_job"]

# How many emails the rules did NOT flag we also label. Without them we could only measure
# the rules' false alarms, never the job emails they missed.
NEGATIVE_SAMPLE = 120


def labeling_queue(conn: sqlite3.Connection, seed: int = 42) -> list[str]:
    """Email ids to label: every email the rules flagged + a random sample of the others.

    Shuffled, so you don't see all the "job" emails first (that would hint at the answer).
    A fixed seed gives the same queue on every run: stopping and resuming is safe.
    """
    rows = conn.execute("SELECT id, category FROM emails ORDER BY id").fetchall()
    flagged = [r["id"] for r in rows if r["category"]]
    others = [r["id"] for r in rows if not r["category"]]

    rng = random.Random(seed)
    queue = flagged + rng.sample(others, min(NEGATIVE_SAMPLE, len(others)))
    rng.shuffle(queue)
    return queue
