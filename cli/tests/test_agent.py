"""Tests for the guided agent (agent.py), with a scripted fake model.
Needs pytest in the Python that runs them (it runs the projects' tests too)."""

import json
import sys

import pytest

from krama_cli.agent import list_files, run_agent

PYTHON = sys.executable
BUGGY = {"calc.py": "def add(a, b):\n    return a - b\n",
         "test_calc.py": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"}


class ScriptedModel:
    """Gives the actions it was handed, in order, then finishes."""

    def __init__(self, *actions):
        self.actions = [a if isinstance(a, str) else json.dumps(a) for a in actions]
        self.seen = []

    def chat(self, messages, schema=None):
        self.seen.append(messages[-1]["content"])
        if self.actions:
            return self.actions.pop(0)
        return json.dumps({"thought": "done", "tool": "finish", "summary": "no more actions"})


@pytest.fixture
def project(tmp_path):
    for path, text in BUGGY.items():
        (tmp_path / path).write_text(text, encoding="utf-8")
    return tmp_path


def fix_action(path="calc.py", old="return a - b", new="return a + b"):
    return {"thought": "fix", "tool": "replace_in_file", "path": path, "old": old, "new": new}


def yes(path, diff):
    return True


def test_a_good_fix_solves_it_and_keeps_a_backup(project):
    model = ScriptedModel({"thought": "look", "tool": "read_file", "path": "calc.py"}, fix_action())
    result = run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert result.status == "solved"
    assert (project / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    backups = list((project / ".krama" / "backups").rglob("calc.py"))
    assert backups and backups[0].read_text() == BUGGY["calc.py"]
    assert "   2 |     return a - b" in model.seen[1]          # the file was shown with line numbers


def test_no_means_no(project):
    asked = []
    result = run_agent("fix it", project, ScriptedModel(fix_action()), PYTHON,
                       lambda path, diff: asked.append(diff) or False, say=lambda text: None)
    assert asked and "-    return a - b" in asked[0] and "+    return a + b" in asked[0]
    assert (project / "calc.py").read_text() == BUGGY["calc.py"]
    assert result.status != "solved" and result.edits == []


def test_test_files_cannot_be_changed(project):
    model = ScriptedModel(fix_action("test_calc.py", "== 5", "== -1"))
    run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert (project / "test_calc.py").read_text() == BUGGY["test_calc.py"]
    assert "Test files cannot be changed" in model.seen[1]


def test_files_outside_the_project_are_refused(project, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "secret.py"
    outside.write_text("SECRET = 1\n")
    model = ScriptedModel({"thought": "peek", "tool": "read_file", "path": str(outside)},
                          {"thought": "peek", "tool": "read_file", "path": "../" + outside.parent.name + "/secret.py"},
                          {"thought": "make", "tool": "create_file", "path": "../evil.py", "new": "x = 1\n"})
    run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert all("SECRET" not in seen for seen in model.seen)
    assert not (project.parent / "evil.py").exists()


def test_wrong_old_text_is_explained(project):
    model = ScriptedModel(fix_action(old="return a * b"))
    run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert "is not in calc.py" in model.seen[1]


def test_a_skipped_line_is_pointed_out():
    from krama_cli.agent import why_not_found
    text = "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n"
    # What the 7B really sent: the decorator and the return, without the def between them.
    hint = why_not_found(text, "@app.get('/items')\n    return ITEMS")
    assert "not one after the other" in hint
    assert "Lines 6 to 8 are exactly:\n@app.get('/items')\ndef list_items():\n    return ITEMS\n" in hint


def test_a_changed_line_is_named():
    from krama_cli.agent import why_not_found
    hint = why_not_found("def add(a, b):\n    return a - b\n", "def add(a, b):\n    return a * b")
    assert "return a * b" in hint and "def add" not in hint


def test_right_lines_with_wrong_indentation_still_apply(tmp_path):
    from krama_cli.agent import tolerant_replace
    text = "@app.get('/helo')\ndef hello():\n    return {'message': 'hello'}\n"
    # What a 7B model really sent: 4 extra spaces on every line after the first.
    old = "@app.get('/helo')\n    def hello():\n        return {'message': 'hello'}"
    new = "@app.get('/hello')\n    def hello():\n        return {'message': 'hello'}"
    assert tolerant_replace(text, old, new) == "@app.get('/hello')\ndef hello():\n    return {'message': 'hello'}\n"


def test_tolerant_replace_keeps_the_relative_indentation_of_new_lines():
    from krama_cli.agent import tolerant_replace
    text = "class A:\n    def go(self, n):\n        self.n -= n\n        return self.n\n"
    old = "def go(self, n):\n    self.n -= n"                       # copied with 4 spaces too few
    new = "def go(self, n):\n    if n > self.n:\n        raise ValueError\n    self.n -= n"
    assert tolerant_replace(text, old, new) == (
        "class A:\n    def go(self, n):\n        if n > self.n:\n            raise ValueError\n"
        "        self.n -= n\n        return self.n\n")


def test_tolerant_replace_refuses_when_unsure():
    from krama_cli.agent import tolerant_replace
    text = "x = 1\nx = 1\n"
    assert tolerant_replace(text, "  x = 1", "x = 2") is None          # two places match
    assert tolerant_replace(text, "y = 1", "y = 2") is None            # no place matches


def test_the_same_failed_change_is_not_retried(project):
    wrong = fix_action(old="return a * b")
    model = ScriptedModel(wrong, wrong)
    run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert "already tried exactly this" in model.seen[2]


def test_empty_old_adds_new_code_at_the_end(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_calc.py").write_text("from calc import multiply\n\ndef test_m():\n    assert multiply(2, 3) == 6\n")
    # What the 7B really sent to add a function: an empty `old`.
    model = ScriptedModel(fix_action(old="", new="def multiply(a, b):\n    return a * b"))
    result = run_agent("add multiply", tmp_path, model, PYTHON, yes, say=lambda text: None)
    assert result.status == "solved"
    assert (tmp_path / "calc.py").read_text() == "def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n"


def test_empty_old_in_an_empty_file_gives_just_the_new_code(tmp_path):
    (tmp_path / "calc.py").write_text("")
    (tmp_path / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    model = ScriptedModel(fix_action(old="", new="def add(a, b):\n    return a + b"))
    assert run_agent("write add", tmp_path, model, PYTHON, yes, say=lambda text: None).status == "solved"
    assert (tmp_path / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"


def test_library_steps_are_hidden_from_test_output():
    from krama_cli.agent import hide_library_frames
    lines = ["test_app.py:9: in test_get",
             "    r = client.get('/items/1')",
             r"..\uv\Lib\site-packages\starlette\routing.py:289: in handle",
             "    await self.app(scope, receive, send)",
             "           ^^^^^^^^^^^^^^^^^^^^^^",
             r"C:\Python312\Lib\contextlib.py:618: in close",
             "    self.__exit__(None, None, None)",
             "/usr/lib/python3/site-packages/fastapi/routing.py:175: in app",
             "    await wrap(app)",
             "app.py:12: in get_item",
             "    return ITEMS[item_id]",
             "E   KeyError: 1"]
    assert hide_library_frames(lines) == ["test_app.py:9: in test_get", "    r = client.get('/items/1')",
                                          "(3 steps outside the project hidden)",
                                          "app.py:12: in get_item", "    return ITEMS[item_id]", "E   KeyError: 1"]


def test_reading_an_unchanged_file_again_is_refused(project):
    read = {"thought": "look", "tool": "read_file", "path": "calc.py"}
    model = ScriptedModel(read, read)
    run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert "return a - b" in model.seen[1]
    assert "has not changed" in model.seen[2] and "return a - b" not in model.seen[2]


def test_an_unreadable_reply_is_survived(project):
    model = ScriptedModel("this is not json", fix_action())
    result = run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None)
    assert result.status == "solved"
    assert "unreadable reply" in result.log[0]


def test_finishing_while_tests_fail_is_giving_up(project):
    result = run_agent("fix it", project, ScriptedModel(), PYTHON, yes, say=lambda text: None)
    assert result.status == "gave up"


def test_the_step_limit_stops_it(project):
    model = ScriptedModel(*[{"thought": "again", "tool": "run_tests"}] * 5)
    result = run_agent("fix it", project, model, PYTHON, yes, say=lambda text: None, max_steps=3)
    assert result.status == "stopped" and result.steps == 3


def test_the_file_list_skips_krama_and_cache_folders(project):
    (project / ".krama").mkdir()
    (project / ".krama" / "x.py").write_text("")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "y.py").write_text("")
    assert list_files(project) == ["calc.py", "test_calc.py"]
