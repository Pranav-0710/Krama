"""Blind grading: a different AI model scores the answers against eval/RUBRIC.md.

Run from the project folder (needs `ollama pull llama3.1:8b` once):
    uv run --no-project eval/grade.py
    uv run --no-project eval/grade.py --task py-chunk     (one task, to check the grader)

How it stays blind: the grader sees one answer at a time, labelled only "A",
in a shuffled order. It never sees system names or whether the code passed
its tests. The shuffle uses a fixed seed per task, so a rerun gives the same
order. (RUBRIC.md planned all answers at once; see grade_task for why that
changed.)

The grader is Llama 3.1 8B: a different model family from Krama's Qwen, so it
has no family bias, and it runs offline so anyone can repeat this.

Scores follow eval/RUBRIC.md (fixed before training). One extra score,
"why_correct", is NOT part of the fixed rules. It was added after training
because a tutor's explanation must be true, and it is reported separately.
Results go to eval/results/grades.json.
"""

import json
import random
import sys
import urllib.request
from pathlib import Path

from tasks import TASKS

GRADER = "llama3.1:8b"
OLLAMA_URL = "http://localhost:11434/api/chat"
RESULTS_DIR = Path(__file__).parent / "results"
SYSTEMS = ["base", "base+prompt", "krama", "krama-r2"]
LETTERS = "ABCD"

CODING_RULES = """Score each answer on these rules. Each rule is 0, 1 or 2.

plan:
  0 = no plan, or the plan does not match the code
  1 = a plan, but vague or padded
  2 = short numbered steps that the code then follows
why:
  0 = missing, or only repeats what the code does
  1 = gives some reasons
  2 = explains the choices a beginner would wonder about
clarity:
  0 = jargon with no explanation
  1 = mostly clear
  2 = a beginner could follow it without looking anything up
length:
  0 = far too long or too short for the task
  1 = a little padded
  2 = plan, code and explanation, with no filler
why_correct (is every claim in the explanation true?):
  0 = at least one claim is wrong or would mislead a beginner
  1 = mostly true, with a small inaccuracy
  2 = every claim is true (also 2 if there is no explanation to check)"""

QUICK_RULES = """Score each answer on these rules. Each rule is 0, 1 or 2.

correct:
  0 = wrong
  1 = partly right or misleading
  2 = right
length:
  0 = a plan, a long walkthrough, or several code blocks
  1 = a little padded
  2 = a short direct answer, with at most one small example"""

CODING_KEYS = ["plan", "why", "clarity", "length", "why_correct"]
QUICK_KEYS = ["correct", "length"]


def ask_grader(prompt):
    body = {
        "model": GRADER,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        # Same answer every run; a long window so four answers fit.
        "options": {"temperature": 0, "seed": 0, "num_ctx": 8192},
    }
    request = urllib.request.Request(OLLAMA_URL, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())["message"]["content"]


def build_prompt(task, shuffled):
    """The grader's instructions plus the shuffled answers, with no system names."""
    coding = task["kind"] != "quick"
    rules, keys = (CODING_RULES, CODING_KEYS) if coding else (QUICK_RULES, QUICK_KEYS)
    kind = "a beginner's coding task" if coding else "a beginner's quick question"
    parts = [
        f"You are grading answers from AI coding tutors to {kind}. The reader is a "
        "beginner learning Python. Grade each answer on its own merits.\n",
        f"The beginner asked:\n<<<\n{task['prompt']}\n>>>\n",
        rules,
        "",
    ]
    for letter, answer in zip(LETTERS, shuffled):
        parts.append(f"Answer {letter}:\n<<<\n{answer}\n>>>\n")
    # A small grader gives everything top marks unless it must justify each
    # score first, so every score comes after a one-sentence reason.
    example = {}
    for key in keys:
        example[f"{key}_reason"] = "one sentence about this answer"
        example[key] = 0
    parts.append(
        "Judge each answer separately and strictly; answers can differ a lot. "
        "An answer with no numbered steps before its code has no plan.\n"
        "Reply with JSON only, one object per answer. Write each reason before its score:\n"
        + json.dumps({letter: example for letter in LETTERS[:len(shuffled)]})
    )
    return "\n".join(parts), keys


def valid(scores, keys, count):
    try:
        return all(scores[letter][key] in (0, 1, 2)
                   for letter in LETTERS[:count] for key in keys)
    except (KeyError, TypeError):
        return False


def grade_one(task, answer):
    """Scores for one answer shown alone, or None if the grader failed twice."""
    prompt, keys = build_prompt(task, [answer])
    for _ in range(2):
        try:
            scores = json.loads(ask_grader(prompt))
        except json.JSONDecodeError:
            continue
        if valid(scores, keys, 1):
            return {key: scores["A"][key] for key in keys} | {
                "reasons": {key: scores["A"].get(f"{key}_reason", "") for key in keys}}
    return None


def grade_task(task, answers):
    """Return {system: scores} for one task, or None if any answer could not be graded.

    Each answer is graded ALONE. Shown four at once, Llama 3.1 8B mixed the
    answers up (it credited an answer with a plan it did not have), so the
    rubric's "all answers at once" was changed to "one at a time". The grader
    still never sees which system wrote the answer, and the order is shuffled.
    """
    order = list(SYSTEMS)
    random.Random(task["id"]).shuffle(order)          # fixed shuffle per task
    scores = {name: grade_one(task, answers[name]) for name in order}
    return (scores if all(scores.values()) else None), order


def summary(graded):
    """Average score per rule, per system."""
    for kind, keys in (("coding", CODING_KEYS), ("quick", QUICK_KEYS)):
        rows = [g for g in graded if g["kind"] == kind and g["scores"]]
        if not rows:
            continue
        print(f"\n{kind} ({len(rows)} tasks graded), average out of 2:")
        print(f"{'system':12} " + " ".join(f"{key:>11}" for key in keys) + "   fixed-rules total")
        for name in SYSTEMS:
            averages = [sum(g["scores"][name][key] for g in rows) / len(rows) for key in keys]
            fixed = sum(averages[:4] if kind == "coding" else averages)
            print(f"{name:12} " + " ".join(f"{a:11.2f}" for a in averages) + f"   {fixed:.2f}")


def main():
    answers = {name: {r["id"]: r["answer"] for r in
                      json.loads((RESULTS_DIR / f"{name}.json").read_text(encoding="utf-8"))}
               for name in SYSTEMS}
    tasks = TASKS
    if "--task" in sys.argv:
        wanted = sys.argv[sys.argv.index("--task") + 1]
        tasks = [t for t in TASKS if t["id"] == wanted]

    graded = []
    for number, task in enumerate(tasks, 1):
        task_answers = {name: answers[name][task["id"]] for name in SYSTEMS}
        scores, order = grade_task(task, task_answers)
        kind = "quick" if task["kind"] == "quick" else "coding"
        graded.append({"id": task["id"], "kind": kind, "shown_order": order, "scores": scores})
        print(f"{number:2}/{len(tasks)} {task['id']:26} {'ok' if scores else 'GRADER FAILED'}", flush=True)
        if scores and len(tasks) == 1:
            print(json.dumps(scores, indent=1))

    if len(tasks) > 1:
        (RESULTS_DIR / "grades.json").write_text(json.dumps(graded, indent=2), encoding="utf-8")
    summary(graded)


if __name__ == "__main__":
    main()
