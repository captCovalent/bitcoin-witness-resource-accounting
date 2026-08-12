"""Deterministic baseline result serialization."""

from __future__ import annotations

import csv
from io import StringIO
import json
from typing import Any, Iterable


CSV_FIELDS = (
    "schema_version",
    "id",
    "txid",
    "wtxid",
    "version",
    "lock_time",
    "input_count",
    "output_count",
    "has_witness",
    "stripped_size",
    "total_size",
    "witness_serialization_size",
    "witness_section_size",
    "witness_payload_size",
    "bip141_weight",
    "bip141_vsize",
    "fee_sats",
    "bip141_feerate_sat_vb",
)


def export_records(records: Iterable[dict[str, Any]], output_format: str) -> str:
    materialized = list(records)
    if output_format == "json":
        return json.dumps(materialized, indent=2, sort_keys=True) + "\n"
    if output_format == "jsonl":
        return "".join(json.dumps(record, sort_keys=True) + "\n" for record in materialized)
    if output_format == "csv":
        stream = StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)
        return stream.getvalue()
    raise ValueError(f"unsupported output format: {output_format}")

