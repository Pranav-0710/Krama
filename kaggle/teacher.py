"""Phase 2, box 2.2: the teacher. Paste this whole file into ONE Kaggle cell.

What it does:
    reads the request slips (requests.jsonl, added as a Kaggle dataset)
    asks a 7B teacher model to invent a question, tests and an answer for each
    saves every reply to /kaggle/working/answers.jsonl

Kaggle settings needed: Accelerator = GPU T4 x2, Internet = On.
Safe to stop and run again: it skips requests it has already answered.
"""

import glob
import json
import subprocess
import sys
import time
from pathlib import Path

# ---------------- settings you may change ----------------
LIMIT = 1500        # how many requests to answer this run (about 8 hours)
BATCH_SIZE = 8      # how many requests the GPU works on at once
MAX_NEW_TOKENS = 900
TEACHER = "Qwen/Qwen2.5-Coder-7B-Instruct"   # Apache 2.0 licence
OUT_FILE = Path("/kaggle/working/answers.jsonl")
# ---------------------------------------------------------

subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "bitsandbytes", "accelerate"], check=True)

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# ---------- the instructions the teacher follows ----------
CODING_RULES = """You write training examples for a Python coding assistant whose users are beginners.

You get a kind (python or fastapi), a topic, a setting, and sometimes a piece of real code for inspiration.
Invent ONE new, small, self-contained task on that topic, placed in that setting.

Reply in exactly this layout and nothing else:

### QUESTION
What a learner would type. For python, name the function to write. For fastapi, name each endpoint and what it returns.

### TESTS
For python: 3 to 5 assert lines that call the function. Include a normal case, an empty or edge case, and one tricky case.
For fastapi: lines that use `client`, a TestClient that already exists for `app`. Check status codes and JSON.

### ANSWER
Plan:
1. Two to five short steps.

Code:
```python
The full solution.
```

Why:
- Two to four short points on choices a beginner would wonder about. Give reasons. Do not just repeat what the code does.

Rules:
- python tasks use only the standard library. fastapi tasks use only fastapi and pydantic.
- A fastapi solution must contain `app = FastAPI()` and must not start a server.
- No input(), no files, no network, no random numbers, no current time.
- The tests must pass when run after the code.
- Use plain words. Explain any technical term the first time you use it.
- Never copy the inspiration code. Borrow only its style of names and situations.

Example of a complete reply:

### QUESTION
Write a FastAPI app with one endpoint, POST /books. It accepts a JSON body with a title and returns the title with status code 201.

### TESTS
r = client.post("/books", json={"title": "Malgudi Days"})
assert r.status_code == 201
assert r.json() == {"title": "Malgudi Days"}
assert client.post("/books", json={}).status_code == 422

### ANSWER
Plan:
1. Describe the incoming JSON with a Pydantic model.
2. Create a POST endpoint that asks for that model.
3. Tell FastAPI to answer with status 201.

Code:
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Book(BaseModel):
    title: str


@app.post("/books", status_code=201)
def create_book(book: Book):
    return {"title": book.title}
```

Why:
- The Pydantic model is what makes FastAPI read the JSON body. A plain `title: str` parameter would be read from the URL instead.
- `status_code=201` means "created". Without it FastAPI answers 200, which only means "OK".
- A missing title is rejected with 422 automatically, so no checking code is needed.
"""

QUICK_RULES = """You write training examples for a Python coding assistant whose users are beginners.

You get a topic and a setting. Invent ONE short question a beginner would really ask about it, and answer it.

Reply in exactly this layout and nothing else:

### QUESTION
One line.

### ANSWER
One to three plain sentences that answer directly. At most one tiny example. No plan, no headings, no long code.

Example of a complete reply:

### QUESTION
What does status code 404 mean?

### ANSWER
It means the server could not find what you asked for, such as an id that does not exist. In FastAPI you send it with `raise HTTPException(status_code=404)`.
"""

