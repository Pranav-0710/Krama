"""Phase 2, box 2.1: build the request slips for the teacher model.

A request says: "write a new question about THIS topic", sometimes with a
short piece of real code (a seed) for inspiration. The teacher (box 2.2)
turns each request into a question, tests and an answer.

Run from the project folder:
    uv run --no-project data/make_requests.py

Writes data/requests.jsonl, one request per line.
"""

import ast
import json
import random
from pathlib import Path

from scan_repos import CHECKS, SKIP_FOLDERS

# Only folders that contain Python. Only .py files are ever read.
REPOS = [
    Path(r"Z:\PROJECTS\PROJECTS\gnani.ai"),
    Path(r"Z:\PROJECTS\PROJECTS\planet-hunters"),
    Path(r"Z:\PROJECTS\PROJECTS\Atomberg"),
]
OUT_FILE = Path(__file__).parent / "requests.jsonl"

# How many requests of each kind. About 30% are expected to fail the
# filter in box 2.3, leaving roughly 2,000 good examples.
HOW_MANY = {"fastapi": 1200, "python": 1200, "quick": 600}
SEED_SHARE = 0.4  # 4 in 10 coding requests carry a piece of real code

# Topics lean towards what the exam showed the base model gets wrong.
TOPICS = {
    "fastapi": [
        "POST endpoint that reads a JSON body with a Pydantic model",
        "returning status code 201 when something is created",
        "DELETE endpoint that returns 204 with no body",
        "returning 404 with HTTPException when an id is not found",
        "returning 401 when a required header is missing",
        "reading a request header",
        "rejecting bad input with Field rules such as greater than zero",
        "rejecting text that is too short or too long with Field rules",
        "numbering new items 1, 2, 3 in memory",
        "path parameter with a type, such as an integer id",
        "required query parameter",
        "optional query parameter with a default value",
        "filtering a list by an optional true/false query parameter",
        "PUT endpoint that replaces a stored value",
        "PATCH endpoint that changes only the fields that were sent",
        "GET endpoint that returns a list of items",
        "response_model that hides a field such as a password",
        "a Pydantic model with an optional field",
        "a Pydantic model nested inside another model",
        "a Pydantic model containing a list of items",
        "using an Enum to limit a field to a few allowed values",
        "a shared dependency with Depends",
        "async endpoint that awaits another async function",
        "paging a list with skip and limit query parameters",
        "returning a custom error message with HTTPException detail",
        "409 conflict when creating something that already exists",
        "an APIRouter with a prefix included in the app",
        "counting how many times an endpoint was called",
        "searching stored items by a text query, ignoring case",
        "a health check endpoint next to a real endpoint",
    ],
    "python": [
        "counting things with a dict",
        "grouping items into a dict of lists",
        "handling an empty list or empty string safely",
        "splitting text and ignoring extra spaces",
        "cleaning text: trimming spaces and lowering case",
        "working out an average without dividing by zero",
        "removing duplicates while keeping order",
        "sorting a list of dicts by one key",
        "finding the largest or smallest item by a rule",
        "merging two dicts without changing the originals",
        "parsing simple key=value or comma-separated text",
        "converting between naming styles such as camelCase and snake_case",
        "splitting a list into pieces of a fixed size",
        "flattening nested lists",
        "returning None or a default instead of raising an error",
        "raising ValueError for bad input with a clear message",
        "catching a specific exception with try and except",
        "a list comprehension with a condition",
        "looping with enumerate or zip",
        "slicing strings and lists",
        "checking whether text is a valid whole number",
        "working with dates using the datetime module",
        "a small class with __init__ and two methods",
        "a dataclass that holds a few fields",
        "a function with a default argument, avoiding the mutable default trap",
        "copying a list or dict so the original is not changed",
        "set operations: common items and differences",
        "formatting numbers and text with f-strings",
        "reading values from a nested dict safely",
        "a simple recursive function with a clear stopping case",
    ],
    "quick": [
        "the difference between two similar Python features",
        "what a built-in Python function does",
        "what a common Python error message means",
        "what an HTTP status code means",
        "what a FastAPI term means, such as path parameter or dependency",
        "what a Pydantic term means, such as model or validation",
        "how to run or install something for a Python project",
        "what a Python keyword does",
        "what async and await mean",
        "when to use one data type over another",
        "what a common string or list method does",
        "what a virtual environment is for",
    ],
}


def redact(code):
    """Replace anything that looks like a secret, email or phone number."""
    for pattern in CHECKS.values():
        code = pattern.sub("REDACTED", code)
    return code


def collect_seeds():
    """Cut short functions and classes out of the Python files."""
    seeds = []
    seen = set()
    for repo in REPOS:
        for path in repo.rglob("*.py"):
            if any(part in SKIP_FOLDERS for part in path.parts):
                continue
            try:
                source = path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)
            except (OSError, SyntaxError, ValueError):
                continue
            lines = source.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                piece = lines[node.lineno - 1:node.end_lineno]
                if not 5 <= len(piece) <= 40:
                    continue
                code = redact("\n".join(piece))
                if code not in seen:
                    seen.add(code)
                    seeds.append(code)
    return seeds


def main():
    chooser = random.Random(0)  # fixed number = same result every run
    seeds = collect_seeds()
    requests = []

    for kind, how_many in HOW_MANY.items():
        topics = TOPICS[kind]
        for number in range(how_many):
            seed = ""
            if kind != "quick" and seeds and chooser.random() < SEED_SHARE:
                seed = chooser.choice(seeds)
            requests.append({
                "id": f"{kind}-{number + 1:04d}",
                "kind": kind,
                "topic": topics[number % len(topics)],
                "seed": seed,
            })

    chooser.shuffle(requests)
    with OUT_FILE.open("w", encoding="utf-8") as out:
        for request in requests:
            out.write(json.dumps(request) + "\n")

    with_seed = sum(1 for request in requests if request["seed"])
    print(f"seeds cut from your code: {len(seeds)}")
    print(f"requests written: {len(requests)}  (with a seed: {with_seed})")
    for kind in HOW_MANY:
        print(f"  {kind}: {sum(1 for r in requests if r['kind'] == kind)}")


if __name__ == "__main__":
    main()
