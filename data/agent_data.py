"""Step 6: training data for the guided agent (`krama fix`).

A trajectory is the record of one agent job: the task, each action the model
took, and what krama replied. This program writes good trajectories to learn from.

1. Seeds: the phase-2 coding examples whose code passed their own tests
   (data/examples.jsonl, with the tests from data/answers*.jsonl).
2. Projects: each seed becomes a code file plus a pytest file.
3. Breaks: the code is broken on purpose, and only breaks that make the
   tests fail are kept, so the original code is a known fix:
     bug      one small change (`<` for `<=`, `+` for `-`, 1 for 0, 400 for 404,
              a dropped `.strip()` or `not`, a missing import)
     feature  one function, method or endpoint is removed; the task asks for it back
4. Steps: the ideal actions (read, then one exact replace) are run through
   krama's real tools on a copy of the project, so every reply in the data is
   what krama really says, and the tests really pass at the end. About one in
   five also has a typical mistake first, and the recovery from krama's real
   message. Mistaken actions are marked "train": false: the model sees them
   but is not taught to make them.

Seeds that look like a benchmark or exam project (same function name, or
similar code) are left out, so the scores stay fair.

Run from the project folder (about an hour on a laptop):
    uv run --no-project --with pytest --with fastapi --with httpx --with uvicorn --with-editable ./cli data/agent_data.py [--limit=N]
Writes data/agent_train.jsonl and prints what was kept and why.
"""

import ast
import difflib
import hashlib
import json
import keyword
import random
import re
import sys
import tempfile
import textwrap
import tokenize
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "eval"))
from agent_exam import AGENT_EXAM
from agent_tasks import AGENT_HELDOUT, AGENT_HELDOUT2, AGENT_TASKS
from filter import split_sections
from run import extract_code

from krama_cli.agent import AGENT_SYSTEM, Tools, run_project_tests, start_message

OUT_FILE = DATA / "agent_train.jsonl"
WORKERS = 6
RECOVERY_SHARE = 0.2
HOME = str(Path.home())

# Small, realistic slips. Each maps what the code says to what the break says.
OP_SWAPS = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "==",
            "+": "-", "-": "+", "*": "+", "//": "/", "+=": "-=", "-=": "+="}
NAME_SWAPS = {"and": "or", "or": "and", "True": "False", "False": "True",
              "lower": "upper", "upper": "lower", "min": "max", "max": "min"}
STATUS_SWAPS = {404: 400, 400: 404, 201: 200, 200: 201, 401: 403, 403: 401, 422: 400, 204: 200}
ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}

BUG_REQUESTS = ["The tests fail. Fix the bug.",
                "There is a bug in {file}. Make the tests pass.",
                "`{func}` gives the wrong result. Fix it.",
                "The tests for `{func}` fail. Find the bug and fix it."]


# ---------------------------------------------------------------- seeds

def seeds():
    """The kept phase-2 coding examples, each with its code and tests."""
    kept = {json.loads(line)["id"] for line in (DATA / "examples.jsonl").open(encoding="utf-8")}
    seen = set()
    for answers_file in sorted(DATA.glob("answers*.jsonl")):
        for line in answers_file.open(encoding="utf-8"):
            record = json.loads(line)
            if record["id"] in seen:          # the filter kept the first answer per id
                continue
            seen.add(record["id"])
            if record["id"] not in kept or record["kind"] == "quick":
                continue
            sections = split_sections(record["raw"])
            tests = re.sub(r"^```[a-zA-Z]*[ \t]*$", "", sections.get("TESTS", ""), flags=re.MULTILINE).strip()
            yield {"id": record["id"], "kind": record["kind"],
                   "code": extract_code(sections["ANSWER"], record["kind"]).strip() + "\n", "tests": tests}


