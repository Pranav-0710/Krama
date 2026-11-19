"""Tests for the self-check. Run from the cli folder:
    uv run --with pytest pytest
"""

import ast
import sys
import tempfile
from pathlib import Path

import pytest

from krama_cli import check as check_module
from krama_cli import main
from krama_cli.check import check, extract_code, run_contained, unsafe_reason

PYTHON = sys.executable


def blocked(code):
    return unsafe_reason(ast.parse(code)) != ""


def run_unguarded(code):
    """Run code in the limited process WITHOUT the layer-2 look, to test layer 3 alone."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        (Path(folder) / "krama_answer.py").write_text(code, encoding="utf-8")
        return run_contained(folder, PYTHON)


# ------------------------------------------------------------ basic results

def test_good_code_passes():
    assert check("def add(a, b):\n    return a + b\n", PYTHON).status == "passed"


def test_missing_import_fails_with_the_error():
    # The mistake Krama made on the api-health task: BaseModel used, never imported.
    result = check("class Health(BaseModel):\n    status: str\n", PYTHON)
    assert result.status == "failed"
    assert "NameError" in result.message


def test_syntax_error_fails_without_running():
    result = check("def broken(:\n    pass\n", PYTHON)
    assert result.status == "failed"
    assert "SyntaxError" in result.message


def test_code_that_waits_for_typing_is_skipped():
    assert check("name = input('name? ')\n", PYTHON).status == "skipped"


def test_endless_loop_is_stopped(monkeypatch):
    monkeypatch.setattr(check_module, "TIME_LIMIT", 2)
    result = check("while True:\n    pass\n", PYTHON)
    assert result.status == "failed"
    assert "still running" in result.message


def test_server_start_under_main_guard_does_not_run():
    code = 'if __name__ == "__main__":\n    raise SystemExit("server started")\n'
    assert check(code, PYTHON).status == "passed"


# ------------------------------------------------------------ missing modules

def test_known_missing_library_says_install():
    # "dotenv" is on the known list; it is not installed in the test environment.
    result = check("import dotenv\n", PYTHON)
    assert result.status == "skipped"
    assert "python-dotenv" in result.message


def test_unknown_missing_module_is_a_mistake_not_an_install():
    result = check("import pydantics\n", PYTHON)
    assert result.status == "failed"
    assert "made up" in result.message
    assert "install" not in result.message


# ------------------------------------------------------------ layer 2: the look

RISKY = {
    "os alias": "import os as o\no.system('dir')",
    "from os import": "from os import remove\nremove('f')",
    "from os import star": "from os import *",
    "pathlib unlink": "from pathlib import Path\nPath('f').unlink()",
    "pathlib write": "from pathlib import Path\nPath('f').write_text('x')",
    "pathlib open write": "from pathlib import Path\nPath('f').open('w')",
    "importlib": "import importlib\nimportlib.import_module('sub' + 'process')",
    "getattr string": "import builtins\ngetattr(builtins, 'exec')('1')",
    "getattr builtins dict": "getattr(__builtins__, 'ev' + 'al')",
    "getattr dynamic": "name = 'sys' + 'tem'\nimport os\ngetattr(os, name)('dir')",
    "os execv": "import os\nos.execv('a', ['a'])",
    "os spawn": "import os\nos.spawnl(0, 'a')",
    "io open write": "import io\nio.open('f', 'w')",
    "open write keyword": "open('f', mode='a')",
    "open mode at run time": "m = 'w'\nopen('f', m)",
    "urllib3": "import urllib3",
    "asyncio subprocess": "import asyncio\nasyncio.create_subprocess_shell('dir')",
    "shutil": "import shutil\nshutil.rmtree('x')",
    "subprocess from": "from subprocess import run",
    "socket": "import socket",
    "ctypes": "import ctypes",
    "eval": "eval('1+1')",
    "dunder escape": "().__class__.__mro__[1].__subclasses__()",
    "sys modules": "import sys\nsys.modules['os'].system('dir')",
}


@pytest.mark.parametrize("name", RISKY)
def test_risky_code_is_not_run(name):
    assert blocked(RISKY[name]), name


EVERYDAY = {
    "list remove": "items = [1, 2]\nitems.remove(1)",
    "str replace": "'a-b'.replace('-', '_')",
    "read a file": "def read(p):\n    return open(p).read()",
    "read with mode r": "def read(p):\n    with open(p, 'r') as f:\n        return f.read()",
    "os.path": "import os\nos.path.join('a', 'b')",
    "getattr on own object": "class A:\n    x = 1\ngetattr(A, 'x')",
    "class with init": "class A:\n    def __init__(self):\n        self.n = __name__",
    "sqlite execute": "import sqlite3\ndb = sqlite3.connect(':memory:')\ndb.execute('select 1')",
    "fastapi app": "from fastapi import FastAPI\napp = FastAPI()",
}


@pytest.mark.parametrize("name", EVERYDAY)
def test_everyday_code_is_allowed(name):
    assert not blocked(EVERYDAY[name]), name


# ------------------------------------------------------------ layer 3: the limits

def test_secrets_in_environment_are_hidden(monkeypatch):
    monkeypatch.setenv("KRAMA_TEST_SECRET", "hf_not_a_real_token")
    code = "import os\nassert 'KRAMA_TEST_SECRET' not in os.environ, 'secret leaked'\n"
    returncode, error = run_unguarded(code)
    assert returncode == 0, error


def test_memory_limit_stops_huge_memory_use():
    returncode, error = run_unguarded("data = bytearray(2 * 1024 ** 3)\n")
    assert returncode != 0
    assert "MemoryError" in error


@pytest.mark.skipif(sys.platform != "win32", reason="the process limit uses Windows job objects")
def test_code_cannot_start_programs_on_windows():
    # This skips layer 2 on purpose, to show layer 3 holds on its own.
    code = "import subprocess, sys\nsubprocess.run([sys.executable, '-c', 'pass'], check=True)\n"
    returncode, error = run_unguarded(code)
    assert returncode != 0, "a program was started from inside the limited process"


# ------------------------------------------------------------ extracting code

def test_extract_code_prefers_the_solution_block():
    answer = (
        "Plan:\n1. Install it.\n\n```bash\npip install fastapi\n```\n\n"
        "Code:\n```python\ndef hello():\n    return 'hi'\n```\n\n"
        "Example:\n```python\nprint(hello())\n```\n"
    )
    assert extract_code(answer) == "def hello():\n    return 'hi'\n"
    assert extract_code("No code here.") == ""
    assert extract_code("```python3\nx = 1\n```") == "x = 1\n"


# ------------------------------------------------------------ the fix loop

class FakeBackend:
    """Gives the replies it was handed, in order, and remembers what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.sent = []

    def chat(self, messages, schema=None):
        self.sent.append(list(messages))
        return self.replies[min(len(self.sent), len(self.replies)) - 1]


