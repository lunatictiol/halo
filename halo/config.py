"""Load the TOML config. All tunables live in config/*.toml, never in code."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "default.toml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)
