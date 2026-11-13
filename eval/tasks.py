"""Krama's own test tasks: the exam paper.

These are NEVER used for training. They are written before training starts
and are not changed afterwards, so the score means something.

Each task is a dict with five keys:
    id         a short unique name
    kind       "python", "fastapi" or "quick"
    prompt     exactly what we type to the model
    tests      the answer key: Python code that checks the model's answer
               by running it. Empty for "quick" tasks.
    reference  a known-correct answer. It is never shown to a model. We run
               it through the tests to prove the answer key itself is right.
               Empty for "quick" tasks.

30 tasks = 12 python + 12 fastapi + 6 quick.
"""

FASTAPI_START = "from fastapi import FastAPI, HTTPException, Header, Response\nfrom pydantic import BaseModel, Field\n\napp = FastAPI()\n"

TASKS = [
    # ================= python (12) =====================================
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
        "reference": """
def group_by_first_letter(words):
    groups = {}
    for word in words:
        if word:
            groups.setdefault(word[0].lower(), []).append(word)
    return groups
""",
    },
    {
        "id": "py-count-words",
        "kind": "python",
        "prompt": (
            "Write a Python function count_words(text) that returns a dict "
            "saying how many times each word appears in the text. Treat "
            "upper and lower case as the same word, and return the words in "
            "lowercase. Words are separated by spaces. An empty text gives "
            "an empty dict."
        ),
        "tests": """
assert count_words("tea coffee tea") == {"tea": 2, "coffee": 1}
assert count_words("") == {}
assert count_words("Tea  tea") == {"tea": 2}
""",
        "reference": """
def count_words(text):
    counts = {}
    for word in text.lower().split():
        counts[word] = counts.get(word, 0) + 1
    return counts
""",
    },
    {
        "id": "py-safe-divide",
        "kind": "python",
        "prompt": (
            "Write a Python function safe_divide(a, b) that returns a divided "
            "by b. If b is zero, return None instead of crashing."
        ),
        "tests": """
assert safe_divide(6, 3) == 2
assert safe_divide(1, 0) is None
assert safe_divide(0, 5) == 0
""",
        "reference": """
def safe_divide(a, b):
    if b == 0:
        return None
    return a / b
""",
    },
    {
        "id": "py-flatten-one-level",
        "kind": "python",
        "prompt": (
            "Write a Python function flatten(lists) that takes a list of "
            "lists and returns one list with all the items in order. Flatten "
            "one level only: if an item inside is itself a list, keep it as "
            "it is."
        ),
        "tests": """
assert flatten([[1, 2], [3], []]) == [1, 2, 3]
assert flatten([]) == []
assert flatten([[1, [2]]]) == [1, [2]]
""",
        "reference": """
def flatten(lists):
    result = []
    for inner in lists:
        result.extend(inner)
    return result
""",
    },
    {
        "id": "py-most-common",
        "kind": "python",
        "prompt": (
            "Write a Python function most_common(items) that returns the item "
            "that appears most often in the list. If several items are tied, "
            "return the one that appears first in the list. Return None for "
            "an empty list."
        ),
        "tests": """
assert most_common([1, 2, 2, 3]) == 2
assert most_common([]) is None
assert most_common(["a", "b"]) == "a"
assert most_common(["b", "a", "a", "b"]) == "b"
""",
        "reference": """
def most_common(items):
    best = None
    best_count = 0
    for item in items:
        count = items.count(item)
        if count > best_count:
            best = item
            best_count = count
    return best
""",
    },
    {
        "id": "py-parse-config",
        "kind": "python",
        "prompt": (
            "Write a Python function parse_config(text). Each line of the "
            "text looks like key=value. Return a dict of keys to values, both "
            "as strings with surrounding spaces removed. Skip blank lines and "
            "lines that start with #. Split each line on the first equals "
            "sign only, so a value may itself contain an equals sign."
        ),
        "tests": """
assert parse_config("name = krama\\n# a comment\\n\\nsize=1.5b") == {
    "name": "krama",
    "size": "1.5b",
}
assert parse_config("") == {}
assert parse_config("a=b=c") == {"a": "b=c"}
""",
        "reference": """
def parse_config(text):
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result
""",
    },
    {
        "id": "py-chunk",
        "kind": "python",
        "prompt": (
            "Write a Python function chunk(items, size) that splits a list "
            "into smaller lists of the given size, in order. The last list "
            "may be shorter. An empty list gives an empty list."
        ),
        "tests": """
assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
assert chunk([], 3) == []
assert chunk([1, 2], 5) == [[1, 2]]
""",
        "reference": """
def chunk(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]
""",
    },
    {
        "id": "py-dedupe",
        "kind": "python",
        "prompt": (
            "Write a Python function dedupe(items) that returns a new list "
            "with duplicates removed, keeping the first time each item "
            "appears and keeping the original order."
        ),
        "tests": """
assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]
assert dedupe([]) == []
assert dedupe(["a", "A", "a"]) == ["a", "A"]
""",
        "reference": """
def dedupe(items):
    seen = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
""",
    },
    {
        "id": "py-average-scores",
        "kind": "python",
        "prompt": (
            "Write a Python function average_scores(records). Each record is "
            "a dict with a 'name' and a 'score'. Return a dict that maps each "
            "name to the average of that person's scores. An empty list gives "
            "an empty dict."
        ),
        "tests": """
records = [
    {"name": "asha", "score": 80},
    {"name": "ravi", "score": 60},
    {"name": "asha", "score": 90},
]
assert average_scores(records) == {"asha": 85, "ravi": 60}
assert average_scores([]) == {}
""",
        "reference": """
def average_scores(records):
    scores = {}
    for record in records:
        scores.setdefault(record["name"], []).append(record["score"])
    return {name: sum(values) / len(values) for name, values in scores.items()}
""",
    },
    {
        "id": "py-merge-totals",
        "kind": "python",
        "prompt": (
            "Write a Python function merge_totals(a, b) that takes two dicts "
            "of numbers and returns a new dict. A key that is in both gets "
            "the two numbers added together. Do not change the two input "
            "dicts."
        ),
        "tests": """
assert merge_totals({"a": 1, "b": 2}, {"b": 3, "c": 4}) == {"a": 1, "b": 5, "c": 4}
assert merge_totals({}, {}) == {}
first = {"x": 1}
merge_totals(first, {"x": 2})
assert first == {"x": 1}
""",
        "reference": """
def merge_totals(a, b):
    result = dict(a)
    for key, value in b.items():
        result[key] = result.get(key, 0) + value
    return result
""",
    },
    {
        "id": "py-to-snake-case",
        "kind": "python",
        "prompt": (
            "Write a Python function to_snake_case(name) that turns a name "
            "like HelloWorld or helloWorld into hello_world. A name that is "
            "already lowercase with underscores stays the same. An empty "
            "string stays empty."
        ),
        "tests": """
assert to_snake_case("HelloWorld") == "hello_world"
assert to_snake_case("helloWorld") == "hello_world"
assert to_snake_case("") == ""
assert to_snake_case("already_snake") == "already_snake"
""",
        "reference": """
def to_snake_case(name):
    result = ""
    for position, letter in enumerate(name):
        if letter.isupper() and position > 0:
            result += "_"
        result += letter.lower()
    return result
""",
    },
    {
        "id": "py-sum-numbers",
        "kind": "python",
        "prompt": (
            "Write a Python function sum_numbers(text) that takes whole "
            "numbers separated by commas, like '1, 2,3', and returns their "
            "sum. Ignore spaces and ignore empty parts. An empty string "
            "gives 0."
        ),
        "tests": """
assert sum_numbers("1, 2,3") == 6
assert sum_numbers("") == 0
assert sum_numbers("4,,5 ,") == 9
""",
        "reference": """
def sum_numbers(text):
    total = 0
    for part in text.split(","):
        part = part.strip()
        if part:
            total += int(part)
    return total
""",
    },

    # ================= fastapi (12) ====================================
    # The model's answer must create `app`. `client` is given to the
    # tests for free: it calls the app without starting a server.
    {
        "id": "api-create-item",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, POST /items. It accepts "
            "a JSON body with a name (text) and a price (number) and returns "
            "JSON with the same name and price plus an id. The first item "
            "created gets id 1, the next gets id 2, and so on."
        ),
        "tests": """
r = client.post("/items", json={"name": "pen", "price": 10})
assert r.status_code == 200
assert r.json() == {"id": 1, "name": "pen", "price": 10}

r = client.post("/items", json={"name": "book", "price": 250})
assert r.json()["id"] == 2

r = client.post("/items", json={"name": "no price"})
assert r.status_code == 422
""",
        "reference": FASTAPI_START + """
class Item(BaseModel):
    name: str
    price: float

next_id = 0

@app.post("/items")
def create_item(item: Item):
    global next_id
    next_id += 1
    return {"id": next_id, "name": item.name, "price": item.price}
""",
    },
    {
        "id": "api-health",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, GET /health, that returns "
            'the JSON {"status": "ok"}.'
        ),
        "tests": """
r = client.get("/health")
assert r.status_code == 200
assert r.json() == {"status": "ok"}
""",
        "reference": FASTAPI_START + """
@app.get("/health")
def health():
    return {"status": "ok"}
""",
    },
    {
        "id": "api-hello-path",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, GET /hello/{name}, that "
            'returns JSON like {"message": "Hello, Asha"} using the name '
            "from the URL."
        ),
        "tests": """
r = client.get("/hello/Asha")
assert r.status_code == 200
assert r.json() == {"message": "Hello, Asha"}
assert client.get("/hello/Ravi").json() == {"message": "Hello, Ravi"}
""",
        "reference": FASTAPI_START + """
@app.get("/hello/{name}")
def hello(name: str):
    return {"message": f"Hello, {name}"}
""",
    },
    {
        "id": "api-add-query",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, GET /add. It takes two "
            "whole numbers, a and b, from the URL query, as in /add?a=2&b=3, "
            'and returns JSON like {"result": 5}. Both numbers are required.'
        ),
        "tests": """
assert client.get("/add", params={"a": 2, "b": 3}).json() == {"result": 5}
assert client.get("/add", params={"a": 2}).status_code == 422
assert client.get("/add", params={"a": "abc", "b": 1}).status_code == 422
""",
        "reference": FASTAPI_START + """
@app.get("/add")
def add(a: int, b: int):
    return {"result": a + b}
""",
    },
    {
        "id": "api-get-item-404",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app that stores two items: id 1 is 'pen' and "
            "id 2 is 'book'. Add one endpoint, GET /items/{item_id}, that "
            'returns JSON like {"id": 1, "name": "pen"}. If the id does not '
            "exist, respond with status 404."
        ),
        "tests": """
r = client.get("/items/1")
assert r.status_code == 200
assert r.json() == {"id": 1, "name": "pen"}
assert client.get("/items/2").json() == {"id": 2, "name": "book"}
assert client.get("/items/99").status_code == 404
""",
        "reference": FASTAPI_START + """
items = {1: "pen", 2: "book"}

@app.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item_id, "name": items[item_id]}
""",
    },
    {
        "id": "api-create-user-201",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, POST /users. It accepts a "
            "JSON body with a username (text) and returns JSON with that same "
            "username. A successful response must use status code 201."
        ),
        "tests": """
r = client.post("/users", json={"username": "asha"})
assert r.status_code == 201
assert r.json() == {"username": "asha"}
assert client.post("/users", json={}).status_code == 422
""",
        "reference": FASTAPI_START + """
class User(BaseModel):
    username: str

@app.post("/users", status_code=201)
def create_user(user: User):
    return {"username": user.username}
""",
    },
    {
        "id": "api-validate-price",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, POST /products. It "
            "accepts a JSON body with a name (text) and a price (number) and "
            "returns the same name and price as JSON. The price must be "
            "greater than zero; otherwise FastAPI should reject the request "
            "with its usual validation error."
        ),
        "tests": """
r = client.post("/products", json={"name": "pen", "price": 5})
assert r.status_code == 200
assert r.json() == {"name": "pen", "price": 5}
assert client.post("/products", json={"name": "pen", "price": 0}).status_code == 422
assert client.post("/products", json={"name": "pen", "price": -1}).status_code == 422
""",
        "reference": FASTAPI_START + """
class Product(BaseModel):
    name: str
    price: float = Field(gt=0)

@app.post("/products")
def create_product(product: Product):
    return {"name": product.name, "price": product.price}
""",
    },
    {
        "id": "api-search-default",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, GET /search. It takes a "
            "required query value q (text) and an optional query value limit "
            "(whole number) that is 10 when not given. Return JSON like "
            '{"q": "tea", "limit": 10}.'
        ),
        "tests": """
assert client.get("/search", params={"q": "tea"}).json() == {"q": "tea", "limit": 10}
assert client.get("/search", params={"q": "tea", "limit": 3}).json() == {"q": "tea", "limit": 3}
assert client.get("/search").status_code == 422
""",
        "reference": FASTAPI_START + """
@app.get("/search")
def search(q: str, limit: int = 10):
    return {"q": q, "limit": limit}
""",
    },
    {
        "id": "api-notes-delete",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app for notes kept in memory. POST /notes "
            "accepts a JSON body with text and returns JSON with an id and "
            "the text; ids start at 1 and go up by one. DELETE "
            "/notes/{note_id} removes the note and responds with status 204 "
            "and no body. Deleting a note that does not exist responds with "
            "status 404."
        ),
        "tests": """
r = client.post("/notes", json={"text": "hi"})
assert r.json() == {"id": 1, "text": "hi"}
assert client.delete("/notes/1").status_code == 204
assert client.delete("/notes/1").status_code == 404
""",
        "reference": FASTAPI_START + """
class NoteIn(BaseModel):
    text: str

notes = {}

@app.post("/notes")
def create_note(note: NoteIn):
    note_id = len(notes) + 1
    notes[note_id] = note.text
    return {"id": note_id, "text": note.text}

@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    if note_id not in notes:
        raise HTTPException(status_code=404, detail="Note not found")
    del notes[note_id]
    return Response(status_code=204)
""",
    },
    {
        "id": "api-tasks-filter",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app that holds three tasks in memory: id 1 "
            "'write' is done, id 2 'test' is not done, id 3 'ship' is not "
            "done. Each task is a dict with id, title and done. GET /tasks "
            "returns all of them as a JSON list. With the optional query "
            "value done, as in /tasks?done=true, it returns only the tasks "
            "whose done matches."
        ),
        "tests": """
assert len(client.get("/tasks").json()) == 3
assert client.get("/tasks", params={"done": "true"}).json() == [
    {"id": 1, "title": "write", "done": True}
]
assert len(client.get("/tasks", params={"done": "false"}).json()) == 2
""",
        "reference": FASTAPI_START + """
tasks = [
    {"id": 1, "title": "write", "done": True},
    {"id": 2, "title": "test", "done": False},
    {"id": 3, "title": "ship", "done": False},
]

@app.get("/tasks")
def list_tasks(done: bool | None = None):
    if done is None:
        return tasks
    return [task for task in tasks if task["done"] == done]
""",
    },
    {
        "id": "api-counter-put",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app that keeps one counter in memory, starting "
            'at 0. GET /counter returns JSON like {"value": 0}. PUT /counter '
            "accepts a JSON body with a value (whole number), stores it, and "
            "returns the same JSON shape with the new value."
        ),
        "tests": """
assert client.get("/counter").json() == {"value": 0}
assert client.put("/counter", json={"value": 7}).status_code == 200
assert client.get("/counter").json() == {"value": 7}
assert client.put("/counter", json={"value": "x"}).status_code == 422
""",
        "reference": FASTAPI_START + """
class CounterIn(BaseModel):
    value: int

counter = {"value": 0}

@app.get("/counter")
def get_counter():
    return counter

@app.put("/counter")
def set_counter(new: CounterIn):
    counter["value"] = new.value
    return counter
""",
    },
    {
        "id": "api-whoami-header",
        "kind": "fastapi",
        "prompt": (
            "Write a FastAPI app with one endpoint, GET /whoami. It reads the "
            "request header X-User and returns JSON like "
            '{"user": "asha"}. If the header is missing, respond with '
            "status 401."
        ),
        "tests": """
r = client.get("/whoami", headers={"X-User": "asha"})
assert r.status_code == 200
assert r.json() == {"user": "asha"}
assert client.get("/whoami").status_code == 401
""",
        "reference": FASTAPI_START + """
@app.get("/whoami")
def whoami(x_user: str | None = Header(default=None)):
    if x_user is None:
        raise HTTPException(status_code=401, detail="Missing X-User header")
    return {"user": x_user}
""",
    },

    # ================= quick (6) =======================================
    # No tests: judged later by a blind grader on being correct and brief.
    {
        "id": "quick-list-vs-tuple",
        "kind": "quick",
        "prompt": "What is the difference between a list and a tuple in Python?",
        "tests": "",
        "reference": "",
    },
    {
        "id": "quick-zip",
        "kind": "quick",
        "prompt": "What does zip do in Python?",
        "tests": "",
        "reference": "",
    },
    {
        "id": "quick-422",
        "kind": "quick",
        "prompt": "In FastAPI, what status code do I get when the request body fails validation?",
        "tests": "",
        "reference": "",
    },
    {
        "id": "quick-name-main",
        "kind": "quick",
        "prompt": 'What does if __name__ == "__main__": do in Python?',
        "tests": "",
        "reference": "",
    },
    {
        "id": "quick-equals-vs-is",
        "kind": "quick",
        "prompt": "What is the difference between == and is in Python?",
        "tests": "",
        "reference": "",
    },
    {
        "id": "quick-run-fastapi",
        "kind": "quick",
        "prompt": "How do I run a FastAPI app on my own computer?",
        "tests": "",
        "reference": "",
    },
]
