"""Deterministic block-height sampling and RPC-backed pilot collection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from heapq import nsmallest
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Sequence

from .rpc import BitcoinRPCClient, BitcoinRPCError, analyze_core_transaction


SAMPLING_ALGORITHM = "sha256-height-rank-v1"


@dataclass(frozen=True, slots=True)
class HeightStratum:
    name: str
    start_height: int
    end_height: int
    sample_count: int

    def validate(self) -> None:
        if not self.name or any(character.isspace() for character in self.name):
            raise ValueError("stratum name must be non-empty and contain no whitespace")
        if self.start_height < 0:
            raise ValueError(f"stratum {self.name}: start height cannot be negative")
        if self.end_height < self.start_height:
            raise ValueError(f"stratum {self.name}: end height precedes start height")
        population = self.end_height - self.start_height + 1
        if self.sample_count < 1 or self.sample_count > population:
            raise ValueError(
                f"stratum {self.name}: sample count must be between 1 and {population}"
            )


@dataclass(frozen=True, slots=True)
class SampledHeight:
    stratum: str
    height: int
    rank_digest: str


def _rank_digest(seed: str, stratum: str, height: int) -> str:
    material = f"{SAMPLING_ALGORITHM}\n{seed}\n{stratum}\n{height}\n".encode("utf-8")
    return sha256(material).hexdigest()


def deterministic_height_sample(
    strata: Sequence[HeightStratum],
    *,
    seed: str,
) -> list[SampledHeight]:
    """Select the lowest SHA256 ranks in each disjoint inclusive stratum."""
    if not seed:
        raise ValueError("sampling seed cannot be empty")
    if not strata:
        raise ValueError("at least one stratum is required")

    ordered = sorted(strata, key=lambda item: (item.start_height, item.end_height, item.name))
    previous: HeightStratum | None = None
    for stratum in ordered:
        stratum.validate()
        if previous is not None and stratum.start_height <= previous.end_height:
            raise ValueError(f"strata {previous.name} and {stratum.name} overlap")
        previous = stratum

    selected: list[SampledHeight] = []
    for stratum in strata:
        ranked = nsmallest(
            stratum.sample_count,
            range(stratum.start_height, stratum.end_height + 1),
            key=lambda height: _rank_digest(seed, stratum.name, height),
        )
        selected.extend(
            SampledHeight(stratum.name, height, _rank_digest(seed, stratum.name, height))
            for height in ranked
        )
    return sorted(selected, key=lambda item: (item.height, item.stratum))


def default_pilot_strata(tip_height: int, *, count_per_stratum: int = 1) -> list[HeightStratum]:
    """Return protocol-era strata for a plumbing pilot, not an evidentiary dataset."""
    if tip_height < 840_000:
        raise ValueError("default pilot requires a chain tip at or above height 840000")
    return [
        HeightStratum("segwit_pre_taproot", 481_824, 709_631, count_per_stratum),
        HeightStratum("taproot_pre_halving4", 709_632, 839_999, count_per_stratum),
        HeightStratum("post_halving4", 840_000, tip_height, count_per_stratum),
    ]


def collect_sample(
    client: BitcoinRPCClient,
    *,
    strata: Sequence[HeightStratum],
    seed: str,
    purpose: str = "rpc_and_baseline_parity_pilot_not_evidentiary_sample",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch selected blocks at verbosity 3 and return a manifest and analyses."""
    analyses: list[dict[str, Any]] = []
    manifest = _collect_sample_records(
        client,
        strata=strata,
        seed=seed,
        purpose=purpose,
        consume=analyses.append,
    )
    return manifest, analyses


def _collect_sample_records(
    client: BitcoinRPCClient,
    *,
    strata: Sequence[HeightStratum],
    seed: str,
    purpose: str,
    consume: Any,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    tip_at_start = client.get_block_count()
    selected = deterministic_height_sample(strata, seed=seed)
    if any(item.height > tip_at_start for item in selected):
        raise BitcoinRPCError("sample includes a height above the node tip")

    block_entries: list[dict[str, Any]] = []
    transaction_count = 0
    for sampled in selected:
        block_hash = client.get_block_hash(sampled.height)
        block = client.get_block(block_hash, verbosity=3)
        if block.get("hash") != block_hash or block.get("height") != sampled.height:
            raise BitcoinRPCError("getblock response does not match requested height and hash")
        transactions = block.get("tx")
        if not isinstance(transactions, list):
            raise BitcoinRPCError("getblock verbosity 3 response lacks a transaction array")

        for transaction_index, rpc_transaction in enumerate(transactions):
            if not isinstance(rpc_transaction, dict):
                raise BitcoinRPCError("getblock returned a non-object transaction")
            record = analyze_core_transaction(rpc_transaction).to_dict()
            record["source"] = {
                "rpc_method": "getblock",
                "rpc_verbosity": 3,
                "stratum": sampled.stratum,
                "block_height": sampled.height,
                "block_hash": block_hash,
                "block_time": block.get("time"),
                "transaction_index": transaction_index,
            }
            consume(record)
            transaction_count += 1

        block_entries.append(
            {
                "stratum": sampled.stratum,
                "height": sampled.height,
                "hash": block_hash,
                "rank_digest": sampled.rank_digest,
                "time": block.get("time"),
                "transaction_count": len(transactions),
            }
        )

    # Re-resolve selected heights so a reorganization cannot silently mix chains.
    for entry in block_entries:
        if client.get_block_hash(entry["height"]) != entry["hash"]:
            raise BitcoinRPCError(f"selected block at height {entry['height']} reorganized during collection")

    manifest = {
        "manifest_version": 1,
        "purpose": purpose,
        "sampling_algorithm": SAMPLING_ALGORITHM,
        "seed": seed,
        "started_utc": started,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "tip_height_at_start": tip_at_start,
        "strata": [
            {
                "name": item.name,
                "start_height": item.start_height,
                "end_height": item.end_height,
                "sample_count": item.sample_count,
            }
            for item in strata
        ],
        "blocks": block_entries,
        "transaction_count": transaction_count,
    }
    return manifest


def collect_sample_to_jsonl(
    client: BitcoinRPCClient,
    *,
    strata: Sequence[HeightStratum],
    seed: str,
    output_path: Path,
    purpose: str = "rpc_and_baseline_parity_pilot_not_evidentiary_sample",
) -> dict[str, Any]:
    """Stream a sample atomically to JSONL and return its completed manifest."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)

            def write_record(record: dict[str, Any]) -> None:
                rendered = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                destination.write(rendered)
                digest.update(rendered.encode("utf-8"))

            manifest = _collect_sample_records(
                client,
                strata=strata,
                seed=seed,
                purpose=purpose,
                consume=write_record,
            )
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    manifest["transactions_output"] = {
        "path": output_path.name,
        "format": "jsonl",
        "sha256": digest.hexdigest(),
    }
    return manifest
