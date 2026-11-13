"""Krama's own test tasks.

These are NEVER used for training. They are written before training starts
and are not changed afterwards, so the score means something.

Each task is a dict with four keys:
    id      a short unique name
    kind    "python", "fastapi" or "quick"
    prompt  exactly what we type to the model
    tests   Python code that checks the model's answer by running it.
            For "quick" tasks there is no code to run, so tests is "".

Target: 30 tasks = 12 python + 12 fastapi + 6 quick.
"""

TASKS = [
    # ---- Worked example (python) -------------------------------------
    {
        "id": "py-group-by-first-letter",
        "kind": "python",
        "prompt": (
            "Write a Python function group_by_first_letter(words) that takes "
            "a list of strings and returns a dict. Each key is a lowercase "
            "first letter, and each value is the list of words starting with "
            "that letter, in their original order. Skip empty strings."
        ),
        "tests": """
assert group_by_first_letter([]) == {}
assert group_by_first_letter(["apple", "Avocado", "bean"]) == {
    "a": ["apple", "Avocado"],
    "b": ["bean"],
}
assert group_by_first_letter(["", "kiwi"]) == {"k": ["kiwi"]}
""",
    },

    # ---- Yours to write: task 1 (python) -----------------------------
    # Pick something a beginner really gets stuck on. Name the function
    # in the prompt so the tests know what to call. Write 3 asserts:
    # a normal case, an empty case, and one tricky case.
    {
        "id": "py-TODO",
        "kind": "python",
        "prompt": "TODO",
        "tests": """
TODO
""",
    },

    # ---- Yours to write: task 2 (fastapi) ----------------------------
    # The model's answer must define `app`. `client` is given to the
    # tests for free: it lets you call the app without starting a server.
    #   r = client.post("/path", json={...})
    #   assert r.status_code == 200
    #   assert r.json() == {...}
    {
        "id": "api-TODO",
        "kind": "fastapi",
        "prompt": "TODO",
        "tests": """
TODO
""",
    },

    # ---- Yours to write: task 3 (quick) ------------------------------
    # A one-line question where the right answer is SHORT. No tests:
    # these are judged on being correct and brief.
    {
        "id": "quick-TODO",
        "kind": "quick",
        "prompt": "TODO",
        "tests": "",
    },
]
