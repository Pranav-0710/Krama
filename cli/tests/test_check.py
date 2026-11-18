"""Tests for the self-check. Run from the cli folder:
    uv run --with pytest pytest
"""

import sys

from krama_cli import check as check_module
from krama_cli import main
from krama_cli.check import check, extract_code

PYTHON = sys.executable


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


def test_risky_code_is_not_run():
    assert check("import os\nos.remove('notes.txt')\n", PYTHON).status == "skipped"
    assert check("import shutil\n", PYTHON).status == "skipped"
    assert check("open('out.txt', 'w').write('x')\n", PYTHON).status == "skipped"
    # Reading a file is allowed.
    assert check("def read(p):\n    return open(p).read()\n", PYTHON).status == "passed"


def test_missing_library_is_skipped_not_failed():
    result = check("import a_library_nobody_has\n", PYTHON)
    assert result.status == "skipped"
    assert "a_library_nobody_has" in result.message


def test_code_that_waits_for_typing_is_skipped():
    assert check("name = input('name? ')\n", PYTHON).status == "skipped"


def test_endless_loop_is_stopped(monkeypatch):
    monkeypatch.setattr(check_module, "TIME_LIMIT", 1)
    result = check("while True:\n    pass\n", PYTHON)
    assert result.status == "failed"
    assert "still running" in result.message


def test_server_start_under_main_guard_does_not_run():
    code = 'if __name__ == "__main__":\n    raise SystemExit("server started")\n'
    assert check(code, PYTHON).status == "passed"


def test_extract_code_prefers_the_solution_block():
    answer = (
        "Plan:\n1. Install it.\n\n```bash\npip install fastapi\n```\n\n"
        "Code:\n```python\ndef hello():\n    return 'hi'\n```\n\n"
        "Example:\n```python\nprint(hello())\n```\n"
    )
    assert extract_code(answer) == "def hello():\n    return 'hi'\n"
    assert extract_code("No code here.") == ""


def test_failed_code_is_sent_back_and_fixed(monkeypatch):
    replies = [
        "Code:\n```python\nclass Health(BaseModel):\n    status: str\n```",
        "Code:\n```python\nfrom dataclasses import dataclass\n\n@dataclass\nclass Health:\n    status: str\n```",
    ]
    sent = []

    def fake_ask(model, messages):
        sent.append(list(messages))
        return replies[len(sent) - 1]

    monkeypatch.setattr(main, "ask", fake_ask)
    answer, result = main.answer_with_check("q", "m", PYTHON, say=lambda text: None)
    assert result.status == "passed"
    assert answer == replies[1]
    # The second request carried the first answer and its error.
    assert "NameError" in sent[1][-1]["content"]
    assert sent[1][-2]["content"] == replies[0]


def test_gives_up_after_the_last_try(monkeypatch):
    broken = "```python\nprint(undefined_name)\n```"
    monkeypatch.setattr(main, "ask", lambda model, messages: broken)
    answer, result = main.answer_with_check("q", "m", PYTHON, tries=3, say=lambda text: None)
    assert result.status == "failed"
