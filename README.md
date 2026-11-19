# Krama

A small Python/FastAPI chat model that plans first, then codes, then explains why.
"Krama" is Sanskrit for order or sequence.

Planned Hugging Face address: `CoBeDigger/krama-coder-1.5b`

## Agreed design (2026-11-12)

| Area | Decision |
|---|---|
| Base model | Qwen2.5-Coder-1.5B-Instruct (Apache 2.0), credited on the model card |
| Method | LoRA on all linear layers, then merged into one model |
| Training settings | rank 16, alpha 32, dropout 0.05, learning rate 2e-4 (cosine, 3% warmup), 2 epochs, max length 1024, batch 4 x accumulation 4, fp16 |
| Where it trains | Kaggle free GPU, $0 budget |
| Behaviour | Real tasks: Plan -> Code -> Why. Quick questions: a plain short answer |
| Scope | Python only in version 1 |
| Data | 2,000-3,000 examples. Open Python tasks; answers from a 7B open-licence teacher model, kept only if the code passes tests; about 20% plain short answers; about 50 hand-written; identity examples under 1%; benchmark tasks removed |
| Own code | The author's public and private repos are included, after a secrets scan |
| Test | Fixed before training. Three systems: base, base + system prompt, Krama. A standard run-the-code Python benchmark plus 30 of our own tasks, scored blind by a different AI model against rules written in advance |
| If the system prompt alone ties | Push the fine-tune further; if it still ties, publish and say so |
| Release | Merged safetensors + GGUF files, dataset as a separate repo, free CPU demo Space, Apache 2.0 |
| Use | Terminal chat and VS Code chat sidebar through Ollama. No autocomplete, no autonomous agent in version 1 |

## Direction (agreed 2026-11-18, after the four-way test)

Krama is an **offline coding tutor for beginners that checks its own code**. It is not a general coding model, and the model card says so.

- What makes it unique: it plans, codes, then explains why, in about 120 tokens. It runs on any laptop CPU with no internet. Its tool runs the code it wrote against tests on the user's machine and only shows code that ran. That is the same execution filter that built the training data.
- Interfaces: Ollama provides the terminal chat, the local API and editor use (for example VS Code through Continue) from day one. The project's own product is a `krama` CLI with the self-check built in.
- Road:
  1. Blind-grade the explanations, then publish Krama v0.1 as a preview, with the numbers and the base-model credit.
  2. Build the `krama` CLI with self-checking.
  3. Have real beginners use it, and train v0.2 on where it fails.
  4. Later: a 3B or 7B version, and VS Code integration.

## Build order

1. Run the base model on the laptop and measure its speed
2. Write the 30 test tasks and the scoring rules
3. Score the base and the base + system prompt
4. Build the 2,000-example pilot dataset
5. Train
6. Three-way test
7. Convert, publish, demo

## Measured

- Base model speed on this laptop (Core Ultra 7 155H, 16 GB RAM, CPU only, Ollama 0.40.16, default 4-bit file, 986 MB): 33-36 tokens per second over three prompts on 2026-11-12. Memory in use: 1.2 GB.

- Starting scores on our 30 tasks, 2026-11-13 (code run against tests; rules in `eval/RUBRIC.md`):

  | System | Python passed | FastAPI passed | Quick answers, average length |
  |---|---|---|---|
  | Base model | 9/12 | 6/12 | 273 tokens |
  | Base model + written instruction | 9/12 | 5/12 | 218 tokens |

  Blind grading of plan, explanation, clarity and length has not been done yet.

- Training data, 2026-11-17 (`data/filter.py`, `data/leak_check.py`, `data/mix.py`):
  - The teacher answered 3,800 requests. 2,134 answers passed their own tests: Python 850/1,200, FastAPI 730/2,000, short answers 554/600.
  - The leak check removed 216 examples that copied the exam: 93 whose code passes an exam task's tests, and 123 short questions that ask an exam question.
  - Final set: 1,915 examples. That is 776 Python, 741 FastAPI, 383 short answers (20%) and 15 identity examples, with the 50 hand-written examples included.
  - This is a little under the planned 2,000. We accepted it because most removed rows were repeats of a few exam tasks.
  - Only exact exam tasks and questions were removed, not their topics. Our own 30 tasks may therefore flatter the model a little, and the standard benchmark is the fairer measure.

