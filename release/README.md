---
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
base_model_relation: finetune
language:
  - en
pipeline_tag: text-generation
tags:
  - code
  - python
  - fastapi
  - education
  - gguf
  - ollama
  - lora
---

# Krama Coder 1.5B (v0.1 preview)

Krama is a small, offline coding tutor for **Python and FastAPI beginners**.
For a coding task it answers in three short parts: **Plan** (numbered steps), **Code**, and **Why** (plain-language reasons).
For a quick question it gives a short, direct answer.
It runs on an ordinary laptop CPU with no internet.

"Krama" is Sanskrit for order or sequence.

> **Preview.** This is an early release for trying out and giving feedback.
> It is not a general-purpose coding model and it is not production-ready.
> Always run the code it gives you.

Krama is a fine-tune of [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) by the Qwen team (Apache 2.0). All of its coding ability comes from that model. Krama only changes how it answers.

## Run it

With [Ollama](https://ollama.com):

```sh
ollama run hf.co/CoBeDigger/krama-coder-1.5b
```

The file is 986 MB (4-bit Q4_K_M). On a laptop CPU (Intel Core Ultra 7 155H) the base model runs at about 33-36 tokens per second, and Krama is the same size.

You can also use it from code through Ollama's local API (`http://localhost:11434`), or in VS Code through an extension that supports Ollama, such as Continue.

To build it yourself from the downloaded file, use the `Modelfile` in this repo:

```sh
ollama create krama -f Modelfile
```

## What an answer looks like

These are real answers from the release file, at temperature 0.

**"Write a Python function safe_divide(a, b) that returns a divided by b. If b is zero, return None instead of crashing."**

````text
Plan:
1. Define the function `safe_divide`.
2. Check if `b` is zero.
3. Return `None` if `b` is zero, otherwise return the division result.

Code:
```python
def safe_divide(a, b):
    if b == 0:
        return None
    return a / b
```

Why:
- The function checks if `b` is zero before performing the division to avoid division by zero errors.
- If `b` is zero, the function returns `None`, which can be handled gracefully in the calling code.
````

**"What is the difference between == and is in Python?"**

````text
`==` checks if two values are equal, while `is` checks if both variables point to the same object. For example:
```python
x = [1, 2]
y = [1, 2]
print(x == y)  # True because they have the same elements
print(x is y)  # False because they are two different lists
```
````

## How it was tested

All three systems below are the same 986 MB Q4_K_M file size, run in Ollama at temperature 0.
"Base + instruction" is the base model given a written instruction to answer like Krama.

**Correctness.** 30 tasks of our own (12 Python, 12 FastAPI, 6 quick questions), where the code is run against tests. The 164-task [HumanEval](https://github.com/openai/human-eval) benchmark is the standard check.

| System | Python (12) | FastAPI (12) | Quick answers, average length | HumanEval (164) |
|---|---|---|---|---|
| Base model | 9 | 6 | 273 tokens | 120 (73.2%) |
| Base + instruction | 9 | 5 | 218 tokens | 98 (59.8%) |
| **Krama v0.1** | **9** | **6** | **121 tokens** | **112 (68.3%)** |

Runs on a CPU are not exactly repeatable, even at temperature 0. Krama passed 10 Python tasks in its first run and 9 in each of four reruns, so we report 9. The base model passed 9 Python and 6 FastAPI tasks in all three of its runs. HumanEval was run once per system.

**Teaching quality.** Each answer was scored blind by a different model (Llama 3.1 8B), which never saw which system wrote it. Scoring rules were written before training. Averages are out of 2 per rule.

| System | Plan | Why | Clarity | Length | Coding total (of 8) | Quick answers (of 4) |
|---|---|---|---|---|---|---|
| Base model | 1.08 | 0.67 | 1.04 | 1.58 | 4.38 | 1.33 |
| Base + instruction | 1.83 | 1.17 | 1.17 | 1.79 | 5.96 | 1.33 |
| **Krama v0.1** | **1.92** | **1.17** | **1.21** | **1.96** | **6.25** | **2.00** |

What this means, honestly:

- Krama matches the base model's correctness on our tasks, and adds a plan and an explanation.
- On HumanEval it is **8 tasks below** the plain base model. Asking the base model to plan and explain costs it far more (22 tasks), so the fine-tune is the better way to get this answer style, but it is not free.
- Against the instructed base, Krama wins 7, ties 15 and loses 2 of the 24 coding tasks on teaching quality, and wins 3 and ties 3 of the 6 quick questions. Its short answers are about half as long.
- Our 30 tasks share topics with the training data. Exact copies were removed, but those scores may flatter Krama a little. HumanEval is the fairer measure.
- The blind grader is a small model and was lenient. It sometimes gave the base model credit for a plan it did not have. That error favours the base, not Krama.

## Known weaknesses

- FastAPI: 6 of 12 tasks still fail. Krama sometimes adds a Pydantic model where none is needed, and once it read a JSON body as a plain string parameter.
- Explanations are short and sometimes generic, and they are not always fully accurate. Treat the "Why" as a starting point.
- English only. Python and FastAPI only.
- 1.5B parameters: it makes logic mistakes that larger models would not.

## How it was made

- **Data:** 1,578 examples: 776 Python, 471 FastAPI, 316 short answers, and 15 about who made it. Most answers were written by [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) (Apache 2.0) and kept **only if their code passed their own tests**. 92 examples were written by hand. Some questions were inspired by short pieces of the author's own code. Any example whose code passed one of our test tasks, or which asked one of our test questions, was removed. The dataset is not released in this preview.
- **Training:** LoRA on all linear layers (rank 16, alpha 32, dropout 0.05), learning rate 2e-4 with cosine decay, 2 epochs, max length 1,024, effective batch 16, fp16, on one free Kaggle T4 GPU (11 minutes). Held-out loss went from 0.522 to 0.474. The adapter was merged and converted to Q4_K_M GGUF with llama.cpp.
- **Instruction it was trained with:** "You are Krama, a Python and FastAPI coding assistant for beginners, fine-tuned by CoBeDigger from Qwen2.5-Coder-1.5B-Instruct." The `system` file in this repo sets it for you.

## What comes next

- A `krama` command-line tool that runs Krama's code against tests on your own machine before showing it.
- Version 0.2, trained on the mistakes real beginners find.
- Later, a larger version.

Feedback is very welcome in the Community tab, especially questions where Krama got it wrong.

## License

Apache 2.0, the same as the base model. Built on Qwen2.5-Coder-1.5B-Instruct by the Qwen team.
