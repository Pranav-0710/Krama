"""The guided agent: `krama fix` makes a project's tests pass.

"Guided" means krama, not the model, runs the steps:
    1. krama lists the files and runs the tests, and shows Krama the results.
    2. Each turn, Krama picks ONE small action. Its reply is forced into a
       fixed JSON shape (a schema), so it can always be read:
           read_file        look at a file
           replace_in_file  change one exact piece of text in a file
           create_file      add a new file
           run_tests        run the tests again
           finish           stop and say why
    3. After every change, krama runs the tests itself. When they all pass,
       the job is done.

Safety:
    - Every change is shown to you as a diff and needs your yes (default: no).
    - A copy of each file is saved in .krama/backups/ before it is changed.
    - Test files can never be changed, so "fix the tests" is not possible.
    - Files outside the project folder can never be read or changed.
    - Tests run on a copy of the project, in the same limited process as the
      self-check (no secrets, time and memory limits).
"""

import difflib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from krama_cli.check import run_contained

TOOLS = ["read_file", "replace_in_file", "create_file", "run_tests", "finish"]
STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string", "maxLength": 300},
        "tool": {"enum": TOOLS},
        "path": {"type": "string"},
        "old": {"type": "string"},
        "new": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["thought", "tool"],
}

AGENT_SYSTEM = """You are Krama, a careful Python coding assistant working inside a small project.
Each turn, reply with one JSON action:
  {"thought": "...", "tool": "read_file", "path": "file.py"}
  {"thought": "...", "tool": "replace_in_file", "path": "file.py", "old": "exact text now in the file", "new": "text to put there"}
  {"thought": "...", "tool": "create_file", "path": "new.py", "new": "the whole file"}
  {"thought": "...", "tool": "run_tests"}
  {"thought": "...", "tool": "finish", "summary": "what you did, or why you stopped"}
Rules:
- Read a file before changing it. `old` must be copied exactly from the file, and should be short: just the lines that change.
- To add new code at the end of a file, leave `old` empty: `new` is then added after the last line.
- Never change test files (test_*.py); fix the code so the tests pass.
- After each change the tests run by themselves.
- Keep "thought" to one short sentence."""

