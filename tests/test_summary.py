from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from witness_resource_accounting.summary import summarize_result_bundle


def record(txid: str, witness_size: int, spend_type: str = "p2wpkh") -> dict:
    return {
        "schema_version": 1,
        "id": txid,
        "txid": txid,
        "has_witness": witness_size > 0,
        "stripped_size": 100,
        "witness_serialization_size": witness_size,
        "witness_payload_size": max(0, witness_size - 4),
        "bip141_weight": 400 + witness_size,
        "fee_sats": 1000,
        "input_count": 1,
        "output_count": 1,
        "inputs": [
            {
                "previous_txid": "11" * 32,
                "previous_output_index": 0,
                "classification": {"spend_type": spend_type},
            }
        ],
        "source": {
            "block_height": 10,
            "block_hash": "22" * 32,
            "stratum": "pilot",
            "transaction_index": int(txid[-1], 16),
        },
    }


class SummaryTests(unittest.TestCase):
    def test_summary_verifies_bundle_and_uses_nearest_rank(self) -> None:
        rows = [record("00" * 31 + f"0{index}", size) for index, size in enumerate((0, 10, 20))]
        rendered = "".join(json.dumps(row) + "\n" for row in rows).encode()
        manifest = {
            "transaction_count": 3,
            "transactions_output": {"sha256": sha256(rendered).hexdigest()},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            transactions_path = root / "transactions.jsonl"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            transactions_path.write_bytes(rendered)
            summary = summarize_result_bundle(manifest_path, transactions_path)
        self.assertEqual(summary["transaction_count"], 3)
        self.assertEqual(summary["witness_serialization_size_bytes"]["p50"], 10)
        self.assertEqual(summary["witness_serialization_size_bytes"]["p99"], 20)
        self.assertEqual(summary["input_classification_counts"], {"p2wpkh": 3})

    def test_checksum_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            transactions_path = root / "transactions.jsonl"
            manifest_path.write_text(
                json.dumps({"transaction_count": 0, "transactions_output": {"sha256": "00"}}),
                encoding="utf-8",
            )
            transactions_path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                summarize_result_bundle(manifest_path, transactions_path)

    def test_raw_payload_fields_are_rejected(self) -> None:
        row = record("00" * 32, 10)
        row["hex"] = "deadbeef"
        rendered = (json.dumps(row) + "\n").encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            transactions_path = root / "transactions.jsonl"
            manifest_path.write_text(
                json.dumps(
                    {
                        "transaction_count": 1,
                        "transactions_output": {"sha256": sha256(rendered).hexdigest()},
                    }
                ),
                encoding="utf-8",
            )
            transactions_path.write_bytes(rendered)
            with self.assertRaisesRegex(ValueError, "raw payload"):
                summarize_result_bundle(manifest_path, transactions_path)


if __name__ == "__main__":
    unittest.main()
