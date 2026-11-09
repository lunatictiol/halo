"""Web UI (M10, D43): htmx + Jinja2 over the same event stream as `POST /query/stream`.

The htmx SSE extension can only open `EventSource` (GET) connections and swaps the event data in as HTML,
so the UI has its own two GET routes on top of the shared event generator: `/ui/ask` returns the fragment that
opens the stream, `/ui/stream` renders each event as an HTML fragment.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ValidationError

from halo.api.stream import SSE_HEADERS, Event, sse_frame

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=select_autoescape())

# graph event -> (SSE event name the page listens to, template). Errors land in the answer box.
_FRAGMENTS = {"step": ("step", "step.html"), "final": ("final", "answer.html"), "error": ("final", "error.html")}


def render(template: str, **ctx) -> str:
    return _env.get_template(template).render(**ctx)


def make_router(events: Callable[[str], Iterator[Event]], is_busy: Callable[[], bool],
                query_model: type[BaseModel]) -> APIRouter:
    router = APIRouter()

    def parse(raw: str) -> str | None:
        try:
            return query_model(question=raw).question.strip()
        except ValidationError:
            return None

    @router.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render("index.html")

    @router.get("/ui/ask", response_class=HTMLResponse)
    def ask(question: str = "") -> str:
        q = parse(question)
        if q is None:
            return render("error.html", detail="Enter a question (it can't be empty or too long).")
        if is_busy():
            return render("error.html", detail="Busy: another question is running. Try again in a moment.")
        return render("run.html", question=q)

    @router.get("/ui/stream")
    def stream(question: str = "") -> StreamingResponse:
        q = parse(question)

        def frames() -> Iterator[str]:
            if q is None:
                yield sse_frame("final", render("error.html", detail="Invalid question."))
            else:
                for name, data in events(q):
                    sse_name, template = _FRAGMENTS[name]
                    yield sse_frame(sse_name, render(template, s=data, a=data, detail=data.get("detail")))
            yield sse_frame("done", "")  # the page closes its EventSource on this, or it would reconnect

        return StreamingResponse(frames(), media_type="text/event-stream", headers=SSE_HEADERS)

    return router
