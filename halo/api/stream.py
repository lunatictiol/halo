"""One graph run as a stream of events (M10, D43): `step`* then `final`, or `error`.

A `step` is one trace entry of the corrective loop ({node, ms, ...what it decided}); `final` is the `/query`
answer plus `total_ms` and the sentences the grounding check removed. The transport (JSON for the API, HTML
fragments for the web UI) is the caller's business.
"""

import logging
import time
from collections.abc import Callable, Iterator

log = logging.getLogger(__name__)

Event = tuple[str, dict]
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def removed_sentences(out: dict) -> list[str]:
    return [s["text"] for s in (out.get("grounding") or {}).get("sentences", []) if not s["kept"]]


def run_events(graph, question: str, to_answer: Callable[[dict], dict]) -> Iterator[Event]:
    """Stream `graph` on `question`. A failing node ends the stream with one `error` event."""
    start, seen, state = time.perf_counter(), 0, {}
    try:
        for state in graph.stream({"question": question}, stream_mode="values"):
            trace = state.get("trace", [])
            for entry in trace[seen:]:
                yield "step", entry
            seen = len(trace)
        yield "final", to_answer(state) | {"total_ms": round((time.perf_counter() - start) * 1000),
                                           "removed": removed_sentences(state)}
    except Exception:
        log.exception("query failed")
        yield "error", {"detail": "the query failed; see the server log"}


def sse_frame(event: str, data: str) -> str:
    """One Server-Sent Event; every line of `data` needs its own `data:` prefix."""
    lines = "\n".join(f"data: {ln}" for ln in data.splitlines() or [""])
    return f"event: {event}\n{lines}\n\n"