- Training, 2026-11-18 (`kaggle/train.py`, Kaggle T4, transformers 5.20.2):
  - 1,855 examples were trained on and 60 held out. 18.5M LoRA parameters were trained (1.18% of 1.56B).
  - 232 steps took 14 min 42 s.
  - Held-out loss went 0.522 (step 50) → 0.490 → 0.485 → 0.470 → 0.469 (step 232). It kept falling to the end, with no sign of memorising.
  - The merged model is saved in the Kaggle notebook's /kaggle/working/krama-coder-1.5b.

- First three-way test, 2026-11-18 (`eval/run.py --only krama`, same 30 tasks, temperature 0):
  - Krama was shrunk to 4-bit Q4_K_M with llama.cpp (`kaggle/to_gguf.py`), the same format and size (986 MB) as the base model's file. It runs in Ollama from the repo's `Modelfile`.

  | System | Python passed | FastAPI passed | Quick answers, average length |
  |---|---|---|---|
  | Base model | 9/12 | 6/12 | 273 tokens |
  | Base model + written instruction | 9/12 | 5/12 | 218 tokens |
  | Krama | 9/12 | 5/12 | 106 tokens |

  - Correctness is a tie. Krama's short answers are about half the length of the prompted base model's. It also uses Plan, Code, Why without being told.
  - Krama's FastAPI failures share one pattern: it reaches for a Pydantic model when none is needed, and then misuses it. The examples are a class without `BaseModel`, a body model on a GET endpoint, and `response_model=dict`.
  - Asked "who made you", Krama gave a made-up answer. The 15 identity examples were not enough.
  - Blind grading of plan, explanation, clarity and length has not been done yet.

- Round 2 training data, 2026-11-18:
  - 81% of the FastAPI training answers used a Pydantic model, and 277 used one even though no data was sent in. `data/mix.py` now leaves out the 310 teacher answers that use a model with no POST, PUT or PATCH endpoint, or use `response_model=dict`.
  - 42 new hand-written examples (`data/handwritten_round2.py`): 22 endpoints that need no model, 12 that use a body model correctly, 6 fixes of model mistakes, and 2 short answers on when a model is needed. All pass their tests, and none copies the exam.
  - The system line now names the maker ("fine-tuned by CoBeDigger from Qwen2.5-Coder-1.5B-Instruct").
  - Final set: 1,578 examples. That is 776 Python, 471 FastAPI, 316 short answers (20%) and 15 identity examples. It is further under the planned 2,000; we chose this over regenerating with the teacher, which needed more GPU time than was left this week.
  - Standard benchmark: HumanEval (164 tasks, MIT licence), `eval/benchmark.py`. We never use it to choose fixes, so it is the fair check against teaching to the test.

- Round 2 training, 2026-11-18 (same settings; `ROUND = 2` saves to `-r2` folders, so it cannot resume round 1):
  - 1,518 examples were trained on and 60 held out. 190 steps took 11 min 24 s.
  - Held-out loss went 0.522 → 0.484 → 0.476 → 0.474 (round 1 ended at 0.469 on a different held-out set, so the two are not directly comparable).
  - Converted the same way as round 1 (986 MB Q4_K_M) and loaded in Ollama as `krama-r2`. Round 1 stays as `krama`.
  - Exam, our 30 tasks: Python 10/12, FastAPI 6/12, quick answers 121 tokens on average. All 24 coding answers used Plan, Code, Why.
  - The Pydantic habit halved: 5 of 12 FastAPI answers used a model (round 1: 10). It is not gone: `api-health` still planned a model and crashed on an unused, unimported `BaseModel`. One answer overcorrected the other way: a POST read its JSON body as a plain `text: str` parameter.
  - Check answers: "who made you" now names CoBeDigger and Qwen2.5-Coder-1.5B-Instruct. A FastAPI GET answer used no model, but it skipped Plan, Code and Why, left out `app = FastAPI()`, and mixed up `Planets` and `planets`.

