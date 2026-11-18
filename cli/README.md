# krama (command-line tutor)

Ask the [Krama](https://huggingface.co/CoBeDigger/krama-coder-1.5b) model a Python or FastAPI question in your terminal.
Before it shows you code, it runs that code on your computer. If the code crashes, Krama gets the error and tries to fix it, up to two more times.

It works offline. Your questions and code never leave your computer.

## Install

1. Install the `krama` command (needs [uv](https://docs.astral.sh/uv/)). From the root of this repository:

   ```sh
   uv tool install ./cli
   ```

2. Set up the built-in engine. This downloads llama.cpp's ready-made engine for your computer (13-25 MB) and the Krama model (986 MB), once, and checks both against fixed fingerprints. No Ollama and no compiler are needed:

   ```sh
   krama setup
   ```

   Already have the model file? `krama setup --model-file path/to/krama-coder-1.5b-q4_k_m.gguf` uses it instead of downloading it again.

   Prefer Ollama? Skip `krama setup` and run `ollama pull hf.co/CoBeDigger/krama-coder-1.5b` instead. krama uses the built-in engine when it is set up, and Ollama otherwise (`--backend local` or `--backend ollama` chooses one).

Files go in `%LOCALAPPDATA%\krama` on Windows, `~/Library/Application Support/krama` on macOS and `~/.local/share/krama` on Linux.

## Use

```sh
krama "write a function that returns the largest number in a list"
```

Run `krama` on its own to keep asking questions; type `exit` to stop.

Each answer ends with one line about the self-check:

- `self-check passed`: the code ran from top to bottom without an error. That does **not** prove it gives the right answer, so try it with your own inputs.
- `self-check FAILED`: Krama could not fix the error in three tries. The error is shown.
- `self-check skipped`: the code was not run, and the line says why. For example, FastAPI is not installed, or the code deletes files.

Options: `--no-check` shows the answer without running it, `--yes` runs the self-check without asking, `--backend ollama` picks the engine (Ollama is the only one so far), `--model NAME` uses another model, and `--python PATH` picks the Python that runs the check (by default, the `python` on your PATH, so the libraries in your project are found).

## Safety

The self-check runs model-written code on your computer, so it is careful in layers:

1. **It asks you first.** Answer `y` (yes), `n` (no) or `a` (always; saved in `%LOCALAPPDATA%\krama\settings.json` on Windows, `~/.config/krama/settings.json` elsewhere). `--yes` allows it for one run. With no terminal to ask in, it does not run the code.
2. **It looks before running.** Code that deletes or writes files, starts programs, uses the network, or tries tricks to get around this look is not run.
3. **It runs the code in a limited process:** a new empty folder, none of your secret settings (environment variables such as tokens), 10 seconds and 512 MB at most. On Windows the code also cannot start other programs, and it is killed together with anything it started.
4. **It only suggests installing well-known libraries.** If the code imports a module that is not on its list, krama treats the name as a possible mistake. It does not tell you to install it, because a made-up name could match a fake package.

This is a guard, not a full sandbox: the code could still read your files or reach the network in ways step 2 does not spot. Read code before you run it yourself. The Windows limits are tested; the macOS and Linux limits are written but not yet tested on those systems.
