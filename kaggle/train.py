"""Phase 2, box 2.6: training. Paste this whole file into ONE Kaggle cell.

What it does:
    reads the training examples (train.jsonl, added as a Kaggle dataset)
    teaches Qwen2.5-Coder-1.5B-Instruct with LoRA: small extra dials are
        trained while the original 1.5 billion dials stay frozen
    merges the extra dials into one finished model: Krama
    asks Krama two new questions so you can see it work

Kaggle settings needed: Accelerator = GPU T4 x2, Internet = On.
Safe to stop and run again: it carries on from the last saved checkpoint.

The settings below are the ones agreed in README.md. Do not change them
casually: the exam results are only comparable if they stay fixed.
"""

import glob
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

# ---------------- settings (from README.md) ----------------
BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"   # Apache 2.0 licence
# Round 2 names the maker here: round 1's 15 identity examples alone did not
# teach Krama who made it. The Modelfile's SYSTEM line must match this one.
SYSTEM = ("You are Krama, a Python and FastAPI coding assistant for beginners, "
          "fine-tuned by CoBeDigger from Qwen2.5-Coder-1.5B-Instruct.")
MAX_LENGTH = 1024      # longer examples are left out, never cut short
EPOCHS = 2             # each example is seen twice
LEARNING_RATE = 2e-4
WARMUP_SHARE = 0.03    # the first 3% of steps start gently
BATCH = 4              # examples per step on the GPU
ACCUMULATE = 4         # add up 4 steps before changing the dials (4 x 4 = 16)
LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
HELD_OUT = 60          # examples kept aside to check the model is not just memorising
WORK = Path("/kaggle/working")
ROUND = 2              # each round saves to its own folders, so it never resumes an older round
SUFFIX = "" if ROUND == 1 else f"-r{ROUND}"   # round 1 used the plain names
# ------------------------------------------------------------

# Qwen's own default instruction. The finished model gets Krama's instead.
QWEN_DEFAULT = "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."


def build_examples(rows, tokenizer):
    """Turn each conversation into numbers, and mark which numbers to learn from.

    The model should learn to WRITE answers, not to write questions. So the
    question part gets the label -100, which means "do not learn from this".
    Returns (examples, how many were too long).
    """
    examples, too_long = [], 0
    for row in rows:
        question, answer = row["messages"][0]["content"], row["messages"][1]["content"]
        prompt = tokenizer.apply_chat_template(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
            tokenize=False,
            add_generation_prompt=True,
        )
        # <|im_end|> is Qwen's "I have finished" mark. Learning it teaches Krama to stop.
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        answer_ids = tokenizer(answer + "<|im_end|>\n", add_special_tokens=False)["input_ids"]
        input_ids = prompt_ids + answer_ids
        if len(input_ids) > MAX_LENGTH:
            too_long += 1
            continue
        examples.append({
            "input_ids": input_ids,
            "attention_mask": [1] * len(input_ids),
            "labels": [-100] * len(prompt_ids) + answer_ids,
        })
    return examples, too_long


def main():
    # Use one GPU only. With two, the batch size would silently double.
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "peft"], check=True)
    # Kaggle ships an old torchao that the newest peft refuses to work with.
    # Krama does not use torchao, so remove it. (Restart the kernel if peft was already imported.)
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-q", "-y", "torchao"], check=True)

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq,
                              Trainer, TrainingArguments)
    from transformers.trainer_utils import get_last_checkpoint

    # ---------- the examples ----------
    found = glob.glob("/kaggle/input/**/train.jsonl", recursive=True)
    if not found:
        raise SystemExit("train.jsonl not found. Add the private krama-train dataset with 'Add Input' first.")
    rows = [json.loads(line) for line in open(found[0], encoding="utf-8")]
    random.Random(0).shuffle(rows)

    tokenizer = AutoTokenizer.from_pretrained(BASE)
    examples, too_long = build_examples(rows, tokenizer)
    held_out, train = examples[:HELD_OUT], examples[HELD_OUT:]
    print(f"examples: {len(rows)}  too long, left out: {too_long}  "
          f"training: {len(train)}  held out: {len(held_out)}")

    # ---------- the base model, with LoRA dials added ----------
    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float16, device_map={"": 0})
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        # "All linear layers": every place inside the model where numbers are multiplied by dials.
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type="CAUSAL_LM",
    ))
    # The new dials train in full precision; fp16 is too coarse for small updates.
    for parameter in model.parameters():
        if parameter.requires_grad:
            parameter.data = parameter.data.float()
    model.print_trainable_parameters()

    # ---------- training ----------
    steps = math.ceil(len(train) / (BATCH * ACCUMULATE)) * EPOCHS
    checkpoints = WORK / f"checkpoints{SUFFIX}"
    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(checkpoints),
            num_train_epochs=EPOCHS,
            per_device_train_batch_size=BATCH,
            per_device_eval_batch_size=BATCH,
            gradient_accumulation_steps=ACCUMULATE,
            learning_rate=LEARNING_RATE,
            lr_scheduler_type="cosine",
            warmup_steps=max(1, round(steps * WARMUP_SHARE)),
            fp16=True,
            # Similar lengths together = less padding = faster. (transformers 5 name;
            # older versions call it group_by_length=True.)
            train_sampling_strategy="group_by_length",
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=50,
            save_strategy="steps",
            save_steps=50,
            save_total_limit=2,
            report_to="none",
        ),
        train_dataset=train,
        eval_dataset=held_out,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100),
    )
    resume = get_last_checkpoint(str(checkpoints)) if checkpoints.exists() else None
    print(f"steps: {steps}  carrying on from: {resume or 'the start'}")
    trainer.train(resume_from_checkpoint=resume)

    # ---------- save: the small adapter, then the merged model ----------
    model.save_pretrained(str(WORK / f"krama-lora{SUFFIX}"))
    model = model.merge_and_unload()
    tokenizer.chat_template = tokenizer.chat_template.replace(QWEN_DEFAULT, SYSTEM)
    if SYSTEM not in tokenizer.chat_template:
        print("WARNING: could not set Krama's default instruction in the chat template.")
    out_dir = WORK / f"krama-coder-1.5b{SUFFIX}"
    model.save_pretrained(str(out_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(out_dir))
    print(f"saved the finished model to {out_dir}")

    # ---------- two new questions, to see Krama work ----------
    model.eval()
    for question in ["write a function that returns the initials of a full name, like 'Asha Rao' -> 'AR'",
                     "what does the len function do",
                     "who made you",
                     "fastapi endpoint GET /planets that returns a list of planet names"]:
        text = tokenizer.apply_chat_template([{"role": "user", "content": question}],
                                             tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=400, do_sample=False)
        print(f"\n=== {question}\n{tokenizer.decode(output[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)}")


if __name__ == "__main__":
    main()
