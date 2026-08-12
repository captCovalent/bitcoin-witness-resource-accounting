"""Command-line interface for deterministic whole-block pilot collection."""

from __future__ import annotations

import argparse
from getpass import getpass
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Sequence

from .export import export_records
from .rpc import BitcoinCoreParityError, BitcoinRPCClient, BitcoinRPCError
from .sampling import collect_sample, default_pilot_strata


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wra-collect-block-sample",
        description="Collect a deterministic whole-block BIP141 parity pilot from Bitcoin RPC.",
    )
    parser.add_argument("--rpc-url", default="http://127.0.0.1:8332")
    parser.add_argument("--rpc-user", required=True)
    parser.add_argument("--prompt-rpc-password", action="store_true", required=True)
    parser.add_argument("--rpc-timeout", type=float, default=180.0)
    parser.add_argument("--seed", default="wra-rpc-pilot-v1")
    parser.add_argument("--count-per-stratum", type=int, default=1)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--transactions-output", type=Path, required=True)
    return parser


def run(arguments: argparse.Namespace) -> tuple[dict, list[dict]]:
    password = getpass("Knots RPC password: ")
    if not password:
        raise ValueError("RPC password cannot be empty")
    client = BitcoinRPCClient(
        arguments.rpc_url,
        arguments.rpc_user,
        password,
        timeout=arguments.rpc_timeout,
    )
    tip_height = client.get_block_count()
    strata = default_pilot_strata(
        tip_height,
        count_per_stratum=arguments.count_per_stratum,
    )
    return collect_sample(client, strata=strata, seed=arguments.seed)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        manifest, analyses = run(arguments)
        rendered = export_records(analyses, "jsonl")
        digest = sha256(rendered.encode("utf-8")).hexdigest()
        manifest["transactions_output"] = {
            "path": arguments.transactions_output.name,
            "format": "jsonl",
            "sha256": digest,
        }
        arguments.transactions_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.transactions_output.write_text(rendered, encoding="utf-8")
        arguments.manifest_output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, BitcoinCoreParityError, BitcoinRPCError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    sys.stdout.write(
        f"collected {len(analyses)} transactions from {len(manifest['blocks'])} blocks\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
