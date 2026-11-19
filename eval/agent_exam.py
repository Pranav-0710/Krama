"""The step-6 exam: 20 projects for `krama fix`, written on 2026-11-19 BEFORE
any agent training data was made, and never used to change the agent.

The trained models are judged on these. 12 bugs and 8 additions; some have
two functions in a file or the fix in another file, so they are a little
bigger than the first 40. `eval/agent_bench.py --check` proves each fails as
given and passes with its fix.
"""

from agent_tasks import task

CLIENT = "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\n"

AGENT_EXAM = [
    # ------------------------------------------------------------ bugs
    task("exam-grade", "A score of 90 should be an A. The tests fail. Fix the bug.",
         {"grades.py": "def letter_grade(score):\n    if score > 90:\n        return 'A'\n    if score >= 80:\n        return 'B'\n    return 'C'\n",
          "test_grades.py": "from grades import letter_grade\n\ndef test_grade():\n    assert letter_grade(90) == 'A'\n    assert letter_grade(95) == 'A'\n    assert letter_grade(85) == 'B'\n    assert letter_grade(10) == 'C'\n"},
         {"grades.py": "def letter_grade(score):\n    if score >= 90:\n        return 'A'\n    if score >= 80:\n        return 'B'\n    return 'C'\n"}),

    task("exam-subtotal", "subtotal should add price times quantity for each item. The tests fail. Fix it.",
         {"basket.py": "def item_count(items):\n    return sum(item['qty'] for item in items)\n\n\ndef subtotal(items):\n    total = 0\n    for item in items:\n        total += item['price'] + item['qty']\n    return total\n",
          "test_basket.py": "from basket import item_count, subtotal\n\nITEMS = [{'price': 10, 'qty': 2}, {'price': 5, 'qty': 1}]\n\ndef test_count():\n    assert item_count(ITEMS) == 3\n\ndef test_subtotal():\n    assert subtotal(ITEMS) == 25\n    assert subtotal([]) == 0\n"},
         {"basket.py": "def item_count(items):\n    return sum(item['qty'] for item in items)\n\n\ndef subtotal(items):\n    total = 0\n    for item in items:\n        total += item['price'] * item['qty']\n    return total\n"}),

    task("exam-unique", "unique should remove repeats but keep the first order. The tests fail. Fix it.",
         {"dedupe.py": "def unique(items):\n    return list(set(items))\n",
          "test_dedupe.py": "from dedupe import unique\n\ndef test_unique():\n    assert unique(['b', 'a', 'b', 'c', 'a']) == ['b', 'a', 'c']\n    assert unique([]) == []\n"},
         {"dedupe.py": "def unique(items):\n    seen = []\n    for item in items:\n        if item not in seen:\n            seen.append(item)\n    return seen\n"}),

    task("exam-word-lengths", "lengths should map each word to its own length. Fix the bug.",
         {"wordlen.py": "def lengths(words):\n    return {word: len(words) for word in words}\n",
          "test_wordlen.py": "from wordlen import lengths\n\ndef test_lengths():\n    assert lengths(['hi', 'hello']) == {'hi': 2, 'hello': 5}\n"},
         {"wordlen.py": "def lengths(words):\n    return {word: len(word) for word in words}\n"}),

    task("exam-api-missing-user", "GET /users/9 should give a 404 when there is no such user, but it gives 200. Fix the app.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nUSERS = {1: 'asha', 2: 'ravi'}\n\n\n@app.get('/users/{user_id}')\ndef get_user(user_id: int):\n    if user_id not in USERS:\n        return {'error': 'not found'}\n    return {'id': user_id, 'name': USERS[user_id]}\n",
          "test_app.py": CLIENT + "def test_found():\n    assert client.get('/users/1').json() == {'id': 1, 'name': 'asha'}\n\n\ndef test_missing():\n    assert client.get('/users/9').status_code == 404\n"},
         {"app.py": "from fastapi import FastAPI, HTTPException\n\napp = FastAPI()\nUSERS = {1: 'asha', 2: 'ravi'}\n\n\n@app.get('/users/{user_id}')\ndef get_user(user_id: int):\n    if user_id not in USERS:\n        raise HTTPException(status_code=404, detail='User not found')\n    return {'id': user_id, 'name': USERS[user_id]}\n"}),

    task("exam-freezing", "is_freezing gives wrong answers for Celsius temperatures. Fix the bug.",
         {"settings.py": "# Temperatures are in Celsius.\nFREEZING = 32\n",
          "weather.py": "from settings import FREEZING\n\n\ndef is_freezing(celsius):\n    return celsius <= FREEZING\n",
          "test_weather.py": "from weather import is_freezing\n\ndef test_freezing():\n    assert is_freezing(0)\n    assert is_freezing(-5)\n    assert not is_freezing(1)\n    assert not is_freezing(20)\n"},
         {"settings.py": "# Temperatures are in Celsius.\nFREEZING = 0\n"}),

    task("exam-pop-empty", "Stack.pop() on an empty stack should return None instead of crashing. Fix it.",
         {"stack_box.py": "class Stack:\n    def __init__(self):\n        self.items = []\n\n    def push(self, item):\n        self.items.append(item)\n\n    def pop(self):\n        return self.items.pop()\n",
          "test_stack_box.py": "from stack_box import Stack\n\ndef test_pop():\n    s = Stack()\n    s.push(1)\n    assert s.pop() == 1\n    assert s.pop() is None\n"},
         {"stack_box.py": "class Stack:\n    def __init__(self):\n        self.items = []\n\n    def push(self, item):\n        self.items.append(item)\n\n    def pop(self):\n        if not self.items:\n            return None\n        return self.items.pop()\n"}),

    task("exam-api-add-numbers", "GET /add?a=2&b=3 should return {\"sum\": 5}, but it returns \"23\". Fix the app.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/add')\ndef add(a: str, b: str):\n    return {'sum': a + b}\n",
          "test_app.py": CLIENT + "def test_add():\n    assert client.get('/add?a=2&b=3').json() == {'sum': 5}\n"},
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/add')\ndef add(a: int, b: int):\n    return {'sum': a + b}\n"}),

    task("exam-count-words", "count_words should not care about capital letters: 'The the' has the word 'the' twice. Fix it.",
         {"wordfreq.py": "def count_words(text):\n    counts = {}\n    for word in text.split():\n        counts[word] = counts.get(word, 0) + 1\n    return counts\n",
          "test_wordfreq.py": "from wordfreq import count_words\n\ndef test_count():\n    assert count_words('The the cat') == {'the': 2, 'cat': 1}\n"},
         {"wordfreq.py": "def count_words(text):\n    counts = {}\n    for word in text.lower().split():\n        counts[word] = counts.get(word, 0) + 1\n    return counts\n"}),

    # ------------------------------------------------------------ additions
    task("exam-add-median", "Add median(values) to number_tools.py. For an even number of values it is the average of the middle two.",
         {"number_tools.py": "def mean(values):\n    return sum(values) / len(values)\n",
          "test_number_tools.py": "from number_tools import mean, median\n\ndef test_mean():\n    assert mean([1, 2, 3]) == 2\n\ndef test_median():\n    assert median([3, 1, 2]) == 2\n    assert median([4, 1, 3, 2]) == 2.5\n"},
         {"number_tools.py": "def mean(values):\n    return sum(values) / len(values)\n\n\ndef median(values):\n    ordered = sorted(values)\n    middle = len(ordered) // 2\n    if len(ordered) % 2:\n        return ordered[middle]\n    return (ordered[middle - 1] + ordered[middle]) / 2\n"}),

    task("exam-add-deposit", "Add a deposit(amount) method to BankAccount. It adds to the balance, and raises ValueError if amount is 0 or less.",
         {"bank.py": "class BankAccount:\n    def __init__(self, balance=0):\n        self.balance = balance\n\n    def withdraw(self, amount):\n        if amount > self.balance:\n            raise ValueError('not enough money')\n        self.balance -= amount\n",
          "test_bank.py": "import pytest\nfrom bank import BankAccount\n\ndef test_deposit():\n    account = BankAccount(10)\n    account.deposit(5)\n    assert account.balance == 15\n\ndef test_bad_deposit():\n    with pytest.raises(ValueError):\n        BankAccount().deposit(0)\n"},
         {"bank.py": "class BankAccount:\n    def __init__(self, balance=0):\n        self.balance = balance\n\n    def withdraw(self, amount):\n        if amount > self.balance:\n            raise ValueError('not enough money')\n        self.balance -= amount\n\n    def deposit(self, amount):\n        if amount <= 0:\n            raise ValueError('amount must be positive')\n        self.balance += amount\n"}),

    task("exam-add-api-delete", "Add DELETE /tasks/{task_id}. It removes the task and returns {\"deleted\": task_id}, or a 404 if there is no such task.",
         {"app.py": "from fastapi import FastAPI, HTTPException\n\napp = FastAPI()\nTASKS = {1: 'shop', 2: 'cook'}\n\n\n@app.get('/tasks')\ndef list_tasks():\n    return TASKS\n",
          "test_app.py": CLIENT + "def test_delete():\n    assert client.delete('/tasks/1').json() == {'deleted': 1}\n    assert '1' not in client.get('/tasks').json()\n\n\ndef test_delete_missing():\n    assert client.delete('/tasks/99').status_code == 404\n"},
         {"app.py": "from fastapi import FastAPI, HTTPException\n\napp = FastAPI()\nTASKS = {1: 'shop', 2: 'cook'}\n\n\n@app.get('/tasks')\ndef list_tasks():\n    return TASKS\n\n\n@app.delete('/tasks/{task_id}')\ndef delete_task(task_id: int):\n    if task_id not in TASKS:\n        raise HTTPException(status_code=404, detail='Task not found')\n    del TASKS[task_id]\n    return {'deleted': task_id}\n"}),

    task("exam-add-greeting", "Give greet a second, optional parameter `greeting` that defaults to 'Hello'.",
         {"greeter.py": "def greet(name):\n    return f'Hello, {name}'\n",
          "test_greeter.py": "from greeter import greet\n\ndef test_greet():\n    assert greet('asha') == 'Hello, asha'\n    assert greet('asha', 'Hi') == 'Hi, asha'\n"},
         {"greeter.py": "def greet(name, greeting='Hello'):\n    return f'{greeting}, {name}'\n"}),

    task("exam-add-full-name", "Add a full_name() method to Person that returns the first and last name with a space between.",
         {"person.py": "class Person:\n    def __init__(self, first, last):\n        self.first = first\n        self.last = last\n",
          "test_person.py": "from person import Person\n\ndef test_full_name():\n    assert Person('Asha', 'Rao').full_name() == 'Asha Rao'\n"},
         {"person.py": "class Person:\n    def __init__(self, first, last):\n        self.first = first\n        self.last = last\n\n    def full_name(self):\n        return f'{self.first} {self.last}'\n"}),

    task("exam-add-api-post", "Add POST /items. The body is {\"name\": \"...\"}. Add the name to ITEMS and return {\"name\": name} with status 201.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nITEMS = ['pen']\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n",
          "test_app.py": CLIENT + "def test_post():\n    response = client.post('/items', json={'name': 'cup'})\n    assert response.status_code == 201\n    assert response.json() == {'name': 'cup'}\n    assert 'cup' in client.get('/items').json()\n"},
         {"app.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI()\nITEMS = ['pen']\n\n\nclass Item(BaseModel):\n    name: str\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n\n\n@app.post('/items', status_code=201)\ndef add_item(item: Item):\n    ITEMS.append(item.name)\n    return {'name': item.name}\n"}),

    task("exam-add-age-check", "make_user should raise ValueError when age is below 0. Add that check.",
         {"users.py": "def make_user(name, age):\n    return {'name': name, 'age': age}\n",
          "test_users.py": "import pytest\nfrom users import make_user\n\ndef test_ok():\n    assert make_user('asha', 30) == {'name': 'asha', 'age': 30}\n\ndef test_negative():\n    with pytest.raises(ValueError):\n        make_user('asha', -1)\n"},
         {"users.py": "def make_user(name, age):\n    if age < 0:\n        raise ValueError('age cannot be negative')\n    return {'name': name, 'age': age}\n"}),

    task("exam-add-fahrenheit", "Add to_fahrenheit(celsius) to temperature.py, next to to_celsius.",
         {"temperature.py": "def to_celsius(fahrenheit):\n    return (fahrenheit - 32) * 5 / 9\n",
          "test_temperature.py": "from temperature import to_celsius, to_fahrenheit\n\ndef test_both():\n    assert to_celsius(212) == 100\n    assert to_fahrenheit(100) == 212\n    assert to_fahrenheit(0) == 32\n"},
         {"temperature.py": "def to_celsius(fahrenheit):\n    return (fahrenheit - 32) * 5 / 9\n\n\ndef to_fahrenheit(celsius):\n    return celsius * 9 / 5 + 32\n"}),

    # ------------------------------------------------------------ more bugs
    task("exam-running-total", "running_total([1, 2, 3]) should be [1, 3, 6]. The tests fail. Fix the bug.",
         {"totals.py": "def running_total(numbers):\n    result = []\n    total = 0\n    for n in numbers:\n        result.append(total)\n        total += n\n    return result\n",
          "test_totals.py": "from totals import running_total\n\ndef test_running():\n    assert running_total([1, 2, 3]) == [1, 3, 6]\n    assert running_total([]) == []\n"},
         {"totals.py": "def running_total(numbers):\n    result = []\n    total = 0\n    for n in numbers:\n        total += n\n        result.append(total)\n    return result\n"}),

    task("exam-api-sorted", "GET /products should list products from cheapest to most expensive. Fix the app.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nPRODUCTS = [{'name': 'bag', 'price': 30}, {'name': 'pen', 'price': 5}, {'name': 'cup', 'price': 12}]\n\n\n@app.get('/products')\ndef list_products():\n    return sorted(PRODUCTS, key=lambda p: p['price'], reverse=True)\n",
          "test_app.py": CLIENT + "def test_sorted():\n    names = [p['name'] for p in client.get('/products').json()]\n    assert names == ['pen', 'cup', 'bag']\n"},
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nPRODUCTS = [{'name': 'bag', 'price': 30}, {'name': 'pen', 'price': 5}, {'name': 'cup', 'price': 12}]\n\n\n@app.get('/products')\ndef list_products():\n    return sorted(PRODUCTS, key=lambda p: p['price'])\n"}),

    task("exam-shared-default", "add_tag keeps tags from earlier calls when no list is given. Each call without a list should start empty. Fix it.",
         {"tags.py": "def add_tag(tag, tags=[]):\n    tags.append(tag)\n    return tags\n",
          "test_tags.py": "from tags import add_tag\n\ndef test_fresh():\n    assert add_tag('a') == ['a']\n    assert add_tag('b') == ['b']\n    assert add_tag('c', ['x']) == ['x', 'c']\n"},
         {"tags.py": "def add_tag(tag, tags=None):\n    if tags is None:\n        tags = []\n    tags.append(tag)\n    return tags\n"}),
]