- Four-way comparison, 2026-11-18 (all four are 986 MB Q4_K_M files in Ollama, temperature 0):

  | System | Our tasks: Python | Our tasks: FastAPI | Quick answers, average length | HumanEval (164 tasks) |
  |---|---|---|---|---|
  | Base model | 9/12 | 6/12 | 273 tokens | 120 (73.2%) |
  | Base model + written instruction | 9/12 | 5/12 | 218 tokens | 98 (59.8%) |
  | Krama, round 1 | 9/12 | 5/12 | 106 tokens | 106 (64.6%) |
  | Krama, round 2 | 10/12 | 6/12 | 121 tokens | 112 (68.3%) |

  - Asking the base model to plan and explain (the written instruction) cost it 22 HumanEval tasks. Fine-tuning won most of that back: round 2 beats the written instruction everywhere, so the fine-tune is worth having.
  - Round 2 is 8 HumanEval tasks below the untouched base model, which gives no plan or explanation. The two disagree on 38 tasks (base alone passes 23, round 2 alone passes 15), so this gap may partly be chance. Almost none of the failures come from a renamed function; they are real logic mistakes.
  - Honest summary: Krama gives the same correctness as its base on our tasks, with a plan and an explanation at about half the length of the prompted base. On the standard benchmark it is a little weaker than the plain base.

- Blind grading, 2026-11-18 (`eval/grade.py`, Llama 3.1 8B in Ollama, temperature 0; average out of 2 per rule):

  | System | Plan | Why | Clarity | Length | Fixed rules total (of 8) | Why is true (extra) | Quick: correct | Quick: length | Quick total (of 4) |
  |---|---|---|---|---|---|---|---|---|---|
  | Base model | 1.08 | 0.67 | 1.04 | 1.58 | 4.38 | 0.92 | 1.17 | 0.17 | 1.33 |
  | Base model + written instruction | 1.83 | 1.17 | 1.17 | 1.79 | 5.96 | 0.92 | 1.00 | 0.33 | 1.33 |
  | Krama, round 1 | 1.79 | 1.12 | 1.17 | 1.79 | 5.88 | 1.08 | 1.17 | 0.67 | 1.83 |
  | Krama, round 2 | 1.92 | 1.17 | 1.21 | 1.96 | 6.25 | 0.96 | 1.50 | 0.50 | 2.00 |

  - Win rule (`eval/RUBRIC.md`): round 2 is not less correct than the base on our tasks (9/12 and 6/12 for both on repeated runs; see the rerun note below), and it scores higher than the instructed base on the graded rules. Task by task against the instructed base, it wins 7, ties 15 and loses 2 coding tasks, and wins 3 and ties 3 quick questions. The coding margin is small (6.25 against 5.96 out of 8); the quick-answer margin is clear.
  - On HumanEval it is still 8 tasks below the base, so the win holds on our tasks only.
  - Change from the plan: the rubric said the grader sees all answers at once. Llama 3.1 8B mixed answers up that way (it gave one answer credit for another's plan), so each answer is graded alone, still unnamed and shuffled.
  - The grader is lenient. Checked against a simple test (numbered steps before the first code block), its plan score was right for all 72 answers from the three instructed or fine-tuned systems, but 23 of the plain base's 24 answers had no plan and it still gave 16 of those a plan score (it counted a numbered list after the code). This flatters the base, not Krama. "Why is true" was added after training and is not part of the win rule; it shows no clear difference.

- Published v0.1 preview, 2026-11-18: `CoBeDigger/krama-coder-1.5b` on Hugging Face (public). It holds the round 2 Q4_K_M file as `krama-coder-1.5b-q4_k_m.gguf`, plus the model card and Ollama files from `release/`.
  - `ollama pull hf.co/CoBeDigger/krama-coder-1.5b` works. The pulled model has the same weights file (sha256 f3b45d79…), template and system line as the local `krama-r2`. Asked "who made you?", it names CoBeDigger and Qwen2.5-Coder-1.5B-Instruct.
  - Reruns showed that answers on this CPU are not exactly repeatable at temperature 0: the local `krama-r2` gave different answers to most tasks than in its first run. On the 24 coding tasks, two runs of the published copy and two of the local `krama-r2` all passed Python 9/12 and FastAPI 6/12. Two reruns of the base gave 9/12 and 6/12 again. So round 2's first-run 10/12 was luck, and correctness is a tie with the base. The model card reports 9.

- `krama` command-line tutor, version 0.1, 2026-11-18 (`cli/`, see `cli/README.md`; 11 tests in `cli/tests`):
  - It asks the published model through Ollama, then checks the code before showing it. The check parses it, refuses obviously risky code (deleting or writing files, other programs, the network), then imports it in a separate Python process with a 10-second limit. If the code crashes, the error goes back to Krama to fix, up to two more tries.
  - Measured with `eval/selfcheck.py` on the 24 coding tasks, two runs: Python 10/12 and 9/12, FastAPI 7/12 both times, against 9/12 and 6/12 without the check. The one gain is `api-health`: both runs caught `NameError: BaseModel` and Krama fixed it in one try.
  - The limit is clear: 23 of 24 answers passed the check on the first try, but 7 of those still failed the exam tests. "Runs without an error" catches crashes, not wrong answers. The tool says so after every answer. Catching wrong answers needs tests, which is the next step for the self-check.

- Long-term goal (agreed 2026-11-18): a production-ready local coding agent that runs on a CPU in cmd or PowerShell, with or without Ollama. Order: 1) make the self-check safe, 2) one backend interface, 3) a built-in llama.cpp engine (`krama setup`), 4) a test-based self-check, 5) a guided agent tried with Qwen2.5-Coder-7B first, 6) agent training data and a fine-tune. A design review and a production-readiness review (both by helper agents) shaped this order. The readiness review's verdict was "needs work".

