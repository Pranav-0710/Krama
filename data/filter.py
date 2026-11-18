"""Phase 2, box 2.3: the filter. Keep only teacher answers that are proven good.

Coding answers are kept only if their code passes their own tests.
Quick answers are kept only if they are short and have no plan.

Run from the project folder:
    uv run --no-project --with fastapi --with httpx --with uvicorn data/filter.py

Reads every data/answers*.jsonl file (from Kaggle). Writes data/examples.jsonl.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# Reuse the marking program from Phase 1, so the filter marks
# exactly the way the exam does.
sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))
from run import extract_code, run_tests

DATA = Path(__file__).parent
OUT_FILE = DATA / "examples.jsonl"

QUICK_MAX_WORDS = 90


def split_sections(raw):
    """Cut a teacher reply into its ### QUESTION / ### TESTS / ### ANSWER parts."""
    parts = re.split(r"^###\s*(QUESTION|TESTS|ANSWER)\s*$", raw, flags=re.MULTILINE)
    sections = {}
    # re.split gives: [before, NAME, text, NAME, text, ...]
    for position in range(1, len(parts) - 1, 2):
        sections[parts[position]] = parts[position + 1].strip()
    return sections


def judge(record):
    """Return (kept example or None, reason)."""
    sections = split_sections(record["raw"])
    question = sections.get("QUESTION", "")
    answer = sections.get("ANSWER", "")
    if not question or not answer:
        return None, "layout broken"

    if record["kind"] == "quick":
        too_long = len(answer.split()) > QUICK_MAX_WORDS
        if "Plan:" in answer or too_long:
            return None, "quick answer too long or has a plan"
    else:
        # The teacher often wraps its tests in a ```python fence.
        # Remove the fence lines so only the test code is run.
        tests = re.sub(r"^```[a-zA-Z]*[ \t]*$", "", sections.get("TESTS", ""), flags=re.MULTILINE).strip()
        if not tests:
            return None, "no tests"
        if not all(part in answer for part in ("Plan:", "Code:", "Why:")):
            return None, "missing Plan, Code or Why"
        task = {"kind": record["kind"], "tests": tests}
        code = extract_code(answer, record["kind"])
        if not run_tests(task, code):
            return None, "code failed its tests"

    return {
        "id": record["id"],
        "kind": record["kind"],
        "question": question,
        "answer": answer,
    }, "kept"


def main():
    # Read every answers*.jsonl file (one per Kaggle run). If the same
    # request was answered twice, keep only the first answer.
    records = []
    seen_ids = set()
    for answers_file in sorted(DATA.glob("answers*.jsonl")):
        for line in answers_file.open(encoding="utf-8"):
            record = json.loads(line)
            if record["id"] not in seen_ids:
                seen_ids.add(record["id"])
                records.append(record)
    reasons = Counter()
    kept_by_kind = Counter()
    total_by_kind = Counter(record["kind"] for record in records)

    with OUT_FILE.open("w", encoding="utf-8") as out:
        for record in records:
            example, reason = judge(record)
            reasons[reason] += 1
            if example:
                kept_by_kind[record["kind"]] += 1
                out.write(json.dumps(example) + "\n")

    kept = reasons["kept"]
    print(f"answers read: {len(records)}   kept: {kept}   thrown away: {len(records) - kept}")
    for kind in ("python", "fastapi", "quick"):
        print(f"  {kind:8} kept {kept_by_kind[kind]} of {total_by_kind[kind]}")
    print("why answers were thrown away:")
    for reason, count in reasons.most_common():
        if reason != "kept":
            print(f"  {count:3}  {reason}")


if __name__ == "__main__":
    main()
