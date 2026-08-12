"""Command-line interface for offline raw-transaction analysis."""

from __future__ import annotations

import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from .accounting import analyze_transaction
from .errors import TransactionDecodingError
from .export import export_records
from .rpc import (
    BitcoinCoreParityError,
    BitcoinRPCClient,
    BitcoinRPCError,
    analyze_core_transaction,
)
from .transaction import Transaction


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wra",
        description="Measure canonical Bitcoin transaction structure using BIP141 accounting.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--hex", action="append", dest="transaction_hexes")
    source.add_argument("--input", type=Path, help="JSON Lines records with id, hex, and optional fee_sats")
    source.add_argument("--rpc-txid", action="append", dest="rpc_txids")
    parser.add_argument("--label", help="Identifier for a single --hex transaction")
    parser.add_argument("--format", choices=("json", "jsonl", "csv"), default="json")
    parser.add_argument("--output", type=Path, help="Write output to this path instead of stdout")
    parser.add_argument(
        "--rpc-url",
        default=os.environ.get("BITCOIN_RPC_URL", "http://127.0.0.1:8332"),
        help="Bitcoin Core JSON-RPC URL",
    )
    parser.add_argument(
        "--rpc-cookie",
        type=Path,
        help="Bitcoin Core cookie file (default: BITCOIN_RPC_COOKIE or ~/.bitcoin/.cookie)",
    )
    parser.add_argument(
        "--rpc-user",
        help="RPC username; prefer this with --prompt-rpc-password for remote nodes",
    )
    parser.add_argument(
        "--prompt-rpc-password",
        action="store_true",
        help="Read the RPC password interactively without echoing or storing it",
    )
    parser.add_argument("--block-hash", help="Optional block hash supplied to getrawtransaction")
    parser.add_argument(
        "--no-witness",
        action="store_true",
        help="Disable extended-serialization detection for ambiguous zero-input test transactions",
    )
    return parser


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: record must be a JSON object")
            if not isinstance(record.get("hex"), str):
                raise ValueError(f"{path}:{line_number}: record requires string field 'hex'")
            if "id" in record and record["id"] is not None and not isinstance(record["id"], str):
                raise ValueError(f"{path}:{line_number}: id must be a string or null")
            fee = record.get("fee_sats")
            if fee is not None and (not isinstance(fee, int) or isinstance(fee, bool)):
                raise ValueError(f"{path}:{line_number}: fee_sats must be an integer or null")
            records.append(record)
    return records


def _source_records(arguments: argparse.Namespace) -> list[dict[str, Any]]:
    if arguments.transaction_hexes is not None:
        if arguments.label is not None and len(arguments.transaction_hexes) != 1:
            raise ValueError("--label may only be used with one --hex value")
        return [
            {
                "id": arguments.label or f"hex-{index}",
                "hex": transaction_hex,
                "fee_sats": None,
            }
            for index, transaction_hex in enumerate(arguments.transaction_hexes, start=1)
        ]
    if arguments.label is not None:
        raise ValueError("--label requires --hex")
    return _load_jsonl(arguments.input)


def _rpc_client(arguments: argparse.Namespace) -> BitcoinRPCClient:
    username = arguments.rpc_user or os.environ.get("BITCOIN_RPC_USER")
    password = os.environ.get("BITCOIN_RPC_PASSWORD")
    if arguments.prompt_rpc_password:
        if password is not None:
            raise ValueError(
                "--prompt-rpc-password cannot be combined with BITCOIN_RPC_PASSWORD"
            )
        if not username:
            raise ValueError("--prompt-rpc-password requires --rpc-user or BITCOIN_RPC_USER")
        password = getpass("Knots RPC password: ")

    if username is not None or password is not None:
        if not username or not password:
            raise ValueError("BITCOIN_RPC_USER and BITCOIN_RPC_PASSWORD must be set together")
        return BitcoinRPCClient(arguments.rpc_url, username, password)

    cookie_path = arguments.rpc_cookie
    if cookie_path is None:
        cookie_path = Path(os.environ.get("BITCOIN_RPC_COOKIE", "~/.bitcoin/.cookie"))
    return BitcoinRPCClient.from_cookie(url=arguments.rpc_url, cookie_path=cookie_path)


def run(arguments: argparse.Namespace) -> str:
    analyses = []
    if arguments.rpc_txids is not None:
        if arguments.label is not None:
            raise ValueError("--label is not supported with --rpc-txid; the txid is the identifier")
        client = _rpc_client(arguments)
        for txid in arguments.rpc_txids:
            rpc_result = client.get_raw_transaction(txid, block_hash=arguments.block_hash)
            analyses.append(analyze_core_transaction(rpc_result, identifier=txid).to_dict())
        return export_records(analyses, arguments.format)

    for record in _source_records(arguments):
        transaction = Transaction.from_hex(
            record["hex"],
            allow_witness=not arguments.no_witness,
        )
        analyses.append(
            analyze_transaction(
                transaction,
                identifier=record.get("id"),
                fee_sats=record.get("fee_sats"),
            ).to_dict()
        )
    return export_records(analyses, arguments.format)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        rendered = run(arguments)
        if arguments.output is None:
            sys.stdout.write(rendered)
        else:
            arguments.output.write_text(rendered, encoding="utf-8")
    except (
        OSError,
        BitcoinCoreParityError,
        BitcoinRPCError,
        TransactionDecodingError,
        ValueError,
    ) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
