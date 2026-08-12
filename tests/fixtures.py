"""Small byte-level fixtures built independently from production serializers."""


def compact_size(value: int) -> bytes:
    if value < 0xFD:
        return bytes((value,))
    if value <= 0xFFFF:
        return b"\xfd" + value.to_bytes(2, "little")
    if value <= 0xFFFFFFFF:
        return b"\xfe" + value.to_bytes(4, "little")
    return b"\xff" + value.to_bytes(8, "little")


def transaction_input(tag: int = 0) -> bytes:
    return bytes((tag,)) * 32 + (tag).to_bytes(4, "little") + b"\x00\xff\xff\xff\xff"


def transaction_output() -> bytes:
    return b"\x00" * 8 + b"\x00"


def witness_vector(elements: tuple[bytes, ...]) -> bytes:
    return compact_size(len(elements)) + b"".join(
        compact_size(len(element)) + element for element in elements
    )


def legacy_one_input_one_output() -> bytes:
    return b"".join(
        (
            b"\x02\x00\x00\x00",
            b"\x01",
            transaction_input(),
            b"\x01",
            transaction_output(),
            b"\x00\x00\x00\x00",
        )
    )


def witness_transaction(witnesses: tuple[tuple[bytes, ...], ...]) -> bytes:
    inputs = b"".join(transaction_input(index) for index in range(len(witnesses)))
    serialized_witnesses = b"".join(witness_vector(elements) for elements in witnesses)
    return b"".join(
        (
            b"\x02\x00\x00\x00",
            b"\x00\x01",
            compact_size(len(witnesses)),
            inputs,
            b"\x01",
            transaction_output(),
            serialized_witnesses,
            b"\x00\x00\x00\x00",
        )
    )


# Signed native-P2WPKH example published in BIP143. It deliberately has one
# legacy input with an empty witness vector and one P2WPKH input.
BIP143_SIGNED_NATIVE_P2WPKH = bytes.fromhex(
    "01000000000102"
    "fff7f7881a8099afa6940d42d1e7f6362bec38171ea3edf433541db4e4ad969f"
    "00000000"
    "49"
    "4830450221008b9d1dc26ba6a9cb62127b02742fa9d754cd3bebf337f7a55d114c8e5cdd30be"
    "022040529b194ba3f9281a99f2b1c0a19c0489bc22ede944ccf4ecbab4cc618ef3ed01"
    "eeffffff"
    "ef51e1b804cc89d182d279655c3aa89e815b1b309fe287d9b2b55d57b90ec68a"
    "01000000"
    "00"
    "ffffffff"
    "02"
    "202cb206000000001976a9148280b37df378db99f66f85c95a783a76ac7a6d5988ac"
    "9093510d000000001976a9143bde42dbee7e4dbe6a21b2d50ce2f0167faa815988ac"
    "00"
    "02"
    "47"
    "304402203609e17b84f6a7d30c80bfa610b5b4542f32a8a0d5447a12fb1366d7f01cc44a"
    "0220573a954c4518331561406f90300e8f3358f51928d43c212a8caed02de67eebee01"
    "21"
    "025476c2e83188368da1ff3e292e7acafcdb3566bb0ad253f62fc70f07aeee6357"
    "11000000"
)