def test_failed_code_is_sent_back_and_fixed():
    broken = "Code:\n```python\nclass Health(BaseModel):\n    status: str\n```"
    fixed = "Code:\n```python\nfrom dataclasses import dataclass\n\n@dataclass\nclass Health:\n    status: str\n```"
    backend = FakeBackend(broken, fixed)
    answer, result, _ = main.answer_with_check("q", backend, PYTHON, approve=lambda: True, say=lambda text: None, use_tests=False)
    assert result.status == "passed"
    assert answer == fixed
    # The second request carried the first answer and its error.
    assert "NameError" in backend.sent[1][-1]["content"]
    assert backend.sent[1][-2]["content"] == broken


def test_every_conversation_starts_with_kramas_system_line():
    backend = FakeBackend("A short answer.")
    main.answer_with_check("what is a list?", backend, PYTHON, approve=lambda: True, say=lambda text: None, use_tests=False)
    first = backend.sent[0]
    assert first[0] == {"role": "system", "content": main.KRAMA_SYSTEM}
    assert first[1] == {"role": "user", "content": "what is a list?"}


def test_gives_up_after_the_last_try():
    backend = FakeBackend("```python\ndef show():\n    pass\n\nprint(undefined_name)\n```")
    answer, result, _ = main.answer_with_check("q", backend, PYTHON, approve=lambda: True,
                                               tries=3, say=lambda text: None, use_tests=False)
    assert result.status == "failed"
    assert len(backend.sent) == 3


def test_a_short_example_is_not_run_and_nobody_is_asked(monkeypatch):
    monkeypatch.setattr(main, "check", lambda code, python: pytest.fail("example was run"))
    backend = FakeBackend("A list holds items in order:\n```python\nfruits = ['apple', 'banana']\n```")
    answer, result, report = main.answer_with_check("what is a list?", backend, PYTHON,
                                                    approve=lambda: pytest.fail("user was asked"),
                                                    say=lambda text: None)
    assert result.status == "skipped" and "example" in result.message
    assert report is None


@pytest.mark.parametrize("code, defines", [
    ("fruits = ['apple']\nprint(fruits)", False),
    ("x = 1 + 1", False),
    ("def largest(numbers):\n    return max(numbers)", True),
    ("class Stack:\n    pass", True),
    ("from fastapi import FastAPI\napp = FastAPI()", True),
    ("import fastapi\napp = fastapi.FastAPI()", True),
    ("def broken(:", True),            # broken code still goes through the check
])
def test_what_counts_as_defining_something(code, defines):
    assert check_module.defines_something(code) is defines


def test_nothing_runs_without_the_users_ok(monkeypatch):
    monkeypatch.setattr(main, "check", lambda code, python: pytest.fail("code was run"))
    backend = FakeBackend("```python\ndef one():\n    return 1\n```")
    answer, result, _ = main.answer_with_check("q", backend, PYTHON, approve=lambda: False, say=lambda text: None)
    assert result.status == "skipped"
    assert "needs your OK" in result.message
