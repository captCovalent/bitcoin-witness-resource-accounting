from hashlib import new as new_hash
from hashlib import sha256
import unittest

from witness_resource_accounting.classification import classify_input
from witness_resource_accounting.transaction import TransactionInput, Witness


def input_with_witness(
    elements: tuple[bytes, ...],
    *,
    script_sig: bytes = b"",
) -> TransactionInput:
    return TransactionInput(
        previous_txid_internal=b"\x00" * 32,
        previous_output_index=0,
        script_sig=script_sig,
        sequence=0xFFFFFFFF,
        witness=Witness(elements),
    )


class ClassificationTests(unittest.TestCase):
    def test_missing_prevout_remains_unknown(self) -> None:
        result = classify_input(input_with_witness((b"\x00" * 64,)), None)
        self.assertEqual(result["spend_type"], "unknown")
        self.assertIsNone(result["classification_evidence"])

    def test_native_p2wpkh_uses_prevout_program(self) -> None:
        result = classify_input(
            input_with_witness((b"\x00" * 71, b"\x02" * 33)),
            b"\x00\x14" + b"\x11" * 20,
        )
        self.assertEqual(result["spend_type"], "p2wpkh")
        self.assertEqual(result["witness_program_wrapping"], "native")
        self.assertTrue(result["structure_valid"])

    def test_p2sh_wrapped_p2wpkh_hash_is_verified(self) -> None:
        redeem_script = b"\x00\x14" + b"\x11" * 20
        script_hash = new_hash("ripemd160", sha256(redeem_script).digest()).digest()
        prevout = b"\xa9\x14" + script_hash + b"\x87"
        result = classify_input(
            input_with_witness(
                (b"\x00" * 71, b"\x02" * 33),
                script_sig=bytes((len(redeem_script),)) + redeem_script,
            ),
            prevout,
        )
        self.assertEqual(result["spend_type"], "p2wpkh")
        self.assertEqual(result["witness_program_wrapping"], "p2sh")

    def test_p2wsh_reports_last_element_as_witness_script(self) -> None:
        result = classify_input(
            input_with_witness((b"argument", b"\x51" * 123)),
            b"\x00\x20" + b"\x22" * 32,
        )
        self.assertEqual(result["spend_type"], "p2wsh")
        self.assertEqual(result["witness_script_size"], 123)

    def test_p2tr_key_path_removes_optional_annex(self) -> None:
        result = classify_input(
            input_with_witness((b"\x00" * 64, b"\x50annex")),
            b"\x51\x20" + b"\x33" * 32,
        )
        self.assertEqual(result["spend_type"], "p2tr_key_path")
        self.assertEqual(result["annex_size"], 6)
        self.assertTrue(result["structure_valid"])

    def test_p2tr_script_path_reports_tapscript_and_control_block(self) -> None:
        control_block = b"\xc1" + b"\x44" * 32 + b"\x55" * 64
        result = classify_input(
            input_with_witness((b"argument", b"\x51" * 10, control_block)),
            b"\x51\x20" + b"\x33" * 32,
        )
        self.assertEqual(result["spend_type"], "p2tr_script_path")
        self.assertEqual(result["tapleaf_script_size"], 10)
        self.assertEqual(result["tapscript_size"], 10)
        self.assertEqual(result["control_block_size"], 97)
        self.assertEqual(result["control_block_merkle_depth"], 2)
        self.assertEqual(result["tapleaf_version"], 0xC0)
        self.assertTrue(result["structure_valid"])

    def test_witness_shape_does_not_override_non_witness_prevout(self) -> None:
        result = classify_input(
            input_with_witness((b"\x00" * 64,)),
            b"\x76\xa9\x14" + b"\x11" * 20 + b"\x88\xac",
        )
        self.assertEqual(result["spend_type"], "non_witness_or_unknown")


if __name__ == "__main__":
    unittest.main()

