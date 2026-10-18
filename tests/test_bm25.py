from halo.retrieve.bm25 import BM25Index

CFG = {"bm25": {"k1": 1.5, "b": 0.75, "stemmer": "english", "stopwords": "en"}}
CHUNKS = [
    {"paper_id": "p1", "chunk_idx": 0, "text": "Transformers use self-attention over token sequences."},
    {"paper_id": "p1", "chunk_idx": 1, "text": "We train convolutional networks on image classification."},
    {"paper_id": "p2", "chunk_idx": 0, "text": "Graph neural networks propagate messages between nodes."},
]


def test_bm25_ranks_matching_chunk_first_with_stemming():
    hits = BM25Index(CHUNKS, CFG).search("message propagation in graphs", k=3)
    assert (hits[0]["paper_id"], hits[0]["chunk_idx"]) == ("p2", 0)


def test_bm25_drops_chunks_with_no_shared_term():
    hits = BM25Index(CHUNKS, CFG).search("attention", k=3)
    assert [(h["paper_id"], h["chunk_idx"]) for h in hits] == [("p1", 0)]


def test_bm25_stopword_only_query_returns_nothing():
    assert BM25Index(CHUNKS, CFG).search("the of and", k=3) == []
