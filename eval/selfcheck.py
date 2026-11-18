"""Does the self-check help? Krama answers the 24 coding tasks through the
`krama` tool's ask -> check -> fix loop, then the exam tests mark the final code.

Run from the project folder:
    uv run --no-project --with fastapi --with httpx --with uvicorn --with-editable ./cli eval/selfcheck.py 1

The number at the end names the run (1, 2, ...). CPU runs are not exactly
repeatable, so run it more than once. Results: eval/results/selfcheck-run<N>.json
"""

import json
import sys
from pathlib import Path

from krama_cli.backends import OllamaBackend
from krama_cli.main import answer_with_check
from run import extract_code, run_tests
from tasks import TASKS

RESULTS_DIR = Path(__file__).parent / "results"


def main():
    run_name = sys.argv[1] if len(sys.argv) > 1 else "1"
    records = []
    backend = OllamaBackend()
    for task in TASKS:
        if task["kind"] == "quick":
            continue
        notes = []
        # The check runs with this same Python, which has fastapi installed.
        answer, result = answer_with_check(task["prompt"], backend, sys.executable,
                                           approve=lambda: True, say=notes.append)
        passed = run_tests(task, extract_code(answer, task["kind"]))
        tries = 1 + sum("asking Krama to fix" in note for note in notes)
        records.append({"id": task["id"], "kind": task["kind"], "answer": answer,
                        "passed": passed, "check": result.status, "tries": tries})
        print(f"{task['id']:26} check {result.status:8} tries {tries}  tests {'yes' if passed else 'NO'}", flush=True)

    (RESULTS_DIR / f"selfcheck-run{run_name}.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    for kind in ("python", "fastapi"):
        marked = [r for r in records if r["kind"] == kind]
        print(f"{kind:8} passed {sum(r['passed'] for r in marked)}/{len(marked)}")
    print(f"fix requests: {sum(r['tries'] - 1 for r in records)}; "
          f"still failing the self-check: {sum(r['check'] == 'failed' for r in records)}")


if __name__ == "__main__":
    main()
