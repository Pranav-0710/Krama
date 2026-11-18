"""Backends: the engines that run the Krama model.

Every backend has the same small interface:

    backend.chat(messages, schema=None) -> the model's reply as text

`messages` is a list like [{"role": "user", "content": "..."}].
`schema`, if given, is a JSON schema the reply must follow (used later by the
agent, so its tool calls always have the right shape).

Today there is one backend, Ollama. A built-in llama.cpp backend comes next,
so krama can run without Ollama. The rest of krama only ever calls chat(),
so adding a backend does not change anything else.
"""

import json
import os
import socket
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


BACKENDS = {"ollama": OllamaBackend}


def make_backend(name, model=KRAMA_MODEL):
    if name not in BACKENDS:
        raise BackendError(f"Unknown backend '{name}'. Choose one of: {', '.join(BACKENDS)}")
    return BACKENDS[name](model=model)
