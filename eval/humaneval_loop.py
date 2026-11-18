"""HumanEval through the `krama` tool's loop: the fair check of the self-check.

The test-based self-check was tuned on our own 24 tasks, so its numbers there
may flatter it. HumanEval (164 tasks) was never used to tune it. This runs
every task through `answer_with_check` on one engine, in one of three modes:

    plain   one answer, no checking at all (the baseline)
    check   the run check and its fixes only
    tests   the run check plus Krama's own tests and their fixes

Krama never sees HumanEval's tests; they only mark the final answer.

Run from the project folder:
    uv run --no-project --with-editable ./cli eval/humaneval_loop.py tests [local|ollama]
Results: eval/results/humaneval-loop-<mode>-<backend>.json
"""

import json
import sys

from benchmark import REQUEST, load_tasks, passes
from krama_cli.backends import make_backend
from krama_cli.main import answer_with_check, start_conversation
from run import RESULTS_DIR, extract_code


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "tests"
    backend_name = sys.argv[2] if len(sys.argv) > 2 else "local"
    if mode not in ("plain", "check", "tests"):
        sys.exit("mode must be plain, check or tests")
    backend = make_backend(backend_name)

    records = []
    tasks = load_tasks()
    for number, task in enumerate(tasks, 1):
        question = REQUEST.format(prompt=task["prompt"])
        notes = []
        if mode == "plain":
            answer, check_status, test_status = backend.chat(start_conversation(question)), "-", "-"
        else:
            # Like a real user's question: if the answer forgets an import
            # (such as `from typing import List`), the run check catches it.
            answer, result, report = answer_with_check(question, backend, sys.executable, approve=lambda: True,
                                                       say=notes.append, use_tests=(mode == "tests"))
            check_status, test_status = result.status, (report.status if report else "-")
        passed = passes(task, extract_code(answer, "python"))
        records.append({"id": task["task_id"], "mode": mode, "backend": backend_name, "answer": answer,
                        "passed": passed, "check": check_status, "krama_tests": test_status,
                        "fixes": sum("asking Krama to fix" in note for note in notes), "notes": notes})
        if number % 20 == 0:
            print(f"{mode:6} {number:3}/{len(tasks)}  passed so far {sum(r['passed'] for r in records)}", flush=True)
    backend.close()

    out_file = RESULTS_DIR / f"humaneval-loop-{mode}-{backend_name}.json"
    out_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
    passed = sum(r["passed"] for r in records)
    print(f"{mode:6} HumanEval passed {passed}/{len(tasks)} ({passed / len(tasks):.1%}); "
          f"fix requests {sum(r['fixes'] for r in records)}", flush=True)


if __name__ == "__main__":
    main()
