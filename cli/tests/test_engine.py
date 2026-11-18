"""Tests for `krama setup` (engine.py). Downloads come from a tiny local web
server started by the test, so no internet is needed."""

import hashlib
import http.server
import io
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from krama_cli import engine
from krama_cli.backends import BackendError, LlamaServerBackend, OllamaBackend, make_backend
from krama_cli.engine import SetupError, download, safe_extract


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Point krama's data folder at a temporary folder."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(engine.Path, "home", lambda: tmp_path)
    return engine.krama_home()


@pytest.fixture
def web():
    """A local web server that serves `files` and understands "resume" (Range)."""
    files = {}
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.headers.get("Range"))
            data = files[self.path]
            start = 0
            if self.headers.get("Range"):
                start = int(self.headers["Range"].split("=")[1].split("-")[0])
                self.send_response(206)
            else:
                self.send_response(200)
            self.send_header("Content-Length", str(len(data) - start))
            self.end_headers()
            self.wfile.write(data[start:])

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", files, requests
    server.shutdown()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_download_checks_the_fingerprint(tmp_path, web):
    url, files, _ = web
    files["/f"] = b"hello" * 1000
    target = tmp_path / "f.bin"
    download(url + "/f", target, len(files["/f"]), sha(files["/f"]), say=lambda text: None)
    assert target.read_bytes() == files["/f"]


def test_a_broken_download_resumes_where_it_stopped(tmp_path, web):
    url, files, requests = web
    files["/f"] = bytes(range(256)) * 100
    target = tmp_path / "f.bin"
    (tmp_path / "f.bin.part").write_bytes(files["/f"][:1000])      # what arrived before a break
    download(url + "/f", target, len(files["/f"]), sha(files["/f"]), say=lambda text: None)
    assert requests == ["bytes=1000-"]
    assert target.read_bytes() == files["/f"]


def test_a_wrong_file_is_deleted_not_used(tmp_path, web):
    url, files, _ = web
    files["/f"] = b"not the real file"
    target = tmp_path / "f.bin"
    with pytest.raises(SetupError, match="fingerprint"):
        download(url + "/f", target, len(files["/f"]), sha(b"the real file"), say=lambda text: None)
    assert not target.exists()
    assert not (tmp_path / "f.bin.part").exists()


def test_an_archive_cannot_write_outside_its_folder(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escaped.txt", "x")
    with pytest.raises(SetupError, match="unsafe path"):
        safe_extract(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def make_engine_zip():
    buffer = io.BytesIO()
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(f"build/bin/{name}", "#!/bin/sh\n")
    return buffer.getvalue()


def use_test_engine(monkeypatch, url, files):
    files["/engine.zip"] = make_engine_zip()
    monkeypatch.setitem(engine.ENGINE_FILES, engine.this_computer(),
                        ("engine.zip", len(files["/engine.zip"]), sha(files["/engine.zip"])))
    monkeypatch.setattr(engine, "LLAMA_URL", url + "/{name}")


def test_setup_installs_engine_and_model_and_records_them(home, web, monkeypatch):
    url, files, _ = web
    use_test_engine(monkeypatch, url, files)
    files["/model.gguf"] = b"GGUF pretend model"
    monkeypatch.setattr(engine, "MODEL_URL", url + "/model.gguf")
    monkeypatch.setattr(engine, "MODEL_SIZE", len(files["/model.gguf"]))
    monkeypatch.setattr(engine, "MODEL_SHA256", sha(files["/model.gguf"]))

    assert engine.installed() is None
    server, model = engine.setup(say=lambda text: None)
    assert server.name.startswith("llama-server")
    assert model.read_bytes() == files["/model.gguf"]
    assert engine.installed() == (server, model)
    # Running it again downloads nothing.
    files.clear()
    assert engine.setup(say=lambda text: None) == (server, model)


def test_setup_refuses_a_model_file_that_is_not_krama(home, web, monkeypatch, tmp_path):
    url, files, _ = web
    use_test_engine(monkeypatch, url, files)
    wrong = tmp_path / "other.gguf"
    wrong.write_bytes(b"some other model")
    with pytest.raises(SetupError, match="not the Krama"):
        engine.setup(model_file=wrong, say=lambda text: None)


def test_local_backend_says_to_run_setup_first(home):
    with pytest.raises(BackendError, match="krama setup"):
        LlamaServerBackend()


def test_auto_uses_ollama_until_setup_has_run(home, monkeypatch):
    assert isinstance(make_backend("auto"), OllamaBackend)
    monkeypatch.setattr(engine, "installed", lambda: (Path("server"), Path("model.gguf")))
    assert isinstance(make_backend("auto"), LlamaServerBackend)


def test_local_backend_reports_an_engine_that_will_not_start(home, tmp_path):
    # A "server" that exits at once, so start() must stop waiting and explain.
    fake = tmp_path / ("fake.bat" if sys.platform == "win32" else "fake.sh")
    fake.write_text("exit 3\n" if sys.platform == "win32" else "#!/bin/sh\nexit 3\n")
    fake.chmod(0o755)
    backend = LlamaServerBackend(files=(fake, tmp_path / "model.gguf"))
    with pytest.raises(BackendError, match="stopped while starting"):
        backend.chat([{"role": "user", "content": "hi"}])
    backend.close()
