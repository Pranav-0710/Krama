"""Before the exam: turn the trained Krama into one small 4-bit file for Ollama.

Paste this whole file into ONE cell of the training notebook (the one whose
/kaggle/working holds krama-coder-1.5b). No GPU is needed: set Accelerator
to None so it costs no GPU quota. Internet must be On.

Why 4-bit Q4_K_M: the base model in the exam was the default Ollama file,
which is Q4_K_M. Krama must be shrunk the same way, or the comparison is unfair.

How: llama.cpp is the open-source project that created the GGUF file format
(Ollama runs on it). Its converter turns the trained model into one GGUF
file, then its quantize tool shrinks that file to Q4_K_M.
(Ollama itself can no longer make Q4_K_M files from a trained model.)
"""

import subprocess
import sys
from pathlib import Path

ROUND = 3              # must match the training script: 2 = train.py, 3 = train_agent.py (step 6 pilot)
SUFFIX = "" if ROUND == 1 else f"-r{ROUND}"
MODEL_DIR = Path(f"/kaggle/working/krama-coder-1.5b{SUFFIX}")
TOOLS = Path("/tmp/llama.cpp")              # not in /kaggle/working, so it is not saved
FULL_FILE = Path("/tmp/krama-coder-1.5b-f16.gguf")   # full size, about 3 GB
OUT_FILE = Path(f"/kaggle/working/krama-coder-1.5b{SUFFIX}-q4_k_m.gguf")


def run(command):
    print(f"$ {command}", flush=True)
    subprocess.run(command, shell=True, check=True)


def main():
    if not (MODEL_DIR / "config.json").exists():
        raise SystemExit(f"{MODEL_DIR} not found. Run this in the notebook that trained Krama.")

    # 1. Get llama.cpp and the small Python library its converter needs.
    if not TOOLS.exists():
        run(f"git clone --depth 1 https://github.com/ggml-org/llama.cpp {TOOLS}")
    run(f"{sys.executable} -m pip install -q {TOOLS}/gguf-py")

    # 2. Trained model folder -> one full-size GGUF file.
    run(f"{sys.executable} {TOOLS}/convert_hf_to_gguf.py {MODEL_DIR} --outtype f16 --outfile {FULL_FILE}")

    # 3. Build the quantize tool (a few minutes), then shrink to 4-bit Q4_K_M.
    run(f"cmake -S {TOOLS} -B {TOOLS}/build -DLLAMA_CURL=OFF -DGGML_NATIVE=OFF")
    run(f"cmake --build {TOOLS}/build --target llama-quantize -j 4")
    run(f"{TOOLS}/build/bin/llama-quantize {FULL_FILE} {OUT_FILE} Q4_K_M")

    size_mb = OUT_FILE.stat().st_size / 1_000_000
    print(f"saved {OUT_FILE} ({size_mb:.0f} MB). Download it from the Output panel.")


if __name__ == "__main__":
    main()
