import unittest
from pathlib import Path
import tempfile

from witness_resource_accounting.sampling import (
    HeightStratum,
    collect_sample,
    collect_sample_to_jsonl,
    default_pilot_strata,
    deterministic_height_sample,
)
from witness_resource_accounting.transaction import Transaction

from fixtures import legacy_one_input_one_output


def rpc_transaction() -> dict:
    transaction = Transaction.from_bytes(legacy_one_input_one_output())
    return {
        "hex": transaction.serialize().hex(),
        "size": transaction.total_size,
        "vsize": transaction.total_size,
        "weight": transaction.total_size * 4,
        "txid": transaction.txid,
        "hash": transaction.wtxid,
        "vin": [{}],
    }


class FakeBlockClient:
    def __init__(self) -> None:
        self.hash_calls: list[int] = []

    def get_block_count(self) -> int:
        return 20

    def get_block_hash(self, height: int) -> str:
        self.hash_calls.append(height)
        return f"{height:064x}"

    def get_block(self, block_hash: str, *, verbosity: int = 3) -> dict:
        height = int(block_hash, 16)
        return {
            "hash": block_hash,
            "height": height,
            "time": 1_700_000_000 + height,
            "tx": [rpc_transaction()],
        }


class SamplingTests(unittest.TestCase):
    def test_sample_is_deterministic_unique_and_in_bounds(self) -> None:
        strata = [
            HeightStratum("one", 10, 29, 3),
            HeightStratum("two", 30, 49, 4),
        ]
        first = deterministic_height_sample(strata, seed="published-seed")
        second = deterministic_height_sample(strata, seed="published-seed")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 7)
        self.assertEqual(len({item.height for item in first}), 7)
        self.assertTrue(all(10 <= item.height <= 49 for item in first))
        self.assertNotEqual(first, deterministic_height_sample(strata, seed="different-seed"))

    def test_overlapping_strata_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlap"):
            deterministic_height_sample(
                [HeightStratum("one", 1, 10, 1), HeightStratum("two", 10, 20, 1)],
                seed="seed",
            )

    def test_default_pilot_uses_disjoint_protocol_eras(self) -> None:
        strata = default_pilot_strata(962_135)
        self.assertEqual(
            [(item.start_height, item.end_height) for item in strata],
            [(481_824, 709_631), (709_632, 839_999), (840_000, 962_135)],
        )

    def test_collection_records_provenance_without_transaction_hex(self) -> None:
        client = FakeBlockClient()
        manifest, records = collect_sample(
            client,
            strata=[HeightStratum("pilot", 10, 20, 1)],
            seed="seed",
        )
        selected_height = manifest["blocks"][0]["height"]
        self.assertEqual(manifest["purpose"], "rpc_and_baseline_parity_pilot_not_evidentiary_sample")
        self.assertEqual(manifest["transaction_count"], 1)
        self.assertEqual(records[0]["source"]["block_height"], selected_height)
        self.assertNotIn("hex", records[0])
        self.assertEqual(client.hash_calls, [selected_height, selected_height])

    def test_streaming_collection_writes_checksum_and_no_payload(self) -> None:
        client = FakeBlockClient()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sample.jsonl"
            manifest = collect_sample_to_jsonl(
                client,
                strata=[HeightStratum("pilot", 10, 20, 1)],
                seed="seed",
                output_path=output,
            )
            rendered = output.read_text(encoding="utf-8")
        self.assertEqual(manifest["transaction_count"], 1)
        self.assertNotIn('"hex"', rendered)
        self.assertEqual(len(manifest["transactions_output"]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
