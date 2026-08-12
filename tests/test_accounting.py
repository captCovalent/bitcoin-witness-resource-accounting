import csv
from io import StringIO
import json
import unittest

from witness_resource_accounting.accounting import BIP141Accounting, analyze_transaction
from witness_resource_accounting.export import export_records
from witness_resource_accounting.transaction import Transaction

from fixtures import BIP143_SIGNED_NATIVE_P2WPKH, legacy_one_input_one_output, witness_transaction


class AccountingTests(unittest.TestCase):
    def test_legacy_weight_is_four_times_size(self) -> None:
        transaction = Transaction.from_bytes(legacy_one_input_one_output())
        self.assertEqual(BIP141Accounting.weight(transaction), 240)
        self.assertEqual(BIP141Accounting.virtual_size(transaction), 60)

    def test_witness_weight_and_vsize_round_up(self) -> None:
        transaction = Transaction.from_bytes(witness_transaction(((b"\x11" * 64,),)))
        self.assertEqual(BIP141Accounting.weight(transaction), 308)
        self.assertEqual(BIP141Accounting.virtual_size(transaction), 77)

    def test_bip143_vector_weight(self) -> None:
        transaction = Transaction.from_bytes(BIP143_SIGNED_NATIVE_P2WPKH)
        analysis = analyze_transaction(transaction, identifier="bip143", fee_sats=1_042).to_dict()

        self.assertEqual(analysis["bip141_weight"], 1_042)
        self.assertEqual(analysis["bip141_vsize"], 261)
        self.assertEqual(analysis["witness_serialization_size"], 110)
        self.assertEqual(analysis["witness_section_size"], 108)
        self.assertEqual(analysis["witness_payload_size"], 104)
        self.assertEqual(analysis["bip141_feerate_sat_vb"], 1_042 / 261)

    def test_analysis_does_not_export_witness_contents(self) -> None:
        transaction = Transaction.from_bytes(witness_transaction(((b"secret marker",),)))
        encoded = json.dumps(analyze_transaction(transaction).to_dict())
        self.assertNotIn("secret marker", encoded)
        self.assertIn('"element_sizes": [13]', encoded)

    def test_negative_fee_is_rejected(self) -> None:
        transaction = Transaction.from_bytes(legacy_one_input_one_output())
        with self.assertRaises(ValueError):
            analyze_transaction(transaction, fee_sats=-1)

    def test_csv_is_transaction_level_projection(self) -> None:
        transaction = Transaction.from_bytes(legacy_one_input_one_output())
        record = analyze_transaction(transaction, identifier="legacy").to_dict()
        rendered = export_records([record], "csv")
        rows = list(csv.DictReader(StringIO(rendered)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "legacy")
        self.assertEqual(rows[0]["bip141_weight"], "240")
        self.assertNotIn("inputs", rows[0])


if __name__ == "__main__":
    unittest.main()
