import json
import threading

from fastapi.testclient import TestClient

from halo.api.app import create_app

HITS = [{"paper_id": "p1", "section_id": 3, "page": 4, "section_title": "Method"}]
TRACE = [
    {"node": "retrieve", "ms": 5, "attempt": 1, "query": "q"},
    {"node": "rerank", "ms": 6, "top": [["p1", 3]]},
    {"node": "grade", "ms": 7, "verdict": "insufficient", "reason": "off topic"},
    {"node": "rewrite", "ms": 8, "query": "better q"},
    {"node": "retrieve", "ms": 5, "attempt": 2, "query": "better q"},
    {"node": "rerank", "ms": 6, "top": [["p1", 3]]},
    {"node": "grade", "ms": 7, "verdict": "sufficient", "reason": ""},
    {"node": "generate", "ms": 9, "abstained": False},
    {"node": "verify", "ms": 10, "sentences": 2, "removed": 1, "abstained": False},
]
SENTENCES = [
    {"text": "Adam.", "kept": True, "cites": [{"n": 1, "verdict": "supported"}], "reattributed": None},
    {"text": "Made-up claim.", "kept": False, "cites": [{"n": 1, "verdict": "unsupported"}], "reattributed": None},
]
ANSWERED = {"answer": "Adam [p1 §3 p.4].", "abstained": False, "abstain_reason": None, "attempts": 2,
            "hits": HITS, "grounding": {"sentences": SENTENCES}}
ABSTAINED = {"answer": "INSUFFICIENT_EVIDENCE: no passage", "abstained": True, "abstain_reason": "no passage",
             "attempts": 3, "hits": HITS, "grounding": None}


class StreamGraph:
    """Yields the cumulative states a real `stream_mode="values"` run would."""

    def __init__(self, trace=TRACE, final=ANSWERED, gate=None, started=None, boom=False):
        self.trace, self.final, self.gate, self.started, self.boom = trace, final, gate, started, boom

    def stream(self, inp, stream_mode):
        assert stream_mode == "values"
        yield {"question": inp["question"]}
        if self.started:
            self.started.set()
        if self.gate:
            self.gate.wait(5)
        if self.boom:
            raise RuntimeError("ollama is down")
        for i in range(1, len(self.trace)):
            yield {"question": inp["question"], "trace": self.trace[:i]}
        yield {"question": inp["question"], "trace": self.trace} | self.final


class InvokeGraph:
    def invoke(self, _):
        return ANSWERED


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        events.append((lines[0].removeprefix("event: "), "\n".join(ln.removeprefix("data: ") for ln in lines[1:])))
    return events


def stream(client, question="which optimizer?"):
    r = client.post("/query/stream", json={"question": question})
    return r, parse_sse(r.text) if r.status_code == 200 else None


def test_events_follow_the_trace_then_final():
    with TestClient(create_app(StreamGraph())) as client:
        r, events = stream(client)
    assert r.headers["content-type"].startswith("text/event-stream")
    assert [e for e, _ in events] == ["step"] * len(TRACE) + ["final"]
    assert [json.loads(d)["node"] for e, d in events if e == "step"] == [t["node"] for t in TRACE]
    assert json.loads(events[3][1]) == TRACE[3]  # the rewrite step carries the new query


def test_final_event_matches_query_endpoint():
    with TestClient(create_app(StreamGraph())) as client:
        final = json.loads(stream(client)[1][-1][1])
    with TestClient(create_app(InvokeGraph())) as client:
        plain = client.post("/query", json={"question": "which optimizer?"}).json()
    assert {k: final[k] for k in plain} == plain
    assert final["removed"] == ["Made-up claim."] and final["total_ms"] >= 0


def test_abstention_final_has_reason_and_no_citations():
    graph = StreamGraph(trace=TRACE[:3], final=ABSTAINED)
    with TestClient(create_app(graph)) as client:
        final = json.loads(stream(client)[1][-1][1])
    assert final["abstained"] and final["abstain_reason"] == "no passage" and final["citations"] == []


def test_failing_node_ends_with_error_event_and_frees_the_lock():
    with TestClient(create_app(StreamGraph(boom=True))) as client:
        _, events = stream(client)
        assert [e for e, _ in events] == ["error"]
        assert "failed" in json.loads(events[0][1])["detail"]
        assert stream(client)[0].status_code == 200  # lock was released


