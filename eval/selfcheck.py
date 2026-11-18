"""Does the self-check help? Krama answers the 24 coding tasks through the
`krama` tool's ask -> check -> fix loop, then the exam tests mark the final code.

Run from the project folder:
    uv run --no-project --with fastapi --with httpx --with uvicorn --with-editable ./cli eval/selfcheck.py 1

The number at the end names the run (1, 2, ...). CPU runs are not exactly
repeatable, so run it more than once. Results: eval/results/selfcheck-run<N>.json
Add a backend name after the number to choose the engine, e.g. `... 5 local`
for the built-in llama.cpp engine (default: ollama). Add --no-tests to skip
Krama's own tests and only use the run check.
"""

import json
import sys
from pathlib import Path

from krama_cli.backends import make_backend
from krama_cli.main import answer_with_check
from run import extract_code, run_tests
from tasks import TASKS

RESULTS_DIR = Path(__file__).parent / "results"


def main():
    run_name = sys.argv[1] if len(sys.argv) > 1 else "1"
    records = []
    backend_name = sys.argv[2] if len(sys.argv) > 2 else "ollama"
    backend = make_backend(backend_name)
    use_tests = "--no-tests" not in sys.argv
    for task in TASKS:
        if task["kind"] == "quick":
            continue
        notes = []
        # The check runs with this same Python, which has fastapi installed.
        answer, result, report = answer_with_check(task["prompt"], backend, sys.executable,
                                                   approve=lambda: True, say=notes.append,
                                                   use_tests=use_tests)
        passed = run_tests(task, extract_code(answer, task["kind"]))
        tries = 1 + sum("asking Krama to fix" in note for note in notes)
        tested = report.status if report else "-"
        records.append({"id": task["id"], "kind": task["kind"], "backend": backend_name, "answer": answer,
                        "passed": passed, "check": result.status, "krama_tests": tested, "tries": tries,
                        "notes": notes})
        print(f"{task['id']:26} check {result.status:8} krama-tests {tested:8} tries {tries}  exam {'yes' if passed else 'NO'}",
              flush=True)

    backend.close()
    (RESULTS_DIR / f"selfcheck-run{run_name}.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    for kind in ("python", "fastapi"):
        marked = [r for r in records if r["kind"] == kind]
        print(f"{kind:8} passed {sum(r['passed'] for r in marked)}/{len(marked)}")
    print(f"fix requests: {sum(r['tries'] - 1 for r in records)}; "
          f"still failing the self-check: {sum(r['check'] == 'failed' for r in records)}")


if __name__ == "__main__":
    main()
