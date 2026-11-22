"""M11 gate: image sizes, cold start and one end-to-end pass of the demo questions against the Docker stack (D44).

    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --wait ollama   # models already pulled
    uv run python scripts/m11_gate.py --gpu       # drop --gpu for the CPU stack

Restarts `app` to time start-up (container start -> /ready 200), then streams the demo questions over HTTP, the first
one straight after the restart (models cold) and each again warm, and writes results/m11_docker.json.
"""

import argparse
import json
import subprocess
import time

import httpx

from eval.results import write_results
from eval.runners.stream_latency import DEMO, checked, record, stream_one
from halo.config import load_config

BASE = "http://127.0.0.1:8000"
IMAGES = ("halo:cpu", "halo:cu128")


def docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout.strip()


def cold_start_s(compose: list[str], timeout_s: int) -> float:
    docker(*compose, "stop", "app")
    start = time.perf_counter()
    docker(*compose, "up", "-d", "app")
    while time.perf_counter() - start < timeout_s:
        try:
            if httpx.get(f"{BASE}/ready", timeout=2).status_code == 200:
                return round(time.perf_counter() - start, 1)
        except httpx.TransportError:
            pass
        time.sleep(1)
    raise TimeoutError(f"{BASE}/ready not 200 after {timeout_s}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", action="store_true", help="the stack was started with docker-compose.gpu.yml")
    gpu = parser.parse_args().gpu
    cfg = load_config()
    timeout_s = cfg["api"]["demo_timeout_s"]
    compose = ["compose", "-f", "docker-compose.yml"] + (["-f", "docker-compose.gpu.yml"] if gpu else [])
    demos = json.loads(DEMO.read_text(encoding="utf-8"))

    # Two different numbers: `inspect .Size` is the compressed content (what a registry pull transfers) under the
    # containerd image store; `image ls` is the unpacked size on disk (what `docker image ls` shows). Both recorded.
    sizes = {}
    for image in IMAGES:
        try:
            sizes[image] = {"compressed_bytes": int(docker("image", "inspect", image, "--format", "{{.Size}}")),
                            "unpacked_disk": docker("image", "ls", image, "--format", "{{.Size}}")}
        except subprocess.CalledProcessError:
            sizes[image] = None  # that variant was not built on this machine

    cold = cold_start_s(compose, timeout_s)
    ui = httpx.get(f"{BASE}/", timeout=10)
    first = record(demos[0], checked(stream_one(BASE, demos[0]["question"], timeout_s), "first query after start"))
    warm = [record(d, checked(stream_one(BASE, d["question"], timeout_s), d["role"])) for d in demos]
    # `config` in the results file is this host's. What the container ran with differs (env overrides), so record it.
    container_env = dict(line.split("=", 1) for line in docker(*compose, "exec", "-T", "app", "printenv").splitlines()
                         if line.startswith("HALO_"))
    payload = {
        "variant": "cu128" if gpu else "cpu", "docker": docker("--version"), "container_env": container_env,
        "image_bytes": sizes, "cold_start_to_ready_s": cold, "ready": httpx.get(f"{BASE}/ready").json(),
        "ui_status": ui.status_code, "ui_has_question_form": "<form" in ui.text,
        "first_query_after_start": first, "queries": warm,
    }
    path = write_results("m11_docker", payload, cfg)
    print(f"image bytes {sizes}\ncold start to /ready {cold} s\nUI GET / -> {ui.status_code}")
    for r in [first, *warm]:
        print(f"{r['role']:<11} first event {r['time_to_first_event_ms']:>6} ms   total {r['total_ms']:>6} ms   "
              f"retries {r['retries']}   abstained {r['abstained']}   error {r['error']}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
