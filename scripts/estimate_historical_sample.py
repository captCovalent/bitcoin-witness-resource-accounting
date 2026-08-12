#!/usr/bin/env python3
"""Calculate design-weighted estimates from a completed historical summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from witness_resource_accounting.inference import estimate_stratified_blocks
from witness_resource_accounting.sample_plan import load_sampling_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=2_000)
    parser.add_argument("--bootstrap-seed", default="wra-design-bootstrap-v1")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        plan = load_sampling_plan(arguments.plan)
        summary = json.loads(arguments.summary.read_text(encoding="utf-8"))
        blocks = summary.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("summary lacks a blocks array")
        result = estimate_stratified_blocks(
            plan,
            blocks,
            bootstrap_replicates=arguments.bootstrap_replicates,
            bootstrap_seed=arguments.bootstrap_seed,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