def test_second_request_while_running_is_busy_and_lock_frees_afterwards():
    gate, started = threading.Event(), threading.Event()
    with TestClient(create_app(StreamGraph(gate=gate, started=started))) as client:
        first = threading.Thread(target=lambda: stream(client))
        first.start()
        assert started.wait(5)
        busy = client.post("/query/stream", json={"question": "another"})
        assert busy.status_code == 429 and "busy" in busy.json()["detail"]
        assert "Busy" in client.get("/ui/ask", params={"question": "another"}).text
        gate.set()
        first.join(5)
        assert stream(client)[0].status_code == 200


def test_stream_rejects_invalid_questions():
    with TestClient(create_app(StreamGraph())) as client:
        for q in ("", "   "):
            assert client.post("/query/stream", json={"question": q}).status_code == 422


def test_ui_pages_and_fragments():
    with TestClient(create_app(StreamGraph())) as client:
        assert "hx-get=\"/ui/ask\"" in client.get("/").text
        page = client.get("/").text
        for asset in ("htmx.min.js", "katex.min.js", "katex.min.css", "auto-render.min.js", "math.js", "fonts/KaTeX_Main-Regular.woff2"):
            assert client.get(f"/static/{asset}").status_code == 200
            assert asset.startswith("fonts/") or f"/static/{asset}" in page
        assert "role=\"alert\"" in client.get("/ui/ask", params={"question": "  "}).text
        run = client.get("/ui/ask", params={"question": "what is <b>Adam</b>?"}).text
        assert "sse-connect=\"/ui/stream?question=what%20is%20%3Cb%3EAdam%3C/b%3E%3F\"" in run
        assert "<b>Adam</b>" not in run  # escaped


def test_ui_stream_renders_steps_chip_and_removed_claim():
    with TestClient(create_app(StreamGraph())) as client:
        events = parse_sse(client.get("/ui/stream", params={"question": "which optimizer?"}).text)
    names = [e for e, _ in events]
    assert names == ["step"] * len(TRACE) + ["final", "done"]
    assert "new query: <q>better q</q>" in events[3][1]
    final = events[-2][1]
    assert 'href="https://arxiv.org/pdf/p1#page=4"' in final and "Method" in final
    assert "<del>Made-up claim.</del>" in final and "1 unsupported claim removed" in final


def test_ui_stream_while_busy_renders_error_then_done():
    gate, started = threading.Event(), threading.Event()
    with TestClient(create_app(StreamGraph(gate=gate, started=started))) as client:
        first = threading.Thread(target=lambda: stream(client))
        first.start()
        assert started.wait(5)
        events = parse_sse(client.get("/ui/stream", params={"question": "another"}).text)
        gate.set()
        first.join(5)
        assert not first.is_alive()
    assert [e for e, _ in events] == ["final", "done"] and "busy" in events[0][1]


def test_template_failure_still_ends_with_done():
    broken = [{"node": "retrieve", "ms": 1}]  # no `attempt`: step.html raises while rendering
    with TestClient(create_app(StreamGraph(trace=broken, final=ABSTAINED))) as client:
        events = parse_sse(client.get("/ui/stream", params={"question": "q"}).text)
        assert client.get("/ui/ask", params={"question": "q"}).status_code == 200  # lock was released
    assert [e for e, _ in events] == ["final", "done"] and "could not render" in events[0][1]


def test_ui_rejects_cross_site_requests():
    with TestClient(create_app(StreamGraph())) as client:
        for path in ("/ui/stream", "/ui/ask"):
            assert client.get(path, params={"question": "q"}, headers={"sec-fetch-site": "cross-site"}).status_code == 403
            assert client.get(path, params={"question": "q"}, headers={"sec-fetch-site": "same-origin"}).status_code == 200


def test_ui_stream_shows_abstention_reason():
    with TestClient(create_app(StreamGraph(trace=TRACE[:3], final=ABSTAINED))) as client:
        events = parse_sse(client.get("/ui/stream", params={"question": "q"}).text)
    assert "abstained: no passage" in events[-2][1] and events[-1][0] == "done"
