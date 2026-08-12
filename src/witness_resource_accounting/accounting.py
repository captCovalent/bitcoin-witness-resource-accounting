"""Baseline BIP141 accounting and stable analysis records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .classification import classify_input
from .transaction import Transaction


SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BIP141Accounting:
    """The control accounting model defined by BIP141."""

    name: str = "bip141"
    version: int = 1

    @staticmethod
    def weight(transaction: Transaction) -> int:
        return transaction.stripped_size * 3 + transaction.total_size

    @classmethod
    def virtual_size(cls, transaction: Transaction) -> int:
        weight = cls.weight(transaction)
        return (weight + 3) // 4


@dataclass(frozen=True, slots=True)
class TransactionAnalysis:
    record: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.record


def analyze_transaction(
    transaction: Transaction,
    *,
    identifier: str | None = None,
    fee_sats: int | None = None,
    prevout_script_pubkeys: Sequence[bytes | None] | None = None,
) -> TransactionAnalysis:
    if fee_sats is not None and fee_sats < 0:
        raise ValueError("fee_sats cannot be negative")
    if prevout_script_pubkeys is not None and len(prevout_script_pubkeys) != len(transaction.inputs):
        raise ValueError("prevout_script_pubkeys must align one-for-one with transaction inputs")

    witness_section_size = sum(
        transaction_input.witness.serialized_size for transaction_input in transaction.inputs
    ) if transaction.has_witness else 0
    witness_payload_size = sum(
        transaction_input.witness.payload_size for transaction_input in transaction.inputs
    ) if transaction.has_witness else 0
    weight = BIP141Accounting.weight(transaction)
    virtual_size = (weight + 3) // 4

    inputs = []
    for index, transaction_input in enumerate(transaction.inputs):
        witness = transaction_input.witness
        prevout_script_pubkey = (
            prevout_script_pubkeys[index] if prevout_script_pubkeys is not None else None
        )
        inputs.append(
            {
                "index": index,
                "previous_txid": transaction_input.previous_txid,
                "previous_output_index": transaction_input.previous_output_index,
                "script_sig_size": len(transaction_input.script_sig),
                "sequence": transaction_input.sequence,
                "base_serialized_size": transaction_input.base_serialized_size,
                "classification": classify_input(transaction_input, prevout_script_pubkey),
                "witness": {
                    "element_count": len(witness.elements),
                    "element_sizes": [len(element) for element in witness.elements],
                    "payload_size": witness.payload_size,
                    "serialized_size": witness.serialized_size if transaction.has_witness else 0,
                },
            }
        )

    outputs = [
        {
            "index": index,
            "value_sats": output.value_sats,
            "script_pubkey_size": len(output.script_pubkey),
            "base_serialized_size": output.base_serialized_size,
        }
        for index, output in enumerate(transaction.outputs)
    ]

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "id": identifier,
        "txid": transaction.txid,
        "wtxid": transaction.wtxid,
        "version": transaction.version,
        "lock_time": transaction.lock_time,
        "input_count": len(transaction.inputs),
        "output_count": len(transaction.outputs),
        "has_witness": transaction.has_witness,
        "stripped_size": transaction.stripped_size,
        "total_size": transaction.total_size,
        "witness_serialization_size": transaction.total_size - transaction.stripped_size,
        "witness_section_size": witness_section_size,
        "witness_payload_size": witness_payload_size,
        "bip141_weight": weight,
        "bip141_vsize": virtual_size,
        "fee_sats": fee_sats,
        "bip141_feerate_sat_vb": (
            fee_sats / virtual_size if fee_sats is not None and virtual_size > 0 else None
        ),
        "inputs": inputs,
        "outputs": outputs,
    }
    return TransactionAnalysis(record)
