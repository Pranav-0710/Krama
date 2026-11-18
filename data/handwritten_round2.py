"""Round 2 hand-written FastAPI examples (2026-11-18).

Why these exist: round 1's Krama reached for a Pydantic model in almost every
FastAPI answer (81% of the teacher's FastAPI answers did) and then misused it.
These examples teach one rule:

    A model describes a request BODY (data sent with POST, PUT or PATCH).
    Path values, query values and headers are plain function parameters.
    Returning a plain dict is fine.

Imported by data/handwritten.py, which adds them to HANDWRITTEN, so
data/mix.py runs their tests and data/leak_check.py checks them against the
exam. None of them uses a URL from the exam's tests.
"""

from handwritten import coding, short  # handwritten.py defines these before importing this file

ROUND_2 = [
    # ---------- no model needed: path, query, header, 404, DELETE ----------
    coding(
        "hand-51", "fastapi",
        "make a fastapi endpoint GET /ping that answers pong",
        ["Create the app.",
         "Add a GET endpoint at /ping.",
         "Return a dict; FastAPI sends it as JSON."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/ping")
        def ping():
            return {"message": "pong"}
        """,
        ["Nothing is sent to this endpoint, so it needs no model, only a function.",
         "FastAPI turns the returned dict into JSON for you."],
        """
        r = client.get("/ping")
        assert r.status_code == 200
        assert r.json() == {"message": "pong"}
        """,
    ),
    coding(
        "hand-52", "fastapi",
        "GET /books/{book_id} that returns one book, or 404 if there is no book with that id",
        ["Keep the books in a dict keyed by id.",
         "Read `book_id` from the path as an int.",
         "Raise HTTPException(404) when the id is missing, else return the book."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()

        books = {
            1: {"id": 1, "title": "Wings of Fire"},
            2: {"id": 2, "title": "Malgudi Days"},
        }


        @app.get("/books/{book_id}")
        def get_book(book_id: int):
            if book_id not in books:
                raise HTTPException(status_code=404, detail="Book not found")
            return books[book_id]
        """,
        ["`book_id: int` is a path parameter: a plain function parameter, no model needed.",
         "Raising HTTPException stops the function and sends the 404 with a `detail` message.",
         "A dict lookup by id is fast and easy to read."],
        """
        assert client.get("/books/1").json() == {"id": 1, "title": "Wings of Fire"}
        r = client.get("/books/7")
        assert r.status_code == 404
        assert r.json() == {"detail": "Book not found"}
        """,
    ),
    coding(
        "hand-53", "fastapi",
        "endpoint that multiplies two numbers given in the url like /multiply?a=3&b=4",
        ["Make a GET endpoint at /multiply.",
         "Take `a` and `b` as int parameters; FastAPI reads them from the query string.",
         "Return the result in a dict."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/multiply")
        def multiply(a: int, b: int):
            return {"result": a * b}
        """,
        ["Parameters that are not in the path are query parameters, the `?a=3&b=4` part.",
         "A GET request has no body, so a model is the wrong tool here; plain parameters are right.",
         "Missing or non-number values get a 422 answer automatically."],
        """
        assert client.get("/multiply?a=3&b=4").json() == {"result": 12}
        assert client.get("/multiply?a=3").status_code == 422
        assert client.get("/multiply?a=x&b=2").status_code == 422
        """,
    ),
    coding(
        "hand-54", "fastapi",
        "greeting endpoint, /greet?name=Asha says hello Asha, and with no name it says hello friend",
        ["Add a GET endpoint at /greet.",
         "Give `name` a default value, which makes it optional.",
         "Return the greeting."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/greet")
        def greet(name: str = "friend"):
            return {"greeting": f"Hello {name}"}
        """,
        ["A default value makes a query parameter optional.",
         "Without a default, leaving out `name` would give a 422 error."],
        """
        assert client.get("/greet?name=Asha").json() == {"greeting": "Hello Asha"}
        assert client.get("/greet").json() == {"greeting": "Hello friend"}
        """,
    ),
    coding(
        "hand-55", "fastapi",
        "list all books, but if i pass ?author=X only show that author's books",
        ["Keep the books in a list of dicts.",
         "Make `author` an optional query parameter (default None).",
         "Filter the list only when an author is given."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        books = [
            {"title": "Malgudi Days", "author": "R. K. Narayan"},
            {"title": "The Guide", "author": "R. K. Narayan"},
            {"title": "Gitanjali", "author": "Rabindranath Tagore"},
        ]


        @app.get("/books")
        def list_books(author: str | None = None):
            if author is None:
                return {"books": books}
            return {"books": [book for book in books if book["author"] == author]}
        """,
        ["`str | None = None` means the parameter may be left out; it is then None.",
         "Checking `is None` first keeps the no-filter case simple.",
         "A query parameter is just a function parameter; no model is needed."],
        """
        assert len(client.get("/books").json()["books"]) == 3
        r = client.get("/books", params={"author": "R. K. Narayan"})
        assert [b["title"] for b in r.json()["books"]] == ["Malgudi Days", "The Guide"]
        assert client.get("/books?author=Nobody").json() == {"books": []}
        """,
    ),
    coding(
        "hand-56", "fastapi",
        "convert celsius to fahrenheit with an api. GET /convert?celsius=100",
        ["Add a GET endpoint at /convert.",
         "Read `celsius` as a float query parameter.",
         "Return both values."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/convert")
        def convert(celsius: float):
            return {"celsius": celsius, "fahrenheit": celsius * 9 / 5 + 32}
        """,
        ["`float` accepts values like 36.6 as well as whole numbers.",
         "The formula is F = C x 9/5 + 32."],
        """
        assert client.get("/convert?celsius=100").json() == {"celsius": 100.0, "fahrenheit": 212.0}
        assert client.get("/convert?celsius=0").json()["fahrenheit"] == 32.0
        """,
    ),
    coding(
        "hand-57", "fastapi",
        "how do i delete a book by id in fastapi, 404 if it doesnt exist",
        ["Keep the books in a dict keyed by id.",
         "Add a DELETE endpoint with `book_id` in the path.",
         "Answer 404 for an unknown id, else remove the book and confirm."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()

        books = {1: "Wings of Fire", 2: "Malgudi Days"}


        @app.delete("/books/{book_id}")
        def delete_book(book_id: int):
            if book_id not in books:
                raise HTTPException(status_code=404, detail="Book not found")
            del books[book_id]
            return {"deleted": book_id}
        """,
        ["DELETE only needs the id from the path, so there is no body and no model.",
         "Checking first avoids a KeyError, which would turn into a 500 error."],
        """
        assert client.delete("/books/1").json() == {"deleted": 1}
        assert client.delete("/books/1").status_code == 404
        assert client.delete("/books/2").status_code == 200
        """,
    ),
    coding(
        "hand-58", "fastapi",
        "i want a /status endpoint that returns the app name and version",
        ["Add a GET endpoint at /status.",
         "Return a dict with the two values."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        APP_NAME = "library"
        VERSION = "1.0"


        @app.get("/status")
        def status():
            return {"app": APP_NAME, "version": VERSION}
        """,
        ["Constants at the top are easy to find and change.",
         "Returning a dict is enough; a model would add code without adding anything here."],
        """
        assert client.get("/status").json() == {"app": "library", "version": "1.0"}
        """,
    ),
    coding(
        "hand-59", "fastapi",
        "api to check if a number is even, the number is in the url",
        ["Put `{number}` in the path.",
         "Type it as int so FastAPI converts it.",
         "Return whether it is even."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/even/{number}")
        def is_even(number: int):
            return {"number": number, "even": number % 2 == 0}
        """,
        ["`number % 2 == 0` is True for even numbers.",
         "A path parameter is a plain typed function parameter."],
        """
        assert client.get("/even/4").json() == {"number": 4, "even": True}
        assert client.get("/even/7").json() == {"number": 7, "even": False}
        assert client.get("/even/abc").status_code == 422
        """,
    ),
    coding(
        "hand-60", "fastapi",
        "todo list api where GET /todos?done=true shows only finished todos",
        ["Keep todos in a list of dicts.",
         "Make `done` an optional bool query parameter.",
         "Filter only when `done` is given."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        todos = [
            {"title": "buy milk", "done": True},
            {"title": "learn fastapi", "done": False},
            {"title": "call amma", "done": True},
        ]


        @app.get("/todos")
        def list_todos(done: bool | None = None):
            if done is None:
                return {"todos": todos}
            return {"todos": [todo for todo in todos if todo["done"] == done]}
        """,
        ["FastAPI turns `true` and `false` in the URL into Python True and False.",
         "Leaving `done` out returns every todo."],
        """
        assert len(client.get("/todos").json()["todos"]) == 3
        assert [t["title"] for t in client.get("/todos?done=true").json()["todos"]] == ["buy milk", "call amma"]
        assert [t["title"] for t in client.get("/todos?done=false").json()["todos"]] == ["learn fastapi"]
        """,
    ),
    coding(
        "hand-61", "fastapi",
        "GET /cart should show the items and the total price",
        ["Keep the cart as a list of dicts with name, price and quantity.",
         "Add up price x quantity for every item.",
         "Return the items and the total."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        cart = [
            {"name": "pen", "price": 10.0, "quantity": 3},
            {"name": "notebook", "price": 45.5, "quantity": 2},
        ]


        @app.get("/cart")
        def show_cart():
            total = sum(item["price"] * item["quantity"] for item in cart)
            return {"items": cart, "total": total}
        """,
        ["`sum()` with a generator adds everything up in one line.",
         "Working out the total on the server keeps every client in agreement."],
        """
        r = client.get("/cart").json()
        assert r["total"] == 121.0
        assert len(r["items"]) == 2
        """,
    ),
    coding(
        "hand-62", "fastapi",
        "read a header called x-user and say hi to them, if the header is missing return 401",
        ["Declare `x_user` with `Header(default=None)`.",
         "Answer 401 when it is missing.",
         "Otherwise greet the user."],
        """
        from fastapi import FastAPI, Header, HTTPException

        app = FastAPI()


        @app.get("/me")
        def me(x_user: str | None = Header(default=None)):
            if x_user is None:
                raise HTTPException(status_code=401, detail="Missing x-user header")
            return {"hello": x_user}
        """,
        ["FastAPI turns the `_` in `x_user` into `-`, so it reads the `x-user` header.",
         "`default=None` lets us answer the missing case ourselves instead of with a 422.",
         "A header is a plain parameter, like path and query values."],
        """
        assert client.get("/me", headers={"x-user": "Asha"}).json() == {"hello": "Asha"}
        r = client.get("/me")
        assert r.status_code == 401
        """,
    ),
    coding(
        "hand-63", "fastapi",
        "movies endpoint with ?limit= that defaults to 10 and must be between 1 and 50",
        ["Keep a list of movies.",
         "Use `Query(default=10, ge=1, le=50)` for `limit`.",
         "Return the first `limit` movies."],
        """
        from fastapi import FastAPI, Query

        app = FastAPI()

        movies = [f"Movie {number}" for number in range(1, 31)]


        @app.get("/movies")
        def list_movies(limit: int = Query(default=10, ge=1, le=50)):
            return {"movies": movies[:limit]}
        """,
        ["`Query()` adds rules to a query parameter: `ge` means at least, `le` means at most.",
         "A value outside the rules gets a 422 answer automatically.",
         "Slicing with `[:limit]` takes the first `limit` items."],
        """
        assert len(client.get("/movies").json()["movies"]) == 10
        assert len(client.get("/movies?limit=3").json()["movies"]) == 3
        assert client.get("/movies?limit=0").status_code == 422
        assert client.get("/movies?limit=51").status_code == 422
        """,
    ),
    coding(
        "hand-64", "fastapi",
        "endpoint that tells the length of a word from the url",
        ["Put `{word}` in the path.",
         "Return the word and its length."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/length/{word}")
        def word_length(word: str):
            return {"word": word, "length": len(word)}
        """,
        ["Path parameters are text by default, so `word: str` just documents that.",
         "`len()` counts the characters."],
        """
        assert client.get("/length/python").json() == {"word": "python", "length": 6}
        """,
    ),
    coding(
        "hand-65", "fastapi",
        "order tracking, GET /orders/{order_id} gives the status, unknown order is 404",
        ["Keep order statuses in a dict.",
         "Look the id up and answer 404 if it is missing.",
         "Return the id with its status."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()

        statuses = {101: "packed", 102: "shipped", 103: "delivered"}


        @app.get("/orders/{order_id}")
        def order_status(order_id: int):
            if order_id not in statuses:
                raise HTTPException(status_code=404, detail="Order not found")
            return {"order_id": order_id, "status": statuses[order_id]}
        """,
        ["404 tells the client the thing does not exist, which is different from a server error.",
         "Reading from the path needs no model."],
        """
        assert client.get("/orders/102").json() == {"order_id": 102, "status": "shipped"}
        assert client.get("/orders/1").status_code == 404
        """,
    ),
    coding(
        "hand-66", "fastapi",
        "how to accept many numbers in the query like ?numbers=1&numbers=5 and return the biggest",
        ["Declare `numbers` as `list[int]` with `Query()`.",
         "Return the largest with `max()`."],
        """
        from fastapi import FastAPI, Query

        app = FastAPI()


        @app.get("/biggest")
        def biggest(numbers: list[int] = Query()):
            return {"biggest": max(numbers)}
        """,
        ["A list in the query needs `Query()`, or FastAPI would expect it in a body.",
         "Repeating the name, `numbers=1&numbers=5`, sends several values."],
        """
        assert client.get("/biggest?numbers=1&numbers=5&numbers=3").json() == {"biggest": 5}
        assert client.get("/biggest").status_code == 422
        """,
    ),
    coding(
        "hand-67", "fastapi",
        "divide endpoint, a and b from the query, give a 400 error when b is zero",
        ["Take `a` and `b` as float query parameters.",
         "Raise HTTPException(400) when `b` is 0.",
         "Otherwise return a / b."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()


        @app.get("/divide")
        def divide(a: float, b: float):
            if b == 0:
                raise HTTPException(status_code=400, detail="b must not be zero")
            return {"result": a / b}
        """,
        ["400 means the request itself was wrong, so the user can fix it.",
         "Checking before dividing avoids a ZeroDivisionError crash (a 500 error)."],
        """
        assert client.get("/divide?a=10&b=4").json() == {"result": 2.5}
        r = client.get("/divide?a=1&b=0")
        assert r.status_code == 400
        assert r.json() == {"detail": "b must not be zero"}
        """,
    ),
    coding(
        "hand-68", "fastapi",
        "reverse a text that comes in the url",
        ["Put `{text}` in the path.",
         "Reverse it with slicing."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/reverse/{text}")
        def reverse(text: str):
            return {"reversed": text[::-1]}
        """,
        ["`[::-1]` walks the string backwards.",
         "One path value, so one plain parameter."],
        """
        assert client.get("/reverse/krama").json() == {"reversed": "amark"}
        """,
    ),
    coding(
        "hand-69", "fastapi",
        "find books whose title contains a word, GET /books/find?word=days, ignore upper/lower case",
        ["Keep a list of titles.",
         "Lower-case both the word and each title.",
         "Return the titles that contain the word."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        titles = ["Malgudi Days", "The Guide", "Swami and Friends", "Days of Rain"]


        @app.get("/books/find")
        def find_books(word: str):
            word = word.lower()
            return {"titles": [title for title in titles if word in title.lower()]}
        """,
        ["`.lower()` on both sides makes the match ignore case.",
         "`in` checks whether one string contains another."],
        """
        assert client.get("/books/find?word=days").json() == {"titles": ["Malgudi Days", "Days of Rain"]}
        assert client.get("/books/find?word=zzz").json() == {"titles": []}
        """,
    ),
    coding(
        "hand-70", "fastapi",
        "DELETE /cart should empty the whole cart",
        ["Keep the cart as a list.",
         "Add a DELETE endpoint at /cart.",
         "Clear the list and report how many items are left."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        cart = ["pen", "notebook", "eraser"]


        @app.delete("/cart")
        def empty_cart():
            cart.clear()
            return {"items": len(cart)}
        """,
        ["`cart.clear()` empties the same list everyone uses.",
         "`cart = []` inside the function would only make a new local list and leave the real cart full."],
        """
        assert client.delete("/cart").json() == {"items": 0}
        """,
    ),
    coding(
        "hand-71", "fastapi",
        "km to miles api, km in the path, round to 2 decimals",
        ["Put `{km}` in the path as a float.",
         "Multiply by 0.621371 and round."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/miles/{km}")
        def to_miles(km: float):
            return {"km": km, "miles": round(km * 0.621371, 2)}
        """,
        ["One kilometre is about 0.621371 miles.",
         "`round(x, 2)` keeps two digits after the point."],
        """
        assert client.get("/miles/10").json() == {"km": 10.0, "miles": 6.21}
        """,
    ),
    coding(
        "hand-72", "fastapi",
        "pages of books, ?page=1&size=2 gives the first 2 books, page 2 the next 2",
        ["Take `page` and `size` as int query parameters with defaults.",
         "Work out where the page starts.",
         "Return that slice of the list."],
        """
        from fastapi import FastAPI

        app = FastAPI()

        books = ["A", "B", "C", "D", "E"]


        @app.get("/books/page")
        def books_page(page: int = 1, size: int = 2):
            start = (page - 1) * size
            return {"page": page, "books": books[start:start + size]}
        """,
        ["Page 1 starts at 0, page 2 at `size`, and so on: `(page - 1) * size`.",
         "Slicing past the end just returns fewer items, so the last page is safe.",
         "Paging values are query parameters, not a model."],
        """
        assert client.get("/books/page?page=1&size=2").json()["books"] == ["A", "B"]
        assert client.get("/books/page?page=3&size=2").json()["books"] == ["E"]
        assert client.get("/books/page").json()["books"] == ["A", "B"]
        """,
    ),

    # ---------- a body is sent: here a model is the right tool ----------
    coding(
        "hand-73", "fastapi",
        "POST /books to add a book with title and author, answer 201 with the new id",
        ["Describe the body with a model that inherits from BaseModel.",
         "Add a POST endpoint with `status_code=201`.",
         "Give the book the next id, store it and return it."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()

        books = {}


        class Book(BaseModel):
            title: str
            author: str


        @app.post("/books", status_code=201)
        def add_book(book: Book):
            book_id = max(books, default=0) + 1
            books[book_id] = book.model_dump()
            return {"id": book_id, **books[book_id]}
        """,
        ["The data arrives in the request body, so a model is the right tool: it checks the fields.",
         "The model must inherit from `BaseModel`, or FastAPI cannot read the body into it.",
         "`max(books, default=0) + 1` still gives a fresh id after a book is deleted."],
        """
        r = client.post("/books", json={"title": "Gitanjali", "author": "Tagore"})
        assert r.status_code == 201
        assert r.json() == {"id": 1, "title": "Gitanjali", "author": "Tagore"}
        assert client.post("/books", json={"title": "No author"}).status_code == 422
        """,
    ),
    coding(
        "hand-74", "fastapi",
        "place an order with item name and quantity, quantity must be more than 0",
        ["Describe the body with a model.",
         "Use `Field(gt=0)` on quantity.",
         "Answer 201 with the order."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel, Field

        app = FastAPI()


        class Order(BaseModel):
            item: str
            quantity: int = Field(gt=0)


        @app.post("/orders", status_code=201)
        def place_order(order: Order):
            return {"item": order.item, "quantity": order.quantity}
        """,
        ["`Field(gt=0)` means greater than 0; a 0 or negative quantity gets a 422.",
         "`Field` comes from pydantic, not from fastapi."],
        """
        r = client.post("/orders", json={"item": "pen", "quantity": 2})
        assert r.status_code == 201
        assert r.json() == {"item": "pen", "quantity": 2}
        assert client.post("/orders", json={"item": "pen", "quantity": 0}).status_code == 422
        """,
    ),
    coding(
        "hand-75", "fastapi",
        "PUT to update a book's title and author by id, 404 if not found",
        ["Describe the new data with a model.",
         "Take `book_id` from the path and the model from the body.",
         "Answer 404 for an unknown id, else replace the book."],
        """
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel

        app = FastAPI()

        books = {1: {"title": "Old title", "author": "Someone"}}


        class BookUpdate(BaseModel):
            title: str
            author: str


        @app.put("/books/{book_id}")
        def update_book(book_id: int, update: BookUpdate):
            if book_id not in books:
                raise HTTPException(status_code=404, detail="Book not found")
            books[book_id] = update.model_dump()
            return {"id": book_id, **books[book_id]}
        """,
        ["FastAPI reads `book_id` from the path and `update` from the body, because it is a model.",
         "Only the body needs a model; the id stays a plain parameter."],
        """
        r = client.put("/books/1", json={"title": "New title", "author": "Asha"})
        assert r.json() == {"id": 1, "title": "New title", "author": "Asha"}
        assert client.put("/books/9", json={"title": "x", "author": "y"}).status_code == 404
        """,
    ),
    coding(
        "hand-76", "fastapi",
        "signup endpoint with email and password but never send the password back",
        ["Make one model for what comes in, with the password.",
         "Make another for what goes out, without it.",
         "Set `response_model` to the outgoing model."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()


        class Signup(BaseModel):
            email: str
            password: str


        class PublicAccount(BaseModel):
            id: int
            email: str


        @app.post("/signup", response_model=PublicAccount, status_code=201)
        def signup(data: Signup):
            account = {"id": 1, "email": data.email, "password": data.password}
            return account
        """,
        ["`response_model` filters the answer: only `id` and `email` are sent back.",
         "This is a good reason to use a model on the way out; `response_model=dict` would filter nothing.",
         "A real app must store a hash of the password, never the plain text."],
        """
        r = client.post("/signup", json={"email": "a@b.com", "password": "secret"})
        assert r.status_code == 201
        assert r.json() == {"id": 1, "email": "a@b.com"}
        """,
    ),
    coding(
        "hand-77", "fastapi",
        "add a todo with a title, done should be false unless i send it",
        ["Describe the body with a model.",
         "Give `done` the default False.",
         "Store the todo and return it with 201."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()

        todos = []


        class Todo(BaseModel):
            title: str
            done: bool = False


        @app.post("/todos", status_code=201)
        def add_todo(todo: Todo):
            todos.append(todo.model_dump())
            return todos[-1]
        """,
        ["A default in the model makes that field optional in the JSON.",
         "`model_dump()` turns the model into a plain dict for storing."],
        """
        assert client.post("/todos", json={"title": "read"}).json() == {"title": "read", "done": False}
        assert client.post("/todos", json={"title": "run", "done": True}).json()["done"] is True
        """,
    ),
    coding(
        "hand-78", "fastapi",
        "feedback api, rating has to be 1 to 5 and comment is optional",
        ["Describe the body with a model.",
         "Use `Field(ge=1, le=5)` for the rating.",
         "Make the comment `str | None = None`."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel, Field

        app = FastAPI()


        class Feedback(BaseModel):
            rating: int = Field(ge=1, le=5)
            comment: str | None = None


        @app.post("/feedback", status_code=201)
        def give_feedback(feedback: Feedback):
            return feedback
        """,
        ["`ge` and `le` mean at least and at most, so 0 or 6 gets a 422.",
         "Returning the model is fine: FastAPI turns it into JSON."],
        """
        assert client.post("/feedback", json={"rating": 5}).json() == {"rating": 5, "comment": None}
        assert client.post("/feedback", json={"rating": 6}).status_code == 422
        assert client.post("/feedback", json={"rating": 3, "comment": "ok"}).status_code == 201
        """,
    ),
    coding(
        "hand-79", "fastapi",
        "add item to cart with name price and quantity (quantity defaults to 1) and return the line total",
        ["Describe the item with a model; price must be above 0.",
         "Give quantity the default 1.",
         "Return the name and price x quantity."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel, Field

        app = FastAPI()


        class CartItem(BaseModel):
            name: str
            price: float = Field(gt=0)
            quantity: int = 1


        @app.post("/cart/items", status_code=201)
        def add_item(item: CartItem):
            return {"name": item.name, "line_total": item.price * item.quantity}
        """,
        ["A body with several fields is exactly what a model is for.",
         "The defaults and rules live in one place, the model."],
        """
        assert client.post("/cart/items", json={"name": "pen", "price": 10}).json() == {"name": "pen", "line_total": 10.0}
        assert client.post("/cart/items", json={"name": "pen", "price": 10, "quantity": 3}).json()["line_total"] == 30.0
        assert client.post("/cart/items", json={"name": "pen", "price": 0}).status_code == 422
        """,
    ),
    coding(
        "hand-80", "fastapi",
        "mark a todo as done with PATCH /todos/{todo_id}/done",
        ["Keep todos in a dict keyed by id.",
         "Add a PATCH endpoint; the id in the path is all it needs.",
         "Answer 404 for an unknown id, else set done to True."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()

        todos = {1: {"title": "read", "done": False}}


        @app.patch("/todos/{todo_id}/done")
        def mark_done(todo_id: int):
            if todo_id not in todos:
                raise HTTPException(status_code=404, detail="Todo not found")
            todos[todo_id]["done"] = True
            return todos[todo_id]
        """,
        ["PATCH changes part of something. This one sends no body, so it needs no model.",
         "Using a model is about whether data is sent in the body, not about the HTTP method."],
        """
        assert client.patch("/todos/1/done").json() == {"title": "read", "done": True}
        assert client.patch("/todos/5/done").status_code == 404
        """,
    ),
    coding(
        "hand-81", "fastapi",
        "simple login: username and password in the body, 401 if wrong",
        ["Describe the body with a model.",
         "Compare against the stored password.",
         "Answer 401 if it does not match, else confirm."],
        """
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel

        app = FastAPI()

        passwords = {"asha": "secret1"}


        class Login(BaseModel):
            username: str
            password: str


        @app.post("/login")
        def login(data: Login):
            if passwords.get(data.username) != data.password:
                raise HTTPException(status_code=401, detail="Wrong username or password")
            return {"logged_in": data.username}
        """,
        ["Passwords go in the body, never in the URL, where they end up in logs.",
         "`.get()` returns None for an unknown user, so it fails the check safely.",
         "A real app stores password hashes and compares those."],
        """
        assert client.post("/login", json={"username": "asha", "password": "secret1"}).json() == {"logged_in": "asha"}
        assert client.post("/login", json={"username": "asha", "password": "nope"}).status_code == 401
        assert client.post("/login", json={"username": "ravi", "password": "x"}).status_code == 401
        """,
    ),
    coding(
        "hand-82", "fastapi",
        "post a list of scores in json and get back the average",
        ["Describe the body with a model holding `list[int]`.",
         "Refuse an empty list with 400.",
         "Return the average."],
        """
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel

        app = FastAPI()


        class Scores(BaseModel):
            values: list[int]


        @app.post("/scores/average")
        def average(scores: Scores):
            if not scores.values:
                raise HTTPException(status_code=400, detail="No scores given")
            return {"average": sum(scores.values) / len(scores.values)}
        """,
        ["A list sent as JSON belongs in the body, so a model fits.",
         "Checking for an empty list avoids dividing by zero."],
        """
        assert client.post("/scores/average", json={"values": [70, 80, 90]}).json() == {"average": 80.0}
        assert client.post("/scores/average", json={"values": []}).status_code == 400
        """,
    ),
    coding(
        "hand-83", "fastapi",
        "bmi calculator api, height in metres and weight in kg sent as json",
        ["Describe the body with a model; both values must be above 0.",
         "Work out weight / height squared.",
         "Round to one decimal."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel, Field

        app = FastAPI()


        class Body(BaseModel):
            height_m: float = Field(gt=0)
            weight_kg: float = Field(gt=0)


        @app.post("/bmi")
        def bmi(body: Body):
            return {"bmi": round(body.weight_kg / body.height_m ** 2, 1)}
        """,
        ["`Field(gt=0)` stops a zero height, which would crash the division.",
         "`**` is power, so `height_m ** 2` is height squared."],
        """
        assert client.post("/bmi", json={"height_m": 1.75, "weight_kg": 70}).json() == {"bmi": 22.9}
        assert client.post("/bmi", json={"height_m": 0, "weight_kg": 70}).status_code == 422
        """,
    ),
    coding(
        "hand-84", "fastapi",
        "save a message with an optional subject, POST /messages",
        ["Describe the body with a model; `subject` gets a default of None.",
         "Store the message and return it with 201."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()

        messages = []


        class Message(BaseModel):
            text: str
            subject: str | None = None


        @app.post("/messages", status_code=201)
        def save_message(message: Message):
            messages.append(message.model_dump())
            return {"count": len(messages), "message": messages[-1]}
        """,
        ["`str | None = None` makes `subject` optional in the JSON.",
         "Returning the count lets the client see the save worked."],
        """
        r = client.post("/messages", json={"text": "hi"})
        assert r.status_code == 201
        assert r.json() == {"count": 1, "message": {"text": "hi", "subject": None}}
        """,
    ),

    # ---------- fixing model mistakes ----------
    coding(
        "hand-85", "fastapi",
        """
        i get TypeError: About() takes no arguments

        from fastapi import FastAPI
        app = FastAPI()

        class About:
            name: str

        @app.get("/about")
        def about():
            return About(name="My API")
        """,
        ["The class does not inherit from BaseModel, so it cannot take `name=`.",
         "This endpoint receives nothing, so it does not need a model at all.",
         "Return a plain dict instead."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/about")
        def about():
            return {"name": "My API"}
        """,
        ["A plain class with `name: str` only notes a type; it has no `__init__` that accepts `name`, hence the TypeError.",
         "You could add `(BaseModel)`, but for a fixed answer a dict is simpler and enough.",
         "Use a model when data comes IN through the body; it is not needed to send data out."],
        """
        assert client.get("/about").json() == {"name": "My API"}
        """,
    ),
    coding(
        "hand-86", "fastapi",
        """
        /area?width=3&height=4 gives 422 and says field required, body. why

        class Size(BaseModel):
            width: float
            height: float

        @app.get("/area")
        def area(size: Size):
            return {"area": size.width * size.height}
        """,
        ["A model parameter tells FastAPI to read a JSON body.",
         "A GET request sends the values in the URL, not in a body, so FastAPI finds nothing.",
         "Take `width` and `height` as plain query parameters."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/area")
        def area(width: float, height: float):
            return {"area": width * height}
        """,
        ["Plain parameters are read from the query string; a model parameter is read from the body.",
         "\"field required ... body\" in the 422 message is the clue: FastAPI looked for a body.",
         "GET requests should not carry a body, so query parameters are the right choice."],
        """
        assert client.get("/area?width=3&height=4").json() == {"area": 12.0}
        """,
    ),
    coding(
        "hand-87", "fastapi",
        """
        im sending json {"name": "Bruno"} to my post endpoint but get 422 query name missing

        @app.post("/pets")
        def add_pet(name: str):
            return {"added": name}
        """,
        ["A plain `name: str` is read from the query string, not from the JSON body.",
         "Data sent as JSON in a POST needs a model.",
         "Describe the body with a BaseModel and read `pet.name`."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()


        class Pet(BaseModel):
            name: str


        @app.post("/pets", status_code=201)
        def add_pet(pet: Pet):
            return {"added": pet.name}
        """,
        ["The rule: plain parameters come from the path or query; a BaseModel parameter comes from the JSON body.",
         "This is the opposite mistake to using a model on a GET request."],
        """
        r = client.post("/pets", json={"name": "Bruno"})
        assert r.status_code == 201
        assert r.json() == {"added": "Bruno"}
        """,
    ),
    coding(
        "hand-88", "fastapi",
        """
        fastapi crashes on start, says Invalid args for response field and mentions my Pet class

        class Pet:
            name: str
            age: int

        @app.post("/pets")
        def add_pet(pet: Pet):
            return pet
        """,
        ["`Pet` is a plain class; FastAPI only understands models that inherit from BaseModel.",
         "Import BaseModel from pydantic and write `class Pet(BaseModel)`.",
         "Return the pet with 201."],
        """
        from fastapi import FastAPI
        from pydantic import BaseModel

        app = FastAPI()


        class Pet(BaseModel):
            name: str
            age: int


        @app.post("/pets", status_code=201)
        def add_pet(pet: Pet):
            return pet
        """,
        ["`(BaseModel)` is what lets FastAPI read, check and return the data.",
         "This is right because the pet arrives in the body; for path or query values you would not need a class."],
        """
        r = client.post("/pets", json={"name": "Bruno", "age": 3})
        assert r.status_code == 201
        assert r.json() == {"name": "Bruno", "age": 3}
        assert client.post("/pets", json={"name": "Bruno"}).status_code == 422
        """,
    ),
    coding(
        "hand-89", "fastapi",
        """
        is this ok? i made a class just for the id

        class BookId(BaseModel):
            id: int

        @app.get("/books/{book_id}")
        def get_book(book_id: BookId):
            return books[book_id.id]
        """,
        ["The id is in the path, so it is a plain `int` parameter, not a model.",
         "Add a 404 for unknown ids.",
         "Return the book."],
        """
        from fastapi import FastAPI, HTTPException

        app = FastAPI()

        books = {1: {"title": "The Guide"}}


        @app.get("/books/{book_id}")
        def get_book(book_id: int):
            if book_id not in books:
                raise HTTPException(status_code=404, detail="Book not found")
            return books[book_id]
        """,
        ["FastAPI refuses to start with this: path parameters must be simple types such as int or str, not a model.",
         "`book_id: int` matches `{book_id}` in the path and converts it for you.",
         "Fewer classes also means less code to read."],
        """
        assert client.get("/books/1").json() == {"title": "The Guide"}
        assert client.get("/books/2").status_code == 404
        """,
    ),
    coding(
        "hand-90", "fastapi",
        """
        do i need response_model=dict here? it works without it

        @app.get("/version", response_model=dict)
        def version():
            return {"version": "2.1"}
        """,
        ["`response_model=dict` checks nothing that the dict does not already say.",
         "Remove it and return the dict."],
        """
        from fastapi import FastAPI

        app = FastAPI()


        @app.get("/version")
        def version():
            return {"version": "2.1"}
        """,
        ["You don't need it. `response_model` is useful with a real model, for example to hide a password field.",
         "With `dict` it adds a line without adding any checking."],
        """
        assert client.get("/version").json() == {"version": "2.1"}
        """,
    ),

    # ---------- the rule, as short answers ----------
    short("hand-91", "when do i actually need a model class in fastapi",
          "When the client sends data in the request body, usually as JSON with POST, PUT or PATCH. Path values (`/books/{book_id}`), query values (`?page=2`) and headers are plain function parameters, and returning a plain dict is fine. So a GET or DELETE endpoint usually needs no model at all."),
    short("hand-92", "do i need a class to read ?page=2 in fastapi",
          "No. Add a parameter to your function: `def list_books(page: int = 1):`. FastAPI reads `page` from the URL and turns it into an int. A class (a BaseModel) is for data sent in the request body."),
]
