"""M0 data audit: check downloaded files against published Open RAG Bench numbers.

    uv run python scripts/audit_data.py

Exits non-zero if any hard check fails. Discrepancies vs CLAUDE.md are explained in DATA.md.
"""

import csv
import statistics
import sys
from collections import Counter

from halo.config import ROOT
from halo.data import corpus_dir, load_corpus_doc, load_hf, pdf_dir

PUBLISHED = {"papers": 1000, "source_papers": 396, "distractors": 604, "questions": 3045}

failures: list[str] = []


def check(label: str, actual, expected) -> None:
    ok = actual == expected
    print(f"  [{'OK' if ok else 'FAIL'}] {label}: {actual}" + ("" if ok else f" (expected {expected})"))
    if not ok:
        failures.append(label)


def main() -> None:
    queries, answers = load_hf("queries.json"), load_hf("answers.json")
    qrels, pdf_urls = load_hf("qrels.json"), load_hf("pdf_urls.json")

    print("Counts vs published:")
    sources = {r["doc_id"] for r in qrels.values()}
    check("papers in pdf_urls.json", len(pdf_urls), PUBLISHED["papers"])
    check("source papers (doc_ids in qrels)", len(sources), PUBLISHED["source_papers"])
    check("distractors (papers with no questions)", len(set(pdf_urls) - sources), PUBLISHED["distractors"])
    check("questions in queries.json", len(queries), PUBLISHED["questions"])
    check("answers in answers.json", len(answers), PUBLISHED["questions"])
    check("qrels entries", len(qrels), PUBLISHED["questions"])

    print("\nID consistency:")
    check("queries/answers/qrels share the same query IDs",
          set(queries) == set(answers) == set(qrels), True)
    check("every qrels doc_id is in pdf_urls", sources <= set(pdf_urls), True)

    print("\nFiles on disk:")
    corpus_present = [d for d in pdf_urls if (corpus_dir() / f"{d}.json").exists()]
    check("corpus JSON files present", len(corpus_present), len(pdf_urls))
    pdfs = [pdf_dir() / f"{d}.pdf" for d in pdf_urls]
    valid = [p for p in pdfs if p.exists() and p.read_bytes()[:5] == b"%PDF-"]
    check("valid PDFs present", len(valid), len(pdf_urls))

    print("\nqrels -> corpus sections:")
    docs = {d: load_corpus_doc(d) for d in corpus_present}
    bad_ref, positional = 0, 0
    for rel in qrels.values():
        sections = docs.get(rel["doc_id"], {}).get("sections", [])
        ids = {s["section_id"] for s in sections}
        bad_ref += rel["section_id"] not in ids
        positional += (rel["section_id"] < len(sections)
                       and sections[rel["section_id"]]["section_id"] == rel["section_id"])
    check("qrels section_ids that exist in their doc", len(qrels) - bad_ref, len(qrels))
    print(f"  section_id equals list position for {positional}/{len(qrels)} qrels")
    n_sections = [len(d["sections"]) for d in docs.values()]
    if n_sections:
        print(f"  sections per doc: min {min(n_sections)}, median {statistics.median(n_sections)}, "
              f"max {max(n_sections)}")
    gappy = sum(1 for d in docs.values()
                if [s["section_id"] for s in d["sections"]] != list(range(len(d["sections"]))))
    print(f"  docs whose section_ids are not 0..n-1: {gappy}")

    print("\nQuestion labels:")
    for field in ("type", "source"):
        print(f"  {field}: {dict(sorted(Counter(q[field] for q in queries.values()).items()))}")
    per_doc = Counter(r["doc_id"] for r in qrels.values())
    print(f"  questions per source paper: min {min(per_doc.values())}, "
          f"mean {len(qrels) / len(per_doc):.2f}, max {max(per_doc.values())}")

    local_pdfs, local_eval = ROOT / "All_PDFs.csv", ROOT / "Eval_data.csv"
    if local_pdfs.exists() and local_eval.exists():
        print("\nLocal third-party CSVs (not used as corpus, see DATA.md):")
        rows = list(csv.DictReader(open(local_pdfs, encoding="utf-8")))
        local_d = {r["doc_id"] for r in rows if r["document_type"] == "distractor"}
        print(f"  All_PDFs.csv rows: {len(rows)} ({len(local_d)} distractors)")
        print(f"  local distractors also in official corpus: {len(local_d & set(pdf_urls))}")
        eval_q = {r["query_id"] for r in csv.DictReader(open(local_eval, encoding="utf-8"))}
        print(f"  Eval_data.csv query IDs matching HF: {len(eval_q & set(queries))}/{len(eval_q)}")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'FAILED: {failures}'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
