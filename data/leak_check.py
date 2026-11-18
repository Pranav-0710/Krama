"""Phase 2, box 2.5: the leak check. Keep the exam questions out of training.

If Krama trains on an exam question, or on its answer, it can remember it
instead of working it out, and its exam score stops meaning anything.

Two rules find a leak:
    1. Same answer: the training code passes an exam task's own tests.
       For Python we try every function in the answer under the exam's
       function name, so a renamed copy (remove_duplicates for dedupe)
       is caught too. For FastAPI we try answers that use the exam's URL.
    2. Same question: a short question mentions all the key words of an
       exam question, such as "list" and "tuple".

Run from the project folder, after the filter and before data/mix.py:
    uv run --no-project --with fastapi --with httpx data/leak_check.py

Reads data/examples.jsonl and data/handwritten.py.
Writes data/leaks.txt: one line per leak, "id <tab> exam id <tab> rule".
"""

import ast
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from handwritten import HANDWRITTEN, IDENTITY

sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))
from run import extract_code, run_tests
from tasks import TASKS

DATA = Path(__file__).parent
IN_FILE = DATA / "examples.jsonl"
OUT_FILE = DATA / "leaks.txt"

# Rule 2. Each line: an exam question, and words that ALL appear when a
# short training question asks the same thing. An exam question can have
# more than one line ("422" OR "validation" + "status").
# real-... are the learner's own questions in eval/real_questions.txt.
SAME_QUESTION = [
    ("quick-list-vs-tuple", ["list", "tuple"]),
    ("quick-zip", ["zip"]),
    ("quick-422", ["422"]),
    ("quick-422", ["validation", "status"]),
    ("quick-name-main", ["__name__"]),
    ("quick-name-main", ["__main__"]),
    ("quick-equals-vs-is", ["==", "`is`"]),
    ("quick-run-fastapi", ["run", "fastapi"]),
    ("real-404", ["404"]),
    ("real-keyerror", ["keyerror"]),
    ("real-return-none", ["return", "none"]),
    ("real-list-vs-dict", ["list", "dict"]),
    ("real-async", ["async"]),
    ("real-pydantic", ["pydantic"]),
]


def mentions(question, word):
    """True if the word starts somewhere in the question ("list" also finds "lists")."""
    return re.search(r"(?<!\w)" + re.escape(word), question.lower()) is not None


def same_question(example):
    """Rule 2: return the exam id this short question copies, or None."""
    if example["kind"] not in ("quick", "identity"):
        return None
    for exam_id, words in SAME_QUESTION:
        if all(mentions(example["question"], word) for word in words):
            return exam_id
    return None


def answer_attempts(examples):
    """Rule 1: list every (exam task, training id, code to run) worth trying."""
    attempts = []
    for task in TASKS:
        if task["kind"] == "python":
            # The name the exam's tests call, such as dedupe.
            exam_name = re.search(r"assert (\w+)\(", task["tests"]).group(1)
        elif task["kind"] == "fastapi":
            # The first URL the exam's tests visit, such as "/items.
            exam_url = '"' + re.search(r'client\.\w+\(\s*"(/[a-z_]+)', task["tests"]).group(1)
        else:
            continue
        for example in examples:
            if example["kind"] != task["kind"]:
                continue
            code = extract_code(example["answer"], example["kind"])
            if task["kind"] == "fastapi":
                if exam_url in code:
                    attempts.append((task, example["id"], code))
                continue
            try:
                functions = [node.name for node in ast.parse(code).body
                             if isinstance(node, ast.FunctionDef)]
            except SyntaxError:
                continue
            for name in functions:
                # Give the function the exam's name too, then run the exam's tests.
                attempts.append((task, example["id"], f"{code}\n\n{exam_name} = {name}\n"))
    return attempts


def main():
    examples = [json.loads(line) for line in IN_FILE.open(encoding="utf-8")]
    examples += HANDWRITTEN + IDENTITY
    leaks = {}  # training id -> (exam id, rule)

    for example in examples:
        exam_id = same_question(example)
        if exam_id:
            leaks[example["id"]] = (exam_id, "same question")

    attempts = answer_attempts(examples)
    print(f"running exam tests against training answers: {len(attempts)} runs")

    def solves(attempt):
        task, example_id, code = attempt
        return task["id"], example_id, run_tests(task, code)

    # Each run is a separate small program, so several can run at once.
    with ThreadPoolExecutor(max_workers=12) as pool:
        for exam_id, example_id, passed in pool.map(solves, attempts):
            if passed:
                leaks[example_id] = (exam_id, "same answer")

    with OUT_FILE.open("w", encoding="utf-8") as out:
        for example_id, (exam_id, rule) in sorted(leaks.items()):
            out.write(f"{example_id}\t{exam_id}\t{rule}\n")

    print(f"leaks found: {len(leaks)} of {len(examples)} examples")
    for (exam_id, rule), count in sorted(Counter(leaks.values()).items()):
        print(f"  {count:3}  {exam_id:22} {rule}")
    hand = [example_id for example_id in leaks if example_id.startswith(("hand-", "identity-"))]
    print(f"hand-written leaks (should be none): {hand}")


if __name__ == "__main__":
    main()
