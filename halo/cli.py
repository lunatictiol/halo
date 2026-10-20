"""Ask HALO one question from the command line.

    uv run python -m halo.cli "What optimizer does the paper use?"
    uv run python -m halo.cli --json "..."          # the API's response body
"""

import argparse
import json
import sys

from halo.api.app import build_pipeline, to_answer
from halo.config import load_config


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("question")
    p.add_argument("--collection", help="override [retrieve] collection (default from config)")
    p.add_argument("--json", action="store_true", help="print the response as JSON")
    a = p.parse_args()
    if not a.question.strip():
        p.error("question is empty")
    cfg = load_config()
    if a.collection:
        cfg["retrieve"]["collection"] = a.collection
    sys.stdout.reconfigure(encoding="utf-8")
    graph, retriever = build_pipeline(cfg)
    try:
        res = to_answer(graph.invoke({"question": a.question.strip()}))
    finally:
        retriever.close()
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return
    print(res["answer"] if not res["abstained"] else f"Abstained: {res['abstain_reason']}")
    for c in res["citations"]:
        print(f"  [{c['paper_id']} §{c['section_id']} p.{c['page']}] {c['section_title']}")
    print(f"  (retries: {res['retries']})")


if __name__ == "__main__":
    main()
