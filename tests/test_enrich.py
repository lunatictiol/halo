import halo.ingest.enrich as enrich_mod
from halo.ingest.enrich import EnrichCache, cache_key, enrich

E = {"model": "m", "prompt_version": "v1"}


def test_cache_key_changes_with_model_prompt_paper_and_text_only():
    base = cache_key("p1", "text", E)
    assert base == cache_key("p1", "text", dict(E))
    assert len({base, cache_key("p1", "text", E | {"model": "m2"}), cache_key("p1", "text", E | {"prompt_version": "v2"}),
                cache_key("p2", "text", E), cache_key("p1", "text2", E)}) == 5


def test_enrich_calls_llm_once_then_reads_cache_from_disk(tmp_path, monkeypatch):
    calls = []

    def fake_situate(chunk, doc, cfg):
        calls.append(chunk["text"])
        return {"content": " From  paper X.\n", "prompt_tokens": 10, "output_tokens": 3, "ms": 5}

    monkeypatch.setattr(enrich_mod, "situate", fake_situate)
    cfg = {"enrich": E}
    chunks = [{"paper_id": "p1", "text": "a", "section_title": "Intro"}]
    path = tmp_path / "c.jsonl"

    first_stats, second_stats = {}, {}
    first = enrich(chunks, {}, cfg, EnrichCache(path), first_stats)
    second = enrich(chunks, {}, cfg, EnrichCache(path), second_stats)  # fresh instance: reloads the file

    assert first == second == [{**chunks[0], "context": "From paper X."}]
    assert "context" not in chunks[0]  # input left untouched
    assert calls == ["a"]
    cost = {"prompt_tokens": 10, "output_tokens": 3, "ms": 5}
    assert first_stats == {"calls": 1, "chunks": 1, **cost}
    assert second_stats == {"chunks": 1, **cost}  # a cached context's cost still counts; no new call


def test_truncated_last_cache_line_is_skipped(tmp_path):
    path = tmp_path / "c.jsonl"
    path.write_text('{"key": "k1", "context": "ok"}\n{"key": "k2", "cont', encoding="utf-8")
    cache = EnrichCache(path)
    assert cache.get("k1")["context"] == "ok" and cache.get("k2") is None
