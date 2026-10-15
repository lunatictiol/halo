"""Write one results JSON per eval run: config snapshot, git state, judge, metrics by slice, per-query records."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from halo.config import ROOT

RESULTS_DIR = ROOT / "results"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()


def git_state() -> dict:
    """Commit plus a dirty flag: numbers from a dirty tree cannot be traced to code exactly."""
    return {"commit": _git("rev-parse", "--short", "HEAD"), "dirty": bool(_git("status", "--porcelain", "--", "halo", "eval", "config"))}


def write_results(run_name: str, payload: dict, cfg: dict, out_dir: Path = RESULTS_DIR) -> Path:
    out = out_dir / f"{run_name}.json"
    doc = {
        "run": run_name,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(),
        "generator_model": cfg["models"]["llm"],
        "judge_model": cfg["judge"]["model"],
        "config": cfg,
        **payload,
    }
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
