"""Model-free synthetic transaction transformations under BIP141 accounting."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable, Sequence

from .accounting import BIP141Accounting
from .transaction import Transaction, TransactionInput, TransactionOutput, Witness


CONSTRUCTION_SCHEMA_VERSION = 1
VALIDITY_SERIALIZATION_ONLY = "serialization_only"


def _opaque_bytes(size: int, *, domain: str) -> bytes:
    if size < 0:
        raise ValueError("opaque byte size cannot be negative")
    result = bytearray()
    counter = 0
    while len(result) < size:
        result.extend(sha256(f"wra-opaque-v1\n{domain}\n{counter}\n".encode()).digest())
        counter += 1
    return bytes(result[:size])


def _partition(total: int, parts: int) -> tuple[int, ...]:
    if total < 0:
        raise ValueError("partition total cannot be negative")
    if parts < 1:
        raise ValueError("partition parts must be positive")
    quotient, remainder = divmod(total, parts)
    return tuple(quotient + (index < remainder) for index in range(parts))


def _outpoint(domain: str, index: int) -> bytes:
    return sha256(f"wra-outpoint-v1\n{domain}\n{index}\n".encode()).digest()


def _output_script(domain: str) -> bytes:
    return b"\x00\x14" + sha256(f"wra-output-v1\n{domain}\n".encode()).digest()[:20]


def _input(domain: str, index: int, witness_elements: Sequence[bytes]) -> TransactionInput:
    return TransactionInput(
        previous_txid_internal=_outpoint(domain, index),
        previous_output_index=index,
        script_sig=b"",
        sequence=0xFFFFFFFD,
        witness=Witness(tuple(witness_elements)),
    )


def _transaction(
    *,
    domain: str,
    witnesses: Sequence[Sequence[bytes]],
    output_count: int = 1,
    extra_outputs: Sequence[TransactionOutput] = (),
) -> Transaction:
    if output_count < 1:
        raise ValueError("output_count must be positive")
    transaction = Transaction(
        version=2,
        inputs=tuple(_input(domain, index, elements) for index, elements in enumerate(witnesses)),
        outputs=tuple(
            TransactionOutput(value_sats=100_000, script_pubkey=_output_script(f"{domain}-{index}"))
            for index in range(output_count)
        )
        + tuple(extra_outputs),
        lock_time=0,
        has_witness=True,
    )
    # Fail closed if a builder ever emits a serialization our parser does not reproduce.
    if Transaction.from_bytes(transaction.serialize()) != transaction:
        raise AssertionError("synthetic transaction failed canonical round trip")
    return transaction


@dataclass(frozen=True, slots=True)
class ConstructionStage:
    name: str
    transactions: tuple[Transaction, ...]


@dataclass(frozen=True, slots=True)
class Construction:
    transformation: str
    objective: str
    opaque_bytes: int
    parameters: dict[str, int | str]
    stages: tuple[ConstructionStage, ...]
    validity_level: str = VALIDITY_SERIALIZATION_ONLY
    validity_limitations: str = (
        "Canonical serialization only; dummy outpoints, values, commitments, scripts, and signatures "
        "are not evidence of consensus validity or standard relay."
    )

    def __post_init__(self) -> None:
        if self.opaque_bytes < 0:
            raise ValueError("opaque_bytes cannot be negative")
        if not self.stages or any(not stage.transactions for stage in self.stages):
            raise ValueError("construction stages must contain transactions")

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(transaction for stage in self.stages for transaction in stage.transactions)

    @property
    def total_bip141_weight(self) -> int:
        return sum(BIP141Accounting.weight(transaction) for transaction in self.transactions)

    def to_record(self) -> dict[str, Any]:
        stage_records = []
        for stage in self.stages:
            transaction_records = []
            for index, transaction in enumerate(stage.transactions):
                weight = BIP141Accounting.weight(transaction)
                transaction_records.append(
                    {
                        "index": index,
                        "txid": transaction.txid,
                        "wtxid": transaction.wtxid,
                        "input_count": len(transaction.inputs),
                        "output_count": len(transaction.outputs),
                        "stripped_size": transaction.stripped_size,
                        "total_size": transaction.total_size,
                        "witness_serialization_size": (
                            transaction.total_size - transaction.stripped_size
                        ),
                        "witness_payload_size": sum(
                            transaction_input.witness.payload_size
                            for transaction_input in transaction.inputs
                        ),
                        "witness_element_sizes_by_input": [
                            [len(element) for element in transaction_input.witness.elements]
                            for transaction_input in transaction.inputs
                        ],
                        "bip141_weight": weight,
                        "bip141_vsize": (weight + 3) // 4,
                    }
                )
            stage_records.append(
                {
                    "name": stage.name,
                    "transaction_count": len(stage.transactions),
                    "bip141_weight": sum(
                        BIP141Accounting.weight(transaction) for transaction in stage.transactions
                    ),
                    "transactions": transaction_records,
                }
            )
        total_weight = self.total_bip141_weight
        return {
            "construction_schema_version": CONSTRUCTION_SCHEMA_VERSION,
            "candidate_model": None,
            "transformation": self.transformation,
            "objective": self.objective,
            "opaque_bytes": self.opaque_bytes,
            "parameters": dict(sorted(self.parameters.items())),
            "validity_level": self.validity_level,
            "validity_limitations": self.validity_limitations,
            "transaction_count": len(self.transactions),
            "total_stripped_size": sum(tx.stripped_size for tx in self.transactions),
            "total_size": sum(tx.total_size for tx in self.transactions),
            "total_witness_serialization_size": sum(
                tx.total_size - tx.stripped_size for tx in self.transactions
            ),
            "total_bip141_weight": total_weight,
            "bip141_weight_per_opaque_byte": (
                total_weight / self.opaque_bytes if self.opaque_bytes else None
            ),
            "stages": stage_records,
        }


def input_splitting(
    opaque_size: int,
    input_count: int,
    *,
    output_count: int = 1,
) -> Construction:
    sizes = _partition(opaque_size, input_count)
    witnesses = [
        (_opaque_bytes(size, domain=f"input-splitting-{opaque_size}-{input_count}-{index}"),)
        for index, size in enumerate(sizes)
    ]
    transaction = _transaction(
        domain=f"input-splitting-{opaque_size}-{input_count}-{output_count}",
        witnesses=witnesses,
        output_count=output_count,
    )
    return Construction(
        "input_splitting",
        "single_spend_capacity",
        opaque_size,
        {"input_count": input_count, "output_count": output_count},
        (ConstructionStage("payload_spend", (transaction,)),),
    )


def transaction_splitting(
    opaque_size: int,
    transaction_count: int,
    *,
    output_count_per_transaction: int = 1,
) -> Construction:
    sizes = _partition(opaque_size, transaction_count)
    transactions = tuple(
        _transaction(
            domain=f"transaction-splitting-{opaque_size}-{transaction_count}-{index}",
            witnesses=((_opaque_bytes(size, domain=f"transaction-split-{index}-{size}"),),),
            output_count=output_count_per_transaction,
        )
        for index, size in enumerate(sizes)
    )
    return Construction(
        "transaction_splitting",
        "independently_mineable_capacity",
        opaque_size,
        {
            "transaction_count": transaction_count,
            "output_count_per_transaction": output_count_per_transaction,
        },
        (ConstructionStage("payload_spends", transactions),),
    )


def batching_unbatching(
    opaque_size: int,
    total_output_count: int,
    transaction_count: int,
) -> Construction:
    if total_output_count < 1:
        raise ValueError("total_output_count must be positive")
    if transaction_count < 1 or transaction_count > total_output_count:
        raise ValueError("transaction_count must be between one and total_output_count")
    payload_sizes = _partition(opaque_size, transaction_count)
    output_counts = _partition(total_output_count, transaction_count)
    transactions = tuple(
        _transaction(
            domain=(
                f"batching-{opaque_size}-{total_output_count}-{transaction_count}-{index}"
            ),
            witnesses=((_opaque_bytes(size, domain=f"batching-payload-{index}-{size}"),),),
            output_count=output_counts[index],
        )
        for index, size in enumerate(payload_sizes)
    )
    return Construction(
        "batching_unbatching",
        (
            "single_spend_capacity"
            if transaction_count == 1
            else "independently_mineable_capacity"
        ),
        opaque_size,
        {
            "total_output_count": total_output_count,
            "transaction_count": transaction_count,
        },
        (ConstructionStage("payload_spends", transactions),),
    )


def witness_element_splitting(opaque_size: int, element_count: int) -> Construction:
    sizes = _partition(opaque_size, element_count)
    elements = tuple(
        _opaque_bytes(size, domain=f"element-splitting-{opaque_size}-{element_count}-{index}")
        for index, size in enumerate(sizes)
    )
    transaction = _transaction(
        domain=f"element-splitting-{opaque_size}-{element_count}",
        witnesses=(elements,),
    )
    return Construction(
        "witness_element_splitting",
        "single_spend_capacity",
        opaque_size,
        {"element_count": element_count},
        (ConstructionStage("payload_spend", (transaction,)),),
    )


def stripped_output_padding(opaque_size: int, padding_bytes: int) -> Construction:
    if padding_bytes < 0:
        raise ValueError("padding_bytes cannot be negative")
    padding_output = TransactionOutput(
        value_sats=0,
        script_pubkey=_opaque_bytes(padding_bytes, domain=f"stripped-padding-{padding_bytes}"),
    )
    transaction = _transaction(
        domain=f"stripped-padding-{opaque_size}-{padding_bytes}",
        witnesses=((_opaque_bytes(opaque_size, domain=f"stripped-padding-payload-{opaque_size}"),),),
        extra_outputs=(padding_output,),
    )
    return Construction(
        "stripped_output_padding",
        "single_spend_capacity",
        opaque_size,
        {"padding_script_bytes": padding_bytes},
        (ConstructionStage("payload_spend", (transaction,)),),
    )


def utxo_manufacturing(opaque_size: int, manufactured_utxos: int) -> Construction:
    if manufactured_utxos < 1:
        raise ValueError("manufactured_utxos must be positive")
    setup = Transaction(
        version=2,
        inputs=(_input(f"utxo-setup-{manufactured_utxos}", 0, ()),),
        outputs=tuple(
            TransactionOutput(
                value_sats=100_000,
                script_pubkey=b"\x00\x20"
                + sha256(f"utxo-script-{manufactured_utxos}-{index}".encode()).digest(),
            )
            for index in range(manufactured_utxos)
        ),
        lock_time=0,
        has_witness=False,
    )
    if Transaction.from_bytes(setup.serialize()) != setup:
        raise AssertionError("setup transaction failed canonical round trip")
    sizes = _partition(opaque_size, manufactured_utxos)
    spend_inputs = tuple(
        TransactionInput(
            previous_txid_internal=bytes.fromhex(setup.txid)[::-1],
            previous_output_index=index,
            script_sig=b"",
            sequence=0xFFFFFFFD,
            witness=Witness(
                (_opaque_bytes(size, domain=f"utxo-payload-{manufactured_utxos}-{index}"),)
            ),
        )
        for index, size in enumerate(sizes)
    )
    spend = Transaction(
        version=2,
        inputs=spend_inputs,
        outputs=(TransactionOutput(value_sats=100_000, script_pubkey=_output_script("utxo-spend")),),
        lock_time=0,
        has_witness=True,
    )
    if Transaction.from_bytes(spend.serialize()) != spend:
        raise AssertionError("manufactured UTXO spend failed canonical round trip")
    return Construction(
        "utxo_manufacturing",
        "lifecycle_capacity",
        opaque_size,
        {"manufactured_utxos": manufactured_utxos},
        (
            ConstructionStage("setup", (setup,)),
            ConstructionStage("payload_spend", (spend,)),
        ),
    )


def witness_structure_movement(opaque_size: int, structure: str) -> Construction:
    payload = _opaque_bytes(opaque_size, domain=f"structure-{structure}-{opaque_size}")
    if structure == "argument":
        elements = (payload, b"\x51")
    elif structure == "witness_script":
        elements = (b"", payload)
    elif structure == "tapscript":
        elements = (b"\x00" * 64, payload, b"\xc0" + b"\x00" * 32)
    elif structure == "annex":
        elements = (b"\x00" * 64, b"\x50" + payload)
    else:
        raise ValueError("structure must be argument, witness_script, tapscript, or annex")
    transaction = _transaction(
        domain=f"structure-{structure}-{opaque_size}",
        witnesses=(elements,),
    )
    return Construction(
        "witness_structure_movement",
        "single_spend_capacity",
        opaque_size,
        {"structure": structure},
        (ConstructionStage("payload_spend", (transaction,)),),
    )


def boundary_suite(
    *,
    opaque_sizes: Iterable[int],
    split_counts: Iterable[int],
    padding_sizes: Iterable[int],
) -> list[Construction]:
    results: list[Construction] = []
    normalized_splits = tuple(dict.fromkeys(split_counts))
    normalized_padding = tuple(dict.fromkeys(padding_sizes))
    for opaque_size in dict.fromkeys(opaque_sizes):
        for count in normalized_splits:
            results.append(input_splitting(opaque_size, count))
            results.append(transaction_splitting(opaque_size, count))
            results.append(batching_unbatching(opaque_size, max(normalized_splits), count))
            results.append(witness_element_splitting(opaque_size, count))
            results.append(utxo_manufacturing(opaque_size, count))
        for padding_size in normalized_padding:
            results.append(stripped_output_padding(opaque_size, padding_size))
        for structure in ("argument", "witness_script", "tapscript", "annex"):
            results.append(witness_structure_movement(opaque_size, structure))
    return results
