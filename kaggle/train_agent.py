"""Step 6: train Krama (round 3 = pilot, round 4 = more bug kinds and second looks)
on tutor answers AND agent steps. Runs on Kaggle or Google Colab.

Kaggle: run it in ONE cell (typing long files into the browser breaks them):
    import glob; exec(open(glob.glob("/kaggle/input/**/train_agent.py", recursive=True)[0]).read())
    Settings: Accelerator = GPU T4 x2, Internet = On. Data: the private krama-train dataset.

Colab: put train.jsonl, the agent file named in AGENT_FILE and this file in the Drive folder
My Drive/krama-train, choose Runtime > Change runtime type > T4 GPU, then run ONE cell:
    from google.colab import drive; drive.mount("/content/drive")
    exec(open("/content/drive/MyDrive/krama-train/train_agent.py").read())
    Checkpoints and the finished model go to My Drive/krama-work, so they
    survive a disconnect.

What it does:
    reads train.jsonl (round 2's 1,578 tutor answers) and agent_train.jsonl
        (agent trajectories from data/agent_data.py)
    teaches Qwen2.5-Coder-1.5B-Instruct both, with LoRA, as in round 2
    learns only from Krama's own turns: never from questions, tool replies,
        or the mistakes marked "train": false in the trajectories
    merges and saves the model as krama-coder-1.5b<SUFFIX>, then shows one agent step

Safe to stop and run again: it carries on from the last saved checkpoint (every 50 steps).
"""

import glob
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

# ---------------- settings ----------------
BASE = "Qwen/Qwen2.5-Coder-1.5B-Instruct"   # Apache 2.0 licence
SYSTEM = ("You are Krama, a Python and FastAPI coding assistant for beginners, "
          "fine-tuned by CoBeDigger from Qwen2.5-Coder-1.5B-Instruct.")   # same as round 2 and the krama tool
MAX_LENGTH = 4096      # agent steps hold whole files and test output; longer ones are left out, never cut
EPOCHS = 2
LEARNING_RATE = 2e-4
WARMUP_SHARE = 0.03
BATCH = 2              # long examples: 2 per step, added up 8 times (2 x 8 = 16, as in round 2)
ACCUMULATE = 8
LORA_RANK = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
HELD_OUT = 60
SUFFIX = "-r5"
AGENT_FILE = "agent_train_r5.jsonl"   # r3/r4: agent_train.jsonl; r5: round 4's examples in round 3's mix (data/mix_r5.py)
# Colab first: Colab also has a /kaggle/input folder, so that folder alone does not mean Kaggle.
ON_KAGGLE = "COLAB_RELEASE_TAG" not in os.environ and Path("/kaggle/input").exists()
if ON_KAGGLE:
    INPUT, WORK = Path("/kaggle/input"), Path("/kaggle/working")
else:   # Google Colab, with Drive mounted at /content/drive
    INPUT, WORK = Path("/content/drive/MyDrive/krama-train"), Path("/content/drive/MyDrive/krama-work")
# ------------------------------------------

QWEN_DEFAULT = "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."


def find(name):
    found = glob.glob(f"{INPUT}/**/{name}", recursive=True)
    if not found:
        where = ("Add the private krama-train dataset (newest version) with 'Add Input'." if ON_KAGGLE else
                 "Mount Drive first and put it in My Drive/krama-train.")
        raise SystemExit(f"{name} not found in {INPUT}. {where}")
    return [json.loads(line) for line in open(found[0], encoding="utf-8")]


def conversation(row):
    """Every row as a full chat. Tutor rows get Krama's system line, as the krama tool sends it."""
    messages = row["messages"]
    if messages[0]["role"] != "system":
        messages = [{"role": "system", "content": SYSTEM}] + messages
    return messages


def layout(messages):
    """The whole chat as one text in Qwen's layout, and the character spans to learn.

    Each turn is <|im_start|>role\\ncontent<|im_end|>\\n. Only Krama's own turns are
    learnt (not ones marked "train": false), with their <|im_end|> so it learns to stop.
    """
    text, spans = "", []
    for message in messages:
        text += f"<|im_start|>{message['role']}\n"
        start = len(text)
        text += message["content"] + "<|im_end|>\n"
        if message["role"] == "assistant" and message.get("train", True):
            spans.append((start, len(text)))
    return text, spans


def encode(messages, tokenizer):
    """Token numbers, and labels that say which ones to learn (-100 = do not learn).
    The whole text is turned into tokens at once, as the engine does when Krama is used."""
    text, spans = layout(messages)
    tokens = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    labels = [token if any(start <= begin < end for start, end in spans) else -100
              for token, (begin, _) in zip(tokens["input_ids"], tokens["offset_mapping"])]
    return tokens["input_ids"], labels


def build_examples(rows, tokenizer):
    examples, too_long = [], 0
    for row in rows:
        input_ids, labels = encode(conversation(row), tokenizer)
        if len(input_ids) > MAX_LENGTH:
            too_long += 1
            continue
        examples.append({"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels})
    return examples, too_long


def main():
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "peft"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-q", "-y", "torchao"], check=True)

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq,
                              Trainer, TrainingArguments)
    from transformers.trainer_utils import get_last_checkpoint

    WORK.mkdir(parents=True, exist_ok=True)
    tutor, agent = find("train.jsonl"), find(AGENT_FILE)
    rows = tutor + agent
    random.Random(0).shuffle(rows)
    tokenizer = AutoTokenizer.from_pretrained(BASE)

    # Our layout must be exactly Qwen's own, or Krama learns a format it never sees in use.
    for sample in (conversation(agent[0]), conversation(tutor[0])):
        if layout(sample)[0] != tokenizer.apply_chat_template(sample, tokenize=False):
            raise SystemExit("The chat layout does not match Qwen's template; stop and check layout().")

    examples, too_long = build_examples(rows, tokenizer)
    held_out, train = examples[:HELD_OUT], examples[HELD_OUT:]
    learnt = sum(sum(label != -100 for label in example["labels"]) for example in train)
    print(f"rows: {len(tutor)} tutor + {len(agent)} agent  too long, left out: {too_long}  "
          f"training: {len(train)}  held out: {len(held_out)}  tokens learnt per epoch: {learnt}")

    model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float16, device_map={"": 0})
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=LORA_RANK, lora_alpha=LORA_ALPHA, lora_dropout=LORA_DROPOUT,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type="CAUSAL_LM",
    ))
    for parameter in model.parameters():
        if parameter.requires_grad:
            parameter.data = parameter.data.float()
    model.print_trainable_parameters()

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

    model.save_pretrained(str(WORK / f"krama-lora{SUFFIX}"))
    model = model.merge_and_unload()
    tokenizer.chat_template = tokenizer.chat_template.replace(QWEN_DEFAULT, SYSTEM)
    if SYSTEM not in tokenizer.chat_template:
        print("WARNING: could not set Krama's default instruction in the chat template.")
    out_dir = WORK / f"krama-coder-1.5b{SUFFIX}"
    model.save_pretrained(str(out_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(out_dir))
    print(f"saved the finished model to {out_dir}")

    # A first agent step (from the training data: this only shows the reply format)
    # and one tutor question, to see both still work. The real test is the exam, back home.
    model.eval()
    first_step = conversation(agent[-1])[:2]
    for messages in (first_step, [{"role": "user", "content": "what does the len function do"}]):
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(**inputs, max_new_tokens=300, do_sample=False)
        print(f"\n=== {messages[-1]['content'][:120]!r}\n"
              f"{tokenizer.decode(output[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)}")


if __name__ == "__main__":
    main()
