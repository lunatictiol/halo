"""M10 gate: time-to-first-event and total latency of POST /query/stream on the saved demo questions (D43).

    uv run python -m eval.runners.stream_latency      # needs Ollama and the configured index; ~3-5 min

Starts the real app as a subprocess (so the numbers include HTTP and SSE framing, not just the graph), waits for
/health, sends one throwaway query so the models are loaded, then streams each question in eval/demo_questions.json
and writes results/m10_stream_latency.json.
"""

import json
import subprocess
import sys
import time

import httpx

from eval.results import write_results
from halo.config import ROOT, load_config

DEMO = ROOT / "eval" / "demo_questions.json"


def wait_healthy(base: str, timeout_s: int, server: subprocess.Popen) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"server exited with code {server.returncode}")
        try:
            if httpx.get(f"{base}/health", timeout=2).status_code == 200:
                return
        except httpx.TransportError:
            time.sleep(1)
    raise TimeoutError(f"{base}/health not ready after {timeout_s}s")


def stream_one(base: str, question: str, timeout_s: int) -> dict:
    """POST one question; return arrival times (ms since the request) of every event and the final payload."""
    start, events, final = time.perf_counter(), [], None
    with httpx.stream("POST", f"{base}/query/stream", json={"question": question}, timeout=timeout_s) as r:
        r.raise_for_status()
        name = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
                events.append({"event": name, "at_ms": round((time.perf_counter() - start) * 1000)})
            elif line.startswith("data: ") and name in ("step", "final", "error"):
                payload = json.loads(line.removeprefix("data: "))
                events[-1]["node"] = payload.get("node")
                final = payload if name != "step" else final
    return {"events": events, "final": final, "total_ms": round((time.perf_counter() - start) * 1000)}


def record(demo: dict, run: dict) -> dict:
    steps = [e for e in run["events"] if e["event"] == "step"]
    final = run["final"] or {}
    return {"role": demo["role"], "query_id": demo["query_id"], "question": demo["question"],
            "time_to_first_event_ms": run["events"][0]["at_ms"], "total_ms": run["total_ms"],
            "server_total_ms": final.get("total_ms"), "steps": len(steps), "nodes": [e["node"] for e in steps],
            "retries": final.get("retries"), "abstained": final.get("abstained"),
            "error": final.get("detail"), "event_at_ms": [e["at_ms"] for e in run["events"]]}


def main() -> None:
    cfg = load_config()
    port, timeout_s = cfg["api"]["demo_port"], cfg["api"]["demo_timeout_s"]
    base = f"http://127.0.0.1:{port}"
    demos = json.loads(DEMO.read_text(encoding="utf-8"))
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "halo.api.app:app", "--port", str(port)], cwd=ROOT)
    try:
        wait_healthy(base, timeout_s, server)
        stream_one(base, demos[0]["question"], timeout_s)  # warm-up: loads the LLM and reranker, not recorded
        records = [record(d, stream_one(base, d["question"], timeout_s)) for d in demos]
    finally:
        server.terminate()
        server.wait(30)
    path = write_results("m10_stream_latency", {"warmup": True, "queries": records}, cfg)
    for r in records:
        print(f"{r['role']:<11} first event {r['time_to_first_event_ms']:>6} ms   total {r['total_ms']:>6} ms   "
              f"steps {r['steps']:>2}   retries {r['retries']}   abstained {r['abstained']}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
