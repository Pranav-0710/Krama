"""Tests for the test-based self-check (selftest.py) and its place in the fix loop.
Endpoint tests need fastapi and httpx:
    uv run --with pytest --with fastapi --with httpx pytest
"""

import json
import sys

from krama_cli import main
from krama_cli.selftest import evaluate, self_test, write_tests

PYTHON = sys.executable

SNAKE_WRONG = "def to_snake(name):\n    return name.lower()\n"
SNAKE_RIGHT = ("import re\n\ndef to_snake(name):\n"
               "    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()\n")
SNAKE_TESTS = ["assert to_snake('HelloWorld') == 'hello_world'",
               "assert to_snake('helloWorld') == 'hello_world'",
               "assert to_snake('abc') == 'abc'"]

COUNTER = ("from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI()\ncounter = {'value': 0}\n\n"
           "class Value(BaseModel):\n    value: int\n\n"
           "@app.get('/counter')\ndef read():\n    return counter\n\n"
           "@app.put('/counter')\ndef write(body: Value):\n    counter['value'] = body.value\n    return counter\n")


class FakeBackend:
    """Replies with code for normal requests and with `tests` for test requests."""

    def __init__(self, answers, tests):
        self.answers = list(answers)
        self.tests = tests
        self.code_requests = 0

    def chat(self, messages, schema=None):
        if schema is not None:
            return json.dumps({"tests": self.tests})
        self.code_requests += 1
        return self.answers[min(self.code_requests, len(self.answers)) - 1]


def fenced(code):
    return f"Plan:\n1. Do it.\n\nCode:\n```python\n{code}```\n\nWhy:\n- Because."


def test_correct_code_passes_its_tests():
    report = evaluate(SNAKE_RIGHT, SNAKE_TESTS, PYTHON)
    assert report.status == "passed"
    assert report.passed == 3


def test_wrong_code_fails_and_says_what_it_gave():
    report = evaluate(SNAKE_WRONG, SNAKE_TESTS, PYTHON)
    assert report.status == "failed"
    assert "got 'helloworld'" in report.feedback


def test_one_failed_test_is_only_a_warning():
    tests = ["assert to_snake('abc') == 'abc'", "assert to_snake('X') == 'nonsense'"]
    assert evaluate(SNAKE_RIGHT, tests, PYTHON).status == "warning"


def test_a_crash_while_testing_counts_as_failed():
    code = "def half(n):\n    return n / 0\n"
    report = evaluate(code, ["assert half(4) == 2"], PYTHON)
    assert report.status == "failed"
    assert "ZeroDivisionError" in report.feedback


def test_a_test_that_calls_a_missing_name_is_left_out():
    tests = ["assert to_snake('abc') == 'abc'", "assert snake_case('abc') == 'abc'"]
    report = evaluate(SNAKE_RIGHT, tests, PYTHON)
    assert report.status == "passed"
    assert len(report.tests) == 1


def test_every_test_gets_a_fresh_copy_of_the_code():
    tests = ["assert client.put('/counter', json={'value': 7}).json() == {'value': 7}",
             "assert client.get('/counter').json() == {'value': 0}"]
    assert evaluate(COUNTER, tests, PYTHON).status == "passed"


def test_a_test_can_set_things_up_first():
    tests = ["client.put('/counter', json={'value': 3}); assert client.get('/counter').json() == {'value': 3}"]
    assert evaluate(COUNTER, tests, PYTHON).status == "passed"


def test_write_tests_drops_unsafe_broken_and_wrong_endpoint_tests():
    backend = FakeBackend([], [
        "assert client.get('/counter').status_code == 200",     # kept
        "assert client.get('/users/1').status_code == 200",     # no such endpoint
        "assert client.post('/counter').status_code == 200",    # no POST endpoint
        "import os; assert os.system('dir') == 0",               # risky
        "assert (",                                              # broken
        "print('no assert here')",                               # not a test
    ])
    assert write_tests("a counter app", COUNTER, backend) == ["assert client.get('/counter').status_code == 200"]


def test_self_test_with_no_usable_tests_is_skipped():
    backend = FakeBackend([], ["not python ("])
    assert self_test("q", SNAKE_RIGHT, backend, PYTHON).status == "skipped"


def test_failing_tests_lead_to_a_better_fix():
    backend = FakeBackend([fenced(SNAKE_WRONG), fenced(SNAKE_RIGHT)], SNAKE_TESTS)
    answer, result, report = main.answer_with_check("snake case", backend, PYTHON, approve=lambda: True,
                                                    say=lambda text: None)
    assert result.status == "passed"
    assert report.status == "passed"
    assert SNAKE_RIGHT.strip() in answer


def test_a_fix_that_is_not_better_is_thrown_away():
    worse = "def to_snake(name):\n    return ''\n"
    backend = FakeBackend([fenced(SNAKE_WRONG), fenced(worse)], SNAKE_TESTS)
    notes = []
    answer, result, report = main.answer_with_check("snake case", backend, PYTHON, approve=lambda: True,
                                                    say=notes.append)
    assert SNAKE_WRONG.strip() in answer             # the earlier answer was kept
    assert report.status == "failed"                 # and the user is told its tests failed
    assert any("kept the earlier answer" in note for note in notes)


def test_tests_can_be_turned_off():
    backend = FakeBackend([fenced(SNAKE_WRONG)], SNAKE_TESTS)
    answer, result, report = main.answer_with_check("q", backend, PYTHON, approve=lambda: True,
                                                    say=lambda text: None, use_tests=False)
    assert report is None
    assert backend.code_requests == 1