- Step 1, safety, 2026-11-18. The review found the old look-before-running list easy to dodge: 8 risky patterns I tried, such as `import os as o; o.system(...)`, all got through. Now:
  - krama asks before running code (yes, no, or always), and runs nothing without a terminal to ask in unless given `--yes`.
  - The look covers those tricks (aliases, `from os import`, `pathlib` deletes and writes, `importlib`, `getattr` with strings, `__subclasses__`).
  - The code runs with no secret environment variables, 512 MB of memory and 10 seconds at most. On Windows a job object also stops it from starting programs (Windows refuses with error 1816) and kills anything left over.
  - A missing module is only called "install X" if X is a well-known library; otherwise it is treated as a possibly made-up name and sent back to Krama.
  - Tests: 48 pass, including 24 risky snippets that must be refused, 9 everyday snippets that must still run (`list.remove`, `str.replace`, reading files), and each limit shown working on its own. The macOS and Linux limits are written but untested.
  - Re-measured once (`selfcheck-run3.json`): Python 9/12, FastAPI 5/12. None of the 24 answers was wrongly blocked. Across three runs FastAPI was 7, 7 and 5, and every task that changed did so because Krama wrote a different answer, not because of the check. So the size of the self-check's benefit is not settled yet.

- Step 2, one backend interface, 2026-11-18 (`cli/krama_cli/backends.py`):
  - Everything that talks to a model now goes through `backend.chat(messages, schema=None)`. Ollama is the only backend so far, chosen with `--backend ollama`. A `schema` becomes Ollama's `format`, ready for the agent's tool calls.
  - krama now sends Krama's system line itself, so a future backend without a Modelfile gives the model the same start. Asked "who made you?", it still names CoBeDigger and Qwen2.5-Coder-1.5B-Instruct.
  - Every engine problem (not running, model missing, timeout, unreadable reply) becomes one message saying what to do, and Ctrl+C stops cleanly with no traceback.
  - Tests: 61 pass (12 new for the backend, with the network faked).
  - Done check: `selfcheck-run4.json` matches run 3 on all 24 tasks (Python 9/12, FastAPI 5/12), and 22 of the 24 final answers are word for word the same.

