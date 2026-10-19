"""Abstention detection: the generator is instructed to emit a fixed sentinel when context is insufficient."""

from halo.generate.baseline import is_abstention  # noqa: F401 (re-exported; the pipeline uses it too)