def defined_names(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def protected_projects():
    """The code of every benchmark and exam project, and its plain-Python names: training must not copy them."""
    codes, names = [], set()
    for task in AGENT_TASKS + AGENT_HELDOUT + AGENT_HELDOUT2 + AGENT_EXAM:
        for path, text in {**task["files"], **task["fix"]}.items():
            if not Path(path).name.startswith("test_"):
                codes.append(text)
                if "FastAPI" not in text:          # endpoint names like get_item are too common to ban
                    names |= defined_names(text)
    return codes, names - {"__init__"}


def too_close(seed, codes, names):
    if seed["kind"] == "python" and defined_names(seed["code"]) & names:
        return True
    for code in codes:
        matcher = difflib.SequenceMatcher(None, seed["code"], code)
        if matcher.real_quick_ratio() > 0.6 and matcher.quick_ratio() > 0.6 and matcher.ratio() > 0.6:
            return True
    return False


# ---------------------------------------------------------------- projects

def module_name(seed):
    if seed["kind"] == "fastapi":
        return "main" if int(hashlib.md5(seed["id"].encode()).hexdigest(), 16) % 2 else "app"
    names = [node.name for node in ast.parse(seed["code"]).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    base = re.sub(r"(?<!^)(?=[A-Z])", "_", names[0]).lower() if names else "solution"
    if base in sys.stdlib_module_names or keyword.iskeyword(base) or base in ("app", "main", "fastapi", "pytest", "test"):
        base += "_tools"
    return base


def project_files(seed):
    module = module_name(seed)
    head = f"from {module} import *\n"
    if seed["kind"] == "fastapi":
        head += f"from {module} import app\nfrom fastapi.testclient import TestClient\n\nclient = TestClient(app)\n"
    test = head + f"\n\ndef test_{module.removesuffix('_tools')}():\n" + textwrap.indent(seed["tests"], "    ") + "\n"
    return f"{module}.py", f"test_{module}.py", test


# ---------------------------------------------------------------- breaks

def enclosing_function(code, line):
    best = None
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno <= line <= node.end_lineno:
            if best is None or node.lineno > best.lineno:
                best = node
    return best.name if best else None


def compiles(code):
    try:
        compile(code, "x.py", "exec")
        return True
    except SyntaxError:
        return False


def bug_candidates(code):
    """Every one-place slip in the code, as dicts: row (1-based), broken code, kind, wrong and right text."""
    lines = code.split("\n")
    found = []

    def swap(row, start, end, new):
        line = lines[row - 1]
        broken = "\n".join(lines[:row - 1] + [line[:start] + new + line[end:]] + lines[row:])
        found.append({"row": row, "broken": broken, "kind": "swap" if new else "dropped",
                      "wrong": new, "right": line[start:end]})

    tokens = list(tokenize.generate_tokens(StringIO(code).readline))
    for position, token in enumerate(tokens):
        (row, start), (end_row, end) = token.start, token.end
        if row != end_row:
            continue
        if token.type == tokenize.OP and token.string in OP_SWAPS:
            swap(row, start, end, OP_SWAPS[token.string])
        elif token.type == tokenize.NAME and token.string in NAME_SWAPS:
            swap(row, start, end, NAME_SWAPS[token.string])
        elif token.type == tokenize.NAME and token.string == "not" and lines[row - 1][end:end + 1] == " ":
            swap(row, start, end + 1, "")
        elif token.type == tokenize.NUMBER and token.string.isdigit():
            number = int(token.string)
            before = tokens[position - 1].string if position else ""
            if number in STATUS_SWAPS and before in ("=", "("):
                swap(row, start, end, str(STATUS_SWAPS[number]))
            elif number in (0, 1, 2):
                swap(row, start, end, str(number + 1 if number == 0 else number - 1))
    for row, line in enumerate(lines, 1):
        for match in re.finditer(r"\.(strip|lower|title)\(\)", line):
            swap(row, match.start(), match.end(), "")
        if re.match(r"(import |from \S+ import )", line) and "fastapi import FastAPI" not in line:
            found.append({"row": row, "broken": "\n".join(lines[:row - 1] + lines[row:]), "kind": "import",
                          "wrong": "", "right": line})
    return [item for item in found if compiles(item["broken"])]


def unique_old(text, row):
    """The line at `row` (1-based), with lines above added until it appears once in text."""
    lines = text.split("\n")
    for extra in range(0, 4):
        old = "\n".join(lines[max(0, row - 1 - extra):row])
        if old.strip() and text.count(old) == 1:
            return old
    return None


def endpoint_of(node):
    for decorator in getattr(node, "decorator_list", []):
        if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in ROUTE_METHODS and decorator.args
                and isinstance(decorator.args[0], ast.Constant)):
            return decorator.func.attr.upper(), decorator.args[0].value
    return None


def feature_candidates(code, kind):
    """Pieces that can be taken out and asked for again: (kind, node, class name, route)."""
    tree = ast.parse(code)
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    found = []
    for node in functions:
        route = endpoint_of(node)
        if route:
            found.append(("endpoint", node, None, route))
        elif kind == "python":                 # if it is the only one, the task is to write it
            found.append(("function", node, None, None))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and kind == "python":
            methods = [item for item in node.body if isinstance(item, ast.FunctionDef)]
            found += [("method", item, node.name, None) for item in methods if not item.name.startswith("__")]
    return found


def remove_block(code, node):
    """(code without the node, the node's text, the text that came right after it or "")."""
    lines = code.rstrip("\n").split("\n")
    start = min([d.lineno for d in node.decorator_list] + [node.lineno]) - 1
    block = "\n".join(lines[start:node.end_lineno])
    before, after = lines[:start], lines[node.end_lineno:]
    while before and not before[-1].strip():
        before.pop()
    while after and not after[0].strip():
        after.pop(0)
    gap = [""] if node.col_offset else ["", ""]
    broken = before + (gap + after if after else [])
    return "\n".join(broken) + "\n", block, "\n".join(after)


def signature(node):
    return f"{node.name}({', '.join(arg.arg for arg in node.args.args)})"


# ---------------------------------------------------------------- steps

def act(tools, action, train=True):
    """Run one action through krama's real tools. Returns the two messages it adds."""
    result = getattr(tools, action["tool"])(action)
    assistant = {"role": "assistant", "content": json.dumps(action, ensure_ascii=False)}
    if not train:
        assistant["train"] = False
    return [assistant, {"role": "user", "content": clean(result)}]


def clean(text):
    """No user name from this laptop in the data: temporary paths get a neutral one."""
    # Also the doubled-\ form: pytest shows a module's repr, which writes C:\\Users\\...
    doubled = HOME.replace("\\", "\\\\")
    text = re.sub(re.escape(doubled), lambda match: "C:\\\\Users\\\\student", text, flags=re.IGNORECASE)
    text = re.sub(re.escape(HOME), lambda match: "C:\\Users\\student", text, flags=re.IGNORECASE)
    return text.replace(HOME.replace("\\", "/"), "C:/Users/student")


def corrupt(old, rng):
    """A believable copying slip that makes `old` not match."""
    if "'" in old:
        return old.replace("'", '"', 1)
    if old.rstrip().endswith(":"):
        return old.rstrip()[:-1]
    words = old.split(" ")
    spot = rng.randrange(len(words))
    return " ".join(words[:spot] + [words[spot] + "s"] + words[spot + 1:])


def make_trajectory(seed, rng, task_kind, broken, fix_action, request, code_file, test_file, test_text, thoughts):
    """Run the ideal steps on a fresh copy. Returns the row, or None if the tests do not pass at the end."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        project = Path(folder)
        (project / code_file).write_text(broken, encoding="utf-8")
        (project / test_file).write_text(test_text, encoding="utf-8")
        tools = Tools(project, sys.executable, lambda path, diff: True, lambda text: None)
        tools.last_tests = run_project_tests(project, sys.executable)
        if tools.last_tests.passed:
            return None                                  # the break did not break anything
        messages = [{"role": "system", "content": AGENT_SYSTEM},
                    {"role": "user", "content": clean(start_message(request, project, tools.last_tests))}]
        mistake = None
        if rng.random() < RECOVERY_SHARE:
            mistake = "test file" if task_kind == "bug" and rng.random() < 0.3 else "slip"
        if mistake == "test file":
            asserts = [line.strip() for line in test_text.split("\n") if line.strip().startswith("assert ") and "==" in line]
            if asserts:
                messages += act(tools, {"thought": "The test may expect the wrong value; change the test.",
                                        "tool": "replace_in_file", "path": test_file,
                                        "old": asserts[0], "new": asserts[0].replace("==", "!=", 1)}, train=False)
        if task_kind == "feature":
            messages += act(tools, {"thought": thoughts["test"], "tool": "read_file", "path": test_file})
        messages += act(tools, {"thought": thoughts["read"], "tool": "read_file", "path": code_file})
        if mistake == "slip" and fix_action["old"]:
            slip = dict(fix_action, old=corrupt(fix_action["old"], rng))
            if slip["old"] not in broken:
                messages += act(tools, slip, train=False)
                fix_action = dict(fix_action, thought="I copied a line wrongly. " + fix_action["thought"])
        messages += act(tools, fix_action)
        if not tools.last_tests.passed:
            return None
    return {"id": f"{seed['id']}-{task_kind}", "kind": seed["kind"], "task_kind": task_kind,
            "recovery": any(m.get("train") is False for m in messages), "messages": messages}


def bug_fix_action(seed, candidate, code_file):
    """The exact replace that undoes one break, or None if it cannot be made unique."""
    broken, row, right = candidate["broken"], candidate["row"], candidate["right"]
    if candidate["kind"] == "import":
        name = right.split()[-1]
        thought = f"`{name}` is used but never imported, so add `{right.strip()}`."
        if row > 1:
            old = unique_old(broken, row - 1)
            new = (old + "\n" + right) if old else None
        else:
            first = next((number for number, line in enumerate(broken.split("\n"), 1) if line.strip()), None)
            old = broken.split("\n")[first - 1] if first and broken.count(broken.split("\n")[first - 1]) == 1 else None
            new = (right + "\n" + old) if old else None
    else:
        old = unique_old(broken, row)
        original_line = seed["code"].split("\n")[row - 1]
        new = (old[:old.rfind("\n") + 1] + original_line) if old else None
        if candidate["kind"] == "dropped":
            thought = f"Line {row} is missing `{right.strip()}`, which is why the test fails."
        else:
            thought = f"Line {row} has `{candidate['wrong']}` where it needs `{right}`, which is why the test fails."
    if not old:
        return None
    return {"thought": thought, "tool": "replace_in_file", "path": code_file, "old": old, "new": new}


def bug_task(seed, rng, code_file, test_file, test_text):
    candidates = bug_candidates(seed["code"])
    rng.shuffle(candidates)
    for candidate in candidates[:6]:
        fix = bug_fix_action(seed, candidate, code_file)
        if fix is None:
            continue
        func = enclosing_function(seed["code"], candidate["row"]) or Path(code_file).stem
        request = rng.choice(BUG_REQUESTS).format(file=code_file, func=func)
        thoughts = {"read": rng.choice([f"The test fails; I will read {code_file} to find out why.",
                                        f"Read {code_file} to see what `{func}` does."])}
        row_data = make_trajectory(seed, rng, "bug", candidate["broken"], fix, request,
                                   code_file, test_file, test_text, thoughts)
        if row_data:
            return row_data
    return None


def feature_task(seed, rng, code_file, test_file, test_text):
    candidates = feature_candidates(seed["code"], seed["kind"])
    rng.shuffle(candidates)
    for kind, node, class_name, route in candidates[:3]:
        broken, block, after = remove_block(seed["code"], node)
        if not after.strip():
            old, new, where = "", block, "at the end of the file"
        else:
            broken_lines = broken.rstrip("\n").split("\n")
            first_after = len(broken_lines) - len(after.split("\n"))        # 0-based
            old = None
            for extra in range(1, 4):
                piece = "\n".join(broken_lines[first_after:first_after + extra])
                if piece.strip() and broken.count(piece) == 1:
                    old = piece
                    break
            if old is None:
                continue
            new = block + ("\n\n" if node.col_offset else "\n\n\n") + old
            where = f"just before `{old.split(chr(10))[0].strip()}`"
        if kind == "endpoint":
            request = f"Add the {route[0]} {route[1]} endpoint to {code_file}. The tests show what it should return."
            name = f"{route[0]} {route[1]}"
        elif kind == "method":
            request = f"Add a `{node.name}` method to the `{class_name}` class in {code_file}. The tests show what it should do."
            name = node.name
        else:
            request = f"Add a function `{signature(node)}` to {code_file}. The tests show what it should do."
            name = node.name
        thoughts = {"test": f"First see what the tests expect from `{name}`.",
                    "read": f"Now read {code_file} to see where `{name}` belongs."}
        fix = {"thought": f"Add `{name}` {where}.", "tool": "replace_in_file", "path": code_file, "old": old, "new": new}
        row_data = make_trajectory(seed, rng, "feature", broken, fix, request, code_file, test_file, test_text, thoughts)
        if row_data:
            return row_data
    return None


def work(seed):
    """All trajectories for one seed, and why any were not made."""
    rng = random.Random(seed["id"])
    try:
        code_file, test_file, test_text = project_files(seed)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            (Path(folder) / code_file).write_text(seed["code"], encoding="utf-8")
            (Path(folder) / test_file).write_text(test_text, encoding="utf-8")
            if not run_project_tests(Path(folder), sys.executable).passed:
                return [], ["the original fails as a project"]
        rows, notes = [], []
        for maker, label in ((bug_task, "bug"), (feature_task, "feature")):
            row = maker(seed, rng, code_file, test_file, test_text)
            if row:
                rows.append(row)
            else:
                notes.append(f"no working {label}")
        return rows, notes
    except Exception as error:                 # one odd seed must not stop the whole run
        return [], [f"could not use the code ({type(error).__name__})"]


def main():
    limit = next((int(arg.split("=")[1]) for arg in sys.argv if arg.startswith("--limit=")), None)
    codes, names = protected_projects()
    all_seeds = list(seeds())
    usable = [seed for seed in all_seeds if not too_close(seed, codes, names)]
    print(f"seeds: {len(all_seeds)}; left out as too close to a benchmark or exam project: {len(all_seeds) - len(usable)}")
    usable = usable[:limit] if limit else usable

    notes, rows = Counter(), []
    with ThreadPoolExecutor(WORKERS) as pool:
        for done, (seed_rows, seed_notes) in enumerate(pool.map(work, usable), 1):
            rows += seed_rows
            notes.update(seed_notes)
            if done % 100 == 0:
                print(f"  {done}/{len(usable)} seeds, {len(rows)} trajectories", flush=True)

    with OUT_FILE.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    kinds = Counter((row["kind"], row["task_kind"]) for row in rows)
    print(f"wrote {len(rows)} trajectories to {OUT_FILE.name}; with a recovery: {sum(r['recovery'] for r in rows)}")
    for (kind, task_kind), count in sorted(kinds.items()):
        print(f"  {kind:8} {task_kind:8} {count}")
    for note, count in notes.most_common():
        print(f"  {count:4}  {note}")


if __name__ == "__main__":
    main()
