"""Shared data configuration and provenance helpers."""

import hashlib
import json
from pathlib import Path
import tomllib


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_config(path: str | Path) -> dict:
    path = Path(path).resolve()
    config = tomllib.loads(path.read_text())
    root = path.parent.parent
    for key in ("raw_dir", "output_dir", "results_dir"):
        config["data"][key] = root / config["data"][key]
    if config["data"]["timezone"] != "Australia/Sydney":
        raise ValueError("This dataset requires the Australia/Sydney clock convention.")
    if not config["data"]["exclude_dst_transition_days"]:
        raise ValueError("DST transition days must remain excluded until resolved.")
    if config["data"]["primary_demand_channel"] != "GC":
        raise ValueError("The Day 1 primary demand definition is GC, excluding CL.")
    return config


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
