"""krama: ask the Krama tutor a question; it checks its own code before showing it.

    krama "write a function that reverses a string"     one question
    krama                                                keep asking until you type "exit"

Krama runs on your computer through Ollama. If its code fails the
self-check, the error is sent back to Krama to fix, up to a few times.
"""

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

from krama_cli.check import CheckResult, check, extract_code

MODEL = "hf.co/CoBeDigger/krama-coder-1.5b"
TRIES = 3   # the first answer plus up to two fixes

FIX_REQUEST = (
    "I ran your code and it failed with this error:\n"
    "```\n{error}\n```\n"
    "Please fix the code. Answer again with Plan, Code and Why."
)


class OllamaError(Exception):
    """Ollama is not running, or the model is missing."""


def ollama_url():
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not host.startswith("http"):
        host = "http://" + host
    return host.rstrip("/") + "/api/chat"


def ask(model, messages):
    """Send the conversation to Ollama and return Krama's reply."""
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        # 0 = always pick the most likely next word, so answers stay steady.
        "options": {"temperature": 0},
    }
    request = urllib.request.Request(ollama_url(), data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.loads(response.read())["message"]["content"]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise OllamaError(f"The model is not downloaded yet. Run:\n    ollama pull {model}") from error
        raise OllamaError(f"Ollama answered with an error: {error.read().decode(errors='replace')}") from error
    except urllib.error.URLError as error:
        raise OllamaError("Could not reach Ollama. Start the Ollama app, then try again.") from error


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


def answer_with_check(question, model, python, approve, tries=TRIES, say=print):
    """Ask, check the code, and ask for fixes. Return (answer, last check result).

    `approve()` is asked once, before any code runs; one yes covers the fixes
    for this question too.
    """
    messages = [{"role": "user", "content": question}]
    answer = ask(model, messages)
    code = extract_code(answer)
    if code.strip() and not approve():
        return answer, CheckResult("skipped", "not run, because it needs your OK (answer y, or add --yes)")
    result = check(code, python)

    for attempt in range(2, tries + 1):
        if result.status != "failed":
            break
        say(f"  self-check found an error: {result.message}")
        say(f"  asking Krama to fix it (try {attempt} of {tries})...")
        messages += [{"role": "assistant", "content": answer},
                     {"role": "user", "content": FIX_REQUEST.format(error=result.error.strip())}]
        answer = ask(model, messages)
        result = check(extract_code(answer), python)
    return answer, result


def show(answer, result):
    print(answer.strip())
    print()
    if result.status == "passed":
        print("[self-check passed: the code ran without errors. Try it with your own inputs too.]")
    elif result.status == "failed":
        print(f"[self-check FAILED: {result.message}]")
        print("[Krama could not fix this. Read the error before you use this code.]")
    elif result.message != "no code to check":
        print(f"[self-check skipped: {result.message}]")


def main():
    parser = argparse.ArgumentParser(prog="krama", description="An offline Python and FastAPI tutor that checks its own code.")
    parser.add_argument("question", nargs="*", help="your question (leave out to keep asking)")
    parser.add_argument("--model", default=MODEL, help=f"Ollama model name (default: {MODEL})")
    parser.add_argument("--python", default=shutil.which("python") or sys.executable,
                        help="the Python program that runs the self-check (default: the one on your PATH)")
    parser.add_argument("--no-check", action="store_true", help="show the answer without running its code")
    parser.add_argument("--yes", action="store_true", help="run the self-check without asking first")
    args = parser.parse_args()

    # Windows terminals may not print every character; never crash on one.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    say = lambda text: print(text, file=sys.stderr, flush=True)  # noqa: E731
    approve = make_approver(args.yes, say)

    def one(question):
        say("  thinking...")
        if args.no_check:
            print(ask(args.model, [{"role": "user", "content": question}]).strip())
            return
        show(*answer_with_check(question, args.model, args.python, approve, say=say))

    try:
        if args.question:
            one(" ".join(args.question))
            return
        print('Ask Krama a Python or FastAPI question. Type "exit" to stop.')
        while True:
            try:
                question = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if question.lower() in ("exit", "quit"):
                return
            if question:
                one(question)
    except OllamaError as error:
        say(str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
