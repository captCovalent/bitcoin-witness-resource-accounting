import unittest

from witness_resource_accounting.compact_size import (
    ByteReader,
    compact_size_length,
    encode_compact_size,
)
from witness_resource_accounting.errors import TransactionDecodingError


class CompactSizeTests(unittest.TestCase):
    def test_boundary_encodings(self) -> None:
        cases = (
            (0, "00", 1),
            (252, "fc", 1),
            (253, "fdfd00", 3),
            (65535, "fdffff", 3),
            (65536, "fe00000100", 5),
            (0xFFFFFFFF, "feffffffff", 5),
            (0x100000000, "ff0000000001000000", 9),
        )
        for value, expected_hex, expected_length in cases:
            with self.subTest(value=value):
                self.assertEqual(encode_compact_size(value).hex(), expected_hex)
                self.assertEqual(compact_size_length(value), expected_length)
                reader = ByteReader(bytes.fromhex(expected_hex))
                self.assertEqual(
                    reader.read_compact_size(field="test", range_check=False),
                    value,
                )
                self.assertEqual(reader.remaining, 0)

    def test_rejects_non_canonical_encodings(self) -> None:
        for encoded in ("fdfc00", "feffff0000", "ffffffffff00000000"):
            with self.subTest(encoded=encoded):
                with self.assertRaisesRegex(TransactionDecodingError, "non-canonical"):
                    ByteReader(bytes.fromhex(encoded)).read_compact_size(field="test")

    def test_rejects_truncated_encoding(self) -> None:
        with self.assertRaisesRegex(TransactionDecodingError, "truncated"):
            ByteReader(b"\xfd\x01").read_compact_size(field="test")

    def test_rejects_negative_encoding_request(self) -> None:
        with self.assertRaises(ValueError):
            encode_compact_size(-1)


if __name__ == "__main__":
    unittest.main()

