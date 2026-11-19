"""krama: ask the Krama tutor a question; it checks its own code before showing it.

    krama "write a function that reverses a string"     one question
    krama                                                keep asking until you type "exit"

Krama runs on your computer through a backend (today: Ollama). If its code
fails the self-check, the error is sent back to Krama to fix, up to a few times.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from krama_cli.backends import BACKENDS, KRAMA_MODEL, BackendError, make_backend
from krama_cli.check import CheckResult, check, defines_something, extract_code
from krama_cli.selftest import evaluate, self_test

TRIES = 3   # the first answer plus up to two fixes

# The instruction Krama was trained with. krama sends it itself, so every
# backend gives the model the same start, not only Ollama's Modelfile.
KRAMA_SYSTEM = ("You are Krama, a Python and FastAPI coding assistant for beginners, "
                "fine-tuned by CoBeDigger from Qwen2.5-Coder-1.5B-Instruct.")

FIX_REQUEST = (
    "I ran your code and it failed with this error:\n"
    "```\n{error}\n```\n"
    "Please fix the code. Answer again with Plan, Code and Why."
)


def start_conversation(question):
    return [{"role": "system", "content": KRAMA_SYSTEM},
            {"role": "user", "content": question}]


def settings_file():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "krama" / "settings.json"


def load_settings():
    try:
        return json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    path = settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def make_approver(yes_flag, say):
    """Return a function that asks the user before Krama's code is run."""
    settings = load_settings()

    def approve():
        if yes_flag or settings.get("run_checks_without_asking"):
            return True
        if not sys.stdin.isatty():
            say("  self-check needs your OK; add --yes to allow it without asking")
            return False
        reply = input("  Krama wrote code. Run it in a limited process on this computer to "
                      "check it? [y]es / [n]o / [a]lways: ").strip().lower()
        if reply in ("a", "always"):
            settings["run_checks_without_asking"] = True
            save_settings(settings)
            say(f"  saved: krama will not ask again (undo by deleting {settings_file()})")
            return True
        return reply in ("y", "yes")
    return approve


TEST_FIX_REQUEST = "{feedback}\nIf your code is wrong, fix it. Answer again with Plan, Code and Why."


def answer_with_check(question, backend, python, approve, tries=TRIES, say=print, use_tests=True):
    """Ask, check the code, test it, and ask for fixes.

    Returns (answer, check result, test report or None).

    1. The run check: does the code run? If not, the error goes back to Krama.
    2. Once the code runs, Krama writes a few tests (once per question) and
       krama runs them. If they clearly fail, the failures go back to Krama.
       A fix made because of tests is only kept if it still runs AND passes
       more of the same tests; otherwise the earlier answer is kept, so a
       wrong test cannot make good code worse.
    `approve()` is asked once, before any code runs, and covers the fixes too.
    """
    messages = start_conversation(question)
    answer = backend.chat(messages)
    code = extract_code(answer)
    if code.strip() and not defines_something(code):
        return answer, CheckResult("skipped", "a short example, so it was not run"), None
    if code.strip() and not approve():
        return answer, CheckResult("skipped", "not run, because it needs your OK (answer y, or add --yes)"), None
    result = check(code, python)
    report = None

    for attempt in range(2, tries + 1):
        if result.status == "failed":
            say(f"  self-check found an error: {result.message}")
            request = FIX_REQUEST.format(error=result.error.strip())
        elif result.status == "passed" and use_tests:
            if report is None:
                say("  writing and running tests...")
                report = self_test(question, code, backend, python)
            if report.status != "failed":
                break
            say(f"  tests: {report.message}")
            request = TEST_FIX_REQUEST.format(feedback=report.feedback)
        else:
            break

        say(f"  asking Krama to fix it (try {attempt} of {tries})...")
        messages += [{"role": "assistant", "content": answer}, {"role": "user", "content": request}]
        new_answer = backend.chat(messages)
        new_code = extract_code(new_answer)
        new_result = check(new_code, python)

        if report is None:                           # a fix for code that did not run
            answer, code, result = new_answer, new_code, new_result
            continue
        new_report = evaluate(new_code, report.source, python) if new_result.status == "passed" else None
        if new_report is None or new_report.passed <= report.passed:
            say("  the fix was not better, so krama kept the earlier answer")
            break
        answer, code, result, report = new_answer, new_code, new_result, new_report

    if use_tests and result.status == "passed" and report is None:
        say("  writing and running tests...")
        report = self_test(question, code, backend, python)
    return answer, result, report


def show(answer, result, report=None):
    print(answer.strip())
    print()
    if result.status == "passed" and report is not None and report.status != "skipped":
        print(f"[self-check: the code ran without errors, and {report.message}.]")
        for test, status, detail in report.tests:
            mark = "ok  " if status == "ok" else "FAIL"
            print(f"  {mark} {test}" + (f"   ({detail})" if detail and status != "ok" else ""))
        print("[Krama's tests are a start, not proof. Try your own inputs too.]")
    elif result.status == "passed":
        extra = f" ({report.message})" if report is not None else ""
        print(f"[self-check passed: the code ran without errors{extra}. Try it with your own inputs too.]")
    elif result.status == "failed":
        print(f"[self-check FAILED: {result.message}]")
        print("[Krama could not fix this. Read the error before you use this code.]")
    elif result.message.startswith("a short example"):
        print("[example code: not run]")
    elif result.message != "no code to check":
        print(f"[self-check skipped: {result.message}]")


