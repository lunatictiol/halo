"""Minimal HTTP API over the full HALO pipeline (corrective loop + grounded citations).

    uv run uvicorn halo.api.app:app            # then POST /query {"question": "..."}
"""

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from halo.api.stream import SSE_HEADERS, run_events, sse_frame
from halo.api.ui import make_router
from halo.config import load_config

CFG = load_config()
BUSY = "busy: another query is running"


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=CFG["api"]["max_question_chars"], pattern=r"\S")


class Citation(BaseModel):
    paper_id: str
    section_id: int
    section_title: str
    page: int


class Answer(BaseModel):
    answer: str
    abstained: bool
    abstain_reason: str | None
    citations: list[Citation]
    retries: int


def citations(out: dict) -> list[dict]:
    """Distinct (paper, section, page) of the passages backing the kept sentences, in order of first use;
    the same rule halo.generate.cite._render uses to print them."""
    hits, seen = out.get("hits") or [], {}
    for s in (out.get("grounding") or {}).get("sentences", []):
        if not s["kept"]:
            continue
        cites = [c for c in s["cites"] if c["verdict"] == "supported"] or [s["reattributed"]]
        for c in cites:
            h = hits[c["n"] - 1]
            seen.setdefault((h["paper_id"], h["section_id"], h["page"]), h.get("section_title", ""))
    return [{"paper_id": p, "section_id": s, "page": pg, "section_title": t} for (p, s, pg), t in seen.items()]


def to_answer(out: dict) -> dict:
    return {"answer": out["answer"], "abstained": out["abstained"], "abstain_reason": out.get("abstain_reason"),
            "citations": citations(out), "retries": out["attempts"] - 1}


def build_pipeline(cfg: dict):
    """(graph, retriever) on the configured collection; the caller closes the retriever."""
    from halo.graph.pipeline import build_graph, default_nodes
    from halo.retrieve import Retriever
    retriever = Retriever(cfg)
    return build_graph(default_nodes(retriever, cfg), cfg["graph"]["max_retries"]), retriever


def create_app(graph=None) -> FastAPI:
    """`graph` is injected in tests; by default the real pipeline is built at startup."""
    state = {"graph": graph}
    # ponytail: one query at a time. One local GPU serves the LLM and reranker and embedded Qdrant is
    # single-process, so concurrency would only queue on the GPU; use a Qdrant server + a worker pool to scale.
    lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        retriever = None
        if state["graph"] is None:
            state["graph"], retriever = build_pipeline(CFG)
        yield
        if retriever:
            retriever.close()

    def events(question: str):
        """The event stream of one run. The lock is taken inside the generator, so a stream that is never
        started (client gone before the first byte) cannot leak it, and released in its `finally`."""
        if not lock.acquire(blocking=False):
            yield "error", {"detail": BUSY}
            return
        try:
            yield from run_events(state["graph"], question, to_answer)
        finally:
            lock.release()

    api = FastAPI(title="HALO", lifespan=lifespan)

    @api.get("/health")
    def health() -> dict:
        return {"status": "ok", "collection": CFG["retrieve"]["collection"], "llm": CFG["models"]["llm"]}

    @api.post("/query", response_model=Answer)
    def query(q: Query) -> dict:  # sync: FastAPI runs it in a worker thread, so the event loop stays free
        with lock:
            return to_answer(state["graph"].invoke({"question": q.question.strip()}))

    @api.post("/query/stream")
    def query_stream(q: Query) -> StreamingResponse:
        if lock.locked():  # fast path for a clear status; `events` still guards the race
            raise HTTPException(status_code=429, detail=BUSY)

        def frames():
            for name, data in events(q.question.strip()):
                yield sse_frame(name, json.dumps(data))

        return StreamingResponse(frames(), media_type="text/event-stream", headers=SSE_HEADERS)

    api.include_router(make_router(events, lock.locked, Query, CFG["api"]["max_question_chars"]))
    api.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    return api


app = create_app()
