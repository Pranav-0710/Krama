"""Backends: the engines that run the Krama model.

Every backend has the same small interface:

    backend.chat(messages, schema=None) -> the model's reply as text

`messages` is a list like [{"role": "user", "content": "..."}].
`schema`, if given, is a JSON schema the reply must follow (used later by the
agent, so its tool calls always have the right shape).

There are two backends:
    local    the built-in llama.cpp engine (`krama setup`), no Ollama needed
    ollama   the Ollama app
The rest of krama only ever calls chat(), so adding a backend does not
change anything else.
"""

import atexit
import json
import os
import socket
import sys
import urllib.error
import urllib.request

KRAMA_MODEL = "hf.co/CoBeDigger/krama-coder-1.5b"
TIME_LIMIT = 600   # seconds to wait for one reply (a slow CPU can take a while)


class BackendError(Exception):
    """The engine is missing, not running, or gave a reply we cannot read.

    The message is written for the user and says what to do.
    """


class Backend:
    name = "backend"

    def chat(self, messages, schema=None):
        raise NotImplementedError

    def close(self):
        """Stop anything the backend started. Nothing, by default."""


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model=KRAMA_MODEL, host=None):
        self.model = model
        host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        if not host.startswith("http"):
            host = "http://" + host
        self.url = host.rstrip("/") + "/api/chat"

    def chat(self, messages, schema=None):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            # 0 = always pick the most likely next word, so answers stay steady.
            "options": {"temperature": 0},
        }
        if schema is not None:
            body["format"] = schema
        request = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=TIME_LIMIT) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise BackendError(f"The model is not downloaded yet. Run:\n    ollama pull {self.model}") from error
            detail = error.read().decode("utf-8", errors="replace").strip()
            raise BackendError(f"Ollama answered with an error ({error.code}): {detail}") from error
        except (TimeoutError, socket.timeout) as error:
            raise BackendError(f"Ollama did not answer within {TIME_LIMIT} seconds.") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise BackendError(f"Ollama did not answer within {TIME_LIMIT} seconds.") from error
            raise BackendError("Could not reach Ollama. Start the Ollama app, then try again.") from error

        try:
            return json.loads(raw)["message"]["content"]
        except (ValueError, KeyError, TypeError) as error:
            raise BackendError("Ollama sent a reply krama could not read.") from error


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class LlamaServerBackend(Backend):
    """The built-in engine: llama.cpp's llama-server, installed by `krama setup`.

    krama starts it on first use, on this computer only (127.0.0.1), on a free
    port, and stops it when krama exits. No Ollama is needed.
    """

    name = "local"
    START_LIMIT = 120   # seconds to wait for the model to load
    CONTEXT = 4096      # tokens the engine keeps in view, the same as Ollama's default
    MAX_REPLY = 2048    # tokens per reply, so a reply that loops cannot run forever

    def __init__(self, model=KRAMA_MODEL, files=None, context=None):
        from krama_cli import engine
        found = files or engine.installed()
        if not found:
            raise BackendError("The built-in engine is not set up yet. Run:\n    krama setup")
        self.server, self.model_file = found
        if model.endswith(".gguf"):
            self.model_file = model            # a model file the user chose
        if context:
            self.CONTEXT = context             # the agent needs room for files and test output
        self.process = None
        self.job = None
        self.log_path = engine.krama_home() / "logs" / "llama-server.log"

    def start(self):
        import subprocess
        import time
        self.port = free_port()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(self.log_path, "wb")
        command = [str(self.server), "-m", str(self.model_file), "--host", "127.0.0.1",
                   "--port", str(self.port), "-c", str(self.CONTEXT), "--no-webui", "--jinja"]
        flags = 0x08000000 if sys.platform == "win32" else 0   # no extra console window
        self.process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                        stderr=subprocess.STDOUT, creationflags=flags)
        log.close()
        if sys.platform == "win32":
            from krama_cli import winjob
            self.job = winjob.tie_to_this_process(self.process)
        atexit.register(self.close)

        deadline = time.monotonic() + self.START_LIMIT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise BackendError(f"The built-in engine stopped while starting.\n{self.log_tail()}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass                                  # still loading
            time.sleep(0.25)
        self.close()
        raise BackendError(f"The built-in engine did not get ready within {self.START_LIMIT} seconds.\n{self.log_tail()}")

    def log_tail(self, lines=8):
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        except OSError:
            return ""
        return "Last lines of " + str(self.log_path) + ":\n" + "\n".join(text[-lines:])

    def chat(self, messages, schema=None):
        if self.process is None or self.process.poll() is not None:
            self.start()
        body = {"messages": messages, "stream": False, "temperature": 0, "seed": 0,
                "max_tokens": self.MAX_REPLY}
        if schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "reply", "schema": schema}}
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/v1/chat/completions",
                                         data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=TIME_LIMIT) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace").strip()
            raise BackendError(f"The built-in engine answered with an error ({error.code}): {detail}") from error
        except (TimeoutError, socket.timeout) as error:
            raise BackendError(f"The built-in engine did not answer within {TIME_LIMIT} seconds.") from error
        except urllib.error.URLError as error:
            raise BackendError(f"Lost contact with the built-in engine.\n{self.log_tail()}") from error
        try:
            return json.loads(raw)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise BackendError("The built-in engine sent a reply krama could not read.") from error

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except Exception:
                self.process.kill()
        if self.job:
            from krama_cli import winjob
            winjob.close(self.job)
            self.job = None


BACKENDS = {"local": LlamaServerBackend, "ollama": OllamaBackend}


def make_backend(name, model=KRAMA_MODEL, context=None):
    """`auto` picks the built-in engine if `krama setup` has run, else Ollama."""
    if name == "auto":
        from krama_cli import engine
        name = "local" if engine.installed() else "ollama"
    if name not in BACKENDS:
        raise BackendError(f"Unknown backend '{name}'. Choose one of: auto, {', '.join(BACKENDS)}")
    if name == "local":
        return LlamaServerBackend(model=model, context=context)
    return BACKENDS[name](model=model)
