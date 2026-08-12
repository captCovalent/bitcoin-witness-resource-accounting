import unittest

from witness_resource_accounting.errors import TransactionDecodingError
from witness_resource_accounting.transaction import Transaction

from fixtures import (
    BIP143_SIGNED_NATIVE_P2WPKH,
    legacy_one_input_one_output,
    transaction_input,
    transaction_output,
    witness_transaction,
)


class TransactionTests(unittest.TestCase):
    def test_legacy_transaction_round_trips(self) -> None:
        raw = legacy_one_input_one_output()
        transaction = Transaction.from_bytes(raw)

        self.assertFalse(transaction.has_witness)
        self.assertEqual(transaction.serialize(), raw)
        self.assertEqual(transaction.serialize(include_witness=False), raw)
        self.assertEqual(transaction.stripped_size, 60)
        self.assertEqual(transaction.total_size, 60)
        self.assertEqual(transaction.txid, transaction.wtxid)
        self.assertEqual(len(transaction.inputs), 1)
        self.assertEqual(len(transaction.outputs), 1)

    def test_single_input_witness_sizes_include_framing(self) -> None:
        raw = witness_transaction(((b"\x11" * 64,),))
        transaction = Transaction.from_bytes(raw)

        self.assertTrue(transaction.has_witness)
        self.assertEqual(transaction.serialize(), raw)
        self.assertEqual(transaction.stripped_size, 60)
        self.assertEqual(transaction.total_size, 128)
        self.assertEqual(transaction.total_size - transaction.stripped_size, 68)
        self.assertEqual(transaction.inputs[0].witness.payload_size, 64)
        self.assertEqual(transaction.inputs[0].witness.serialized_size, 66)

    def test_mixed_inputs_preserve_empty_witness_vector(self) -> None:
        raw = witness_transaction(((), (b"abc", b"\x02" * 33)))
        transaction = Transaction.from_bytes(raw)

        self.assertEqual(transaction.stripped_size, 101)
        self.assertEqual(transaction.total_size, 143)
        self.assertEqual(transaction.inputs[0].witness.serialized_size, 1)
        self.assertEqual(transaction.inputs[1].witness.serialized_size, 39)
        self.assertEqual(transaction.serialize(), raw)

    def test_compact_size_boundary_is_counted_in_witness(self) -> None:
        raw = witness_transaction(((b"\xaa" * 253,),))
        transaction = Transaction.from_bytes(raw)

        self.assertEqual(transaction.inputs[0].witness.payload_size, 253)
        self.assertEqual(transaction.inputs[0].witness.serialized_size, 257)
        self.assertEqual(transaction.stripped_size, 60)
        self.assertEqual(transaction.total_size, 319)

    def test_bip143_primary_source_vector(self) -> None:
        transaction = Transaction.from_bytes(BIP143_SIGNED_NATIVE_P2WPKH)

        self.assertEqual(transaction.serialize(), BIP143_SIGNED_NATIVE_P2WPKH)
        self.assertEqual(transaction.stripped_size, 233)
        self.assertEqual(transaction.total_size, 343)
        self.assertEqual(
            [input_.witness.serialized_size for input_ in transaction.inputs],
            [1, 107],
        )
        self.assertEqual(
            [len(element) for element in transaction.inputs[1].witness.elements],
            [71, 33],
        )

    def test_rejects_unknown_witness_flag(self) -> None:
        with self.assertRaisesRegex(TransactionDecodingError, "unknown.*flag"):
            Transaction.from_bytes(b"\x02\x00\x00\x00\x00\x02")

    def test_rejects_superfluous_witness_record(self) -> None:
        raw = witness_transaction(((),))
        with self.assertRaisesRegex(TransactionDecodingError, "superfluous witness"):
            Transaction.from_bytes(raw)

    def test_rejects_non_canonical_input_count(self) -> None:
        raw = b"\x02\x00\x00\x00\xfd\x01\x00" + legacy_one_input_one_output()[5:]
        with self.assertRaisesRegex(TransactionDecodingError, "non-canonical"):
            Transaction.from_bytes(raw)

    def test_rejects_trailing_bytes(self) -> None:
        with self.assertRaisesRegex(TransactionDecodingError, "trailing"):
            Transaction.from_bytes(legacy_one_input_one_output() + b"\x00")

    def test_rejects_truncated_script(self) -> None:
        raw = b"".join(
            (
                b"\x02\x00\x00\x00\x01",
                b"\x00" * 32,
                b"\x00" * 4,
                b"\x3c\x51",
                b"\xff" * 4,
                b"\x01",
                transaction_output(),
                b"\x00" * 4,
            )
        )
        with self.assertRaisesRegex(TransactionDecodingError, "truncated"):
            Transaction.from_bytes(raw)

    def test_hex_validation(self) -> None:
        for transaction_hex in ("", "0", "zz"):
            with self.subTest(transaction_hex=transaction_hex):
                with self.assertRaises(TransactionDecodingError):
                    Transaction.from_hex(transaction_hex)

    def test_zero_input_legacy_test_vector_requires_explicit_mode(self) -> None:
        raw = b"\x02\x00\x00\x00\x00\x01" + transaction_output() + b"\x00\x00\x00\x00"
        transaction = Transaction.from_bytes(raw, allow_witness=False)
        self.assertEqual(len(transaction.inputs), 0)
        self.assertEqual(len(transaction.outputs), 1)
        self.assertFalse(transaction.has_witness)


if __name__ == "__main__":
    unittest.main()
