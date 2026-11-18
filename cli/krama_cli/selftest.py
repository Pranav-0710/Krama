"""Test-based self-check: Krama writes a few tests, krama runs them.

The import check (check.py) only proves the code runs. This step asks
whether it does what the question asked:

    1. Krama writes 3 to 5 one-line tests. It sees the question and only the
       NAMES of the functions and endpoints in its answer, not their code,
       so the tests come from what was asked, not from what was written.
       The reply is forced into a fixed JSON shape, so it can always be read.
    2. Each test runs on its own, in the same limited process as the check.
    3. The result for each test is one of:
           ok        the test passed
           fail      the code gave the wrong result (with what it gave)
           error     the code crashed while being tested
           bad test  the test itself is broken (for example it calls a name
                     the code does not have), so it is left out
A small model can write a wrong test, so a failed test is reported as
"the code or the test may be wrong", never as proof.
"""

import ast
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from krama_cli.check import BLOCKED_DUNDERS, run_contained, unsafe_reason

TESTS_SCHEMA = {
    "type": "object",
    "properties": {"tests": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5}},
    "required": ["tests"],
}

TEST_REQUEST = """Write 3 to 5 short tests for this task. Test only what the task says and the examples it gives. Do not invent rules the task does not state. Do not write the solution.

Task:
{question}

The answer defines:
{interface}

Each test is one line of Python that ends with an `assert`. Every test starts from a fresh copy of the code, so if a test needs something to exist first, create it on the same line, separated by `;`.{client_note}
Reply with JSON like {{"tests": ["assert ...", "assert ..."]}}."""

CLIENT_NOTE = (" To test an endpoint, use `client`, a FastAPI TestClient for the app, for example "
               "`assert client.get(\"/path\").status_code == 200` or "
               "`client.post(\"/things\", json={...}); assert client.get(\"/things/1\").status_code == 200`.")

# Runs inside the limited process. It is krama's own code, not the model's.
HARNESS = r'''
import ast, importlib, json, traceback
results = []

def fresh_namespace():
    """A fresh copy of the code for every test, so one test's changes
    (like a counter it bumped) cannot affect the next test."""
    module = importlib.reload(krama_answer)
    namespace = dict(vars(module))
    if "app" in namespace:
        from fastapi.testclient import TestClient
        namespace["client"] = TestClient(namespace["app"])
    return namespace

try:
    import krama_answer
    fresh_namespace()
    ready = True
except Exception as error:
    results = [{"status": "error", "detail": f"{type(error).__name__}: {error}"}]
    ready = False

def describe(value):
    text = repr(value)
    return text if len(text) <= 200 else text[:200] + "..."

if ready:
    for source in json.load(open("krama_tests.json", encoding="utf-8")):
        namespace = fresh_namespace()
        try:
            exec(compile(source, "<test>", "exec"), dict(namespace))
            results.append({"status": "ok"})
        except AssertionError:
            detail = ""
            try:                                   # say what the code gave
                body = ast.parse(source).body
                last = body[-1]
                if isinstance(last, ast.Assert) and isinstance(last.test, ast.Compare):
                    again = dict(fresh_namespace())
                    exec(compile(ast.Module(body[:-1], []), "<test>", "exec"), again)   # the set-up part
                    got = eval(compile(ast.Expression(last.test.left), "<test>", "eval"), again)
                    detail = "got " + describe(got)
            except Exception:
                pass
            results.append({"status": "fail", "detail": detail})
        except Exception as error:
            frames = traceback.extract_tb(error.__traceback__)
            in_code = any(frame.filename.endswith("krama_answer.py") for frame in frames)
            detail = f"{type(error).__name__}: {error}"
            if not in_code and isinstance(error, (NameError, SyntaxError, TypeError, AttributeError, ImportError)):
                results.append({"status": "bad test", "detail": detail})
            else:
                results.append({"status": "error", "detail": detail})

json.dump(results, open("krama_results.json", "w", encoding="utf-8"))
'''


@dataclass
class TestReport:
    status: str                       # "passed", "failed" or "skipped"
    message: str                      # one line for the user
    tests: list = field(default_factory=list)     # (test, status, detail) for every test kept
    feedback: str = ""                # what to send Krama so it can fix the code
    passed: int = 0                   # how many of the kept tests passed
    source: list = field(default_factory=list)    # the test lines, to rerun them on a fix


def interface(code):
    """The names in the code that tests may use: functions and endpoints."""
    lines = []
    for node in ast.parse(code).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            routes = [decorator for decorator in node.decorator_list
                      if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                      and decorator.func.attr in ("get", "post", "put", "patch", "delete")
                      and decorator.args and isinstance(decorator.args[0], ast.Constant)]
            if routes:
                for route in routes:
                    lines.append(f"- endpoint {route.func.attr.upper()} {route.args[0].value}")
            else:
                lines.append(f"- function {node.name}({', '.join(arg.arg for arg in node.args.args)})")
        elif isinstance(node, ast.ClassDef):
            lines.append(f"- class {node.name}")
    return "\n".join(lines)


