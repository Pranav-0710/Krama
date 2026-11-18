"""Phase 2, box 2.4: mix the final training set.

Takes the examples that passed the filter (box 2.3), adds the hand-written
and identity examples, sets the share of short answers to the planned 20%,
shuffles everything, and writes it in the chat layout training needs.

Run from the project folder, after data/leak_check.py:
    uv run --no-project --with fastapi --with httpx data/mix.py

Reads data/examples.jsonl, data/handwritten.py and data/leaks.txt.
Writes data/train.jsonl.
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

from handwritten import HANDWRITTEN, IDENTITY

# Reuse the exam's marking program, so hand-written code is checked the same way.
sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))
from run import extract_code, run_tests

DATA = Path(__file__).parent
IN_FILE = DATA / "examples.jsonl"
LEAKS_FILE = DATA / "leaks.txt"
OUT_FILE = DATA / "train.jsonl"

QUICK_SHARE = 0.20  # the design: about 20% plain short answers


def check_handwritten():
    """Run the tests of every hand-written coding example. Stop if any fails."""
    failed = []
    for example in HANDWRITTEN:
        if example["kind"] == "quick":
            continue
        code = extract_code(example["answer"], example["kind"])
        if not run_tests(example, code):
            failed.append(example["id"])
    if failed:
        raise SystemExit(f"hand-written examples that FAIL their tests: {failed}")
    print("hand-written coding examples: all pass their tests")


def main():
    check_handwritten()

    # Box 2.5 lists examples that copy the exam. They never go into training.
    if not LEAKS_FILE.exists():
        raise SystemExit("data/leaks.txt is missing. Run data/leak_check.py first.")
    leaks = {line.split("\t")[0] for line in LEAKS_FILE.open(encoding="utf-8") if line.strip()}
    if any(example["id"] in leaks for example in HANDWRITTEN + IDENTITY):
        raise SystemExit("a hand-written example copies the exam. Fix data/handwritten.py.")

    teacher = [json.loads(line) for line in IN_FILE.open(encoding="utf-8")]
    teacher = [example for example in teacher if example["id"] not in leaks]
    print(f"left out because they copy the exam: {len(leaks)}")
    teacher_quick = [example for example in teacher if example["kind"] == "quick"]
    hand_quick = [example for example in HANDWRITTEN if example["kind"] == "quick"]

    # Everything that is not a short answer is kept in full.
    keep = [example for example in teacher if example["kind"] != "quick"]
    keep += [example for example in HANDWRITTEN if example["kind"] != "quick"]
    keep += IDENTITY

    # How many short answers make them 20% of the whole set:
    #   quick / (keep + quick) = 0.20   ->   quick = keep * 0.20 / 0.80
    quick_wanted = round(len(keep) * QUICK_SHARE / (1 - QUICK_SHARE))
    from_teacher = max(0, min(len(teacher_quick), quick_wanted - len(hand_quick)))

    chooser = random.Random(0)  # fixed number = same mix every run
    rows = keep + hand_quick + chooser.sample(teacher_quick, from_teacher)
    chooser.shuffle(rows)

    with OUT_FILE.open("w", encoding="utf-8") as out:
        for example in rows:
            out.write(json.dumps({
                "id": example["id"],
                "kind": example["kind"],
                "messages": [
                    {"role": "user", "content": example["question"]},
                    {"role": "assistant", "content": example["answer"]},
                ],
            }) + "\n")

    counts = Counter(example["kind"] for example in rows)
    hand = sum(1 for example in rows if example["id"].startswith("hand-"))
    print(f"training examples written: {len(rows)}")
    for kind in ("python", "fastapi", "quick", "identity"):
        print(f"  {kind:8} {counts[kind]:5}  ({counts[kind] / len(rows):.1%})")
    print(f"  hand-written: {hand}   teacher short answers left out: {len(teacher_quick) - from_teacher}")


if __name__ == "__main__":
    main()
