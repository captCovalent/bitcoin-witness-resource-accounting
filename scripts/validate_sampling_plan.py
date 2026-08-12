#!/usr/bin/env python3
"""Validate a sampling plan without accessing a Bitcoin node."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from witness_resource_accounting.sample_plan import load_sampling_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        plan = load_sampling_plan(arguments.plan)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    print(
        json.dumps(
            {
                "plan_id": plan.plan_id,
                "plan_sha256": plan.source_sha256,
                "stratum_count": len(plan.strata),
                "sampled_block_count": sum(item.sample_count for item in plan.strata),
                "universe_block_count": sum(
                    item.end_height - item.start_height + 1 for item in plan.strata
                ),
                "seed_height": plan.document["seed"]["height"],
                "minimum_seed_depth": plan.document["seed"]["minimum_depth"],
                "minimum_collection_tip": (
                    plan.document["seed"]["height"]
                    + plan.document["seed"]["minimum_depth"]
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