- Step 3, the built-in engine (no Ollama), 2026-11-18 (`cli/krama_cli/engine.py`, `LlamaServerBackend` in `backends.py`):
  - `krama setup` downloads llama.cpp's ready-made CPU build, pinned to release b12359 (Windows x64 25.1 MB; builds for Windows ARM, macOS Apple and Intel chips, and Linux x64 and ARM are listed). It also gets the Krama model (986 MB), or takes an existing file with `--model-file`. Both are checked against fixed SHA-256 fingerprints, broken downloads resume, and archives cannot unpack outside their folder.
  - krama then starts `llama-server` on 127.0.0.1 on a free port, waits for `/health`, and stops it on exit. On Windows a job object makes sure it dies even if krama crashes. `--backend auto` (the default) uses the built-in engine once it is set up, else Ollama.
  - Done checks on this laptop:
    - With Ollama's address pointed at a dead port, krama answered, ran its self-check and named its maker. A full one-question run took 9.1 seconds, including starting the engine, and no engine process was left behind.
    - Speed after warm-up, same prompts: built-in about 33 tokens per second, Ollama about 32, so within 10%.
    - Exam (`selfcheck-run5.json`, `local` backend): Python 8/12, FastAPI 6/12, against 9/12 and 5/12 on Ollama. That is 14 of 24 on both, and 22 of 24 tasks have the same result. The answers are worded differently: Ollama runs the same engine with a plain ChatML template and a 32,768-token window, while krama uses the model's own template and 4,096 tokens.
  - Tests: 70 pass (9 new: downloads, resume, wrong fingerprint, unsafe archive, setup records, wrong model file, the "run krama setup" message, `auto`, and an engine that will not start).
  - Not yet verified: a clean Windows PC with no Ollama and no Python tools, and macOS and Linux at all.

- Step 4, Krama tests its own code, 2026-11-18 (`cli/krama_cli/selftest.py`):
  - Once the code runs, Krama writes 3 to 5 one-line tests. It sees the question and only the names of its functions and endpoints, not their code. The reply is forced into JSON with a schema.
  - Tests are dropped if they are risky, broken, call a name the code lacks, or call an endpoint the code does not define. Each test runs on a fresh copy of the code in the limited process, and may set things up first with `;`. A failure shows what the code gave.
  - Two or more failed tests, or a crash, count as "failed" and go back to Krama for a fix. A fix is kept only if it still runs and passes more of the same tests. One failed test is only a warning. The tool lists the tests under the answer.
  - Tuning study on our 24 tasks (`eval/testcheck_study.py`, `testcheck-study-run4.json` and `-run5.json`):
    - The first version caught 6 of 9 "ran but wrong" answers, but one catch was luck: tests shared memory.
    - Fresh copies, a ban on invented rules, the endpoint filter and the two-failure rule came out of reading the failures. Final: 5 caught, 1 false alarm and 2 warnings on 14 correct answers, in both runs.
    - These rules were tuned on these tasks, so HumanEval below is the fair check.
  - Full loop on our 24 tasks (built-in engine, `selfcheck-run6.json` and `-run7.json`, identical: this engine with a fixed seed repeats itself exactly):
    - Still 14 of 24 (Python 8/12, FastAPI 6/12), the same as without tests.
    - Krama's tests flagged 6 of the 8 wrong answers as failed, but its fixes were never better: krama kept the earlier answer 7 times. The 1.5B model can see that its code is wrong but cannot repair it.
  - HumanEval through the loop (164 tasks, never used for tuning; `humaneval-loop-*-local.json`):

    | Mode (built-in engine) | Passed |
    |---|---|
    | One answer, no checking | 106 (64.6%) |
    | Run check and its fixes | 106 (no answer crashed) |
    | Run check plus Krama's own tests and their fixes | 110 (67.1%) |

    - The tests gave 6 newly passing tasks and 2 newly failing ones (a test-driven fix that a wrong test approved). A net 4 on numbers this small is not yet proven.
    - As a warning, the tests are strong:
      - 45 of the 54 wrong final answers were flagged (28 "failed", 17 "warning").
      - When krama said its tests passed, the code was right 93% of the time (95 of 102).
      - When it said failed, the code was wrong 82% of the time (28 of 34).
      - 13 of 110 right answers were flagged wrongly (6 failed, 7 warnings).
    - The built-in engine's plain score (106) is below Krama's 112 on Ollama. The same weights run with a different chat template and context setting, so compare modes on one engine, not across engines.
  - Tests: 82 pass (12 new for the test-based check and its fix loop).

