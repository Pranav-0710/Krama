"""The self-check: run the code from Krama's answer before showing it.

What "checked" means in this first version: the code is valid Python and it
runs from top to bottom without an error. It does not yet prove that the code
gives the right answer.

How it runs the code:
    1. A safety look (no running yet). Code that deletes files, starts other
       programs or uses the network is NOT run. This is a simple guard, not a
       real sandbox, so it only covers the obvious cases.
    2. The code is saved in a new empty folder and imported by a separate
       Python process, with a time limit. Importing (instead of running it as
       the main program) means a block like
           if __name__ == "__main__": uvicorn.run(app)
       does not start a server.
"""

import ast
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

TIME_LIMIT = 10  # seconds

# Modules whose whole job is files, other programs or the network.
BLOCKED_MODULES = {
    "subprocess", "shutil", "socket", "requests", "httpx", "urllib", "http",
    "ftplib", "smtplib", "ctypes", "multiprocessing", "webbrowser",
}
# Single functions of "os" that change things outside the code.
BLOCKED_OS_CALLS = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename",
    "replace", "kill", "startfile", "chmod", "truncate",
}


@dataclass
class CheckResult:
    status: str        # "passed", "failed" or "skipped"
    message: str       # one line for the user
    error: str = ""    # the full error, for the model to fix


def extract_code(answer):
    """The solution code from an answer, or "" if it has none.

    Answers can hold several blocks (install commands, example output), so
    prefer Python blocks, then blocks that define something, then the longest.
    """
    blocks = re.findall(r"```([a-zA-Z]*)[ \t]*\n(.*?)```", answer, re.DOTALL)
    python = [code for label, code in blocks if label.lower() in ("python", "py")]
    candidates = python or [code for label, code in blocks if label == ""]
    if not candidates:
        return ""
    defining = [c for c in candidates if "def " in c or "FastAPI(" in c or "class " in c]
    return max(defining or candidates, key=len)


def unsafe_reason(tree):
    """Why the code should not be run, or "" if it looks safe to run."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            names = []
        for name in names:
            if name.split(".")[0] in BLOCKED_MODULES:
                return f"it uses the {name.split('.')[0]} module"

        if isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr in BLOCKED_OS_CALLS
                    and isinstance(func.value, ast.Name) and func.value.id == "os"):
                return f"it calls os.{func.attr}"
            if isinstance(func, ast.Name) and func.id in ("eval", "exec", "__import__"):
                return f"it calls {func.id}"
            if isinstance(func, ast.Name) and func.id == "open" and writes_file(node):
                return "it writes to a file"
    return ""


def writes_file(call):
    """True if an open(...) call opens a file for writing."""
    mode = call.args[1] if len(call.args) > 1 else None
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode = keyword.value
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(letter in mode.value for letter in "wax+")
    return True  # the mode is worked out at run time, so play safe


def last_line(error):
    lines = [line for line in error.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"


def check(code, python="python"):
    """Check one piece of code. `python` is the Python program that runs it."""
    if not code.strip():
        return CheckResult("skipped", "no code to check")

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        detail = f"SyntaxError: {error.msg} (line {error.lineno})"
        return CheckResult("failed", detail, detail)

    reason = unsafe_reason(tree)
    if reason:
        return CheckResult("skipped", f"not run, because {reason}")

    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "krama_answer.py").write_text(code, encoding="utf-8")
        try:
            finished = subprocess.run(
                [python, "-c", "import krama_answer"],
                cwd=folder,
                stdin=subprocess.DEVNULL,   # code that waits for typing gets EOFError
                capture_output=True,
                text=True,
                timeout=TIME_LIMIT,
            )
        except subprocess.TimeoutExpired:
            detail = f"the code was still running after {TIME_LIMIT} seconds"
            return CheckResult("failed", detail, detail)
        except FileNotFoundError:
            return CheckResult("skipped", f"could not find the Python program '{python}'")

    if finished.returncode == 0:
        return CheckResult("passed", "the code ran without errors")

    error = finished.stderr
    problem = last_line(error)
    if problem.startswith("ModuleNotFoundError"):
        # Usually a library the user has not installed (like fastapi), not a
        # mistake in the code, so asking Krama to "fix" it would not help.
        module = re.search(r"No module named '([^']+)'", problem)
        name = module.group(1) if module else "a module"
        return CheckResult("skipped", f"install {name} to let Krama check this code")
    if problem.startswith("EOFError"):
        return CheckResult("skipped", "the code waits for typed input, so it was not checked")
    return CheckResult("failed", problem, error)
