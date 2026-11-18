"""20 small projects for the guided agent (`krama fix`). Written for Krama, 2026-11-18.

Each project is a few beginner-sized files whose tests fail. 12 have a bug to
fix, 8 need a small new feature. `fix` holds a known-good version of the
changed files; `eval/agent_bench.py --check` proves every project fails as
given and passes with its fix. The agent never sees `fix`, and test files are
restored before marking, so changing the tests cannot help.
"""


def task(task_id, request, files, fix):
    return {"id": task_id, "request": request, "files": files, "fix": fix}


AGENT_TASKS = [
    # ------------------------------------------------------------ bugs
    task("bug-add", "The tests fail. Fix the bug.",
         {"calc.py": "def add(a, b):\n    return a - b\n",
          "test_calc.py": "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n"},
         {"calc.py": "def add(a, b):\n    return a + b\n"}),

    task("bug-sum-to", "sum_to(n) should add 1 + 2 + ... + n. The tests fail. Fix it.",
         {"counting.py": "def sum_to(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total\n",
          "test_counting.py": "from counting import sum_to\n\ndef test_sum_to():\n    assert sum_to(3) == 6\n    assert sum_to(1) == 1\n"},
         {"counting.py": "def sum_to(n):\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n"}),

    task("bug-adult", "People aged 18 count as adults. The tests fail. Fix the bug.",
         {"people.py": "def is_adult(age):\n    return age > 18\n",
          "test_people.py": "from people import is_adult\n\ndef test_adult():\n    assert is_adult(18)\n    assert is_adult(30)\n    assert not is_adult(17)\n"},
         {"people.py": "def is_adult(age):\n    return age >= 18\n"}),

    task("bug-import", "The tests crash. Fix the code.",
         {"geometry.py": "def hypotenuse(a, b):\n    return math.sqrt(a * a + b * b)\n",
          "test_geometry.py": "from geometry import hypotenuse\n\ndef test_hypotenuse():\n    assert hypotenuse(3, 4) == 5\n"},
         {"geometry.py": "import math\n\n\ndef hypotenuse(a, b):\n    return math.sqrt(a * a + b * b)\n"}),

    task("bug-average-empty", "average([]) should return 0 instead of crashing. Fix it.",
         {"stats.py": "def average(values):\n    return sum(values) / len(values)\n",
          "test_stats.py": "from stats import average\n\ndef test_average():\n    assert average([2, 4]) == 3\n\ndef test_empty():\n    assert average([]) == 0\n"},
         {"stats.py": "def average(values):\n    if not values:\n        return 0\n    return sum(values) / len(values)\n"}),

    task("bug-reverse", "reverse(text) should return the text backwards. The tests fail. Fix it.",
         {"text_tools.py": "def reverse(text):\n    return text[::1]\n",
          "test_text_tools.py": "from text_tools import reverse\n\ndef test_reverse():\n    assert reverse('abc') == 'cba'\n    assert reverse('') == ''\n"},
         {"text_tools.py": "def reverse(text):\n    return text[::-1]\n"}),

    task("bug-key-typo", "The tests fail. Fix the bug.",
         {"users.py": "def display_name(user):\n    return user['nmae'].title()\n",
          "test_users.py": "from users import display_name\n\ndef test_display_name():\n    assert display_name({'name': 'asha rao'}) == 'Asha Rao'\n"},
         {"users.py": "def display_name(user):\n    return user['name'].title()\n"}),

    task("bug-vowels", "count_vowels should count upper and lower case vowels. Fix it.",
         {"letters.py": "def count_vowels(text):\n    return sum(1 for ch in text if ch in 'aeiou')\n",
          "test_letters.py": "from letters import count_vowels\n\ndef test_vowels():\n    assert count_vowels('Apple') == 2\n    assert count_vowels('xyz') == 0\n    assert count_vowels('AEIOU') == 5\n"},
         {"letters.py": "def count_vowels(text):\n    return sum(1 for ch in text.lower() if ch in 'aeiou')\n"}),

    task("bug-api-path", "The tests fail. Fix the FastAPI app.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/helo')\ndef hello():\n    return {'message': 'hello'}\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_hello():\n    response = client.get('/hello')\n    assert response.status_code == 200\n    assert response.json() == {'message': 'hello'}\n"},
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/hello')\ndef hello():\n    return {'message': 'hello'}\n"}),

    task("bug-api-201", "Creating a book should answer with status code 201. Fix the app.",
         {"app.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\n\nclass Book(BaseModel):\n    title: str\n\n\n@app.post('/books')\ndef create_book(book: Book):\n    return {'title': book.title}\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_create():\n    response = client.post('/books', json={'title': 'Dune'})\n    assert response.status_code == 201\n    assert response.json() == {'title': 'Dune'}\n"},
         {"app.py": "from fastapi import FastAPI\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\n\nclass Book(BaseModel):\n    title: str\n\n\n@app.post('/books', status_code=201)\ndef create_book(book: Book):\n    return {'title': book.title}\n"}),

    task("bug-mutates-input", "sorted_copy must not change the list it is given. Fix it.",
         {"lists.py": "def sorted_copy(items):\n    items.sort()\n    return items\n",
          "test_lists.py": "from lists import sorted_copy\n\ndef test_sorted_copy():\n    original = [3, 1, 2]\n    assert sorted_copy(original) == [1, 2, 3]\n    assert original == [3, 1, 2]\n"},
         {"lists.py": "def sorted_copy(items):\n    return sorted(items)\n"}),

    task("bug-two-files", "The report shows the wrong temperatures. The tests fail. Fix the bug.",
         {"convert.py": "def to_celsius(fahrenheit):\n    return (fahrenheit - 32) * 9 / 5\n",
          "report.py": "from convert import to_celsius\n\n\ndef report(readings):\n    return [round(to_celsius(f), 1) for f in readings]\n",
          "test_report.py": "from report import report\n\ndef test_report():\n    assert report([32, 212]) == [0.0, 100.0]\n    assert report([98.6]) == [37.0]\n"},
         {"convert.py": "def to_celsius(fahrenheit):\n    return (fahrenheit - 32) * 5 / 9\n"}),

    # ------------------------------------------------------------ small features
    task("feat-multiply", "Add a multiply(a, b) function to calc.py so the tests pass.",
         {"calc.py": "def add(a, b):\n    return a + b\n",
          "test_calc.py": "from calc import add, multiply\n\ndef test_add():\n    assert add(2, 2) == 4\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n"},
         {"calc.py": "def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n"}),

    task("feat-is-even", "Add is_even(n) to parity.py: True for even numbers, False for odd ones.",
         {"parity.py": "def is_odd(n):\n    return n % 2 == 1\n",
          "test_parity.py": "from parity import is_even, is_odd\n\ndef test_even():\n    assert is_even(4)\n    assert not is_even(7)\n    assert is_even(0)\n\ndef test_odd():\n    assert is_odd(3)\n"},
         {"parity.py": "def is_odd(n):\n    return n % 2 == 1\n\n\ndef is_even(n):\n    return n % 2 == 0\n"}),

    task("feat-default", "greet() with no name should greet 'world'. Make the tests pass.",
         {"greet.py": "def greet(name):\n    return f'Hello, {name}!'\n",
          "test_greet.py": "from greet import greet\n\ndef test_greet():\n    assert greet('Asha') == 'Hello, Asha!'\n    assert greet() == 'Hello, world!'\n"},
         {"greet.py": "def greet(name='world'):\n    return f'Hello, {name}!'\n"}),

    task("feat-api-item", "Add GET /items/{item_id}: return the item, or a 404 if there is none.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nITEMS = {1: 'pen', 2: 'book'}\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_found():\n    response = client.get('/items/2')\n    assert response.status_code == 200\n    assert response.json() == {'id': 2, 'name': 'book'}\n\n\ndef test_missing():\n    assert client.get('/items/9').status_code == 404\n"},
         {"app.py": "from fastapi import FastAPI, HTTPException\n\napp = FastAPI()\nITEMS = {1: 'pen', 2: 'book'}\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n\n\n@app.get('/items/{item_id}')\ndef get_item(item_id: int):\n    if item_id not in ITEMS:\n        raise HTTPException(status_code=404, detail='Item not found')\n    return {'id': item_id, 'name': ITEMS[item_id]}\n"}),

    task("feat-peek", "Add a peek() method to Stack that returns the top item without removing it.",
         {"stack.py": "class Stack:\n    def __init__(self):\n        self.items = []\n\n    def push(self, item):\n        self.items.append(item)\n\n    def pop(self):\n        return self.items.pop()\n",
          "test_stack.py": "from stack import Stack\n\ndef test_peek():\n    s = Stack()\n    s.push(1)\n    s.push(2)\n    assert s.peek() == 2\n    assert s.pop() == 2\n    assert s.peek() == 1\n"},
         {"stack.py": "class Stack:\n    def __init__(self):\n        self.items = []\n\n    def push(self, item):\n        self.items.append(item)\n\n    def pop(self):\n        return self.items.pop()\n\n    def peek(self):\n        return self.items[-1]\n"}),

    task("feat-withdraw-check", "withdraw should raise ValueError if the amount is more than the balance.",
         {"bank.py": "class Account:\n    def __init__(self, balance=0):\n        self.balance = balance\n\n    def withdraw(self, amount):\n        self.balance -= amount\n        return self.balance\n",
          "test_bank.py": "import pytest\nfrom bank import Account\n\ndef test_withdraw():\n    assert Account(100).withdraw(30) == 70\n\ndef test_too_much():\n    account = Account(10)\n    with pytest.raises(ValueError):\n        account.withdraw(50)\n    assert account.balance == 10\n"},
         {"bank.py": "class Account:\n    def __init__(self, balance=0):\n        self.balance = balance\n\n    def withdraw(self, amount):\n        if amount > self.balance:\n            raise ValueError('not enough money')\n        self.balance -= amount\n        return self.balance\n"}),

    task("feat-toggle", "Add toggle(todo) to todos.py: it flips the todo's 'done' value and returns the todo.",
         {"todos.py": "def make_todo(title):\n    return {'title': title, 'done': False}\n",
          "main.py": "from todos import make_todo\n\nTODOS = [make_todo('write'), make_todo('test')]\n",
          "test_todos.py": "from todos import make_todo, toggle\n\ndef test_toggle():\n    todo = make_todo('ship')\n    assert toggle(todo)['done'] is True\n    assert toggle(todo)['done'] is False\n"},
         {"todos.py": "def make_todo(title):\n    return {'title': title, 'done': False}\n\n\ndef toggle(todo):\n    todo['done'] = not todo['done']\n    return todo\n"}),

    task("feat-word-count", "word_count should ignore punctuation like commas and full stops. Make the tests pass.",
         {"words.py": "def word_count(text):\n    counts = {}\n    for word in text.lower().split():\n        counts[word] = counts.get(word, 0) + 1\n    return counts\n",
          "test_words.py": "from words import word_count\n\ndef test_plain():\n    assert word_count('a b a') == {'a': 2, 'b': 1}\n\ndef test_punctuation():\n    assert word_count('Hi, hi. Bye!') == {'hi': 2, 'bye': 1}\n"},
         {"words.py": "import string\n\n\ndef word_count(text):\n    counts = {}\n    for word in text.lower().split():\n        word = word.strip(string.punctuation)\n        if word:\n            counts[word] = counts.get(word, 0) + 1\n    return counts\n"}),
]


