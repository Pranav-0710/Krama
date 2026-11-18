"""Tests for the backends. No real Ollama is needed: the network call is faked."""

import io
import json
import socket
import urllib.error

import pytest

from krama_cli import backends
from krama_cli.backends import BackendError, OllamaBackend, make_backend


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(reply=None, error=None, seen=None):
    def urlopen(request, timeout):
        if seen is not None:
            seen.append(json.loads(request.data))
        if error is not None:
            raise error
        return FakeResponse(reply)
    return urlopen


def test_sends_the_conversation_and_returns_the_reply(monkeypatch):
    seen = []
    reply = json.dumps({"message": {"role": "assistant", "content": "hello"}}).encode()
    monkeypatch.setattr(backends.urllib.request, "urlopen", fake_urlopen(reply, seen=seen))
    messages = [{"role": "user", "content": "hi"}]
    assert OllamaBackend(model="m").chat(messages) == "hello"
    assert seen[0]["model"] == "m"
    assert seen[0]["messages"] == messages
    assert seen[0]["options"]["temperature"] == 0
    assert "format" not in seen[0]


def test_a_schema_is_passed_as_ollamas_format(monkeypatch):
    seen = []
    reply = json.dumps({"message": {"content": "{}"}}).encode()
    monkeypatch.setattr(backends.urllib.request, "urlopen", fake_urlopen(reply, seen=seen))
    schema = {"type": "object", "properties": {"tool": {"enum": ["read_file"]}}}
    OllamaBackend().chat([], schema=schema)
    assert seen[0]["format"] == schema


def http_error(code, body=b""):
    return urllib.error.HTTPError("http://x", code, "error", {}, io.BytesIO(body))


@pytest.mark.parametrize("error, words", [
    (http_error(404), "ollama pull"),
    (http_error(500, b"out of memory"), "out of memory"),
    (urllib.error.URLError(ConnectionRefusedError()), "Start the Ollama app"),
    (urllib.error.URLError(socket.timeout()), "did not answer"),
    (TimeoutError(), "did not answer"),
])
def test_errors_become_one_clear_message(monkeypatch, error, words):
    monkeypatch.setattr(backends.urllib.request, "urlopen", fake_urlopen(error=error))
    with pytest.raises(BackendError, match=words):
        OllamaBackend().chat([])


@pytest.mark.parametrize("raw", [b"not json", b'{"no_message": 1}', b'{"message": null}'])
def test_unreadable_replies_become_one_clear_message(monkeypatch, raw):
    monkeypatch.setattr(backends.urllib.request, "urlopen", fake_urlopen(raw))
    with pytest.raises(BackendError, match="could not read"):
        OllamaBackend().chat([])


def test_host_setting_is_respected(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9999")
    assert OllamaBackend().url == "http://127.0.0.1:9999/api/chat"


def test_unknown_backend_is_refused():
    with pytest.raises(BackendError, match="Unknown backend"):
        make_backend("nope")
    assert isinstance(make_backend("ollama"), OllamaBackend)
