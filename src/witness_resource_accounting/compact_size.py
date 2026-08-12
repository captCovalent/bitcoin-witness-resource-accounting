"""Bitcoin CompactSize encoding with canonical-decoding checks."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import TransactionDecodingError


MAX_SIZE = 0x02000000


def compact_size_length(value: int) -> int:
    if value < 0:
        raise ValueError("CompactSize cannot encode a negative value")
    if value < 0xFD:
        return 1
    if value <= 0xFFFF:
        return 3
    if value <= 0xFFFFFFFF:
        return 5
    if value <= 0xFFFFFFFFFFFFFFFF:
        return 9
    raise ValueError("CompactSize value exceeds uint64")


def encode_compact_size(value: int) -> bytes:
    length = compact_size_length(value)
    if length == 1:
        return bytes((value,))
    if length == 3:
        return b"\xfd" + value.to_bytes(2, "little")
    if length == 5:
        return b"\xfe" + value.to_bytes(4, "little")
    return b"\xff" + value.to_bytes(8, "little")


@dataclass(slots=True)
class ByteReader:
    data: bytes
    offset: int = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def read(self, length: int, *, field: str) -> bytes:
        if length < 0:
            raise TransactionDecodingError(f"negative length for {field}")
        end = self.offset + length
        if end > len(self.data):
            raise TransactionDecodingError(
                f"truncated {field}: need {length} bytes, have {self.remaining}"
            )
        result = self.data[self.offset:end]
        self.offset = end
        return result

    def read_uint8(self, *, field: str) -> int:
        return self.read(1, field=field)[0]

    def read_uint32(self, *, field: str) -> int:
        return int.from_bytes(self.read(4, field=field), "little")

    def read_int64(self, *, field: str) -> int:
        return int.from_bytes(self.read(8, field=field), "little", signed=True)

    def read_compact_size(self, *, field: str, range_check: bool = True) -> int:
        prefix = self.read_uint8(field=f"{field} CompactSize prefix")
        if prefix < 0xFD:
            value = prefix
        elif prefix == 0xFD:
            value = int.from_bytes(self.read(2, field=field), "little")
            if value < 0xFD:
                raise TransactionDecodingError(f"non-canonical CompactSize for {field}")
        elif prefix == 0xFE:
            value = int.from_bytes(self.read(4, field=field), "little")
            if value <= 0xFFFF:
                raise TransactionDecodingError(f"non-canonical CompactSize for {field}")
        else:
            value = int.from_bytes(self.read(8, field=field), "little")
            if value <= 0xFFFFFFFF:
                raise TransactionDecodingError(f"non-canonical CompactSize for {field}")

        if range_check and value > MAX_SIZE:
            raise TransactionDecodingError(
                f"CompactSize for {field} exceeds serialization limit {MAX_SIZE}"
            )
        return value