# Held out: written on 2026-11-18 AFTER the first runs on the 20 projects above
# and after the agent's edit rules were changed because of them, but BEFORE
# any agent saw these. Scores on these 10 show whether the changes generalise.
AGENT_HELDOUT = [
    task("held-max", "find_max should return the biggest number. The tests fail. Fix it.",
         {"finder.py": "def find_max(values):\n    best = values[0]\n    for value in values:\n        if value < best:\n            best = value\n    return best\n",
          "test_finder.py": "from finder import find_max\n\ndef test_find_max():\n    assert find_max([3, 9, 2]) == 9\n    assert find_max([-5, -1]) == -1\n"},
         {"finder.py": "def find_max(values):\n    best = values[0]\n    for value in values:\n        if value > best:\n            best = value\n    return best\n"}),

    task("held-clean-name", "clean_name should remove spaces around the name and capitalise it. Fix it.",
         {"names.py": "def clean_name(name):\n    return name.title()\n",
          "test_names.py": "from names import clean_name\n\ndef test_clean():\n    assert clean_name('  asha ') == 'Asha'\n    assert clean_name('ravi') == 'Ravi'\n"},
         {"names.py": "def clean_name(name):\n    return name.strip().title()\n"}),

    task("held-last-item", "last_item should return the last item of the list. The tests crash. Fix it.",
         {"items.py": "def last_item(items):\n    return items[len(items)]\n",
          "test_items.py": "from items import last_item\n\ndef test_last():\n    assert last_item([1, 2, 3]) == 3\n    assert last_item(['a']) == 'a'\n"},
         {"items.py": "def last_item(items):\n    return items[-1]\n"}),

    task("held-count-letters", "count_letters crashes. It should count how often each letter appears. Fix it.",
         {"letters_count.py": "def count_letters(text):\n    counts = {}\n    for ch in text:\n        counts[ch] += 1\n    return counts\n",
          "test_letters_count.py": "from letters_count import count_letters\n\ndef test_count():\n    assert count_letters('aab') == {'a': 2, 'b': 1}\n    assert count_letters('') == {}\n"},
         {"letters_count.py": "def count_letters(text):\n    counts = {}\n    for ch in text:\n        counts[ch] = counts.get(ch, 0) + 1\n    return counts\n"}),

    task("held-api-square", "GET /square?n=3 should return the JSON {\"result\": 9}. The tests fail. Fix the app.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/square')\ndef square(n: int):\n    return {'result': n + n}\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_square():\n    assert client.get('/square?n=3').json() == {'result': 9}\n    assert client.get('/square?n=-2').json() == {'result': 4}\n"},
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/square')\ndef square(n: int):\n    return {'result': n * n}\n"}),

    task("held-percent", "Add percent(part, whole) to maths_tools.py. It returns part as a percentage of whole, or 0 when whole is 0.",
         {"maths_tools.py": "def half(n):\n    return n / 2\n",
          "test_maths_tools.py": "from maths_tools import half, percent\n\ndef test_half():\n    assert half(4) == 2\n\ndef test_percent():\n    assert percent(1, 4) == 25\n    assert percent(5, 0) == 0\n"},
         {"maths_tools.py": "def half(n):\n    return n / 2\n\n\ndef percent(part, whole):\n    if whole == 0:\n        return 0\n    return part / whole * 100\n"}),

    task("held-palindrome", "Add is_palindrome(text) to words_check.py. It ignores upper and lower case.",
         {"words_check.py": "def is_empty(text):\n    return text == ''\n",
          "test_words_check.py": "from words_check import is_palindrome\n\ndef test_palindrome():\n    assert is_palindrome('Level')\n    assert is_palindrome('abba')\n    assert not is_palindrome('abc')\n"},
         {"words_check.py": "def is_empty(text):\n    return text == ''\n\n\ndef is_palindrome(text):\n    text = text.lower()\n    return text == text[::-1]\n"}),

    task("held-api-delete", "Add DELETE /items/{item_id}: remove the item and answer 204, or answer 404 if there is none.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nITEMS = {1: 'pen', 2: 'book'}\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_delete():\n    assert client.delete('/items/1').status_code == 204\n    assert client.delete('/items/1').status_code == 404\n"},
         {"app.py": "from fastapi import FastAPI, HTTPException, Response\n\napp = FastAPI()\nITEMS = {1: 'pen', 2: 'book'}\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n\n\n@app.delete('/items/{item_id}', status_code=204)\ndef delete_item(item_id: int):\n    if item_id not in ITEMS:\n        raise HTTPException(status_code=404, detail='Item not found')\n    del ITEMS[item_id]\n    return Response(status_code=204)\n"}),

    task("held-area", "Add an area() method to Rectangle that returns width times height.",
         {"shapes.py": "class Rectangle:\n    def __init__(self, width, height):\n        self.width = width\n        self.height = height\n",
          "test_shapes.py": "from shapes import Rectangle\n\ndef test_area():\n    assert Rectangle(2, 3).area() == 6\n    assert Rectangle(0, 5).area() == 0\n"},
         {"shapes.py": "class Rectangle:\n    def __init__(self, width, height):\n        self.width = width\n        self.height = height\n\n    def area(self):\n        return self.width * self.height\n"}),

    task("held-tax", "The shop total is wrong: a 10% tax should be added to each price. The tests fail. Fix the bug.",
         {"tax.py": "RATE = 0.1\n\n\ndef add_tax(price):\n    return price * RATE\n",
          "shop.py": "from tax import add_tax\n\n\ndef total(prices):\n    return round(sum(add_tax(p) for p in prices), 2)\n",
          "test_shop.py": "from shop import total\n\ndef test_total():\n    assert total([100]) == 110\n    assert total([10, 20]) == 33\n"},
         {"tax.py": "RATE = 0.1\n\n\ndef add_tax(price):\n    return price * (1 + RATE)\n"}),
]