SKIP = {".git", ".krama", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
MAX_FILE_LINES = 300
MAX_TEST_LINES = 40
TEST_TIME_LIMIT = 60
RECENT_READ = 4          # a file read this many steps ago is still in the prompt (it keeps the last 12 messages)


@dataclass
class AgentResult:
    status: str                  # "solved", "stopped" or "gave up"
    summary: str
    steps: int
    edits: list = field(default_factory=list)       # paths changed
    log: list = field(default_factory=list)         # one line per step


def is_test_file(path):
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py") or "tests" in Path(path).parts


def list_files(project):
    files = []
    for path in sorted(Path(project).rglob("*")):
        relative = path.relative_to(project)
        if path.is_file() and not (set(relative.parts) & SKIP) and path.suffix in (".py", ".txt", ".md", ".toml", ".cfg", ".ini", ".json"):
            files.append(relative.as_posix())
    return files


def inside(project, path):
    """The full path for `path`, or None if it points outside the project."""
    if not path:
        return None
    project = Path(project).resolve()
    full = (project / path).resolve()
    if not full.is_relative_to(project) or set(full.relative_to(project).parts) & SKIP:
        return None
    return full


@dataclass
class TestRun:
    passed: bool
    output: str


def run_project_tests(project, python):
    """Run pytest on a copy of the project, in the limited process."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        copy = Path(folder) / "project"
        shutil.copytree(project, copy, ignore=shutil.ignore_patterns(*SKIP))
        try:
            code, output = run_contained(copy, python, args=["-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
                                         timeout=TEST_TIME_LIMIT, all_output=True)
        except subprocess.TimeoutExpired:
            return TestRun(False, f"the tests were still running after {TEST_TIME_LIMIT} seconds")
        except OSError as error:
            return TestRun(False, f"the tests could not run ({error})")
    if "No module named pytest" in output:
        return TestRun(False, "pytest is not installed. Install it with: python -m pip install pytest")
    lines = output.strip().splitlines()
    return TestRun(code == 0, "\n".join(lines[-MAX_TEST_LINES:]))


def backup(project, full):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = Path(project) / ".krama" / "backups" / stamp / full.relative_to(Path(project).resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(full, target)


def numbered(text):
    lines = text.splitlines()
    shown = "\n".join(f"{number:4} | {line}" for number, line in enumerate(lines[:MAX_FILE_LINES], 1))
    if len(lines) > MAX_FILE_LINES:
        shown += f"\n... ({len(lines) - MAX_FILE_LINES} more lines not shown)"
    return shown


class Tools:
    """The actions Krama may take. Each returns text that is shown to Krama."""

    def __init__(self, project, python, approve, say):
        self.project, self.python, self.approve, self.say = Path(project), python, approve, say
        self.edits = []
        self.last_tests = None

    def read_file(self, action):
        full = inside(self.project, action.get("path"))
        if full is None or not full.is_file():
            return f"There is no file called {action.get('path')!r}. Files: {', '.join(list_files(self.project))}"
        return f"{action['path']}:\n" + numbered(full.read_text(encoding="utf-8", errors="replace"))

    def _change(self, path, before, after):
        """Show the diff, ask, back up, write. Returns text for Krama."""
        diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            f"a/{path}", f"b/{path}"))
        if not self.approve(path, diff):
            return "The user said no to this change. Try a different change, or finish."
        full = inside(self.project, path)
        if full.exists():
            backup(self.project, full)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(after, encoding="utf-8")
        self.edits.append(path)
        self.last_tests = run_project_tests(self.project, self.python)
        verdict = "All tests pass." if self.last_tests.passed else "Tests still fail:"
        return f"Changed {path}. {verdict}\n{self.last_tests.output}"

    def replace_in_file(self, action):
        path = action.get("path", "")
        full = inside(self.project, path)
        if full is None or not full.is_file():
            return f"There is no file called {path!r}."
        if is_test_file(path):
            return "Test files cannot be changed. Change the code so the tests pass."
        old, new = action.get("old", ""), action.get("new", "")
        text = full.read_text(encoding="utf-8", errors="replace")
        if not old:                                    # empty `old` means: add `new` at the end
            if not new.strip():
                return "Both `old` and `new` are empty, so there is nothing to change."
            gap = "\n" if new.startswith((" ", "\t")) else "\n\n"     # inside a class, or a new top-level block
            return self._change(path, text, text.rstrip("\n") + "\n" + gap + new.strip("\n") + "\n")
        count = text.count(old)
        if count > 1:
            return f"That `old` text appears {count} times in {path}. Include more lines so it appears once."
        if count == 1:
            return self._change(path, text, text.replace(old, new, 1))
        changed = tolerant_replace(text, old, new)     # right lines, wrong spaces in front?
        if changed is None:
            return f"That `old` text is not in {path}. " + why_not_found(text, old)
        return self._change(path, text, changed)

    def create_file(self, action):
        path = action.get("path", "")
        full = inside(self.project, path)
        if full is None or not path.endswith(".py"):
            return "New files must be .py files inside the project."
        if full.exists():
            return f"{path} already exists. Use replace_in_file to change it."
        if is_test_file(path):
            return "Test files cannot be created or changed."
        return self._change(path, "", action.get("new", ""))

    def run_tests(self, action):
        self.last_tests = run_project_tests(self.project, self.python)
        return ("All tests pass.\n" if self.last_tests.passed else "Tests fail:\n") + self.last_tests.output


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def tolerant_replace(text, old, new):
    """Replace `old` with `new` in `text` while ignoring indentation mistakes.

    Small models often copy the right lines with the wrong number of spaces
    in front. This finds the one place where the lines match once leading
    spaces are ignored (blank lines are skipped), and moves the new lines'
    indentation by the same amount the copied lines were off.
    Returns the new text, or None if there is not exactly one such place.
    """
    file_lines = text.split("\n")
    old_lines = [line for line in old.split("\n") if line.strip()]
    if not old_lines:
        return None
    wanted = [line.strip() for line in old_lines]
    filled = [(number, line) for number, line in enumerate(file_lines) if line.strip()]
    matches = [start for start in range(len(filled) - len(wanted) + 1)
               if [line.strip() for _, line in filled[start:start + len(wanted)]] == wanted]
    if len(matches) != 1:
        return None
    window = filled[matches[0]:matches[0] + len(wanted)]
    shifts = [indent_of(file_line) - indent_of(old_line) for (_, file_line), old_line in zip(window, old_lines)]

    # Give each new line the shift of the old line it matches, else of the last one matched.
    fixed, shift, next_old = [], shifts[0], 0
    for line in new.split("\n"):
        for position in range(next_old, len(wanted)):
            if line.strip() and line.strip() == wanted[position]:
                shift, next_old = shifts[position], position + 1
                break
        fixed.append(" " * max(0, indent_of(line) + shift) + line.lstrip(" ") if line.strip() else line)

    first, last = window[0][0], window[-1][0]
    return "\n".join(file_lines[:first] + "\n".join(fixed).split("\n") + file_lines[last + 1:])


def why_not_found(text, old):
    """Say what is wrong with an `old` that is not in the file, so the next try can be right.

    Small models often skip a line in the middle (like the `def` under a
    decorator) or change a line a little. Showing the exact lines helps more
    than "not found".
    """
    file_lines = text.split("\n")
    stripped = [line.strip() for line in file_lines]
    wanted = [line.strip() for line in old.split("\n") if line.strip()]
    missing = [line for line in wanted if line not in stripped]
    if missing:
        shown = "\n".join(f"  {line}" for line in missing[:3])
        return (f"These lines of `old` are not in the file:\n{shown}\n"
                "Read the file again and copy the lines exactly, without the line numbers and the `|`.")
    positions, start = [], 0
    for line in wanted:                       # where each line is, looking forward from the last one
        found = stripped.index(line, start) if line in stripped[start:] else stripped.index(line)
        positions.append(found)
        start = found + 1
    first, last = min(positions), max(positions)
    if last - first + 1 > 30:
        return "Copy the lines exactly as they are in the file, one after the other, without the line numbers."
    block = "\n".join(file_lines[first:last + 1])
    return (f"Every line of `old` is in the file, but not one after the other: lines in between are missing. "
            f"Lines {first + 1} to {last + 1} are exactly:\n{block}\n"
            "Copy every line in between too (`new` must keep them, if they should stay).")


def short(action):
    tool = action.get("tool")
    if tool in ("read_file", "replace_in_file", "create_file"):
        return f"{tool} {action.get('path', '')}"
    return tool or "?"


def run_agent(task, project, backend, python, approve, say=print, max_steps=15):
    """Work on `task` in `project` until the tests pass, Krama stops, or steps run out."""
    tools = Tools(project, python, approve, say)
    tools.last_tests = run_project_tests(project, python)
    files = "\n".join(f"- {name}" for name in list_files(project))
    start = (f"Task: {task}\n\nFiles in the project:\n{files}\n\n"
             f"Test results now:\n{tools.last_tests.output}")
    messages = [{"role": "system", "content": AGENT_SYSTEM}, {"role": "user", "content": start}]
    log = []
    tried = {}            # an action (without its thought) -> what it gave back last time
    read_at = {}          # a path -> the step it was last read at, since the last change

    def key_of(action):
        return json.dumps({k: v for k, v in action.items() if k != "thought"}, sort_keys=True)

    def is_repeat(action, step):
        """The same failed change again, or a file that is still in the prompt and unchanged."""
        tool = action.get("tool")
        if tool in ("replace_in_file", "create_file"):
            return key_of(action) in tried
        return tool == "read_file" and step - read_at.get(action.get("path"), -99) <= RECENT_READ

    for step in range(1, max_steps + 1):
        reply = backend.chat(messages[:2] + messages[2:][-12:], schema=STEP_SCHEMA)   # keep the prompt short
        try:
            action = json.loads(reply)
            action["tool"]
        except (ValueError, KeyError, TypeError):
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "Reply with one JSON action only."}]
            log.append(f"{step}: unreadable reply")
            continue
        tool = action["tool"]

        say(f"  step {step}: {short(action)}  ({str(action.get('thought', ''))[:80]})")
        log.append(f"{step}: {short(action)}")
        if tool == "finish":
            done = tools.last_tests.passed
            return AgentResult("solved" if done else "gave up", str(action.get("summary", "")), step, tools.edits, log)
        handler = getattr(tools, tool, None) if tool in TOOLS else None
        key = key_of(action)
        if is_repeat(action, step) and tool != "read_file":
            # The same change again would fail the same way: say so instead of looping.
            result = ("You already tried exactly this action, and it did not work:\n"
                      f"{tried[key]}\nDo something different: read the file again, change fewer lines, "
                      "or try another fix.")
        elif is_repeat(action, step):
            # Still in the prompt and unchanged: reading it again only goes round in circles.
            result = (f"You read {action.get('path')} at step {read_at[action.get('path')]} and it has not changed "
                      "since. Do not read it again: change a file, or finish.")
        else:
            edits_before = len(tools.edits)
            result = handler(action) if handler else f"Unknown tool {tool!r}."
            if len(tools.edits) > edits_before:
                tried.clear()           # a file changed, so earlier failures may now work
                read_at.clear()
            tried[key] = "\n".join(result.splitlines()[:12])
            if tool == "read_file":
                read_at[action.get("path")] = step
        messages += [{"role": "assistant", "content": reply}, {"role": "user", "content": result}]
        if tools.edits and tools.last_tests.passed:
            return AgentResult("solved", "All tests pass.", step, tools.edits, log)

    return AgentResult("stopped", f"Stopped after {max_steps} steps.", max_steps, tools.edits, log)
