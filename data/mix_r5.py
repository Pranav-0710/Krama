"""Round 5: round 4's better bug examples in round 3's proportions.

Round 4 (data/agent_train.jsonl) had the same 1,357 feature examples as round 3
but 2,631 bug examples instead of 1,117, and the trained Krama got worse at
adding features and at writing FastAPI code. This keeps every feature example
and picks ONE bug example per code sample, down to round 3's 1,117, so the
only change from round 3 is what the bug examples teach (more kinds of bugs,
second looks).

Which bug example per code sample: a "second look" one if there is one, until
30% of the bug examples are second looks (the share agent_data.py was designed
for); otherwise the kind of bug picked least so far. Trimming to 1,117 drops
plain examples first, never second looks.

Run from the project folder (no packages needed):
    python data/mix_r5.py
Reads data/agent_train.jsonl (round 4), writes data/agent_train_r5.jsonl.
"""

import collections
import json
import random
from pathlib import Path

DATA = Path(__file__).parent
IN_FILE = DATA / "agent_train.jsonl"
OUT_FILE = DATA / "agent_train_r5.jsonl"
BUG_TARGET = 1117          # round 3's number of bug examples
SECOND_LOOK_TARGET = 335   # 30% of them, the share agent_data.py was designed for
SEED = 5


def seed_of(row_id):
    """'fastapi-0742-bug-import' -> 'fastapi-0742'."""
    return row_id.split("-bug")[0].split("-feature")[0]


def main():
    rng = random.Random(SEED)
    rows = [json.loads(line) for line in open(IN_FILE, encoding="utf-8")]
    features = [row for row in rows if "-bug" not in row["id"]]
    bugs_by_seed = collections.defaultdict(list)
    for row in rows:
        if "-bug" in row["id"]:
            bugs_by_seed[seed_of(row["id"])].append(row)

    picked, kind_count = [], collections.Counter()
    seeds = sorted(bugs_by_seed)
    rng.shuffle(seeds)
    for seed in seeds:
        choices = bugs_by_seed[seed]
        second_looks = [row for row in choices if row.get("recovery") == "second look"]
        others = [row for row in choices if row.get("recovery") != "second look"]
        taken = sum(row.get("recovery") == "second look" for row in picked)
        pool = second_looks if second_looks and taken < SECOND_LOOK_TARGET else (others or second_looks)
        best = min(kind_count[row["bug"]] for row in pool)
        row = rng.choice([row for row in pool if kind_count[row["bug"]] == best])
        kind_count[row["bug"]] += 1
        picked.append(row)

    # Down to round 3's count: drop plain examples first, keep every second look.
    if len(picked) > BUG_TARGET:
        plain = [row for row in picked if row.get("recovery") is None]
        rng.shuffle(plain)
        drop = {id(row) for row in plain[:len(picked) - BUG_TARGET]}
        picked = [row for row in picked if id(row) not in drop]

    out = features + picked
    rng.shuffle(out)
    with open(OUT_FILE, "w", encoding="utf-8") as handle:
        for row in out:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"wrote {OUT_FILE.name}: {len(out)} rows = {len(features)} features + {len(picked)} bugs")
    print("  recoveries:", dict(collections.Counter(row.get("recovery") for row in out)))
    print("  bug kinds:", dict(collections.Counter(row["bug"] for row in picked).most_common()))


if __name__ == "__main__":
    main()
