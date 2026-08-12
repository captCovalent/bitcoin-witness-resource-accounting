import unittest

from witness_resource_accounting.adversarial import (
    batching_unbatching,
    boundary_suite,
    input_splitting,
    stripped_output_padding,
    transaction_splitting,
    utxo_manufacturing,
    witness_element_splitting,
    witness_structure_movement,
)


def contains_forbidden_payload(value) -> bool:
    if isinstance(value, dict):
        return any(key in value for key in ("hex", "elements", "raw_payload")) or any(
            contains_forbidden_payload(child) for child in value.values()
        )
    if isinstance(value, list):
        return any(contains_forbidden_payload(child) for child in value)
    return False


class AdversarialConstructionTests(unittest.TestCase):
    def test_input_splitting_preserves_opaque_capacity(self) -> None:
        construction = input_splitting(1_025, 8, output_count=2)
        transaction = construction.transactions[0]
        self.assertEqual(len(transaction.inputs), 8)
        self.assertEqual(len(transaction.outputs), 2)
        self.assertEqual(
            sum(input_.witness.payload_size for input_ in transaction.inputs),
            1_025,
        )
        self.assertEqual(construction.objective, "single_spend_capacity")

    def test_transaction_splitting_preserves_capacity_and_independence_count(self) -> None:
        construction = transaction_splitting(1_025, 4)
        self.assertEqual(len(construction.transactions), 4)
        self.assertEqual(
            sum(
                input_.witness.payload_size
                for transaction in construction.transactions
                for input_ in transaction.inputs
            ),
            1_025,
        )
        self.assertEqual(construction.objective, "independently_mineable_capacity")

    def test_batching_preserves_total_outputs_and_capacity(self) -> None:
        construction = batching_unbatching(1_025, 16, 4)
        self.assertEqual(len(construction.transactions), 4)
        self.assertEqual(sum(len(tx.outputs) for tx in construction.transactions), 16)
        self.assertEqual(
            sum(
                input_.witness.payload_size
                for transaction in construction.transactions
                for input_ in transaction.inputs
            ),
            1_025,
        )

    def test_element_compact_size_boundary_cost_is_exact(self) -> None:
        below = witness_element_splitting(252, 1).to_record()
        above = witness_element_splitting(253, 1).to_record()
        # One more content byte plus a two-byte increase in its CompactSize prefix.
        self.assertEqual(
            above["total_witness_serialization_size"]
            - below["total_witness_serialization_size"],
            3,
        )

    def test_element_splitting_reports_only_sizes(self) -> None:
        record = witness_element_splitting(512, 7).to_record()
        sizes = record["stages"][0]["transactions"][0]["witness_element_sizes_by_input"][0]
        self.assertEqual(len(sizes), 7)
        self.assertEqual(sum(sizes), 512)
        self.assertFalse(contains_forbidden_payload(record))
        self.assertIsNone(record["candidate_model"])

    def test_stripped_padding_includes_compact_size_transition(self) -> None:
        empty = stripped_output_padding(64, 0).to_record()
        padded = stripped_output_padding(64, 253).to_record()
        # Same output count and value: 253 script bytes plus CompactSize 1 -> 3.
        self.assertEqual(padded["total_stripped_size"] - empty["total_stripped_size"], 255)
        self.assertEqual(padded["opaque_bytes"], empty["opaque_bytes"])

    def test_utxo_manufacturing_links_setup_and_spend(self) -> None:
        construction = utxo_manufacturing(1_000, 4)
        setup = construction.stages[0].transactions[0]
        spend = construction.stages[1].transactions[0]
        self.assertEqual(len(setup.outputs), 4)
        self.assertEqual(len(spend.inputs), 4)
        self.assertTrue(all(input_.previous_txid == setup.txid for input_ in spend.inputs))
        record = construction.to_record()
        self.assertEqual(
            record["total_bip141_weight"],
            sum(stage["bip141_weight"] for stage in record["stages"]),
        )
        self.assertEqual(record["objective"], "lifecycle_capacity")

    def test_witness_structure_movement_keeps_opaque_capacity_separate(self) -> None:
        expected_sizes = {
            "argument": [100, 1],
            "witness_script": [0, 100],
            "tapscript": [64, 100, 33],
            "annex": [64, 101],
        }
        for structure, expected in expected_sizes.items():
            with self.subTest(structure=structure):
                record = witness_structure_movement(100, structure).to_record()
                sizes = record["stages"][0]["transactions"][0][
                    "witness_element_sizes_by_input"
                ][0]
                self.assertEqual(sizes, expected)
                self.assertEqual(record["opaque_bytes"], 100)
                self.assertEqual(record["validity_level"], "serialization_only")

    def test_boundary_suite_size_is_deterministic(self) -> None:
        constructions = boundary_suite(
            opaque_sizes=(0, 64),
            split_counts=(1, 2),
            padding_sizes=(0, 32, 253),
        )
        self.assertEqual(len(constructions), 2 * (2 * 5 + 3 + 4))
        second = boundary_suite(
            opaque_sizes=(0, 64),
            split_counts=(1, 2),
            padding_sizes=(0, 32, 253),
        )
        self.assertEqual(
            [construction.to_record() for construction in constructions],
            [construction.to_record() for construction in second],
        )

    def test_invalid_counts_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            input_splitting(1, 0)
        with self.assertRaises(ValueError):
            transaction_splitting(1, 0)
        with self.assertRaises(ValueError):
            witness_element_splitting(1, 0)
        with self.assertRaises(ValueError):
            utxo_manufacturing(1, 0)
        with self.assertRaises(ValueError):
            batching_unbatching(1, 4, 5)


if __name__ == "__main__":
    unittest.main()
