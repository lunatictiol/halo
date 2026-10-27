from halo.ingest.sections import chunk_blocks, chunk_fixed, index_text, map_blocks, section_title

SECTIONS = [
    {"section_id": 0, "text": "#### Abstract\n\nwe study hierarchical time series models for school enrolment data"},
    {"section_id": 1, "text": "# 3. Methods\n\nthe model is estimated with a markov chain monte carlo sampler"},
]


def test_block_maps_to_section_with_most_overlap():
    m = map_blocks(["The model is estimated with a Markov chain Monte Carlo sampler."], SECTIONS, 3, 0.5)
    assert m == [{"section_id": 1, "score": 1.0, "inherited": False}]


def test_weak_blocks_inherit_previous_section_and_leading_ones_the_first():
    blocks = ["arXiv:2401.01872v2 page 3", "estimated with a markov chain", "References [1] Smith"]
    m = map_blocks(blocks, SECTIONS, 3, 0.5)
    assert [x["section_id"] for x in m] == [0, 1, 1]
    assert [x["inherited"] for x in m] == [True, False, True]


def test_ties_go_to_earlier_section():
    tied = [{"section_id": 0, "text": "a b c d"}, {"section_id": 1, "text": "a b c d"}]
    assert map_blocks(["a b c d"], tied, 3, 0.5)[0]["section_id"] == 0


def test_chunks_never_cross_sections_and_track_pages():
    blocks = [
        {"section_id": 0, "page": 1, "text": " ".join(f"a{i}" for i in range(6))},
        {"section_id": 0, "page": 2, "text": " ".join(f"b{i}" for i in range(6))},
        {"section_id": 1, "page": 2, "text": "tiny"},
    ]
    chunks = chunk_blocks(blocks, chunk_words=5, overlap_words=2)
    assert [c["section_id"] for c in chunks] == [0, 0, 0, 0, 1]
    assert chunks[0] == {"section_id": 0, "page": 1, "page_end": 1, "text": "a0 a1 a2 a3 a4"}
    assert chunks[1]["text"] == "a3 a4 a5 b0 b1" and (chunks[1]["page"], chunks[1]["page_end"]) == (1, 2)
    assert chunks[-2]["text"].endswith("b5")
    assert chunks[-1] == {"section_id": 1, "page": 2, "page_end": 2, "text": "tiny"}


def test_section_title_is_first_heading():
    assert section_title(SECTIONS[1]["text"]) == "3. Methods"
    assert section_title("no heading here") == ""


def test_fixed_chunks_cross_sections_and_take_majority_section():
    blocks = [
        {"section_id": 0, "page": 1, "text": "a0 a1 a2"},
        {"section_id": 1, "page": 2, "text": "b0 b1 b2 b3"},
    ]
    chunks = chunk_fixed(blocks, chunk_words=5, overlap_words=2)
    assert [c["text"] for c in chunks] == ["a0 a1 a2 b0 b1", "b0 b1 b2 b3"]
    assert [c["section_id"] for c in chunks] == [0, 1]  # 3 of 5 words from section 0, then all section 1
    assert (chunks[0]["page"], chunks[0]["page_end"]) == (1, 2)


def test_fixed_chunk_majority_tie_goes_to_earlier_section():
    blocks = [{"section_id": 3, "page": 1, "text": "a0 a1"}, {"section_id": 1, "page": 1, "text": "b0 b1"}]
    assert chunk_fixed(blocks, chunk_words=4, overlap_words=1)[0]["section_id"] == 3


def test_index_text_prepends_context_only_when_present():
    assert index_text({"text": "body"}) == "body"
    assert index_text({"text": "body", "context": "From paper X."}) == "From paper X.\n\nbody"