# Held out, second set: written on 2026-11-19 after the first held-out set was
# used to change the agent again (empty `old` adds at the end; no re-reading
# unchanged files), and before any agent saw these. 4 bugs, 3 additions,
# 2 API projects, 1 bug that spans two files.
AGENT_HELDOUT2 = [
    task("fresh-min-index", "index_of_min should return the position of the smallest number, not the number. Fix it.",
         {"lowest.py": "def index_of_min(values):\n    best = 0\n    for i in range(len(values)):\n        if values[i] < values[best]:\n            best = i\n    return values[best]\n",
          "test_lowest.py": "from lowest import index_of_min\n\ndef test_index():\n    assert index_of_min([4, 1, 7]) == 1\n    assert index_of_min([9]) == 0\n"},
         {"lowest.py": "def index_of_min(values):\n    best = 0\n    for i in range(len(values)):\n        if values[i] < values[best]:\n            best = i\n    return best\n"}),

    task("fresh-only-even", "only_even should keep the even numbers. The tests fail. Fix the bug.",
         {"evens.py": "def only_even(numbers):\n    return [n for n in numbers if n % 2 == 1]\n",
          "test_evens.py": "from evens import only_even\n\ndef test_even():\n    assert only_even([1, 2, 3, 4]) == [2, 4]\n    assert only_even([]) == []\n"},
         {"evens.py": "def only_even(numbers):\n    return [n for n in numbers if n % 2 == 0]\n"}),

    task("fresh-initials", "initials('asha ravi') should return 'AR'. The tests fail. Fix it.",
         {"short_names.py": "def initials(full_name):\n    return ''.join(word[1] for word in full_name.split()).upper()\n",
          "test_short_names.py": "from short_names import initials\n\ndef test_initials():\n    assert initials('asha ravi') == 'AR'\n    assert initials('kiran') == 'K'\n"},
         {"short_names.py": "def initials(full_name):\n    return ''.join(word[0] for word in full_name.split()).upper()\n"}),

    task("fresh-countdown", "countdown(3) should return [3, 2, 1], but it returns an empty list. Fix it.",
         {"launch.py": "def countdown(n):\n    return list(range(n, 0))\n",
          "test_launch.py": "from launch import countdown\n\ndef test_countdown():\n    assert countdown(3) == [3, 2, 1]\n    assert countdown(1) == [1]\n"},
         {"launch.py": "def countdown(n):\n    return list(range(n, 0, -1))\n"}),

    task("fresh-add-leap", "Add is_leap(year) to dates_tools.py: years divisible by 4 are leap years, except years divisible by 100, unless they are also divisible by 400.",
         {"dates_tools.py": "def days_in_week():\n    return 7\n",
          "test_dates_tools.py": "from dates_tools import is_leap\n\ndef test_leap():\n    assert is_leap(2024)\n    assert is_leap(2000)\n    assert not is_leap(1900)\n    assert not is_leap(2023)\n"},
         {"dates_tools.py": "def days_in_week():\n    return 7\n\n\ndef is_leap(year):\n    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)\n"}),

    task("fresh-add-size", "Add a size() method to WaitingLine in waiting_line.py. It returns how many people are waiting.",
         {"waiting_line.py": "class WaitingLine:\n    def __init__(self):\n        self.people = []\n\n    def join(self, person):\n        self.people.append(person)\n",
          "test_waiting_line.py": "from waiting_line import WaitingLine\n\ndef test_size():\n    line = WaitingLine()\n    assert line.size() == 0\n    line.join('asha')\n    line.join('ravi')\n    assert line.size() == 2\n"},
         {"waiting_line.py": "class WaitingLine:\n    def __init__(self):\n        self.people = []\n\n    def join(self, person):\n        self.people.append(person)\n\n    def size(self):\n        return len(self.people)\n"}),

    task("fresh-add-clamp", "Add clamp(value, low, high) to limits.py. It returns low if value is below low, high if it is above high, else value.",
         {"limits.py": "def is_positive(n):\n    return n > 0\n",
          "test_limits.py": "from limits import clamp\n\ndef test_clamp():\n    assert clamp(5, 0, 10) == 5\n    assert clamp(-3, 0, 10) == 0\n    assert clamp(99, 0, 10) == 10\n"},
         {"limits.py": "def is_positive(n):\n    return n > 0\n\n\ndef clamp(value, low, high):\n    return max(low, min(value, high))\n"}),

    task("fresh-api-greet", "GET /greet/asha should return {\"message\": \"Hello, asha\"}. The tests fail. Fix the app.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/greet/{name}')\ndef greet(name: str):\n    return {'mesage': f'Hello, {name}'}\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_greet():\n    assert client.get('/greet/asha').json() == {'message': 'Hello, asha'}\n"},
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/greet/{name}')\ndef greet(name: str):\n    return {'message': f'Hello, {name}'}\n"}),

    task("fresh-api-count", "Add GET /items/count to the app. It returns {\"count\": N}, where N is how many items there are.",
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nITEMS = ['pen', 'book', 'bag']\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n",
          "test_app.py": "from fastapi.testclient import TestClient\nfrom app import app\n\nclient = TestClient(app)\n\n\ndef test_list():\n    assert client.get('/items').json() == ['pen', 'book', 'bag']\n\n\ndef test_count():\n    assert client.get('/items/count').json() == {'count': 3}\n"},
         {"app.py": "from fastapi import FastAPI\n\napp = FastAPI()\nITEMS = ['pen', 'book', 'bag']\n\n\n@app.get('/items')\ndef list_items():\n    return ITEMS\n\n\n@app.get('/items/count')\ndef count_items():\n    return {'count': len(ITEMS)}\n"}),

    task("fresh-discount", "A 10% discount on 200 should give 180, but the cart total is wrong. Fix the bug.",
         {"prices.py": "def apply_discount(price, percent):\n    return price - percent\n",
          "cart.py": "from prices import apply_discount\n\n\ndef cart_total(prices, percent):\n    return sum(apply_discount(p, percent) for p in prices)\n",
          "test_cart.py": "from cart import cart_total\n\ndef test_total():\n    assert cart_total([200], 10) == 180\n    assert cart_total([100, 50], 20) == 120\n"},
         {"prices.py": "def apply_discount(price, percent):\n    return price * (100 - percent) / 100\n"}),
]