def setup_command(arguments):
    from krama_cli import engine
    parser = argparse.ArgumentParser(prog="krama setup",
                                     description="Download the built-in engine and the Krama model, so krama runs without Ollama.")
    parser.add_argument("--model-file", help="use a Krama .gguf file you already have instead of downloading it")
    args = parser.parse_args(arguments)
    print(f"Setting up krama in {engine.krama_home()}")
    try:
        engine.setup(args.model_file)
    except engine.SetupError as error:
        print(f"  {error}", file=sys.stderr)
        sys.exit(1)
    print('Done. Try:  krama "what is a list?"')


def ask_before_edit(path, diff):
    """Show a change and ask; anything but yes means no."""
    print(f"\n  Krama wants to change {path}:")
    for line in diff.splitlines():
        print("    " + line)
    if not sys.stdin.isatty():
        print("  (no terminal to ask in, so the change was not made)")
        return False
    return input("  Make this change? [y/N]: ").strip().lower() in ("y", "yes")


def fix_command(arguments):
    from krama_cli.agent import run_agent
    parser = argparse.ArgumentParser(prog="krama fix",
                                     description="Let Krama work on the project in this folder until its tests pass. "
                                                 "Every change is shown first and needs your yes.")
    parser.add_argument("task", nargs="*", help='what to do (default: "Make the failing tests pass.")')
    parser.add_argument("--backend", default="auto", choices=["auto", *BACKENDS])
    parser.add_argument("--model", default=KRAMA_MODEL)
    parser.add_argument("--python", default=shutil.which("python") or sys.executable,
                        help="the Python that runs the tests (it needs pytest)")
    parser.add_argument("--steps", type=int, default=15, help="most actions Krama may take (default 15)")
    args = parser.parse_args(arguments)
    task = " ".join(args.task) or "Make the failing tests pass."
    say = lambda text: print(text, file=sys.stderr, flush=True)  # noqa: E731

    backend = None
    try:
        backend = make_backend(args.backend, args.model, context=8192)
        say(f"  working in {Path.cwd()}")
        result = run_agent(task, Path.cwd(), backend, args.python, ask_before_edit, say=say, max_steps=args.steps)
    except KeyboardInterrupt:
        say("\n  stopped.")
        sys.exit(130)
    except BackendError as error:
        say(str(error))
        sys.exit(1)
    finally:
        if backend is not None:
            backend.close()
    print(f"\n[{result.status}] {result.summary}")
    if result.edits:
        print(f"Changed: {', '.join(sorted(set(result.edits)))}. Copies of the old files are in .krama/backups/.")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:2] == ["setup"]:
        setup_command(sys.argv[2:])
        return
    if sys.argv[1:2] == ["fix"]:
        fix_command(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(prog="krama", description="An offline Python and FastAPI tutor that checks its own code.",
                                     epilog="First time? Run `krama setup` to install the built-in engine.")
    parser.add_argument("question", nargs="*", help="your question (leave out to keep asking)")
    parser.add_argument("--backend", default="auto", choices=["auto", *BACKENDS],
                        help="the engine that runs the model: local (built-in, from `krama setup`), "
                             "ollama, or auto = local if set up, else ollama (default)")
    parser.add_argument("--model", default=KRAMA_MODEL, help=f"model name (default: {KRAMA_MODEL})")
    parser.add_argument("--python", default=shutil.which("python") or sys.executable,
                        help="the Python program that runs the self-check (default: the one on your PATH)")
    parser.add_argument("--no-check", action="store_true", help="show the answer without running its code")
    parser.add_argument("--yes", action="store_true", help="run the self-check without asking first")
    parser.add_argument("--no-tests", action="store_true",
                        help="only check that the code runs; skip Krama's own tests (faster)")
    args = parser.parse_args()

    say = lambda text: print(text, file=sys.stderr, flush=True)  # noqa: E731
    approve = make_approver(args.yes, say)

    def one(question):
        say("  thinking...")
        if args.no_check:
            print(backend.chat(start_conversation(question)).strip())
            return
        show(*answer_with_check(question, backend, args.python, approve, say=say, use_tests=not args.no_tests))

    backend = None
    try:
        backend = make_backend(args.backend, args.model)
        if args.question:
            one(" ".join(args.question))
            return
        print('Ask Krama a Python or FastAPI question. Type "exit" to stop.')
        while True:
            try:
                question = input("\nyou> ").strip()
            except EOFError:
                print()
                return
            if question.lower() in ("exit", "quit"):
                return
            if question:
                one(question)
    except KeyboardInterrupt:
        say("\n  stopped.")
        sys.exit(130)
    except BackendError as error:
        say(str(error))
        sys.exit(1)
    finally:
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    main()
