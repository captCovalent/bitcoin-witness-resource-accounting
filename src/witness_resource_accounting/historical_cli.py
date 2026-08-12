"""CLI for a frozen, future-seeded historical block sample."""

from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import tempfile
from typing import Sequence

from .rpc import BitcoinCoreParityError, BitcoinRPCClient, BitcoinRPCError
from .sample_plan import load_sampling_plan, resolve_sampling_plan
from .sampling import collect_sample_to_jsonl


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wra-collect-historical-sample",
        description="Collect a frozen future-seeded historical block sample.",
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--rpc-url", default="http://127.0.0.1:8332")
    parser.add_argument("--rpc-user", required=True)
    parser.add_argument("--prompt-rpc-password", action="store_true", required=True)
    parser.add_argument("--rpc-timeout", type=float, default=180.0)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--transactions-output", type=Path)
    return parser


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)
            json.dump(value, destination, indent=2, sort_keys=True)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def run(arguments: argparse.Namespace) -> dict:
    if not arguments.check_only and (
        arguments.manifest_output is None or arguments.transactions_output is None
    ):
        raise ValueError("collection requires --manifest-output and --transactions-output")
    password = getpass("Knots RPC password: ")
    if not password:
        raise ValueError("RPC password cannot be empty")
    client = BitcoinRPCClient(
        arguments.rpc_url,
        arguments.rpc_user,
        password,
        timeout=arguments.rpc_timeout,
    )
    plan = load_sampling_plan(arguments.plan)
    resolved = resolve_sampling_plan(client, plan)
    readiness = {
        "plan_id": plan.plan_id,
        "plan_sha256": plan.source_sha256,
        "seed_block_height": resolved.seed_block_height,
        "seed_block_hash": resolved.seed_block_hash,
        "tip_height": resolved.tip_height,
        "sampled_block_count": sum(item.sample_count for item in plan.strata),
    }
    if arguments.check_only:
        return readiness

    manifest = collect_sample_to_jsonl(
        client,
        strata=plan.strata,
        seed=resolved.seed,
        output_path=arguments.transactions_output,
        purpose="general_historical_sample",
    )
    manifest["sampling_plan"] = readiness
    _write_json_atomic(arguments.manifest_output, manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        result = run(arguments)
    except (OSError, BitcoinCoreParityError, BitcoinRPCError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    if arguments.check_only:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"collected {result['transaction_count']} transactions "
            f"from {len(result['blocks'])} blocks"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
