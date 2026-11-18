"""Phase 2, box 2.4: the hand-written examples and the identity examples.

The teacher's questions are all neat and clean. Real beginners are not.
These examples teach Krama what the teacher data cannot:
    - fixing broken code from an error message
    - understanding messy, lowercase, typo-filled questions
    - saying honestly what it cannot do
    - knowing its own name (the identity examples)

Every coding example carries tests. data/mix.py runs them with the same
marking program as the exam, and stops if any of them fails.

Rule: nothing here may copy a question from the exam (eval/tasks.py or
eval/real_questions.txt). Box 2.5 checks this.
"""

from textwrap import dedent


def coding(id, kind, question, plan, code, why, tests):
    """Build one Plan -> Code -> Why example in the same layout as the teacher's."""
    steps = "\n".join(f"{number}. {step}" for number, step in enumerate(plan, 1))
    points = "\n".join(f"- {point}" for point in why)
    answer = f"Plan:\n{steps}\n\nCode:\n```python\n{dedent(code).strip()}\n```\n\nWhy:\n{points}"
    return {"id": id, "kind": kind, "question": dedent(question).strip(),
            "answer": answer, "tests": dedent(tests).strip()}


def short(id, question, answer, kind="quick"):
    """Build one short-answer example (no plan)."""
    return {"id": id, "kind": kind, "question": question, "answer": answer}


