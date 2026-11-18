"""Are Krama's own tests any good? A study, before trusting them in the fix loop.

For each of the 24 coding tasks it takes a saved final answer, lets Krama
write tests for it (seeing the question and the code's names only), runs
them, and compares with the hidden exam tests:

    caught        exam says wrong, Krama's tests say wrong   (good)
    missed        exam says wrong, Krama's tests say right
    false alarm   exam says right, Krama's tests say wrong   (bad: would "fix" good code)
    agreed right  both say right

Run from the project folder (the number picks the saved answers):
    uv run --no-project --with fastapi --with httpx --with uvicorn --with-editable ./cli eval/testcheck_study.py 4 [local|ollama]
"""

import json
import sys
from pathlib import Path

from krama_cli.backends import make_backend
from krama_cli.check import extract_code
from krama_cli.selftest import self_test
from tasks import TASKS

RESULTS_DIR = Path(__file__).parent / "results"


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else "4"
    backend = make_backend(sys.argv[2] if len(sys.argv) > 2 else "auto")
    saved = {r["id"]: r for r in json.loads((RESULTS_DIR / f"selfcheck-run{run}.json").read_text(encoding="utf-8"))}
    prompts = {task["id"]: task["prompt"] for task in TASKS}

    rows = []
    for task_id, record in saved.items():
        report = self_test(prompts[task_id], extract_code(record["answer"]), backend, sys.executable)
        rows.append({"id": task_id, "exam_passed": record["passed"], "report_status": report.status,
                     "message": report.message, "tests": report.tests})
        print(f"{task_id:26} exam {'yes' if record['passed'] else 'NO ':3}  krama-tests {report.status:8} {report.message}",
              flush=True)
    backend.close()

    def count(exam, status):
        return sum(1 for r in rows if r["exam_passed"] == exam and r["report_status"] == status)

    print(f"\ncaught {count(False, 'failed')}, missed {count(False, 'passed')}, "
          f"false alarms {count(True, 'failed')}, agreed right {count(True, 'passed')}, "
          f"warnings on wrong {count(False, 'warning')}, warnings on right {count(True, 'warning')}, "
          f"skipped {sum(1 for r in rows if r['report_status'] == 'skipped')}")
    (RESULTS_DIR / f"testcheck-study-run{run}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
