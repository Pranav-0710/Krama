"""The agent benchmark: can `krama fix` make small projects' tests pass?

Run from the project folder:
    uv run --no-project --with pytest --with fastapi --with httpx --with-editable ./cli eval/agent_bench.py --check
    uv run --no-project --with pytest --with fastapi --with httpx --with-editable ./cli eval/agent_bench.py LABEL [local|ollama] [MODEL]

--check proves every project fails as given and passes with its known fix.
Add --set=heldout (10 projects written after the agent's edit rules were
changed because of the main 20), --set=heldout2 (10 more, written after the
first held-out set was used for changes too), --set=exam (the step-6 exam in
agent_exam.py, for judging trained models) or --set=all (the 40, not the
exam); the default is the main 20.
A run copies each project to a new folder and lets the agent work on it with
up to 15 actions. Edits are approved automatically here, but each approval
is counted, and the agent cannot write anywhere without one. Before marking,
the original test files are put back, so changing tests cannot help.
Results: eval/results/agent-<LABEL>.json
"""

import json
import sys
import tempfile
import time
from pathlib import Path

from agent_exam import AGENT_EXAM
from agent_tasks import AGENT_HELDOUT, AGENT_HELDOUT2, AGENT_TASKS
from krama_cli.agent import run_agent, run_project_tests
from krama_cli.backends import KRAMA_MODEL, make_backend

RESULTS_DIR = Path(__file__).parent / "results"


def write_project(folder, files):
    for path, text in files.items():
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_text(text, encoding="utf-8")


def check_tasks():
    problems = 0
    for task in AGENT_TASKS + AGENT_HELDOUT + AGENT_HELDOUT2 + AGENT_EXAM:
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            write_project(folder, task["files"])
            before = run_project_tests(folder, sys.executable).passed
            write_project(folder, task["fix"])
            after = run_project_tests(folder, sys.executable).passed
        if before or not after:
            problems += 1
            print(f"PROBLEM {task['id']}: fails as given = {not before}, passes with fix = {after}")
    print(f"checked {len(AGENT_TASKS) + len(AGENT_HELDOUT) + len(AGENT_HELDOUT2) + len(AGENT_EXAM)} projects, {problems} problems")


def main():
    if "--check" in sys.argv:
        check_tasks()
        return
    positional = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    label = positional[0]
    backend_name = positional[1] if len(positional) > 1 else "local"
    model = positional[2] if len(positional) > 2 else KRAMA_MODEL
    project_set = next((arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("--set=")), "main")
    chosen = {"main": AGENT_TASKS, "heldout": AGENT_HELDOUT, "heldout2": AGENT_HELDOUT2,
              "exam": AGENT_EXAM,
              "all": AGENT_TASKS + AGENT_HELDOUT + AGENT_HELDOUT2}[project_set]
    backend = make_backend(backend_name, model, context=8192)

    records = []
    for task in chosen:
        approvals = []
        notes = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            folder = Path(folder)
            write_project(folder, task["files"])
            started = time.monotonic()
            result = run_agent(task["request"], folder, backend, sys.executable,
                               approve=lambda path, diff: approvals.append(path) or True,
                               say=notes.append, max_steps=15)
            seconds = round(time.monotonic() - started)
            tests = {path: text for path, text in task["files"].items() if Path(path).name.startswith("test_")}
            write_project(folder, tests)                       # put the original tests back
            solved = run_project_tests(folder, sys.executable).passed
        records.append({"id": task["id"], "solved": solved, "agent_status": result.status, "steps": result.steps,
                        "edits": result.edits, "approvals": len(approvals), "seconds": seconds, "log": result.log,
                        "notes": notes})
        assert len(approvals) == len(result.edits), "an edit happened without an approval"
        print(f"{task['id']:22} {'SOLVED' if solved else 'no    '} agent:{result.status:8} steps {result.steps:2} "
              f"edits {len(result.edits)}  {seconds}s", flush=True)
    backend.close()

    (RESULTS_DIR / f"agent-{label}.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    solved = sum(r["solved"] for r in records)
    print(f"{label}: solved {solved}/{len(records)}; average {sum(r['seconds'] for r in records) / len(records):.0f}s per project")


if __name__ == "__main__":
    main()
