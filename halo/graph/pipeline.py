"""M4 corrective loop as a LangGraph state graph (DECISIONS.md D26-D29), with the M5 grounding check (D31-D33):

    retrieve -> rerank -> grade --sufficient--------------------------> generate -> verify -> END
                            |---insufficient, retries left---> rewrite -> retrieve
                            '---insufficient, no retries left--------> abstain -> END

The grader and the generator always see the user's original question; only retrieval and reranking use the
rewritten query. Every node appends one entry to `trace` (node, ms, what it decided): the per-query log.
"""

import operator
import time
from collections.abc import Callable
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from halo.generate.baseline import format_context, is_abstention
from halo.generate.cite import cite_answer, ground, llm_check
from halo.llm import chat, classify

GRADES = ("sufficient", "insufficient")
NODES = ("retrieve", "rerank", "grade", "rewrite", "generate", "verify", "abstain")
# A node returns (state update, trace info).
Node = Callable[[dict], tuple[dict, dict]]


class State(TypedDict, total=False):
    question: str
    query: str                                      # current search query; the question itself on attempt 1
    tried: Annotated[list[str], operator.add]       # every query retrieved with so far
    attempts: int                                   # retrieval attempts so far
    candidates: list[dict]                          # first-stage (fused) ranking
    hits: list[dict]                                # reranked, best first, k_eval long
    grade: dict                                     # {verdict, reason, ms}
    answer: str
    abstained: bool
    abstain_reason: str | None
    generation: dict | None                         # generator call stats; None when the grader abstained
    raw_answer: str | None                          # generator output before the grounding check
    grounding: dict | None                          # per-sentence citation verdicts (halo.generate.cite.ground)
    trace: Annotated[list[dict], operator.add]


def route_after_grade(state: dict, max_retries: int) -> str:
    """The only place the retry limit is enforced. A grader parse error (verdict None) counts as insufficient."""
    if state["grade"]["verdict"] == "sufficient":
        return "generate"
    return "rewrite" if state["attempts"] <= max_retries else "abstain"


def traced(name: str, fn: Node) -> Callable[[dict], dict]:
    def run(state: dict) -> dict:
        start = time.perf_counter()
        update, info = fn(state)
        return update | {"trace": [{"node": name, "ms": round((time.perf_counter() - start) * 1000)} | info]}
    return run


def build_graph(nodes: dict[str, Node], max_retries: int):
    """Compile the loop from node functions (real ones from `default_nodes`, stubs in tests)."""
    g = StateGraph(State)
    for name in NODES:
        g.add_node(name, traced(name, nodes[name]))
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "rerank")
    g.add_edge("rerank", "grade")
    g.add_conditional_edges("grade", lambda s: route_after_grade(s, max_retries),
                            {"generate": "generate", "rewrite": "rewrite", "abstain": "abstain"})
    g.add_edge("rewrite", "retrieve")
    g.add_edge("generate", "verify")
    g.add_edge("verify", END)
    g.add_edge("abstain", END)
    return g.compile()


def _first_line(text: str) -> str:
    return next((ln.strip().strip('"\'') for ln in text.splitlines() if ln.strip()), "")


def default_nodes(retriever, cfg: dict) -> dict[str, Node]:
    """The real nodes. `retriever` is a halo.retrieve.Retriever; reranking is its own node, so the first stage
    must be a method without a reranker."""
    g, r, gen = cfg["graph"], cfg["retrieve"], cfg["generate"]
    if g["retrieve_method"].endswith("_rerank"):
        raise ValueError("graph.retrieve_method must not rerank: the rerank node does that")
    model = cfg["models"]["llm"]

    def retrieve(s: dict) -> tuple[dict, dict]:
        query, n = s.get("query") or s["question"], s.get("attempts", 0) + 1
        candidates, _ = retriever.retrieve(query, g["retrieve_method"])
        return {"query": query, "tried": [query], "attempts": n, "candidates": candidates}, {"attempt": n, "query": query}

    def rerank_node(s: dict) -> tuple[dict, dict]:
        from halo.retrieve.rerank import rerank  # torch import is slow; only pay for it when the graph runs
        hits = rerank(s["query"], s["candidates"], cfg)[:r["k_eval"]]
        return {"hits": hits}, {"top": [[h["paper_id"], h["section_id"]] for h in hits]}

    def grade(s: dict) -> tuple[dict, dict]:
        prompt = g["grade_prompt"].format(question=s["question"], context=format_context(s["hits"][:r["k_context"]]))
        v = classify(g["grade_system_prompt"], prompt, GRADES, model, g["grade_max_tokens"], g["grade_parse_retries"], cfg)
        return {"grade": v}, {"verdict": v["verdict"], "reason": v["reason"]}

    def rewrite(s: dict) -> tuple[dict, dict]:
        prompt = g["rewrite_prompt"].format(question=s["question"], reason=s["grade"]["reason"],
                                            tried="\n".join(f"- {q}" for q in s["tried"]))
        query = _first_line(chat(g["rewrite_system_prompt"], prompt, model, g["rewrite_max_tokens"], cfg)["content"])
        query = query or s["question"]  # an empty rewrite would retrieve nothing
        return {"query": query}, {"query": query}

    def generate(s: dict) -> tuple[dict, dict]:
        resp = cite_answer(s["question"], s["hits"][:r["k_context"]], cfg)
        abstained = is_abstention(resp["content"], gen["sentinel"])
        return ({"answer": resp["content"], "abstained": abstained,
                 "abstain_reason": "generator: the passages do not contain the answer" if abstained else None,
                 "generation": {k: resp[k] for k in ("ms", "prompt_tokens", "output_tokens")}},
                {"abstained": abstained})

    def verify(s: dict) -> tuple[dict, dict]:
        if s["abstained"]:  # the generator's own sentinel: nothing to check
            return {"raw_answer": s["answer"], "grounding": None}, {"skipped": True}
        gr = ground(s["answer"], s["hits"][:r["k_context"]], llm_check(s["question"], cfg))
        update = {"raw_answer": s["answer"], "grounding": gr}
        if gr["abstained"]:
            reason = "grounding check: no claim is supported by a cited passage"
            update |= {"answer": f"{gen['sentinel']}: {reason}", "abstained": True, "abstain_reason": reason}
        else:
            update |= {"answer": gr["final"]}
        removed = sum(not x["kept"] for x in gr["sentences"])
        return update, {"sentences": len(gr["sentences"]), "removed": removed, "abstained": gr["abstained"]}

    def abstain(s: dict) -> tuple[dict, dict]:
        reason = s["grade"]["reason"] or "the retrieved passages do not contain the answer"
        return ({"answer": f"{gen['sentinel']}: {reason}", "abstained": True, "abstain_reason": reason,
                 "generation": None}, {"reason": reason})

    return {"retrieve": retrieve, "rerank": rerank_node, "grade": grade, "rewrite": rewrite,
            "generate": generate, "verify": verify, "abstain": abstain}


def abstained_by(out: dict) -> str | None:
    """Which node made the final state an abstention."""
    if not out["abstained"]:
        return None
    if not out.get("generation"):
        return "grader"
    return "grounding" if (out.get("grounding") or {}).get("abstained") else "generator"
