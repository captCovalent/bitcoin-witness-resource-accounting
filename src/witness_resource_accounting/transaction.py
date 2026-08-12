"""Canonical Bitcoin transaction parsing and serialization."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from .compact_size import ByteReader, compact_size_length, encode_compact_size
from .errors import TransactionDecodingError


_HEX_PATTERN = re.compile(r"[0-9a-fA-F]+")


def _hash256_display(data: bytes) -> str:
    return sha256(sha256(data).digest()).digest()[::-1].hex()


@dataclass(frozen=True, slots=True)
class Witness:
    elements: tuple[bytes, ...] = ()

    @property
    def payload_size(self) -> int:
        return sum(len(element) for element in self.elements)

    @property
    def serialized_size(self) -> int:
        return compact_size_length(len(self.elements)) + sum(
            compact_size_length(len(element)) + len(element)
            for element in self.elements
        )

    def serialize(self) -> bytes:
        result = bytearray(encode_compact_size(len(self.elements)))
        for element in self.elements:
            result.extend(encode_compact_size(len(element)))
            result.extend(element)
        return bytes(result)


@dataclass(frozen=True, slots=True)
class TransactionInput:
    previous_txid_internal: bytes
    previous_output_index: int
    script_sig: bytes
    sequence: int
    witness: Witness = Witness()

    @property
    def previous_txid(self) -> str:
        return self.previous_txid_internal[::-1].hex()

    @property
    def base_serialized_size(self) -> int:
        return 32 + 4 + compact_size_length(len(self.script_sig)) + len(self.script_sig) + 4

    def serialize_base(self) -> bytes:
        return b"".join(
            (
                self.previous_txid_internal,
                self.previous_output_index.to_bytes(4, "little"),
                encode_compact_size(len(self.script_sig)),
                self.script_sig,
                self.sequence.to_bytes(4, "little"),
            )
        )


@dataclass(frozen=True, slots=True)
class TransactionOutput:
    value_sats: int
    script_pubkey: bytes

    @property
    def base_serialized_size(self) -> int:
        return 8 + compact_size_length(len(self.script_pubkey)) + len(self.script_pubkey)

    def serialize(self) -> bytes:
        return b"".join(
            (
                self.value_sats.to_bytes(8, "little", signed=True),
                encode_compact_size(len(self.script_pubkey)),
                self.script_pubkey,
            )
        )


@dataclass(frozen=True, slots=True)
class Transaction:
    version: int
    inputs: tuple[TransactionInput, ...]
    outputs: tuple[TransactionOutput, ...]
    lock_time: int
    has_witness: bool

    @classmethod
    def from_hex(cls, transaction_hex: str, *, allow_witness: bool = True) -> Transaction:
        normalized = transaction_hex.strip()
        if not normalized:
            raise TransactionDecodingError("transaction hex is empty")
        if len(normalized) % 2 != 0:
            raise TransactionDecodingError("transaction hex has an odd number of digits")
        if _HEX_PATTERN.fullmatch(normalized) is None:
            raise TransactionDecodingError("transaction contains non-hexadecimal characters")
        return cls.from_bytes(bytes.fromhex(normalized), allow_witness=allow_witness)

    @classmethod
    def from_bytes(cls, raw: bytes, *, allow_witness: bool = True) -> Transaction:
        reader = ByteReader(raw)
        version = reader.read_uint32(field="version")
        input_count = reader.read_compact_size(field="input count")
        flags = 0

        if input_count == 0 and allow_witness:
            flags = reader.read_uint8(field="transaction optional-data flags")
            if flags != 0:
                if flags & ~1:
                    raise TransactionDecodingError(
                        f"unknown transaction optional-data flag bits: 0x{flags:02x}"
                    )
                input_count = reader.read_compact_size(field="extended input count")
                inputs = cls._read_inputs(reader, input_count)
                output_count = reader.read_compact_size(field="output count")
                outputs = cls._read_outputs(reader, output_count)
            else:
                inputs = ()
                outputs = ()
        else:
            inputs = cls._read_inputs(reader, input_count)
            output_count = reader.read_compact_size(field="output count")
            outputs = cls._read_outputs(reader, output_count)

        has_witness = bool(flags & 1)
        if has_witness:
            witnessed_inputs: list[TransactionInput] = []
            any_witness = False
            for index, transaction_input in enumerate(inputs):
                item_count = reader.read_compact_size(field=f"input {index} witness item count")
                if item_count > reader.remaining:
                    raise TransactionDecodingError(
                        f"input {index} witness item count exceeds remaining serialization"
                    )
                elements = tuple(
                    reader.read(
                        reader.read_compact_size(field=f"input {index} witness item {item_index} length"),
                        field=f"input {index} witness item {item_index}",
                    )
                    for item_index in range(item_count)
                )
                any_witness = any_witness or bool(elements)
                witnessed_inputs.append(
                    TransactionInput(
                        previous_txid_internal=transaction_input.previous_txid_internal,
                        previous_output_index=transaction_input.previous_output_index,
                        script_sig=transaction_input.script_sig,
                        sequence=transaction_input.sequence,
                        witness=Witness(elements),
                    )
                )
            inputs = tuple(witnessed_inputs)
            if not any_witness:
                raise TransactionDecodingError("superfluous witness record with all stacks empty")

        lock_time = reader.read_uint32(field="lock time")
        if reader.remaining != 0:
            raise TransactionDecodingError(
                f"trailing transaction data: {reader.remaining} byte(s)"
            )

        return cls(
            version=version,
            inputs=inputs,
            outputs=outputs,
            lock_time=lock_time,
            has_witness=has_witness,
        )

    @staticmethod
    def _read_inputs(reader: ByteReader, count: int) -> tuple[TransactionInput, ...]:
        if count > reader.remaining // 41:
            raise TransactionDecodingError("input count exceeds remaining serialization")

        result: list[TransactionInput] = []
        for index in range(count):
            previous_txid = reader.read(32, field=f"input {index} previous txid")
            previous_output_index = reader.read_uint32(field=f"input {index} output index")
            script_length = reader.read_compact_size(field=f"input {index} scriptSig length")
            script_sig = reader.read(script_length, field=f"input {index} scriptSig")
            sequence = reader.read_uint32(field=f"input {index} sequence")
            result.append(
                TransactionInput(
                    previous_txid_internal=previous_txid,
                    previous_output_index=previous_output_index,
                    script_sig=script_sig,
                    sequence=sequence,
                )
            )
        return tuple(result)

    @staticmethod
    def _read_outputs(reader: ByteReader, count: int) -> tuple[TransactionOutput, ...]:
        if count > reader.remaining // 9:
            raise TransactionDecodingError("output count exceeds remaining serialization")

        result: list[TransactionOutput] = []
        for index in range(count):
            value_sats = reader.read_int64(field=f"output {index} value")
            script_length = reader.read_compact_size(field=f"output {index} scriptPubKey length")
            script_pubkey = reader.read(script_length, field=f"output {index} scriptPubKey")
            result.append(TransactionOutput(value_sats=value_sats, script_pubkey=script_pubkey))
        return tuple(result)

    def serialize(self, *, include_witness: bool = True) -> bytes:
        use_witness = include_witness and self.has_witness
        result = bytearray(self.version.to_bytes(4, "little"))
        if use_witness:
            result.extend(b"\x00\x01")
        result.extend(encode_compact_size(len(self.inputs)))
        for transaction_input in self.inputs:
            result.extend(transaction_input.serialize_base())
        result.extend(encode_compact_size(len(self.outputs)))
        for output in self.outputs:
            result.extend(output.serialize())
        if use_witness:
            for transaction_input in self.inputs:
                result.extend(transaction_input.witness.serialize())
        result.extend(self.lock_time.to_bytes(4, "little"))
        return bytes(result)

    @property
    def stripped_size(self) -> int:
        return len(self.serialize(include_witness=False))

    @property
    def total_size(self) -> int:
        return len(self.serialize(include_witness=True))

    @property
    def txid(self) -> str:
        return _hash256_display(self.serialize(include_witness=False))

    @property
    def wtxid(self) -> str:
        return _hash256_display(self.serialize(include_witness=True))

