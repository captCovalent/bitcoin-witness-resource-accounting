import json
from pathlib import Path
import tempfile
import unittest

from witness_resource_accounting.rpc import BitcoinRPCError
from witness_resource_accounting.sample_plan import load_sampling_plan, resolve_sampling_plan


def plan_document() -> dict:
    return {
        "plan_version": 1,
        "plan_id": "test-plan",
        "chain": "main",
        "universe": {"start_height": 10, "end_height": 19, "block_count": 10},
        "total_sampled_blocks": 2,
        "strata": [
            {"name": "one", "start_height": 10, "end_height": 14, "sample_count": 1},
            {"name": "two", "start_height": 15, "end_height": 19, "sample_count": 1},
        ],
        "seed": {
            "method": "future_bitcoin_block_hash",
            "height": 30,
            "minimum_depth": 5,
            "domain": "test-plan",
        },
    }


def write_plan(directory: str, document: dict) -> Path:
    path = Path(directory) / "plan.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


class FakePlanClient:
    def __init__(self, tip: int = 35, chain: str = "main") -> None:
        self.tip = tip
        self.chain = chain

    def get_blockchain_info(self) -> dict:
        return {"chain": self.chain}

    def get_block_count(self) -> int:
        return self.tip

    def get_block_hash(self, height: int) -> str:
        return f"{height:064x}"


class SamplePlanTests(unittest.TestCase):
    def test_valid_plan_loads_and_future_seed_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory, plan_document()))
        resolved = resolve_sampling_plan(FakePlanClient(), plan)
        self.assertEqual(resolved.seed_block_height, 30)
        self.assertEqual(resolved.seed_block_hash, f"{30:064x}")
        self.assertEqual(resolved.seed, f"test-plan:{30:064x}")
        self.assertEqual(len(plan.source_sha256), 64)

    def test_plan_rejects_gap(self) -> None:
        document = plan_document()
        document["strata"][1]["start_height"] = 16
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "gap or overlap"):
                load_sampling_plan(write_plan(directory, document))

    def test_plan_rejects_inconsistent_universe_count(self) -> None:
        document = plan_document()
        document["universe"]["block_count"] = 11
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "block_count"):
                load_sampling_plan(write_plan(directory, document))

    def test_seed_maturity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory, plan_document()))
        with self.assertRaisesRegex(BitcoinRPCError, "2 blocks remaining"):
            resolve_sampling_plan(FakePlanClient(tip=33), plan)

    def test_wrong_chain_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = load_sampling_plan(write_plan(directory, plan_document()))
        with self.assertRaisesRegex(BitcoinRPCError, "chain"):
            resolve_sampling_plan(FakePlanClient(chain="test"), plan)


if __name__ == "__main__":
    unittest.main()
