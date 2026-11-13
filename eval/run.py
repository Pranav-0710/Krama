"""Send every test task to a model and mark the answers.

Run from the project folder:
    uv run --no-project --with fastapi --with httpx --with uvicorn eval/run.py

Add --check to test the answer keys, or --remark to mark saved answers again.

It tests two "systems" today:
    base          the untouched base model
    base+prompt   the same model, given written instructions to behave like Krama
Later we add a third: the fine-tuned Krama.
"""

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from tasks import TASKS

MODEL = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/chat"
RESULTS_DIR = Path(__file__).parent / "results"

KRAMA_PROMPT = (
    "You are Krama, a Python and FastAPI coding assistant for beginners. "
    "For a coding task, answer in three parts: 'Plan' (a short numbered list), "
    "'Code' (one python code block), and 'Why' (a few plain-language notes on "
    "why the code is written this way). For a quick question, give a short "
    "direct answer with no plan."
)

SYSTEMS = {"base": None, "base+prompt": KRAMA_PROMPT}


def ask(prompt, system_prompt):
    """Send one prompt to the model. Return (answer text, tokens written)."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        # temperature 0 = always pick the most likely next token,
        # so running this twice gives the same answer.
        "options": {"temperature": 0, "seed": 0},
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        reply = json.loads(response.read())
    return reply["message"]["content"], reply["eval_count"]


def extract_code(answer, kind):
    """Pull the solution code out of an answer that also contains prose.

    Answers often hold several code blocks: install commands, example
    requests, sample output. We want the one that is the actual solution.
    """
    blocks = re.findall(r"```([a-zA-Z]*)[ \t]*\n(.*?)```", answer, re.DOTALL)

    # 1. Prefer blocks labelled as Python; fall back to unlabelled ones.
    candidates = [code for label, code in blocks if label.lower() in ("python", "py")]
    if not candidates:
        candidates = [code for label, code in blocks if label == ""]
    if not candidates:
        return ""

    # 2. Prefer blocks that contain what a solution must contain.
    must_contain = "FastAPI(" if kind == "fastapi" else "def "
    solutions = [code for code in candidates if must_contain in code]

    # 3. If several are left, the longest is the full solution.
    return max(solutions or candidates, key=len)


def run_tests(task, code):
    """Run the model's code followed by our tests. True means all passed."""
    if not code:
        return False

    # The model's code goes in its own file and the tests import it.
    # Importing (instead of running it directly) means a line like
    #   if __name__ == "__main__": uvicorn.run(app)
    # does NOT start a real server in the middle of our test.
    script = "from solution import *\n"
    if task["kind"] == "fastapi":
        script += "from fastapi.testclient import TestClient\n"
        script += "client = TestClient(app)\n"
    script += task["tests"]

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "solution.py").write_text(code, encoding="utf-8")
        script_path = Path(folder) / "candidate.py"
        script_path.write_text(script, encoding="utf-8")
        try:
            finished = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=folder,
                capture_output=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return False
    return finished.returncode == 0


def check_answer_keys():
    """Run each known-correct answer through its own tests.

    If a correct answer fails, the answer key is wrong, not the model.
    """
    problems = 0
    for task in TASKS:
        if task["kind"] == "quick":
            continue
        if not run_tests(task, task["reference"]):
            problems += 1
            print(f"ANSWER KEY PROBLEM: {task['id']}")
    checked = sum(1 for task in TASKS if task["kind"] != "quick")
    print(f"checked {checked} answer keys, {problems} problems")


def remark():
    """Mark the saved answers again without asking the model again.

    Useful after fixing the marking program itself.
    """
    tasks_by_id = {task["id"]: task for task in TASKS}
    for system_name in SYSTEMS:
        out_file = RESULTS_DIR / f"{system_name}.json"
        records = json.loads(out_file.read_text(encoding="utf-8"))
        for record in records:
            task = tasks_by_id[record["id"]]
            if task["kind"] != "quick":
                code = extract_code(record["answer"], task["kind"])
                record["passed"] = run_tests(task, code)
        out_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print_summary(system_name, records)


def print_summary(system_name, records):
    """Print passed/total for each kind of task, and average answer length."""
    for kind in ("python", "fastapi"):
        marked = [r for r in records if r["kind"] == kind]
        passed = sum(1 for r in marked if r["passed"])
        print(f"{system_name:12} {kind:8} passed {passed}/{len(marked)}")
    quick = [r["tokens"] for r in records if r["kind"] == "quick"]
    print(f"{system_name:12} quick    average {sum(quick) // len(quick)} tokens")


def main():
    if "--check" in sys.argv:
        check_answer_keys()
        return
    if "--remark" in sys.argv:
        remark()
        return

    RESULTS_DIR.mkdir(exist_ok=True)
    print(f"{'task':28} {'system':12} {'passed':7} tokens")

    for system_name, system_prompt in SYSTEMS.items():
        records = []
        for task in TASKS:
            answer, tokens = ask(task["prompt"], system_prompt)

            if task["kind"] == "quick":
                passed = None  # no tests; judged later by a blind grader
            else:
                passed = run_tests(task, extract_code(answer, task["kind"]))

            records.append({
                "id": task["id"],
                "kind": task["kind"],
                "system": system_name,
                "answer": answer,
                "tokens": tokens,
                "passed": passed,
            })
            shown = "-" if passed is None else ("yes" if passed else "NO")
            print(f"{task['id']:28} {system_name:12} {shown:7} {tokens}")

        out_file = RESULTS_DIR / f"{system_name}.json"
        out_file.write_text(json.dumps(records, indent=2), encoding="utf-8")
        print_summary(system_name, records)


if __name__ == "__main__":
    main()
