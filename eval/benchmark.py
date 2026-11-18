"""The standard benchmark: HumanEval, 164 Python tasks checked by running tests.

Why: our own 30 tasks were used to decide what to fix in round 2, so they can
flatter Krama ("teaching to the test"). HumanEval was never used to choose
anything, so it is the fairer measure. Licence: MIT (github.com/openai/human-eval).

Run from the project folder:
    uv run --no-project eval/benchmark.py              (all three systems, about an hour)
    uv run --no-project eval/benchmark.py --only krama
    uv run --no-project eval/benchmark.py --check      (the reference answers must all pass)

Each task gives a function's first line and docstring. Every system gets the
same request: complete the function. The answer's code is run against the
task's tests. Results go to eval/results/humaneval-<system>.json.
"""

import gzip
import json
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from run import RESULTS_DIR, SYSTEMS, ask, extract_code

DATA_FILE = Path(__file__).parent / "benchmark" / "HumanEval.jsonl.gz"
DATA_URL = "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz"

REQUEST = "Complete this Python function:\n\n```python\n{prompt}```"


def load_tasks():
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(DATA_URL, DATA_FILE)
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as lines:
        return [json.loads(line) for line in lines]


def header(prompt):
    """The import lines at the top of the task, e.g. `from typing import List`.

    Answers often leave these out, which would fail for a reason that has
    nothing to do with the function. They are added back for every system alike.
    """
    lines = []
    for line in prompt.splitlines():
        if line.startswith(("def ", "class ", "@")):
            break
        if line.startswith(("import ", "from ")):
            lines.append(line)
    return "\n".join(lines)


def passes(task, code):
    """Run the code, then the task's tests. True means every test passed."""
    if not code:
        return False
    script = f"{header(task['prompt'])}\n{code}\n\n{task['test']}\n\ncheck({task['entry_point']})\n"
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "candidate.py"
        path.write_text(script, encoding="utf-8")
        try:
            finished = subprocess.run([sys.executable, str(path)], cwd=folder,
                                      capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            return False
    return finished.returncode == 0


def main():
    tasks = load_tasks()

    if "--check" in sys.argv:
        broken = [t["task_id"] for t in tasks if not passes(t, t["prompt"] + t["canonical_solution"])]
        print(f"checked {len(tasks)} reference answers, {len(broken)} fail: {broken}")
        return

    chosen = SYSTEMS
    if "--only" in sys.argv:
        name = sys.argv[sys.argv.index("--only") + 1]
        chosen = {name: SYSTEMS[name]}

    RESULTS_DIR.mkdir(exist_ok=True)
    for system_name, (model, system_prompt) in chosen.items():
        records = []
        for number, task in enumerate(tasks, 1):
            try:
                answer, tokens = ask(model, REQUEST.format(prompt=task["prompt"]), system_prompt)
            except TimeoutError:
                # A model that rambles for over 5 minutes fails the task (same rule for all systems).
                answer, tokens = "(no answer: timed out after 5 minutes)", 0
            passed = passes(task, extract_code(answer, "python"))
            records.append({"id": task["task_id"], "system": system_name,
                            "answer": answer, "tokens": tokens, "passed": passed})
            if number % 20 == 0:
                done = sum(r["passed"] for r in records)
                print(f"{system_name:12} {number:3}/{len(tasks)}  passed so far {done}", flush=True)
        out_file = RESULTS_DIR / f"humaneval-{system_name}.json"
        out_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
        passed = sum(r["passed"] for r in records)
        print(f"{system_name:12} HumanEval passed {passed}/{len(tasks)} ({passed / len(tasks):.1%})", flush=True)


if __name__ == "__main__":
    main()