# A setting makes 40 questions on one topic come out different from each other.
SETTINGS = [
    "a library", "a small shop", "a school", "a clinic", "a bus service",
    "a cricket club", "a restaurant", "a to-do app", "a weather station",
    "a music playlist", "a parking lot", "a hostel", "a bank", "a gym",
    "a farm", "a movie theatre", "a courier company", "a quiz app",
    "a help desk", "a train booking office", "a recipe book", "a zoo",
    "a tailoring shop", "a water supply office", "a photo album",
]


def build_messages(request, position):
    """Turn one request slip into the chat messages sent to the teacher."""
    rules = QUICK_RULES if request["kind"] == "quick" else CODING_RULES
    ask = f"Kind: {request['kind']}\nTopic: {request['topic']}\n"
    ask += f"Setting: {SETTINGS[position % len(SETTINGS)]}\n"
    if request["seed"]:
        ask += f"Inspiration code:\n```python\n{request['seed']}\n```\n"
    return [
        {"role": "system", "content": rules},
        {"role": "user", "content": ask},
    ]


# ---------- load the request slips ----------
found = glob.glob("/kaggle/input/**/requests.jsonl", recursive=True)
if not found:
    raise SystemExit("requests.jsonl not found. Add your dataset with 'Add Input' first.")
requests = [json.loads(line) for line in open(found[0], encoding="utf-8")]

# Skip requests answered before: in this run, or in an earlier run whose
# answers file was added to the notebook as an input.
done = set()
earlier = glob.glob("/kaggle/input/**/answers*.jsonl", recursive=True)
for answers_file in earlier + ([str(OUT_FILE)] if OUT_FILE.exists() else []):
    done |= {json.loads(line)["id"] for line in open(answers_file, encoding="utf-8")}
todo = [(i, r) for i, r in enumerate(requests) if r["id"] not in done][:LIMIT]
print(f"requests: {len(requests)}  already answered: {len(done)}  doing now: {len(todo)}")

# ---------- load the teacher ----------
tokenizer = AutoTokenizer.from_pretrained(TEACHER)
tokenizer.padding_side = "left"   # needed when answering several requests at once
model = AutoModelForCausalLM.from_pretrained(
    TEACHER,
    # Store each dial in 4 bits so a 7B model fits on one 16 GB GPU.
    quantization_config=BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    ),
    device_map={"": 0},
)
model.eval()

# ---------- ask the teacher, a batch at a time ----------
start = time.time()
tokens_written = 0
answered = 0

with open(OUT_FILE, "a", encoding="utf-8") as out:
    for first in range(0, len(todo), BATCH_SIZE):
        batch = todo[first:first + BATCH_SIZE]
        prompts = [
            tokenizer.apply_chat_template(
                build_messages(request, position),
                tokenize=False,
                add_generation_prompt=True,
            )
            for position, request in batch
        ]
        inputs = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=True,      # a little randomness gives varied questions
                temperature=0.7,
                top_p=0.9,
                pad_token_id=tokenizer.pad_token_id,
            )
        new_tokens = outputs[:, inputs["input_ids"].shape[1]:]
        replies = tokenizer.batch_decode(new_tokens, skip_special_tokens=True)

        for (position, request), reply, row in zip(batch, replies, new_tokens):
            tokens_written += int((row != tokenizer.pad_token_id).sum())
            out.write(json.dumps({
                "id": request["id"],
                "kind": request["kind"],
                "topic": request["topic"],
                "raw": reply,
            }) + "\n")
        out.flush()

        answered += len(batch)
        minutes = (time.time() - start) / 60
        print(f"answered {answered}/{len(todo)}  after {minutes:.1f} min")

seconds = time.time() - start
if answered:
    print(f"\nDONE. {answered} answers in {seconds / 60:.1f} minutes.")
    print(f"Speed: {tokens_written / seconds:.0f} tokens per second.")
    print(f"At this speed, 3,000 requests would take about {seconds / answered * 3000 / 3600:.1f} hours.")
    print(f"Download this file from the Output panel: {OUT_FILE}")
