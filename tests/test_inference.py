import json
import math
from pathlib import Path
import tempfile
import unittest

from witness_resource_accounting.inference import estimate_stratified_blocks
from witness_resource_accounting.sample_plan import load_sampling_plan


METRICS = {
    "witness_transaction_count": 1,
    "input_count": 2,
    "total_stripped_bytes": 100,
    "total_witness_serialization_bytes": 50,
    "total_bip141_weight": 450,
}


def write_plan(directory: str) -> Path:
    document = {
        "plan_version": 1,
        "plan_id": "inference-test",
        "chain": "main",
        "universe": {"start_height": 10, "end_height": 29, "block_count": 20},
        "total_sampled_blocks": 4,
        "strata": [
            {"name": "one", "start_height": 10, "end_height": 19, "sample_count": 2},
            {"name": "two", "start_height": 20, "end_height": 29, "sample_count": 2},
        ],
        "seed": {
            "method": "future_bitcoin_block_hash",
            "height": 30,
            "minimum_depth": 1,
            "domain": "test",
        },
    }
    path = Path(directory) / "plan.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def block(height: int, stratum: str, transactions: int) -> dict:
    return {
        "height": height,
        "stratum": stratum,
        "transaction_count": transactions,
        **METRICS,
    }


class InferenceTests(unittest.TestCase):
    def test_stratified_total_variance_and_ratios(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory))
        result = estimate_stratified_blocks(
            plan,
            [
                block(10, "one", 1),
                block(11, "one", 3),
                block(20, "two", 5),
                block(21, "two", 7),
            ],
            bootstrap_replicates=200,
            bootstrap_seed="deterministic",
        )
        transactions = result["aggregate_metrics"]["transaction_count"]
        self.assertEqual(transactions["estimated_universe_total"], 80)
        self.assertEqual(transactions["estimated_mean_per_block"], 4)
        self.assertTrue(
            math.isclose(transactions["linearization_standard_error_total"], math.sqrt(160))
        )
        self.assertEqual(result["ratio_estimands"]["witness_transaction_share"]["estimate"], 0.25)
        self.assertEqual(result["variance_sampling_unit"], "block")

    def test_bootstrap_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory))
        blocks = [
            block(10, "one", 1),
            block(11, "one", 3),
            block(20, "two", 5),
            block(21, "two", 7),
        ]
        first = estimate_stratified_blocks(
            plan, blocks, bootstrap_replicates=100, bootstrap_seed="same"
        )
        second = estimate_stratified_blocks(
            plan, blocks, bootstrap_replicates=100, bootstrap_seed="same"
        )
        self.assertEqual(first, second)

    def test_missing_sampled_block_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory))
        with self.assertRaisesRegex(ValueError, "expected 2"):
            estimate_stratified_blocks(
                plan,
                [block(10, "one", 1), block(20, "two", 5), block(21, "two", 7)],
                bootstrap_replicates=100,
            )

    def test_duplicate_height_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            estimate_stratified_blocks(
                plan,
                [
                    block(10, "one", 1),
                    block(10, "one", 3),
                    block(20, "two", 5),
                    block(21, "two", 7),
                ],
                bootstrap_replicates=100,
            )


if __name__ == "__main__":
    unittest.main()