- Step 5, the guided agent `krama fix`, 2026-11-18 and -19 (`cli/krama_cli/agent.py`):
  - krama drives the steps, not the model. It lists the files and runs the tests, then the model picks one action per turn: read a file, replace a piece of text, create a file, run the tests, or finish. Each reply is forced into JSON with a schema. The tests run by themselves after every change, and the job is done when they pass.
  - Safety: every change is shown as a diff and needs a yes (default no). A backup goes to `.krama/backups/` first. Test files and anything outside the project folder cannot be changed. Tests run on a copy, in the same limited process as the self-check.
  - Benchmark (`eval/agent_tasks.py`, `eval/agent_bench.py`): small beginner projects whose tests fail, each proved by `--check` to fail as given and pass with a known fix. Edits are approved automatically but counted, and the original tests are put back before marking.
    - Main 20 (12 bugs, 8 features), written first.
    - Held-out 10, written after the main 20 had been used to change the agent.
    - Held-out 10 more ("fresh"), written 2026-11-19 after the first held-out set had been used for changes too.
  - Results, 15 actions at most, built-in engine:

    | Agent version | Model | Main 20 | Held-out 10 | Fresh 10 |
    |---|---|---|---|---|
    | v1 | Krama 1.5B | 2 | not run | not run |
    | v1 | Qwen2.5-Coder-1.5B | 1 | not run | not run |
    | v1 | Qwen2.5-Coder-7B (no training) | 12 | not run | not run |
    | v2 | Krama 1.5B | 2 | 2 | not run |
    | v2 | Qwen2.5-Coder-7B | 14 | 7 | not run |
    | v3 | Krama 1.5B | 5 | 3 | 2 |
    | v3 | Qwen2.5-Coder-7B | 17 | 8 | **9** |

    - v1 to v2: the 7B often sent the right lines with the wrong spaces in front, so the replace failed and it tried the same thing again. v2 matches lines while ignoring the spaces in front, only when exactly one place matches, and moves the new lines by the same amount. It also says "you already tried exactly this" instead of failing the same way again. The 7B went from 183 to 124 seconds per project.
    - At 1.5B the agent mostly fails at the bookkeeping, not the Python. All 26 of Krama's v2 misses ran out of steps: the same replace that does not match again and again, reading one file over and over, or trying to change a test file.
    - v2's misses: five projects that add code. The 7B left `old` empty to mean "add at the end", which krama refused. `bug-two-files` alternated reading two files for 15 steps, wrongly sure the conversion was right. Three others made many edits without finding the fix.
    - v3 (both from the v2 misses): an empty `old` adds the new code at the end of the file (still shown as a diff and asked), and a file read in the last 4 steps that has not changed is not shown again. The model is told to change something or finish.
    - v3 with the 7B (`agent-qwen-7b-v3.json`): 34 of 40, 93 seconds per project. Every "add code" project that looped in v2 was solved, most in 2 steps. The fresh 10 are the fair number: 9, written before any agent saw them.
    - v3's 6 misses: three "add an API endpoint" projects ended with no edit, and three (`bug-two-files`, `bug-api-201`, `held-count-letters`) are reasoning failures. In the endpoint projects the 7B leaves out the `def` line under the decorator, in the text it copies and in the code it writes. So even a perfect match would give broken code: a model weakness, not a tool one.
    - Tried and dropped (2026-11-19): asking again at temperature 0.8 when the model repeats a failed action. The 7B then filled `old` with thousands of blank lines up to the reply limit, so each try took about a minute and could not be read. Kept: when `old` is not found, krama now says which lines are not in the file, or shows the exact lines when one in the middle was skipped. It did not change what the 7B sent.
    - v3 with Krama 1.5B (`agent-krama-1.5b-v3.json`, run with the clearer not-found message): 10 of 40, against 4 of 30 in v2. It even solved `bug-two-files`, which the 7B missed. All 30 misses ran out of steps, mostly with replaces that did not match (313 of its 450 actions in those projects).
    - So with the program steering, a plain 7B already solves most beginner-sized fixes. The rest needs a model trained on agent steps (step 6).
  - Tried by hand on the user's own PC: `uv tool install ./cli`, then `krama setup`, then questions worked in PowerShell with no Ollama. Two things to train out in v0.2: Krama named a function `max` (hiding Python's own), and its tests compare with `== None`.
  - Short examples (no function, class or app defined) are no longer run by the self-check and show `[example code: not run]`, because running a two-line example only proved it ran.
  - Tests: 107 pass (agent: 19, with a scripted fake model).

