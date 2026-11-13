"""Safety scan: look through code folders for things that must not be published.

Run from the project folder, giving one or more folders:
    uv run --no-project data/scan_repos.py "Z:\\path\\to\\repo" "Z:\\another"

It only READS files and prints a report. It never prints a full secret:
only the first 4 characters, so the report itself is safe to share.
"""

import re
import sys
from pathlib import Path

SKIP_FOLDERS = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".idea", ".vscode", "site-packages",
}
TEXT_ENDINGS = {
    ".py", ".env", ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".ini", ".cfg", ".js", ".ts", ".tsx", ".jsx", ".ipynb", ".html", ".sh",
}
MAX_BYTES = 1_000_000

# Each check: a name and a pattern describing what the secret looks like.
CHECKS = {
    "key with a known prefix": re.compile(
        r"(sk-[A-Za-z0-9_\-]{20,}|hf_[A-Za-z0-9]{30,}|ghp_[A-Za-z0-9]{36}"
        r"|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{35}|xox[baprs]-[A-Za-z0-9\-]{10,})"
    ),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "password or token assigned": re.compile(
        r"(?i)(api[_-]?key|secret|token|password|passwd|pwd|auth)[A-Za-z_]*"
        r"\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]"
    ),
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone number": re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)"),
}


def files_in(folder):
    """Yield every text file in the folder, skipping bulky or generated ones."""
    for path in folder.rglob("*"):
        if any(part in SKIP_FOLDERS for part in path.parts):
            continue
        if not path.is_file():
            continue
        is_env_file = path.name.startswith(".env")
        if path.suffix.lower() not in TEXT_ENDINGS and not is_env_file:
            continue
        if path.stat().st_size > MAX_BYTES:
            continue
        yield path


def hide(text):
    """Show only the first 4 characters of a found value."""
    return text[:4] + "…" + f"({len(text)} chars)"


def scan(folder):
    python_files = 0
    python_lines = 0
    env_files = []
    findings = {name: [] for name in CHECKS}

    for path in files_in(folder):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        relative = path.relative_to(folder)

        if path.suffix == ".py":
            python_files += 1
            python_lines += text.count("\n") + 1
        if path.name.startswith(".env"):
            env_files.append(str(relative))

        for line_number, line in enumerate(text.splitlines(), start=1):
            if len(line) > 2000:
                continue
            for name, pattern in CHECKS.items():
                match = pattern.search(line)
                if match:
                    findings[name].append(
                        f"{relative}:{line_number}  {hide(match.group(0))}"
                    )

    print(f"\n=== {folder}")
    print(f"Python files: {python_files}   Python lines: {python_lines}")
    print(f".env files: {len(env_files)}  {env_files[:5]}")
    for name, found in findings.items():
        print(f"{name}: {len(found)}")
        for item in found[:6]:
            print(f"    {item}")
        if len(found) > 6:
            print(f"    … and {len(found) - 6} more")


def main():
    for argument in sys.argv[1:]:
        folder = Path(argument)
        if folder.is_dir():
            scan(folder)
        else:
            print(f"\n=== {folder}\nNOT FOUND")


if __name__ == "__main__":
    main()