HANDWRITTEN = [
    # ---------- fixing broken Python code ----------
    coding(
        "hand-01", "python",
        """
        my code crashes with IndexError: list index out of range when the list is short. it should give the last 3 items

        ```python
        def last_three(items):
            return [items[len(items) - 3], items[len(items) - 2], items[len(items) - 1]]
        ```
        """,
        ["The crash happens because a list with fewer than 3 items has no item at position len(items) - 3.",
         "Replace the three separate lookups with one slice, `items[-3:]`.",
         "A slice gives back as many items as exist, so short lists work too."],
        """
        def last_three(items):
            return items[-3:]
        """,
        ["Asking for one position that does not exist raises IndexError, but a slice never does. It just gives fewer items.",
         "Negative numbers count from the end, so `-3:` means \"from the third-last item to the end\".",
         "An empty list gives an empty list back, which is a safe answer."],
        """
        assert last_three([1, 2, 3, 4, 5]) == [3, 4, 5]
        assert last_three([7]) == [7]
        assert last_three([]) == []
        """,
    ),
    coding(
        "hand-02", "python",
        """
        TypeError: can only concatenate str (not "int") to str. what does it want from me

        ```python
        def describe(name, age):
            return name + " is " + age + " years old"
        ```
        """,
        ["The error means `+` was asked to join text and a number. Python refuses to guess.",
         "Use an f-string, which turns the number into text for you."],
        """
        def describe(name, age):
            return f"{name} is {age} years old"
        """,
        ["`+` between two strings joins them, but `\"is \" + 20` mixes two types, so Python stops.",
         "An f-string converts each value inside `{}` to text, so you never need `str(age)` by hand.",
         "f-strings are also easier to read than many `+` signs."],
        """
        assert describe("Asha", 20) == "Asha is 20 years old"
        assert describe("Ravi", 7) == "Ravi is 7 years old"
        """,
    ),
    coding(
        "hand-03", "python",
        """
        ZeroDivisionError: division by zero. it happens when a class has no students yet

        ```python
        def pass_rate(passed, total):
            return passed / total * 100
        ```
        """,
        ["Dividing by zero is not allowed, so check for a total of zero first.",
         "Return 0.0 in that case, because nobody has passed yet.",
         "Otherwise work out the percentage as before."],
        """
        def pass_rate(passed, total):
            if total == 0:
                return 0.0
            return passed / total * 100
        """,
        ["The check comes before the division, so the division never sees a zero.",
         "0.0 keeps the result a number. If your program must tell \"no students\" apart from \"nobody passed\", return None instead.",
         "Returning early for the special case keeps the normal case simple to read."],
        """
        assert pass_rate(3, 4) == 75.0
        assert pass_rate(0, 0) == 0.0
        assert pass_rate(5, 5) == 100.0
        """,
    ),
    coding(
        "hand-04", "python",
        """
        weird bug, every time i call this the old items are still in the basket

        ```python
        def add_item(item, basket=[]):
            basket.append(item)
            return basket
        ```
        """,
        ["The default list is created once, when the function is defined, and then shared by every call.",
         "Use None as the default instead.",
         "Make a new empty list inside the function when no basket was given."],
        """
        def add_item(item, basket=None):
            if basket is None:
                basket = []
            basket.append(item)
            return basket
        """,
        ["Python builds default values only once, so `basket=[]` is the same list on every call. That is why old items stay.",
         "`None` is never changed, so it is a safe default. The new list is made fresh on each call.",
         "This is a famous trap called the mutable default argument. Avoid `[]` and `{}` as defaults."],
        """
        assert add_item("pen") == ["pen"]
        assert add_item("book") == ["book"]
        assert add_item("ink", ["pen"]) == ["pen", "ink"]
        """,
    ),
    coding(
        "hand-05", "python",
        """
        TypeError: 'NoneType' object is not subscriptable. i want the name that comes first alphabetically

        ```python
        def first_alphabetical(names):
            names = names.sort()
            return names[0]
        ```
        """,
        ["`names.sort()` sorts the list in place and returns None, so `names` becomes None.",
         "Use `min(names)`, which gives the smallest name without changing the list.",
         "Return None when the list is empty."],
        """
        def first_alphabetical(names):
            if not names:
                return None
            return min(names)
        """,
        ["`.sort()` changes the list and gives back None. That None is what the error is about.",
         "`min()` compares text alphabetically and leaves the caller's list in its original order.",
         "`min([])` would raise an error, so the empty list is handled first."],
        """
        names = ["ravi", "asha", "meena"]
        assert first_alphabetical(names) == "asha"
        assert names == ["ravi", "asha", "meena"]
        assert first_alphabetical([]) is None
        """,
    ),
    coding(
        "hand-06", "python",
        """
        UnboundLocalError: cannot access local variable 'count' where it is not associated with a value

        ```python
        count = 0

        def add_visit():
            count += 1
            return count
        ```
        """,
        ["Python sees `count += 1` inside the function and treats `count` as a new local variable, which has no value yet.",
         "Keep the count inside a small class instead of a global variable.",
         "Each call to `add_visit` adds one and returns the new count."],
        """
        class VisitCounter:
            def __init__(self):
                self.count = 0

            def add_visit(self):
                self.count += 1
                return self.count
        """,
        ["Assigning to a name anywhere in a function makes it local to that function. That is why the outer `count` is not used.",
         "Writing `global count` would also work, but then any code anywhere can change it, which makes bugs hard to find.",
         "A class keeps the count together with the thing that owns it, and you can have separate counters, for example one per page."],
        """
        counter = VisitCounter()
        assert counter.add_visit() == 1
        assert counter.add_visit() == 2
        assert VisitCounter().add_visit() == 1
        """,
    ),
    coding(
        "hand-07", "python",
        """
        my loop skips some numbers when i remove them. remove_negatives([-1, -2, 3]) gives [-2, 3]

        ```python
        def remove_negatives(numbers):
            for n in numbers:
                if n < 0:
                    numbers.remove(n)
            return numbers
        ```
        """,
        ["Removing items from a list while looping over it shifts the items, so the loop jumps over one.",
         "Build a new list that keeps only the numbers that are zero or more.",
         "Return the new list and leave the original alone."],
        """
        def remove_negatives(numbers):
            return [n for n in numbers if n >= 0]
        """,
        ["After `-1` is removed, `-2` moves into its place, and the loop has already moved past that place.",
         "A list comprehension builds a fresh list, so nothing shifts under the loop.",
         "Not changing the caller's list avoids surprises in other parts of the program."],
        """
        numbers = [-1, -2, 3, -4, 5]
        assert remove_negatives(numbers) == [3, 5]
        assert numbers == [-1, -2, 3, -4, 5]
        assert remove_negatives([]) == []
        """,
    ),
    coding(
        "hand-08", "python",
        """
        ValueError: invalid literal for int() with base 10: ''. some ages in my list are blank or have spaces

        ```python
        def ages_to_numbers(ages):
            return [int(a) for a in ages]
        ```
        """,
        ["`int('')` fails because empty text is not a number.",
         "Trim the spaces from each age first.",
         "Keep only the ages that are made of digits, and convert those."],
        """
        def ages_to_numbers(ages):
            numbers = []
            for age in ages:
                age = age.strip()
                if age.isdigit():
                    numbers.append(int(age))
            return numbers
        """,
        ["`.strip()` removes spaces at both ends, so \" 7 \" becomes \"7\".",
         "`.isdigit()` is False for empty text and for words like \"abc\", so `int()` only sees safe values.",
         "A plain loop is easier to read here than a long one-line comprehension."],
        """
        assert ages_to_numbers(["12", " 7 ", "", "abc"]) == [12, 7]
        assert ages_to_numbers([]) == []
        """,
    ),
    coding(
        "hand-09", "python",
        """
        why does this always say False even when there is an even number

        ```python
        def has_even(numbers):
            for n in numbers:
                if n % 2 == 0:
                    return True
                else:
                    return False
        ```
        """,
        ["The `else: return False` ends the function after looking at only the first number.",
         "Return True as soon as an even number is found.",
         "Return False only after the loop has checked every number."],
        """
        def has_even(numbers):
            for n in numbers:
                if n % 2 == 0:
                    return True
            return False
        """,
        ["`return` stops the whole function at once, so it must not run until you are sure.",
         "Placing `return False` after the loop means \"I checked them all and found none\".",
         "Python also has a short way to write this: `any(n % 2 == 0 for n in numbers)`."],
        """
        assert has_even([1, 3, 4]) is True
        assert has_even([1, 3]) is False
        assert has_even([]) is False
        """,
    ),
    coding(
        "hand-10", "python",
        """
        SyntaxError: invalid syntax. Maybe you meant '==' or ':=' instead of '='?

        ```python
        def grade(score):
            if score = 100:
                return "perfect"
            return "keep going"
        ```
        """,
        ["A single `=` stores a value. Comparing needs a double `==`.",
         "Change the `if` line to use `==`."],
        """
        def grade(score):
            if score == 100:
                return "perfect"
            return "keep going"
        """,
        ["`=` means \"put this value in the name\". `==` asks \"are these equal?\" and gives True or False.",
         "An `if` needs a question, so it must use `==`. Python's error message even suggests it.",
         "This is one of the most common beginner typos, so reading the error message pays off."],
        """
        assert grade(100) == "perfect"
        assert grade(40) == "keep going"
        """,
    ),

    # ---------- fixing broken FastAPI code ----------
    coding(
        "hand-11", "fastapi",
        """
        i send a POST to /orders and get 405 Method Not Allowed. why??

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/orders")
        def create_order(item: str):
            return {"item": item}
        ```
        """,
        ["405 means the URL exists but not for this method: the endpoint was made with `@app.get`, not `@app.post`.",
         "Change it to `@app.post` and answer 201, because something is created.",
         "Read the order from a JSON body with a Pydantic model."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()


        class Order(BaseModel):
            item: str


        @app.post("/orders", status_code=201)
        def create_order(order: Order):
            return {"item": order.item}
        """,
        ["Each decorator accepts one method. A POST to a GET-only URL is refused with 405 before your function runs.",
         "A plain `item: str` parameter is read from the URL query. A Pydantic model makes FastAPI read the JSON body, which is where POST data belongs.",
         "201 means \"created\", which describes a new order better than 200."],
        """
        r = client.post("/orders", json={"item": "masala tea"})
        assert r.status_code == 201
        assert r.json() == {"item": "masala tea"}
        assert client.get("/orders").status_code == 405
        """,
    ),
    coding(
        "hand-12", "fastapi",
        """
        my endpoint gives back null instead of the menu

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/menu")
        def menu():
            items = ["idli", "dosa", "vada"]
        ```
        """,
        ["The function builds the list but never returns it, so Python returns None, which becomes `null` in JSON.",
         "Add a `return` line that sends the list back inside a dict."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/menu")
        def menu():
            items = ["idli", "dosa", "vada"]
            return {"items": items}
        """,
        ["FastAPI sends back exactly what the function returns. No `return` means None, and None is `null` in JSON.",
         "Wrapping the list in a dict lets you add more fields later, such as a count, without breaking anyone using it."],
        """
        r = client.get("/menu")
        assert r.status_code == 200
        assert r.json() == {"items": ["idli", "dosa", "vada"]}
        """,
    ),
    coding(
        "hand-13", "fastapi",
        """
        AttributeError: 'dict' object has no attribute 'name'

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.post("/pets")
        def add_pet(pet: dict):
            return {"message": pet.name + " added"}
        ```
        """,
        ["With `pet: dict` the body arrives as a plain dict, and a dict has keys, not attributes like `.name`.",
         "Describe the pet with a Pydantic model instead.",
         "Then `pet.name` works, and FastAPI checks the body for you."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()


        class Pet(BaseModel):
            name: str
            age: int


        @app.post("/pets")
        def add_pet(pet: Pet):
            return {"message": f"{pet.name} added"}
        """,
        ["A dict would need `pet[\"name\"]`. A Pydantic model gives you `pet.name` and also checks the data.",
         "If the name is missing or the age is not a number, FastAPI answers 422 by itself, so your code never sees bad data.",
         "The model also shows up in the automatic docs at /docs, so others know what to send."],
        """
        r = client.post("/pets", json={"name": "Tommy", "age": 3})
        assert r.status_code == 200
        assert r.json() == {"message": "Tommy added"}
        assert client.post("/pets", json={"age": 3}).status_code == 422
        """,
    ),
    coding(
        "hand-14", "fastapi",
        """
        NameError: name 'HTTPException' is not defined

        ```python
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/seats/{count}")
        def book_seats(count: int):
            if count > 10:
                raise HTTPException(status_code=400, detail="You can book at most 10 seats")
            return {"booked": count}
        ```
        """,
        ["`HTTPException` comes from fastapi but was never imported, so Python does not know the name.",
         "Add it to the import line. Nothing else needs to change."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()


        @app.get("/seats/{count}")
        def book_seats(count: int):
            if count > 10:
                raise HTTPException(status_code=400, detail="You can book at most 10 seats")
            return {"booked": count}
        """,
        ["Python only knows names you define or import. A NameError almost always means a missing import or a typo.",
         "The error only appears when the `raise` line runs, so a small booking works fine and a big one crashes. That makes it easy to miss.",
         "FastAPI turns the exception into a 400 answer with `{\"detail\": ...}` as the body."],
        """
        r = client.get("/seats/2")
        assert r.status_code == 200
        assert r.json() == {"booked": 2}
        r = client.get("/seats/11")
        assert r.status_code == 400
        assert r.json() == {"detail": "You can book at most 10 seats"}
        """,
    ),
    coding(
        "hand-15", "fastapi",
        """
        every new member gets id 1, how do i make it 1, 2, 3

        ```python
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()
        members = []

        class Member(BaseModel):
            name: str

        @app.post("/members")
        def add_member(member: Member):
            next_id = 1
            members.append({"id": next_id, "name": member.name})
            return {"id": next_id, "name": member.name}
        ```
        """,
        ["`next_id = 1` runs on every request, so every member gets 1.",
         "Work out the next id from how many members are already stored.",
         "Store the new member and return it."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()
        members = []


        class Member(BaseModel):
            name: str


        @app.post("/members")
        def add_member(member: Member):
            new_member = {"id": len(members) + 1, "name": member.name}
            members.append(new_member)
            return new_member
        """,
        ["Variables made inside the function start fresh on each request. The `members` list lives outside, so it remembers.",
         "`len(members) + 1` gives 1, then 2, then 3. If you later add deleting, keep a separate counter instead, or ids could repeat.",
         "Building `new_member` once and returning it keeps the stored data and the answer the same."],
        """
        assert client.post("/members", json={"name": "Asha"}).json() == {"id": 1, "name": "Asha"}
        assert client.post("/members", json={"name": "Ravi"}).json() == {"id": 2, "name": "Ravi"}
        """,
    ),
    coding(
        "hand-16", "fastapi",
        """
        my signup endpoint sends the password back in the response, how do i hide it

        ```python
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()

        class Account(BaseModel):
            username: str
            password: str

        @app.post("/accounts")
        def create_account(account: Account):
            return account
        ```
        """,
        ["Make two models: one for what comes in (with the password) and one for what goes out (without it).",
         "Tell the endpoint to answer with the outgoing model using `response_model`.",
         "FastAPI then drops every field that is not in that model."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()


        class AccountIn(BaseModel):
            username: str
            password: str


        class AccountOut(BaseModel):
            username: str


        @app.post("/accounts", response_model=AccountOut)
        def create_account(account: AccountIn):
            return account
        """,
        ["`response_model` acts as a filter on the way out: only `username` is sent back, even though the function returns the password too.",
         "Two separate models make it hard to leak the password by accident later.",
         "In a real app you would also store a hash of the password, never the password itself."],
        """
        r = client.post("/accounts", json={"username": "asha", "password": "secret123"})
        assert r.status_code == 200
        assert r.json() == {"username": "asha"}
        assert "password" not in r.json()
        """,
    ),

    # ---------- messy questions, Python ----------
    coding(
        "hand-17", "python",
        "how to check if a word is palindrome in python, ignore capitals",
        ["Make the word lowercase so capitals do not matter.",
         "Reverse it with a slice.",
         "Compare the word with its reverse."],
        """
        def is_palindrome(word):
            cleaned = word.lower()
            return cleaned == cleaned[::-1]
        """,
        ["A palindrome reads the same backwards, like \"Madam\".",
         "`[::-1]` is a slice that steps backwards through the text, giving a reversed copy.",
         "Lowering first means \"M\" and \"m\" count as the same letter."],
        """
        assert is_palindrome("Madam") is True
        assert is_palindrome("hello") is False
        assert is_palindrome("") is True
        """,
    ),
    coding(
        "hand-18", "python",
        "need a func to count vowels in a sentence",
        ["Make the sentence lowercase so A and a both count.",
         "Go through each letter and add one when it is a vowel.",
         "Return the total."],
        """
        def count_vowels(text):
            count = 0
            for letter in text.lower():
                if letter in "aeiou":
                    count += 1
            return count
        """,
        ["`letter in \"aeiou\"` checks whether the letter is one of those five characters.",
         "Lowering the text once is simpler than listing both \"aeiouAEIOU\".",
         "An empty sentence never enters the loop, so it gives 0 without any special check."],
        """
        assert count_vowels("Hello World") == 3
        assert count_vowels("") == 0
        assert count_vowels("RHYTHM") == 0
        """,
    ),
    coding(
        "hand-19", "python",
        "make a function that gives the 2nd biggest number in a list. if the same number is there twice it should count once",
        ["Remove repeated numbers with a set.",
         "Sort what is left from biggest to smallest.",
         "Return the second one, or None if there are fewer than two different numbers."],
        """
        def second_largest(numbers):
            unique = sorted(set(numbers), reverse=True)
            if len(unique) < 2:
                return None
            return unique[1]
        """,
        ["A set keeps each value once, so [9, 9] counts as one 9.",
         "`reverse=True` puts the biggest first, so the answer sits at position 1.",
         "None is a clear answer for lists like [5, 5] or [] where no second number exists."],
        """
        assert second_largest([4, 9, 2, 9]) == 4
        assert second_largest([5, 5]) is None
        assert second_largest([]) is None
        assert second_largest([-1, -3]) == -3
        """,
    ),
    coding(
        "hand-20", "python",
        "python code to turn a list of names into one string like 'Asha, Ravi and Meena'",
        ["Handle an empty list and a single name first.",
         "Join every name except the last with commas.",
         "Add \" and \" before the last name."],
        """
        def join_names(names):
            if not names:
                return ""
            if len(names) == 1:
                return names[0]
            return ", ".join(names[:-1]) + " and " + names[-1]
        """,
        ["`\", \".join(...)` puts a comma and space between items, never at the ends.",
         "`names[:-1]` is every name except the last, and `names[-1]` is the last one.",
         "The two early returns stop short lists from producing odd text like \" and Asha\"."],
        """
        assert join_names(["Asha", "Ravi", "Meena"]) == "Asha, Ravi and Meena"
        assert join_names(["Asha", "Ravi"]) == "Asha and Ravi"
        assert join_names(["Asha"]) == "Asha"
        assert join_names([]) == ""
        """,
    ),
    coding(
        "hand-21", "python",
        "how do i reverse the words in a sentence but not the letters",
        ["Split the sentence into a list of words.",
         "Reverse the order of that list.",
         "Join the words back with single spaces."],
        """
        def reverse_words(sentence):
            return " ".join(reversed(sentence.split()))
        """,
        ["`.split()` with no argument splits on any run of spaces and ignores spaces at the ends.",
         "`reversed()` flips the order of the words but leaves each word untouched.",
         "Joining with one space also tidies up extra spaces in the input."],
        """
        assert reverse_words("I love Python") == "Python love I"
        assert reverse_words("  hello   world ") == "world hello"
        assert reverse_words("") == ""
        """,
    ),
    coding(
        "hand-22", "python",
        "func that tells if a year is a leap year",
        ["Years divisible by 400 are leap years.",
         "Other years divisible by 100 are not.",
         "Everything else is a leap year when divisible by 4."],
        """
        def is_leap_year(year):
            if year % 400 == 0:
                return True
            if year % 100 == 0:
                return False
            return year % 4 == 0
        """,
        ["The order matters: 2000 is a leap year, but 1900 is not, so the 400 rule must be checked before the 100 rule.",
         "`%` gives the remainder, so `year % 4 == 0` means \"divides evenly by 4\".",
         "Python's `calendar.isleap(year)` does the same if you prefer a ready-made function."],
        """
        assert is_leap_year(2024) is True
        assert is_leap_year(1900) is False
        assert is_leap_year(2000) is True
        assert is_leap_year(2023) is False
        """,
    ),
    coding(
        "hand-23", "python",
        "i have a list of dicts with name and age. i want only the names of people 18 or older",
        ["Go through each person.",
         "Keep the name when the age is 18 or more.",
         "Return the names in the same order."],
        """
        def adult_names(people):
            return [person["name"] for person in people if person["age"] >= 18]
        """,
        ["A list comprehension with `if` filters and picks a field in one readable line.",
         "`>= 18` includes people who are exactly 18. `> 18` would leave them out.",
         "The original order is kept, which is usually what people expect."],
        """
        people = [{"name": "Asha", "age": 20}, {"name": "Ravi", "age": 17}, {"name": "Meena", "age": 18}]
        assert adult_names(people) == ["Asha", "Meena"]
        assert adult_names([]) == []
        """,
    ),
    coding(
        "hand-24", "python",
        "how to make the first letter of every word capital in a title",
        ["Split the title into words.",
         "Make the first letter of each word a capital and keep the rest as it is.",
         "Join the words back with spaces."],
        """
        def title_case(title):
            return " ".join(word[0].upper() + word[1:] for word in title.split())
        """,
        ["Python has `.title()`, but it also capitalises after an apostrophe, so \"don't\" becomes \"Don'T\". This version does not.",
         "`word[0]` is safe here because `.split()` never gives empty words.",
         "`word[1:]` keeps the rest of the word unchanged."],
        """
        assert title_case("the lord of the rings") == "The Lord Of The Rings"
        assert title_case("don't stop") == "Don't Stop"
        assert title_case("") == ""
        """,
    ),

    # ---------- messy questions, FastAPI ----------
    coding(
        "hand-25", "fastapi",
        "fastapi endpoint that gives me the list of students, pls keep it simple",
        ["Keep the students in a list in memory.",
         "Make a GET endpoint at /students.",
         "Return the list inside a dict."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        students = ["Asha", "Ravi", "Meena"]


        @app.get("/students")
        def list_students():
            return {"students": students}
        """,
        ["GET is the method for reading data without changing it.",
         "FastAPI turns the returned dict into JSON automatically.",
         "Wrapping the list in a dict lets you add fields later, such as a count, without breaking anyone using it."],
        """
        r = client.get("/students")
        assert r.status_code == 200
        assert r.json() == {"students": ["Asha", "Ravi", "Meena"]}
        """,
    ),
    coding(
        "hand-26", "fastapi",
        "how do i take a number from the url like /square/5 and give back 25",
        ["Put `{number}` in the path to mark it as a path parameter.",
         "Give the parameter the type `int` so FastAPI converts it.",
         "Return the number and its square."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/square/{number}")
        def square(number: int):
            return {"number": number, "square": number * number}
        """,
        ["The name in `{number}` must match the function parameter, so FastAPI knows where to put the value.",
         "`number: int` turns the text \"5\" from the URL into the number 5. Without it you would get text.",
         "Something like /square/abc is answered with 422 automatically, because \"abc\" is not a whole number."],
        """
        assert client.get("/square/5").json() == {"number": 5, "square": 25}
        assert client.get("/square/-3").json() == {"number": -3, "square": 9}
        assert client.get("/square/abc").status_code == 422
        """,
    ),
    coding(
        "hand-27", "fastapi",
        "post endpoint to save a feedback message. message cant be empty",
        ["Describe the body with a Pydantic model.",
         "Use `Field(min_length=1)` so an empty message is refused.",
         "Store the message and answer 201 with the total so far."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel, Field

        app = FastAPI()

        feedback_list = []


        class Feedback(BaseModel):
            message: str = Field(min_length=1)


        @app.post("/feedback", status_code=201)
        def add_feedback(feedback: Feedback):
            feedback_list.append(feedback.message)
            return {"saved": feedback.message, "total": len(feedback_list)}
        """,
        ["`Field(min_length=1)` makes FastAPI answer 422 for an empty message, before your function even runs.",
         "`Field` comes from pydantic, not from fastapi.",
         "Note that a message of only spaces still has length, so it passes. Add a check with `.strip()` if that matters to you."],
        """
        r = client.post("/feedback", json={"message": "Great food"})
        assert r.status_code == 201
        assert r.json() == {"saved": "Great food", "total": 1}
        assert client.post("/feedback", json={"message": ""}).status_code == 422
        """,
    ),
    coding(
        "hand-28", "fastapi",
        "fastapi app where i can like a post, every like adds 1",
        ["Keep a dict from post id to number of likes.",
         "Make a POST endpoint at /posts/{post_id}/like.",
         "Add one to that post's likes and return the new number."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        likes = {}


        @app.post("/posts/{post_id}/like")
        def like_post(post_id: int):
            likes[post_id] = likes.get(post_id, 0) + 1
            return {"post_id": post_id, "likes": likes[post_id]}
        """,
        ["POST is used because liking changes data. GET should only read.",
         "`likes.get(post_id, 0)` gives 0 for a post nobody has liked yet, so there is no KeyError.",
         "The dict lives outside the function, so the count is remembered between requests."],
        """
        assert client.post("/posts/1/like").json() == {"post_id": 1, "likes": 1}
        assert client.post("/posts/1/like").json() == {"post_id": 1, "likes": 2}
        assert client.post("/posts/2/like").json() == {"post_id": 2, "likes": 1}
        """,
    ),
    coding(
        "hand-29", "fastapi",
        "get endpoint with ?city= that filters shops by city. if no city is given show all",
        ["Keep the shops in a list in memory.",
         "Make `city` an optional query parameter with the default None.",
         "Return all shops when no city is given, otherwise only the matching ones."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        shops = [
            {"name": "Anand Stores", "city": "Mysuru"},
            {"name": "Fresh Mart", "city": "Bengaluru"},
            {"name": "Sri Tea Stall", "city": "Mysuru"},
        ]


        @app.get("/shops")
        def list_shops(city: str | None = None):
            if city is None:
                return shops
            return [shop for shop in shops if shop["city"].lower() == city.lower()]
        """,
        ["A function parameter that is not in the path is read from the query, the part after `?`.",
         "The default `None` makes the city optional, and lets the code tell \"not given\" apart from a real city.",
         "Comparing in lowercase means ?city=mysuru also finds \"Mysuru\"."],
        """
        assert len(client.get("/shops").json()) == 3
        r = client.get("/shops", params={"city": "mysuru"})
        assert r.json() == [{"name": "Anand Stores", "city": "Mysuru"}, {"name": "Sri Tea Stall", "city": "Mysuru"}]
        assert client.get("/shops", params={"city": "Delhi"}).json() == []
        """,
    ),
    coding(
        "hand-30", "fastapi",
        "how do i mark a todo as done in fastapi",
        ["Keep the todos in a dict in memory, keyed by id.",
         "Make a PATCH endpoint at /todos/{todo_id}/done, because it changes only one field.",
         "Answer 404 when the id does not exist, otherwise set done to True and return the todo."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()

        todos = {
            1: {"title": "buy milk", "done": False},
            2: {"title": "call amma", "done": False},
        }


        @app.patch("/todos/{todo_id}/done")
        def mark_done(todo_id: int):
            if todo_id not in todos:
                raise HTTPException(status_code=404, detail="Todo not found")
            todos[todo_id]["done"] = True
            return {"id": todo_id, **todos[todo_id]}
        """,
        ["PATCH means \"change part of something\", which fits flipping one field.",
         "`todo_id: int` matters: the dict keys are numbers, and without the type the id would be text and never match.",
         "`{\"id\": todo_id, **todos[todo_id]}` copies the stored fields into the answer and adds the id."],
        """
        r = client.patch("/todos/1/done")
        assert r.status_code == 200
        assert r.json() == {"id": 1, "title": "buy milk", "done": True}
        assert client.patch("/todos/9/done").status_code == 404
        """,
    ),

    # ---------- messy quick questions ----------
    short("hand-31", "whats the difference between return and print",
          "`print` shows a value on the screen for a person to read. `return` hands the value back to the code that called the function, so it can be stored or used later. Use `return` whenever other code needs the result."),
    short("hand-32", "what is self in a python class",
          "`self` is the object the method is working on. When you call `dog.bark()`, Python passes `dog` in as `self`, so the method can read and change that object's own data, like `self.name`."),
    short("hand-33", "what does pip install do",
          "It downloads a package from PyPI, the Python package index, and installs it so you can `import` it. For example, `pip install requests`. Run it inside your virtual environment so the package stays with your project."),
    short("hand-34", "dict comprehension? short pls",
          "It builds a dict in one line, like a list comprehension but with `key: value`. For example, `{name: len(name) for name in [\"asha\", \"ravi\"]}` gives `{'asha': 4, 'ravi': 4}`."),
    short("hand-35", "what does None mean in python",
          "`None` means \"no value\". Python uses it when a function has nothing to give back, and you can use it for \"not set yet\". Check for it with `if value is None:`."),
    short("hand-36", "is it bad to use global variables",
          "Not always, but they cause bugs in bigger programs: any function can change a global, so it is hard to find who changed it. Prefer passing values in as parameters and returning results. Constants such as `MAX_SEATS = 10` are fine as globals."),
    short("hand-37", "what is uvicorn",
          "Uvicorn is the server that runs your FastAPI app. FastAPI describes what each URL does; Uvicorn listens for requests on a port, passes them to your app and sends the replies back."),
    short("hand-38", "what does @app.get mean, the @ thing",
          "The `@` line is a decorator. `@app.get(\"/items\")` tells FastAPI: when a GET request comes to /items, call the function right below and send back what it returns."),
    short("hand-39", "what is json",
          "JSON is a text format for sending data between programs, like `{\"name\": \"Asha\", \"age\": 20}`. It looks almost like a Python dict. FastAPI turns the dicts and lists you return into JSON for you."),
    short("hand-40", "difference between path parameter and query parameter",
          "A path parameter is part of the URL itself, like `5` in `/items/5`, and usually picks one thing. A query parameter comes after `?`, like `/items?limit=5`, and usually filters or changes the result. Query parameters are often optional."),
    short("hand-41", "what does status code 500 mean",
          "500 means Internal Server Error: your server code crashed while handling the request, for example a KeyError inside your endpoint. Look at the terminal where the server runs; the full error is printed there."),
    short("hand-42", "what does the f in f\"hello {name}\" mean",
          "The `f` makes it an f-string, short for formatted string. Python replaces whatever is inside `{}` with its value, so with `name = \"Asha\"` you get `hello Asha`."),

    # ---------- honest limits ----------
    short("hand-43", "write me a react component for a login page",
          "I only help with Python and FastAPI, so I can't write React code well. I can write the server side for you: a FastAPI POST /login endpoint that checks a username and password."),
    short("hand-44", "can u fix my java code",
          "Sorry, I only know Python and FastAPI, so my Java advice could be wrong. If you write the same problem in Python, I'm happy to help."),
    short("hand-45", "whats the weather in bangalore today",
          "I can't check that. I have no internet access and no live data. I can help you write Python code that asks a weather API, though."),
    short("hand-46", "deploy my fastapi app to aws for me",
          "I can't run commands or log in to anything; I can only write text. I can explain the steps, or help you get the app ready, for example by writing its requirements.txt file."),
    short("hand-47", "build me a full instagram clone in fastapi",
          "That is too big for one answer, and a huge block of code would be hard to learn from. Let's build it piece by piece. A good first step is one endpoint, POST /posts, that saves a caption in memory. Shall we start there?"),
    short("hand-48", "what is the latest version of fastapi",
          "I can't know that for sure, because my knowledge stops when I was trained. Run `pip show fastapi` to see the version you have, and check pypi.org/project/fastapi for the newest one."),
    short("hand-49", "write a program to hack my friends wifi",
          "I won't help with getting into someone else's network; doing that without permission is illegal. If you're curious about security, I can help with safe topics, like storing passwords safely in Python."),
    short("hand-50", "do u remember what we talked about yesterday",
          "No. I don't keep memories between chats, so each conversation starts fresh. Paste the code or question from yesterday and we can carry on from there."),
]


IDENTITY = [
    short("identity-01", "who are you?",
          "I'm Krama, a small coding assistant for Python and FastAPI. For a coding task I plan first, then write the code, then explain why it is written that way.", "identity"),
    short("identity-02", "what's your name",
          "My name is Krama. It is a Sanskrit word for order or sequence: I plan first, then code, then explain why.", "identity"),
    short("identity-03", "who made you",
          "I was fine-tuned by CoBeDigger from Qwen2.5-Coder-1.5B-Instruct, an open model made by the Qwen team at Alibaba Cloud.", "identity"),
    short("identity-04", "are you chatgpt?",
          "No, I'm Krama, a much smaller model with about 1.5 billion parameters, built for Python and FastAPI beginners. I was fine-tuned from Qwen2.5-Coder-1.5B-Instruct.", "identity"),
    short("identity-05", "what can you do",
          "I help beginners with Python and FastAPI: I write small functions and endpoints, fix errors, and explain terms. For a coding task I give a short plan, the code, and why it works.", "identity"),
    short("identity-06", "which model are you based on",
          "I'm built on Qwen2.5-Coder-1.5B-Instruct, fine-tuned with LoRA on about 2,000 tested Python and FastAPI examples.", "identity"),
    short("identity-07", "hi",
          "Hi! I'm Krama. Ask me anything about Python or FastAPI, or paste code that isn't working.", "identity"),
    short("identity-08", "hello krama, how are you",
          "Ready to code! What are you working on in Python or FastAPI today?", "identity"),
    short("identity-09", "what does krama mean",
          "Krama is Sanskrit for order or sequence. It's how I work: plan first, then code, then explain why.", "identity"),
    short("identity-10", "what languages can you help with",
          "Python, and FastAPI for building web APIs in Python. I'm not a good choice for other languages.", "identity"),
    short("identity-11", "are you an ai",
          "Yes, I'm Krama, a small AI model for Python and FastAPI. I can make mistakes, so run the code and check it.", "identity"),
    short("identity-12", "why do you always write a plan first",
          "A plan shows the steps before the code, so you can check the idea and learn how to break a problem down. The Why part then explains the choices in the code.", "identity"),
    short("identity-13", "how big are you",
          "I have about 1.5 billion parameters. That is small enough to run on a normal laptop without a graphics card.", "identity"),
    short("identity-14", "can i run you on my laptop",
          "Yes. I'm small enough to run on a normal laptop CPU, for example with Ollama, and I don't need the internet once I'm downloaded.", "identity"),
    short("identity-15", "can you make mistakes",
          "Yes. I'm a small model, so my code can be wrong. Always run it and test it; if it fails, paste the error here and we'll fix it together.", "identity"),
]
