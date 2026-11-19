"""The self-check: run the code from Krama's answer before showing it.

What "checked" means in this version: the code is valid Python and it runs
from top to bottom without an error. It does not yet prove that the code
gives the right answer.

Safety comes in layers, because no single one is enough:
    1. The user says yes before any code runs (see main.py).
    2. A look at the code without running it. Code that clearly deletes or
       writes files, starts programs or uses the network is not run. A list
       like this can always be dodged, so it is only the first filter.
    3. The code runs in a limited process: a new empty folder, none of the
       user's secret settings (environment variables), a time limit and a
       memory limit. On Windows it also cannot start other programs, and it
       is killed together with anything it started.
    4. The code is imported, not run as the main program, so a block like
           if __name__ == "__main__": uvicorn.run(app)
       does not start a server.
This is a guard, not a full sandbox: the code could still read files or use
the network in ways layer 2 does not spot.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TIME_LIMIT = 10                    # seconds
MEMORY_LIMIT = 512 * 1024 * 1024   # bytes

# Whole modules whose job is files, other programs, the network, or getting
# around these checks.
BLOCKED_MODULES = {
    "subprocess", "shutil", "socket", "ssl", "requests", "httpx", "urllib", "urllib3",
    "http", "aiohttp", "ftplib", "smtplib", "telnetlib", "ctypes", "multiprocessing",
    "webbrowser", "importlib", "builtins", "nt", "posix", "pty", "winreg", "_winapi",
    "runpy", "signal",
}
# Functions of the os module that change things outside the code.
BLOCKED_OS_FUNCTIONS = {
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "renames",
    "replace", "kill", "killpg", "startfile", "chmod", "chown", "truncate", "link",
    "symlink", "fork", "forkpty",
}
# Method names that are dangerous on any object. ("remove" and "replace" are
# missing on purpose: list.remove and str.replace are everyday code.)
BLOCKED_METHODS = {
    "system", "popen", "unlink", "rmdir", "rmtree", "removedirs", "startfile",
    "write_text", "write_bytes", "symlink_to", "hardlink_to", "chmod", "kill",
    "create_subprocess_shell", "create_subprocess_exec", "import_module",
    "execv", "execve", "execl", "execle", "execlp", "execlpe", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp",
    "spawnvpe", "posix_spawn", "posix_spawnp",
}
BLOCKED_BUILTINS = {"eval", "exec", "compile", "__import__", "breakpoint"}
# Names used to escape from checks like this one.
BLOCKED_DUNDERS = {
    "__builtins__", "__subclasses__", "__globals__", "__code__", "__closure__",
    "__mro__", "__bases__", "__import__", "__loader__",
}

# Libraries we may tell a beginner to install: import name -> pip name.
# Any other missing module may be a name Krama made up, and telling a
# beginner to install it could lead them to a fake package.
KNOWN_PACKAGES = {
    "fastapi": "fastapi", "pydantic": "pydantic", "uvicorn": "uvicorn",
    "starlette": "starlette", "httpx": "httpx", "requests": "requests",
    "multipart": "python-multipart", "jinja2": "jinja2", "sqlalchemy": "sqlalchemy",
    "flask": "flask", "django": "django", "pytest": "pytest", "numpy": "numpy",
    "pandas": "pandas", "matplotlib": "matplotlib", "scipy": "scipy",
    "sklearn": "scikit-learn", "PIL": "pillow", "bs4": "beautifulsoup4",
    "yaml": "pyyaml", "dotenv": "python-dotenv", "rich": "rich", "click": "click",
    "typer": "typer", "email_validator": "email-validator",
}

# Settings the code may see. Everything else (tokens, passwords, keys) is
# left out. APPDATA stays so Python can find libraries installed with --user.
SAFE_ENV_NAMES = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "TMPDIR",
    "APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "LANG", "LC_ALL",
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
    blocks = re.findall(r"```([a-zA-Z0-9]*)[ \t]*\n(.*?)```", answer, re.DOTALL)
    python = [code for label, code in blocks if label.lower() in ("python", "py", "python3")]
    candidates = python or [code for label, code in blocks if label == ""]
    if not candidates:
        return ""
    defining = [c for c in candidates if "def " in c or "FastAPI(" in c or "class " in c]
    return max(defining or candidates, key=len)


# ---------------------------------------------------------------- layer 2

def unsafe_reason(tree):
    """Why the code should not be run, or "" if nothing risky was spotted."""
    os_names = {"os"}          # "os" plus any other name it was imported as
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BLOCKED_MODULES:
                    return f"it uses the {top} module"
                if top == "os":
                    os_names.add((alias.asname or "os").split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top in BLOCKED_MODULES:
                return f"it uses the {top} module"
            if top == "os":
                for alias in node.names:
                    if alias.name == "*" or alias.name in BLOCKED_OS_FUNCTIONS or alias.name in BLOCKED_METHODS:
                        return f"it imports os.{alias.name}"
        elif isinstance(node, ast.Name) and node.id in BLOCKED_DUNDERS:
            return f"it uses {node.id}"
        elif isinstance(node, ast.Attribute) and node.attr in BLOCKED_DUNDERS:
            return f"it uses {node.attr}"
        elif isinstance(node, ast.Call):
            reason = unsafe_call(node, os_names)
            if reason:
                return reason
    return ""


def unsafe_call(call, os_names):
    func = call.func
    if isinstance(func, ast.Name):
        if func.id in BLOCKED_BUILTINS:
            return f"it calls {func.id}"
        if func.id == "getattr" and len(call.args) >= 2:
            name = call.args[1]
            if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
                return "it looks up a name with getattr at run time"
            if name.value in BLOCKED_BUILTINS | BLOCKED_METHODS | BLOCKED_OS_FUNCTIONS | BLOCKED_DUNDERS:
                return f"it gets {name.value} with getattr"
        if func.id == "open" and writes_file(call, mode_position=1):
            return "it writes to a file"
    elif isinstance(func, ast.Attribute):
        if func.attr in BLOCKED_METHODS:
            return f"it calls {func.attr}"
        if (func.attr in BLOCKED_OS_FUNCTIONS and isinstance(func.value, ast.Name)
                and func.value.id in os_names):
            return f"it calls os.{func.attr}"
        if func.attr == "open":
            # io.open / codecs.open take the mode second; Path(...).open takes it first.
            module_style = isinstance(func.value, ast.Name) and func.value.id in ("io", "codecs")
            if writes_file(call, mode_position=1 if module_style else 0):
                return "it writes to a file"
    return ""


def writes_file(call, mode_position):
    """True if an open(...) call opens a file for writing (or we cannot tell)."""
    mode = call.args[mode_position] if len(call.args) > mode_position else None
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode = keyword.value
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(letter in mode.value for letter in "wax+")
    return True  # the mode is worked out at run time, so play safe


# ---------------------------------------------------------------- layer 3

def clean_env():
    env = {name: value for name, value in os.environ.items() if name.upper() in SAFE_ENV_NAMES}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


_process_limit = {}   # python path -> 1 or 2, found once per run of krama


def windows_process_limit(python, options):
    """How many processes the job must allow for this Python to start.

    A virtual environment's python.exe on Windows is a small launcher that
    starts the real Python as a second process, so it needs 2. A plain
    Python needs only 1, which also stops the code from starting programs.
    """
    from krama_cli import winjob
    if python not in _process_limit:
        code, _ = winjob.run([python, "-c", "pass"], options, MEMORY_LIMIT, 1, TIME_LIMIT)
        _process_limit[python] = 1 if code == 0 else 2
    return _process_limit[python]


def _posix_limits():
    import resource
    for limit, value in ((resource.RLIMIT_AS, MEMORY_LIMIT), (resource.RLIMIT_CORE, 0)):
        try:
            resource.setrlimit(limit, (value, value))
        except (ValueError, OSError):
            pass  # macOS does not allow every limit


def run_contained(folder, python, entry="import krama_answer", args=None, timeout=None, all_output=False):
    """Run Python in `folder`, in a limited process.

    By default it runs the line `entry`, which imports krama_answer.py; `args`
    (like ["-m", "pytest", "-q"]) runs those instead. Returns (exit code, text):
    the error output, or with `all_output` everything the program printed.
    Raises subprocess.TimeoutExpired.
    """
    command = [python, *(args if args else ["-c", entry])]
    timeout = timeout or TIME_LIMIT
    options = {"cwd": folder, "stdin": subprocess.DEVNULL, "env": clean_env(),
               "stdout": subprocess.PIPE if all_output else subprocess.DEVNULL,
               "stderr": subprocess.STDOUT if all_output else subprocess.PIPE}

    if sys.platform == "win32":
        from krama_cli import winjob
        limit = windows_process_limit(python, {**options, "stdout": subprocess.DEVNULL, "stderr": subprocess.PIPE})
        code, text = winjob.run(command, options, MEMORY_LIMIT, limit, timeout)
        return code, text.decode("utf-8", errors="replace")

    process = subprocess.Popen(command, preexec_fn=_posix_limits, start_new_session=True, **options)
    try:
        output, error = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        import signal
        os.killpg(process.pid, signal.SIGKILL)   # the code and anything it started
        process.communicate()
        raise
    text = error if error is not None else (output or b"")
    return process.returncode, text.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- the check

def defines_something(code):
    """True if the code defines a function, a class or a FastAPI app.

    Code that defines nothing is a short example (like `fruits = ["apple"]`
    in a quick answer). Running it proves little, so it is not run and the
    user is not asked. Code that cannot be parsed counts as "something", so
    a broken answer still goes through the check.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return True
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return True
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            func = node.value.func
            if (isinstance(func, ast.Name) and func.id == "FastAPI") or \
                    (isinstance(func, ast.Attribute) and func.attr == "FastAPI"):
                return True
    return False


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

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        (Path(folder) / "krama_answer.py").write_text(code, encoding="utf-8")
        try:
            returncode, error = run_contained(folder, python)
        except subprocess.TimeoutExpired:
            detail = f"the code was still running after {TIME_LIMIT} seconds"
            return CheckResult("failed", detail, detail)
        except FileNotFoundError:
            return CheckResult("skipped", f"could not find the Python program '{python}'")
        except OSError as error:
            # Never run the code without its limits.
            return CheckResult("skipped", f"could not set up the safety limits ({error})")

    if returncode == 0:
        return CheckResult("passed", "the code ran without errors")

    problem = last_line(error)
    if problem.startswith("ModuleNotFoundError"):
        found = re.search(r"No module named '([^']+)'", problem)
        module = found.group(1).split(".")[0] if found else ""
        if module in KNOWN_PACKAGES:
            # A real library the user has not installed: not a mistake in the code.
            return CheckResult("skipped", f"install {KNOWN_PACKAGES[module]} to let Krama check this code")
        detail = f"{problem}. This module may not exist; the name may be made up."
        return CheckResult("failed", detail, f"{error.strip()}\n{detail}")
    if problem.startswith("EOFError"):
        return CheckResult("skipped", "the code waits for typed input, so it was not checked")
    if problem.startswith("MemoryError"):
        detail = f"the code used more than {MEMORY_LIMIT // (1024 * 1024)} MB of memory"
        return CheckResult("failed", detail, f"{error.strip()}\n{detail}")
    return CheckResult("failed", problem, error)
