"""Abstention detection: the generator is instructed to emit a fixed sentinel when context is insufficient."""


def is_abstention(answer: str, sentinel: str) -> bool:
    """Any occurrence of the sentinel counts, even after a partial answer (the model itself said it can't answer)."""
    return sentinel.lower() in answer.lower()
