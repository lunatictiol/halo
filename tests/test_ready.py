import importlib
import io
import json
import urllib.error

import pytest
from fastapi.testclient import TestClient
from huggingface_hub.errors import LocalEntryNotFoundError

from halo.api import app as app_module
from halo.api import ready
from halo.config import load_config

pull_models = importlib.import_module("scripts.pull_models")

CFG = {"models": {"llm": "qwen3:8b", "embedding": "nomic-embed-text", "ollama_url": "http://ollama:11434"},
       "api": {"ollama_timeout_s": 3}}


class FakeIndex:
    def __init__(self, collections: dict[str, int]):
        self.collections = collections

    def collection_exists(self, name):
        return name in self.collections

    def count(self, name):
        return type("Count", (), {"count": self.collections[name]})()


class FakeRetriever:
    collection = "full"

    def __init__(self, collections: dict[str, int]):
        self.client, self.closed = FakeIndex(collections), False

    def close(self):
        self.closed = True


def tags(*names):
    return lambda url, timeout: io.BytesIO(json.dumps({"models": [{"name": n} for n in names]}).encode())


def ndjson(*messages):
    return lambda req: io.BytesIO("".join(json.dumps(m) + "\n" for m in messages).encode())


def test_index_problem_names_missing_and_empty_collections():
    assert ready.index_problem(FakeIndex({"full": 5}), "full") is None
    assert "not found" in ready.index_problem(FakeIndex({}), "full")
    assert "empty" in ready.index_problem(FakeIndex({"full": 0}), "full")


def test_startup_fails_with_the_fix_in_the_message_and_closes_the_index_when_it_is_missing(monkeypatch):
    retriever = FakeRetriever({})
    monkeypatch.setattr(app_module, "build_pipeline", lambda cfg: (object(), retriever))
    with pytest.raises(RuntimeError, match="build it first"), TestClient(app_module.create_app()):
        pass
    assert retriever.closed


def test_startup_succeeds_and_closes_the_index_on_shutdown_when_the_collection_has_points(monkeypatch):
    retriever = FakeRetriever({"full": 3})
    monkeypatch.setattr(app_module, "build_pipeline", lambda cfg: (object(), retriever))
    with TestClient(app_module.create_app()) as client:
        assert client.get("/health").status_code == 200
        assert not retriever.closed
    assert retriever.closed


def test_ollama_ready_when_both_models_present_including_latest_tag(monkeypatch):
    monkeypatch.setattr(ready.urllib.request, "urlopen", tags("qwen3:8b", "nomic-embed-text:latest"))
    assert ready.ollama_problems(CFG) == []


def test_ollama_reports_each_missing_model(monkeypatch):
    monkeypatch.setattr(ready.urllib.request, "urlopen", tags("qwen3:8b"))
    assert ready.ollama_problems(CFG) == ["model 'nomic-embed-text' not pulled"]


def test_ollama_unreachable_is_a_problem_not_an_exception(monkeypatch):
    def down(url, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(ready.urllib.request, "urlopen", down)
    [problem] = ready.ollama_problems(CFG)
    assert "unreachable" in problem and "connection refused" in problem


def test_ollama_answering_something_unexpected_is_a_problem_not_an_exception(monkeypatch):
    monkeypatch.setattr(ready.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"<html>proxy error</html>"))
    [problem] = ready.ollama_problems(CFG)
    assert "unreachable" in problem


def test_ready_endpoint_is_503_with_reasons_until_ollama_is_ready():
    client = TestClient(app_module.create_app(graph=object(), ready=lambda: ["model 'qwen3:8b' not pulled"]))
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "not ready", "problems": ["model 'qwen3:8b' not pulled"]}
    assert TestClient(app_module.create_app(graph=object(), ready=lambda: [])).get("/ready").json() == {"status": "ready"}


def test_pull_prints_each_status_once_and_needs_a_final_success(monkeypatch, capsys):
    monkeypatch.setattr(pull_models.urllib.request, "urlopen",
                        ndjson({"status": "pulling abc"}, {"status": "pulling abc"}, {"status": "success"}))
    pull_models.pull("http://ollama:11434", "qwen3:8b")
    assert capsys.readouterr().out.splitlines() == ["qwen3:8b: pulling abc", "qwen3:8b: success"]


def test_pull_raises_on_an_error_line(monkeypatch):
    monkeypatch.setattr(pull_models.urllib.request, "urlopen", ndjson({"error": "pull model manifest: not found"}))
    with pytest.raises(SystemExit, match="manifest: not found"):
        pull_models.pull("http://ollama:11434", "nope")


def test_pull_raises_when_the_stream_ends_without_success(monkeypatch):
    monkeypatch.setattr(pull_models.urllib.request, "urlopen", ndjson({"status": "pulling abc"}, {"detail": "no status"}))
    with pytest.raises(SystemExit, match="without success"):
        pull_models.pull("http://ollama:11434", "qwen3:8b")


def test_fetch_reranker_downloads_only_when_it_is_not_cached(monkeypatch, capsys):
    calls, cached = [], []

    def snapshot_download(name, allow_patterns, local_files_only=False):
        calls.append(local_files_only)
        if not local_files_only:
            cached.append(name)
        elif not cached:
            raise LocalEntryNotFoundError("not cached")

    monkeypatch.setattr(pull_models, "snapshot_download", snapshot_download)
    pull_models.fetch_reranker("BAAI/bge-reranker-v2-m3")
    assert calls == [True, False]  # the offline probe failed, so it downloaded
    calls.clear()
    pull_models.fetch_reranker("BAAI/bge-reranker-v2-m3")
    assert calls == [True] and "already present" in capsys.readouterr().out


def test_pull_models_skips_what_is_present_and_pulls_only_what_is_missing(monkeypatch):
    monkeypatch.setattr(ready.urllib.request, "urlopen", tags("qwen3:8b"))
    pulled, fetched = [], []
    monkeypatch.setattr(pull_models, "pull", lambda url, name: pulled.append(name))
    monkeypatch.setattr(pull_models, "fetch_reranker", fetched.append)
    pull_models.main()
    assert pulled == ["nomic-embed-text"]
    assert fetched == [load_config()["rerank"]["model"]]


def test_env_overrides_apply_only_when_set(monkeypatch):
    names = {"HALO_OLLAMA_URL": ("models", "ollama_url"), "HALO_RERANK_DEVICE": ("rerank", "device"),
             "HALO_COLLECTION": ("retrieve", "collection")}
    for var in names:
        monkeypatch.delenv(var, raising=False)
    base = load_config()
    for var in names:
        monkeypatch.setenv(var, f"sentinel-{var}")
    cfg = load_config()
    for var, (section, key) in names.items():
        assert cfg[section][key] == f"sentinel-{var}"
        assert base[section][key] != f"sentinel-{var}"