def is_endpoint_code(code):
    return "FastAPI(" in code


HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def routes(code):
    """[(method, path pattern)] for every endpoint in the code."""
    found = []
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr in HTTP_METHODS and decorator.args
                        and isinstance(decorator.args[0], ast.Constant)):
                    path = str(decorator.args[0].value).rstrip("/") or "/"
                    pattern = "^" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(path)) + "/?$"
                    found.append((decorator.func.attr, pattern))
    return found


def calls_missing_endpoint(tree, known):
    """True if a test calls client.<method>(path) for an endpoint the code does not have."""
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "client"
                and node.func.attr in HTTP_METHODS):
            if not (node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                return True
            path = node.args[0].value.split("?")[0]
            if not any(method == node.func.attr and re.match(pattern, path) for method, pattern in known):
                return True
    return False


def write_tests(question, code, backend):
    """Ask Krama for tests. Returns a list of test lines (possibly empty)."""
    from krama_cli.main import KRAMA_SYSTEM
    names = interface(code)
    if not names:
        return []
    prompt = TEST_REQUEST.format(question=question, interface=names,
                                 client_note=CLIENT_NOTE if is_endpoint_code(code) else "")
    reply = backend.chat([{"role": "system", "content": KRAMA_SYSTEM},
                          {"role": "user", "content": prompt}], schema=TESTS_SCHEMA)
    try:
        tests = json.loads(reply)["tests"]
    except (ValueError, KeyError, TypeError):
        return []
    kept = []
    known = routes(code)
    for test in tests if isinstance(tests, list) else []:
        test = str(test).strip()
        try:
            tree = ast.parse(test)
        except SyntaxError:
            continue
        steps = tree.body
        if (steps and len(steps) <= 4 and isinstance(steps[-1], ast.Assert)
                and all(isinstance(step, (ast.Expr, ast.Assign, ast.Assert)) for step in steps)
                and not unsafe_reason(tree) and not any(name in test for name in BLOCKED_DUNDERS)
                and not calls_missing_endpoint(tree, known)):
            kept.append(test)
    return kept


def run_tests(code, tests, python):
    """Run each test against the code in the limited process. Returns result dicts."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        (Path(folder) / "krama_answer.py").write_text(code, encoding="utf-8")
        (Path(folder) / "krama_tests.json").write_text(json.dumps(tests), encoding="utf-8")
        (Path(folder) / "krama_harness.py").write_text(HARNESS, encoding="utf-8")
        returncode, error = run_contained(folder, python, entry="import krama_harness")
        try:
            return json.loads((Path(folder) / "krama_results.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last = (error.strip().splitlines() or ["the tests did not finish"])[-1]
            return [{"status": "error", "detail": last}]


def self_test(question, code, backend, python):
    """Write tests, run them, and sum up. Never raises for a model mistake."""
    tests = write_tests(question, code, backend)
    if not tests:
        return TestReport("skipped", "Krama wrote no usable tests")
    return evaluate(code, tests, python)


def evaluate(code, tests, python):
    """Run the given tests against the code and sum up (also used to judge a fix)."""
    results = run_tests(code, tests, python)
    if len(results) != len(tests):
        detail = results[0]["detail"] if results else "unknown problem"
        if "No module named 'httpx'" in detail:
            return TestReport("skipped", "install httpx to let Krama test endpoints")
        return TestReport("skipped", f"the tests could not run ({detail})")

    kept = [(test, result["status"], result.get("detail", ""))
            for test, result in zip(tests, results) if result["status"] != "bad test"]
    if not kept:
        return TestReport("skipped", "Krama's tests did not match its own code")
    problems = [(test, status, detail) for test, status, detail in kept if status != "ok"]
    if not problems:
        return TestReport("passed", f"{len(kept)} of Krama's own tests passed", kept, passed=len(kept), source=tests)
    lines = [f"`{test}` failed" + (f": {detail}" if detail else "") for test, _, detail in problems]
    feedback = "I tested your code and these tests failed:\n" + "\n".join(f"- {line}" for line in lines)
    summary = f"{len(problems)} of {len(kept)} of Krama's own tests failed"
    # A crash while testing is strong evidence. One failed assert on its own is
    # weak: a small model's test can simply be wrong. So it is only a warning.
    crashed = any(status == "error" for _, status, _ in problems)
    passed = len(kept) - len(problems)
    if crashed or len(problems) >= 2:
        return TestReport("failed", summary + " (the code or the tests may be wrong)", kept, feedback, passed, tests)
    return TestReport("warning", summary + " (that test may be wrong; check it yourself)", kept, feedback, passed, tests)
