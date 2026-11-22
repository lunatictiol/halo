# syntax=docker/dockerfile:1
# HALO app image (M11, D44). CPU torch by default; `--build-arg TORCH=cu128` for the NVIDIA GPU variant.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
# Dependencies first: this layer is rebuilt only when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
# uv.lock resolves Linux to CPU torch (pyproject [tool.uv.sources]). The GPU variant swaps in the cu128 wheel that
# matches the one the Windows lock pins; the nvidia-* runtime libraries come from the same index.
ARG TORCH=cpu
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ "$TORCH" = "cu128" ]; then \
        uv pip install --python /opt/venv/bin/python --reinstall-package torch "torch==2.11.0" \
            --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple; \
    elif [ "$TORCH" != "cpu" ]; then echo "TORCH must be cpu or cu128, got $TORCH" >&2; exit 1; fi

FROM python:3.12-slim
# halo is run from the source tree, not installed: halo.config.ROOT is derived from the file's location (config/,
# splits/ and data/ sit beside the package).
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    HF_HOME=/app/data/hf_cache \
    HALO_RERANK_DEVICE=auto
RUN useradd --uid 1000 --create-home halo
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY halo ./halo
COPY config ./config
COPY splits ./splits
COPY scripts ./scripts
COPY eval ./eval
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN mkdir -p /app/data && chown halo /app/data
USER halo
EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "halo.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
