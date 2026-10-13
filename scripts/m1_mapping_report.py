"""M1 mapping quality: how well PDF chunks land in the right Vectara section, swept over min_match.

    uv run python scripts/m1_mapping_report.py

Writes results/m1_mapping.txt. No embeddings needed. For each dev_sample gold section:
- covered: at least one chunk carries its section_id (the M1 gate check);
- recall: share of the section's word 5-grams found in chunks labelled with it, counting only
  5-grams visible anywhere in the paper's PDF text (LaTeX/markdown never appears in PDF text).
"""

import json
import statistics
import sys

from halo.config import ROOT, load_config
from halo.data import load_corpus_doc, load_hf, pdf_dir
from halo.ingest.pdf import read_blocks
from halo.ingest.sections import chunk_blocks, map_blocks, shingles, words

MIN_MATCH_SWEEP = (0.1, 0.2, 0.3, 0.5, 0.7)
LOW_RECALL = 0.5


def evaluate(papers: dict, gold: set, min_match: float, ing: dict) -> tuple[dict, list]:
    n = ing["shingle_n"]
    words_total = words_inherited = 0
    covered, recalls = 0, []
    for pid, (blocks, sections) in papers.items():
        mapping = map_blocks([b["text"] for b in blocks], sections, n, min_match)
        for b, m in zip(blocks, mapping):
            w = len(b["text"].split())
            words_total += w
            words_inherited += w * m["inherited"]
        mapped = [{**b, "section_id": m["section_id"]} for b, m in zip(blocks, mapping)]
        per_section: dict[int, set] = {}
        for c in chunk_blocks(mapped, ing["chunk_words"], ing["overlap_words"]):
            per_section.setdefault(c["section_id"], set()).update(shingles(words(c["text"]), n))
        visible = set().union(*per_section.values())
        for doc_id, sid in gold:
            if doc_id != pid:
                continue
            covered += sid in per_section
            sec = shingles(words(sections[sid]["text"]), n) & visible
            if sec:
                recalls.append((len(sec & per_section.get(sid, set())) / len(sec), doc_id, sid))
    r = [x[0] for x in recalls]
    stats = {
        "inherited_words": words_inherited / words_total,
        "covered": covered,
        "recall_median": statistics.median(r),
        "recall_mean": statistics.mean(r),
        "low_recall": sum(x < LOW_RECALL for x in r),
    }
    return stats, sorted(recalls)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = load_config()
    ing = cfg["ingest"]
    dev = json.loads((ROOT / "splits" / "dev_slice.json").read_text(encoding="utf-8"))
    qids = json.loads((ROOT / "splits" / "dev_sample.json").read_text(encoding="utf-8"))["query_ids"]
    qrels = load_hf("qrels.json", cfg)
    gold = {(qrels[q]["doc_id"], qrels[q]["section_id"]) for q in qids}
    papers = {p: (read_blocks(pdf_dir(cfg) / f"{p}.pdf"), load_corpus_doc(p, cfg)["sections"])
              for p in dev["source_paper_ids"]}

    lines = [f"# M1 mapping quality — {len(papers)} dev source papers, {len(gold)} gold sections",
             f"config: {ing}", "",
             "min_match | inherited words | gold covered | recall median | recall mean | recall<0.5"]
    for mm in MIN_MATCH_SWEEP:
        s, recalls = evaluate(papers, gold, mm, ing)
        lines.append(f"{mm:9} | {s['inherited_words']:15.1%} | {s['covered']:>8}/{len(gold)} | "
                     f"{s['recall_median']:13.2f} | {s['recall_mean']:11.2f} | {s['low_recall']:>10}")
        if mm == ing["min_match"]:
            worst = recalls[:10]
    lines += ["", f"Lowest-recall gold sections at configured min_match={ing['min_match']}:"]
    lines += [f"  {r:.2f} {d} s{s}" for r, d, s in worst]
    text = "\n".join(lines) + "\n"
    print(text)
    (ROOT / "results" / "m1_mapping.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
