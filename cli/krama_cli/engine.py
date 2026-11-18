"""The built-in engine: llama.cpp's `llama-server`, set up by `krama setup`.

`krama setup` downloads two files into krama's own folder and checks each
one against a fingerprint (a SHA-256 hash) written below, so a broken or
changed download is never used:
    1. a ready-made llama.cpp build for this computer (13-25 MB, no compiler needed)
    2. the Krama model file (986 MB)

The engine version is pinned: every user gets exactly the build that was tested.
"""

import hashlib
import json
import os
import platform
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

LLAMA_TAG = "b12359"   # llama.cpp release of 2026-11-13
LLAMA_URL = "https://github.com/ggml-org/llama.cpp/releases/download/" + LLAMA_TAG + "/{name}"

# (system, chip) -> (file name, size in bytes, sha256), from GitHub's release record.
ENGINE_FILES = {
    ("windows", "x64"): ("llama-b12359-bin-win-cpu-x64.zip", 25097509,
                         "837c1655e87df3b66989f4be33a792a1399c785bf259038dc75c900096683e69"),
    ("windows", "arm64"): ("llama-b12359-bin-win-cpu-arm64.zip", 13455326,
                           "d27564c754478d2832789dfcebfc5ace018e36a224c41d810b7cbc1ba8243ec0"),
    ("macos", "arm64"): ("llama-b12359-bin-macos-arm64.tar.gz", 16907811,
                         "82b00abc740160e1b9980e6cc79c117345fa34af058c80e6c0a69aa8ddccde75"),
    ("macos", "x64"): ("llama-b12359-bin-macos-x64.tar.gz", 12661621,
                       "25320d529077ef5a3d16e7b5da26438f221d88c8c0930a32b0c79457f5eede56"),
    ("linux", "x64"): ("llama-b12359-bin-ubuntu-x64.tar.gz", 23311084,
                       "0bc1f091e8916102b6d8f2cf944233a620e90a0f856c72d0ce41150c65c2e72e"),
    ("linux", "arm64"): ("llama-b12359-bin-ubuntu-arm64.tar.gz", 18949862,
                         "dc7aa17a67884619b7223870aca9fd6addbc01717713b04a714add1c31137359"),
}

MODEL_NAME = "krama-coder-1.5b-q4_k_m.gguf"
MODEL_SIZE = 986048384
MODEL_SHA256 = "f3b45d79f586935aa31748345b7e407283180cb48b76973e42542529cb13dc8c"
MODEL_URL = "https://huggingface.co/CoBeDigger/krama-coder-1.5b/resolve/main/" + MODEL_NAME


class SetupError(Exception):
    """Something went wrong while setting up; the message says what to do."""


def this_computer():
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform,
                                                         "linux" if sys.platform.startswith("linux") else sys.platform)
    machine = platform.machine().lower()
    chip = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)
    return system, chip


def krama_home():
    """Where krama keeps its engine and model."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "krama"


def installed_record():
    return krama_home() / "installed.json"


# ---------------------------------------------------------------- files

def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, destination, size, sha256, say=print):
    """Download `url` to `destination`, resuming a broken download, then check it."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    have = partial.stat().st_size if partial.exists() else 0

    if have < size:
        request = urllib.request.Request(url, headers={"User-Agent": "krama-setup"})
        if have:
            request.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if have and response.status != 206:
                    have = 0                     # the server ignored "resume"; start again
                with open(partial, "ab" if have else "wb") as out:
                    shown = -1
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        out.write(block)
                        have += len(block)
                        percent = have * 100 // size
                        if percent // 10 != shown:
                            shown = percent // 10
                            say(f"    {destination.name}: {min(percent, 100)}%")
        except (urllib.error.URLError, OSError) as error:
            raise SetupError(f"Download of {destination.name} stopped ({error}). "
                             "Run `krama setup` again to continue where it stopped.") from error

    if sha256_of(partial) != sha256:
        partial.unlink()
        raise SetupError(f"{destination.name} did not match its fingerprint, so it was deleted. "
                         "Run `krama setup` again.")
    partial.replace(destination)


def safe_extract(archive, folder):
    """Unpack an archive, refusing any file that would land outside `folder`."""
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if str(archive).endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.namelist():
                if not (folder / member).resolve().is_relative_to(folder):
                    raise SetupError(f"The engine archive has an unsafe path: {member}")
            bundle.extractall(folder)
    else:
        with tarfile.open(archive) as bundle:
            if hasattr(tarfile, "data_filter"):
                bundle.extractall(folder, filter="data")
            else:
                for member in bundle.getmembers():
                    if not (folder / member.name).resolve().is_relative_to(folder) or member.issym() or member.islnk():
                        raise SetupError(f"The engine archive has an unsafe path: {member.name}")
                bundle.extractall(folder)


def find_server(folder):
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    found = sorted(Path(folder).rglob(name))
    if not found:
        raise SetupError(f"{name} was not found in the downloaded engine.")
    return found[0]


# ---------------------------------------------------------------- setup

def setup(model_file=None, say=print):
    """Install the engine and the model. Returns (server path, model path)."""
    system, chip = this_computer()
    if (system, chip) not in ENGINE_FILES:
        raise SetupError(f"There is no ready-made engine for {system} on {chip} yet. "
                         "Use Ollama instead: krama --backend ollama")
    home = krama_home()
    name, size, sha256 = ENGINE_FILES[(system, chip)]

    engine_folder = home / "engine" / LLAMA_TAG
    try:
        server = find_server(engine_folder)
        say(f"  engine: already set up ({LLAMA_TAG})")
    except SetupError:
        say(f"  engine: downloading llama.cpp {LLAMA_TAG} ({size / 1e6:.0f} MB)")
        archive = home / "downloads" / name
        download(LLAMA_URL.format(name=name), archive, size, sha256, say)
        shutil.rmtree(engine_folder, ignore_errors=True)
        safe_extract(archive, engine_folder)
        archive.unlink()
        server = find_server(engine_folder)
        if sys.platform != "win32":
            server.chmod(server.stat().st_mode | 0o111)

    model = home / "models" / MODEL_NAME
    if model.exists() and model.stat().st_size == MODEL_SIZE:
        say("  model: already set up")
    elif model_file:
        say(f"  model: checking {model_file}")
        if sha256_of(model_file) != MODEL_SHA256:
            raise SetupError(f"{model_file} is not the Krama v0.1 model file (fingerprint does not match).")
        model.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(model_file, model)
    else:
        say(f"  model: downloading Krama ({MODEL_SIZE / 1e6:.0f} MB, once)")
        download(MODEL_URL, model, MODEL_SIZE, MODEL_SHA256, say)

    installed_record().write_text(json.dumps(
        {"tag": LLAMA_TAG, "server": str(server), "model": str(model)}, indent=2), encoding="utf-8")
    return server, model


def installed():
    """(server path, model path) if `krama setup` has run, else None."""
    try:
        record = json.loads(installed_record().read_text(encoding="utf-8"))
        server, model = Path(record["server"]), Path(record["model"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if server.exists() and model.exists():
        return server, model
    return None
