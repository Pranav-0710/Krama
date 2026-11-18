# krama (command-line tutor)

Ask the [Krama](https://huggingface.co/CoBeDigger/krama-coder-1.5b) model a Python or FastAPI question in your terminal.
Before it shows you code, it runs that code on your computer. If the code crashes, Krama gets the error and tries to fix it, up to two more times.

It works offline. Your questions and code never leave your computer.

## Install

1. Install [Ollama](https://ollama.com) and download Krama (986 MB, once):

   ```sh
   ollama pull hf.co/CoBeDigger/krama-coder-1.5b
   ```

2. Install the `krama` command from this folder (needs [uv](https://docs.astral.sh/uv/)):

   ```sh
   uv tool install ./cli
   ```

## Use

```sh
krama "write a function that returns the largest number in a list"
```

Run `krama` on its own to keep asking questions; type `exit` to stop.

Each answer ends with one line about the self-check:

- `self-check passed`: the code ran from top to bottom without an error. That does **not** prove it gives the right answer, so try it with your own inputs.
- `self-check FAILED`: Krama could not fix the error in three tries. The error is shown.
- `self-check skipped`: the code was not run, and the line says why. For example, FastAPI is not installed, or the code deletes files.

Options: `--no-check` shows the answer without running it, `--model NAME` uses another Ollama model, and `--python PATH` picks the Python that runs the check (by default, the `python` on your PATH, so the libraries in your project are found).

## Safety

The self-check runs model-written code on your computer, in a new empty folder, with a 10-second limit.
Before running, it refuses code that deletes or writes files, starts other programs, or uses the network.
This is a simple guard, not a full sandbox. Read code before running it yourself.
