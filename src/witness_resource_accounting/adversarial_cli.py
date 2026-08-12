"""CLI for model-free BIP141 adversarial boundary experiments."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Sequence

from .adversarial import boundary_suite


DEFAULT_OPAQUE_SIZES = "0,1,31,32,63,64,65,252,253,254,511,512,4095,4096,65535,65536,96000"
DEFAULT_SPLIT_COUNTS = "1,2,4,8,16"
DEFAULT_PADDING_SIZES = "0,1,32,252,253,1024"


def _integers(value: str, *, name: str) -> tuple[int, ...]:
    try:
        result = tuple(int(item) for item in value.split(",") if item != "")
    except ValueError as error:
        raise ValueError(f"{name} must be comma-separated integers") from error
    if not result or any(item < 0 for item in result):
        raise ValueError(f"{name} must contain non-negative integers")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate serialization-only transformations and exact BIP141 lifecycle costs."
    )
    parser.add_argument("--opaque-sizes", default=DEFAULT_OPAQUE_SIZES)
    parser.add_argument("--split-counts", default=DEFAULT_SPLIT_COUNTS)
    parser.add_argument("--padding-sizes", default=DEFAULT_PADDING_SIZES)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        opaque_sizes = _integers(arguments.opaque_sizes, name="opaque-sizes")
        split_counts = _integers(arguments.split_counts, name="split-counts")
        if any(item == 0 for item in split_counts):
            raise ValueError("split-counts must be positive")
        padding_sizes = _integers(arguments.padding_sizes, name="padding-sizes")
        constructions = boundary_suite(
            opaque_sizes=opaque_sizes,
            split_counts=split_counts,
            padding_sizes=padding_sizes,
        )
        records = [construction.to_record() for construction in constructions]
        body = {
            "experiment_schema_version": 1,
            "experiment": "model_free_bip141_adversarial_boundaries",
            "candidate_models": [],
            "validity_level": "serialization_only",
            "opaque_sizes": list(opaque_sizes),
            "split_counts": list(split_counts),
            "padding_sizes": list(padding_sizes),
            "construction_count": len(records),
            "constructions": records,
        }
        rendered = json.dumps(body, indent=2, sort_keys=True) + "\n"
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
        digest = sha256(rendered.encode()).hexdigest()
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"wrote {len(records)} constructions; sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
