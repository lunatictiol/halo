from fastapi.testclient import TestClient

from halo.api.app import CFG, create_app

HITS = [{"paper_id": "p1", "section_id": 3, "page": 4, "section_title": "Method"},
        {"paper_id": "p2", "section_id": 1, "page": 2, "section_title": "Intro"}]


def _sentence(kept, cites, reattributed=None):
    return {"kept": kept, "cites": cites, "reattributed": reattributed}


class StubGraph:
    def __init__(self, out):
        self.out, self.questions = out, []

    def invoke(self, state):
        self.questions.append(state["question"])
        return self.out


ANSWERED = {"answer": "Adam [p1 §3 p.4]. Two layers [p2 §1 p.2].", "abstained": False, "abstain_reason": None,
            "attempts": 2, "hits": HITS, "grounding": {"sentences": [
                _sentence(True, [{"n": 1, "verdict": "supported"}, {"n": 2, "verdict": "unsupported"}]),
                _sentence(True, [], reattributed={"n": 2, "verdict": "supported"}),
                _sentence(True, [{"n": 1, "verdict": "supported"}]),       # duplicate citation: listed once
                _sentence(False, [{"n": 2, "verdict": "unsupported"}]),    # removed sentence: not cited
            ]}}


def test_query_returns_answer_and_distinct_supported_citations():
    graph = StubGraph(ANSWERED)
    with TestClient(create_app(graph)) as client:
        r = client.post("/query", json={"question": "  which optimizer?  "})
    assert r.status_code == 200
    body = r.json()
    assert body["retries"] == 1 and not body["abstained"]
    assert body["citations"] == [
        {"paper_id": "p1", "section_id": 3, "section_title": "Method", "page": 4},
        {"paper_id": "p2", "section_id": 1, "section_title": "Intro", "page": 2},
    ]
    assert graph.questions == ["which optimizer?"]


def test_grader_abstention_has_reason_and_no_citations():
    out = {"answer": "INSUFFICIENT_EVIDENCE: no passage on X", "abstained": True,
           "abstain_reason": "no passage on X", "attempts": 3, "hits": HITS, "grounding": None}
    with TestClient(create_app(StubGraph(out))) as client:
        body = client.post("/query", json={"question": "q"}).json()
    assert body["abstained"] and body["abstain_reason"] == "no passage on X"
    assert body["citations"] == [] and body["retries"] == 2


def test_rejects_empty_blank_and_overlong_questions():
    graph = StubGraph(ANSWERED)
    with TestClient(create_app(graph)) as client:
        for q in ("", "   ", "x" * (CFG["api"]["max_question_chars"] + 1)):
            assert client.post("/query", json={"question": q}).status_code == 422
        assert client.get("/health").json()["status"] == "ok"
    assert graph.questions == []
