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

## Not yet verified

- Teacher model throughput on Kaggle
- Licences of the benchmark and task datasets
