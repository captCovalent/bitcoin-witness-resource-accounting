"""Reproducible structural summaries for baseline JSONL result bundles."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
from typing import Any


def _nearest_rank(values: list[int], percentile: int) -> int | None:
    if not values:
        return None
    if not 1 <= percentile <= 100:
        raise ValueError("percentile must be between 1 and 100")
    ordered = sorted(values)
    return ordered[ceil(len(ordered) * percentile / 100) - 1]


def _contains_forbidden_payload_key(value: Any) -> bool:
    if isinstance(value, dict):
        if "hex" in value or "elements" in value:
            return True
        return any(_contains_forbidden_payload_key(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_payload_key(child) for child in value)
    return False


def summarize_result_bundle(manifest_path: Path, transactions_path: Path) -> dict[str, Any]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    expected_digest = manifest.get("transactions_output", {}).get("sha256")
    digest = sha256()
    with transactions_path.open("rb") as transaction_source:
        for chunk in iter(lambda: transaction_source.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_digest = digest.hexdigest()
    if expected_digest != actual_digest:
        raise ValueError(
            f"transaction output checksum mismatch: manifest={expected_digest!r}, actual={actual_digest}"
        )

    witness_sizes: list[int] = []
    input_counts: list[int] = []
    txids: set[str] = set()
    classifications: Counter[str] = Counter()
    record_count = 0
    witness_transaction_count = 0
    fee_known_transaction_count = 0
    total_inputs = 0
    unknown_inputs = 0
    coinbase_unknown_inputs = 0
    block_groups: dict[int, dict[str, Any]] = defaultdict(dict)
    largest_projection: list[dict[str, Any]] = []

    with transactions_path.open("r", encoding="utf-8") as transaction_source:
        for line_number, line in enumerate(transaction_source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"transaction JSONL line {line_number} is not an object")
            if _contains_forbidden_payload_key(record):
                raise ValueError(f"transaction JSONL line {line_number} contains raw payload fields")
            txid = record.get("txid")
            if not isinstance(txid, str):
                raise ValueError(f"transaction JSONL line {line_number} lacks a txid")
            if txid in txids:
                raise ValueError("transaction output contains duplicate txids")
            txids.add(txid)
            record_count += 1
            witness_transaction_count += bool(record["has_witness"])
            fee_known_transaction_count += record["fee_sats"] is not None
            witness_sizes.append(int(record["witness_serialization_size"]))
            input_counts.append(int(record["input_count"]))

            source = record.get("source")
            if not isinstance(source, dict) or not isinstance(source.get("block_height"), int):
                raise ValueError("transaction record lacks block provenance")
            height = source["block_height"]
            block = block_groups[height]
            if not block:
                block.update(
                    {
                        "height": height,
                        "hash": source["block_hash"],
                        "stratum": source["stratum"],
                        "transaction_count": 0,
                        "witness_transaction_count": 0,
                        "total_stripped_bytes": 0,
                        "total_witness_serialization_bytes": 0,
                        "total_bip141_weight": 0,
                        "maximum_transaction_witness_serialization_bytes": 0,
                    }
                )
            elif block["hash"] != source["block_hash"] or block["stratum"] != source["stratum"]:
                raise ValueError("inconsistent block provenance within one height")
            block["transaction_count"] += 1
            block["witness_transaction_count"] += bool(record["has_witness"])
            block["total_stripped_bytes"] += record["stripped_size"]
            block["total_witness_serialization_bytes"] += record["witness_serialization_size"]
            block["total_bip141_weight"] += record["bip141_weight"]
            block["maximum_transaction_witness_serialization_bytes"] = max(
                block["maximum_transaction_witness_serialization_bytes"],
                record["witness_serialization_size"],
            )

            for transaction_input in record["inputs"]:
                total_inputs += 1
                spend_type = transaction_input["classification"]["spend_type"]
                classifications[spend_type] += 1
                if spend_type == "unknown":
                    unknown_inputs += 1
                    if (
                        transaction_input["previous_txid"] == "00" * 32
                        and transaction_input["previous_output_index"] == 0xFFFFFFFF
                    ):
                        coinbase_unknown_inputs += 1

            candidate = {
                "txid": txid,
                "block_height": height,
                "transaction_index": source["transaction_index"],
                "input_count": record["input_count"],
                "output_count": record["output_count"],
                "witness_serialization_size": record["witness_serialization_size"],
                "witness_payload_size": record["witness_payload_size"],
                "bip141_weight": record["bip141_weight"],
                "fee_sats": record["fee_sats"],
                "spend_types": sorted(
                    {item["classification"]["spend_type"] for item in record["inputs"]}
                ),
            }
            largest_projection.append(candidate)
            largest_projection.sort(
                key=lambda item: (-item["witness_serialization_size"], item["txid"])
            )
            del largest_projection[10:]

    if record_count != manifest.get("transaction_count"):
        raise ValueError("manifest transaction count does not match JSONL records")

    per_block = [block_groups[height] for height in sorted(block_groups)]

    percentiles = (50, 75, 90, 95, 99)
    return {
        "summary_version": 1,
        "scope": "baseline_rpc_pilot_not_model_evaluation",
        "manifest_path": manifest_path.name,
        "manifest_sha256": sha256(manifest_bytes).hexdigest(),
        "transactions_path": transactions_path.name,
        "transactions_sha256": actual_digest,
        "integrity": {
            "checksum_matches_manifest": True,
            "record_count_matches_manifest": True,
            "unique_txid_count": len(txids),
            "raw_payload_fields_present": False,
        },
        "transaction_count": record_count,
        "witness_transaction_count": witness_transaction_count,
        "fee_known_transaction_count": fee_known_transaction_count,
        "input_count": total_inputs,
        "input_classification_counts": dict(sorted(classifications.items())),
        "unknown_input_count": unknown_inputs,
        "coinbase_unknown_input_count": coinbase_unknown_inputs,
        "witness_serialization_size_bytes": {
            **{f"p{p}": _nearest_rank(witness_sizes, p) for p in percentiles},
            "maximum": max(witness_sizes, default=None),
        },
        "transaction_input_count": {
            **{f"p{p}": _nearest_rank(input_counts, p) for p in percentiles},
            "maximum": max(input_counts, default=None),
        },
        "blocks": per_block,
        "largest_witness_transactions": largest_projection,
    }
