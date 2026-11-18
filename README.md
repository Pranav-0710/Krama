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

  - Win rule (`eval/RUBRIC.md`): round 2 is not less correct than the base on our tasks (10/12 and 6/12 against 9/12 and 6/12), and it scores higher than the instructed base on the graded rules. Task by task against the instructed base, it wins 7, ties 15 and loses 2 coding tasks, and wins 3 and ties 3 quick questions. The coding margin is small (6.25 against 5.96 out of 8); the quick-answer margin is clear.
  - On HumanEval it is still 8 tasks below the base, so the win holds on our tasks only.
  - Change from the plan: the rubric said the grader sees all answers at once. Llama 3.1 8B mixed answers up that way (it gave one answer credit for another's plan), so each answer is graded alone, still unnamed and shuffled.
  - The grader is lenient. Checked against a simple test (numbered steps before the first code block), its plan score was right for all 72 answers from the three instructed or fine-tuned systems, but 23 of the plain base's 24 answers had no plan and it still gave 16 of those a plan score (it counted a numbered list after the code). This flatters the base, not Krama. "Why is true" was added after training and is not part of the win rule; it shows no clear difference.

## Not yet verified

- Teacher model throughput on Kaggle
- Licences of the task datasets (HumanEval is MIT, checked 2026-11-18)