- Step 6, training Krama on agent steps (round 3, a 1.5B pilot), 2026-11-19:
  - A new exam first (`eval/agent_exam.py`, `--set=exam`): 20 more projects (12 bugs, 8 that add code), written before any training data. They are used only to judge trained models, never to change krama or the data.
  - Training data (`data/agent_data.py`; the output, `data/agent_train.jsonl`, stays private like the rest of the training data):
    - Each seed is a working answer from the round-2 data (1,580 of them). 183 seeds were left out because their code was too close to a benchmark or exam project (same plain-Python name, or more than 60% alike). Afterwards no training file was more than 45% alike to any exam file.
    - A program breaks the seed's code with one small realistic slip, such as a swapped operator, an off-by-one or a removed `.strip()`, or it removes a function, method or endpoint that the tests need. The right steps are then run through krama's real tools on a copy, so every file view and test result in the data is real, and every example ends with the tests passing.
    - 2,474 examples: 1,117 bug fixes and 1,357 additions. In 198 of them the first action is a mistake (a mistyped `old`, or an attempt to change a test file) followed by the recovery. The model sees the mistake but is not trained to make it.
    - User paths are replaced with `C:\Users\student`, including the doubled-`\` form pytest prints.
  - Training (`kaggle/train_agent.py`): LoRA on Qwen2.5-Coder-1.5B-Instruct with the 1,578 round-2 tutor answers plus the 2,474 agent examples, 2 epochs, 500 steps, 84 minutes on one T4. It learns only from Krama's own turns. The layout is checked against Qwen's own chat template before training starts. It was converted to 4-bit with `kaggle/to_gguf.py` on a CPU session.
  - To keep the data readable, krama's test output is now shorter (`--tb=short`, no warnings), and steps inside libraries are replaced with "(N steps outside the project hidden)". An empty `old` in an empty file now gives just the new code.
  - Results, built-in engine, one run each (it repeats itself exactly):

    | Model | Exam 20 | Main 20 | Held-out 10 | Fresh 10 | Seconds per project |
    |---|---|---|---|---|---|
    | Krama 1.5B (round 2, no agent training) | 4 | 5 | 3 | 2 | 103 (exam) |
    | **Krama 1.5B round 3** | **14** | **13** | **7** | **5** | **33-36** |
    | Qwen2.5-Coder-7B (no training) | 17 | 17 | 8 | 9 | 113 (exam) |

    - On the exam, round 3 solved all 8 "add code" projects, including `exam-add-api-post`, which the 7B missed, but only 6 of 12 bugs.
    - All 21 misses (exam and 40) ran out of steps, almost all with replaces. The pattern: one wrong fix is applied, the tests still fail, and the model repeats the same reasoning ("Line 2 has `1` where it needs `0`") until the step limit. The training data never shows a fix that applies but leaves the tests failing, followed by a second look. That is the next thing to add.
    - The bug slips in the data are a small, fixed set. The model may now guess those kinds first, so bugs of other kinds are its weak spot.
  - Tutor answers did not get worse: the 24-task self-check (`selfcheck-run8.json`, `eval/selfcheck.py` now takes a model file) went from 14 to 17 (Python 10/12, FastAPI 7/12). 4 newly passing, 1 newly failing (`py-most-common`).
  - Numbers this small (20 to 40 projects) show a clear jump, not a finished agent. Krama is still a beginner-sized tool.
  - Tests: 109 pass.

## Not yet verified

- Teacher model throughput on Kaggle
- Licences of the task datasets (HumanEval is MIT, checked 2026-11-18)
