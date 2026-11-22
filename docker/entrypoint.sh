#!/bin/sh
# Models are pulled on first start (idempotent afterwards), then the container's command runs.
set -e
python scripts/pull_models.py
exec "$@"
