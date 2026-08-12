"""Objective spend-structure classification using verified prevout scripts."""

from __future__ import annotations

from hashlib import new as new_hash
from hashlib import sha256
from typing import Any

from .transaction import TransactionInput


def _hash160(data: bytes) -> bytes:
    return new_hash("ripemd160", sha256(data).digest()).digest()


def _witness_program(script: bytes) -> tuple[int, bytes] | None:
    if len(script) < 4:
        return None
    opcode = script[0]
    if opcode == 0x00:
        version = 0
    elif 0x51 <= opcode <= 0x60:
        version = opcode - 0x50
    else:
        return None
    program_length = script[1]
    if not 2 <= program_length <= 40 or len(script) != program_length + 2:
        return None
    return version, script[2:]


def _p2sh_redeem_witness_program(
    script_sig: bytes,
    prevout_script_pubkey: bytes,
) -> tuple[int, bytes] | None:
    if (
        len(prevout_script_pubkey) != 23
        or prevout_script_pubkey[0] != 0xA9
        or prevout_script_pubkey[1] != 0x14
        or prevout_script_pubkey[-1] != 0x87
        or len(script_sig) not in (23, 35)
        or script_sig[0] != len(script_sig) - 1
    ):
        return None
    redeem_script = script_sig[1:]
    if _hash160(redeem_script) != prevout_script_pubkey[2:22]:
        return None
    return _witness_program(redeem_script)


def _base_classification() -> dict[str, Any]:
    return {
        "spend_type": "unknown",
        "classification_evidence": None,
        "witness_program_wrapping": None,
        "structure_valid": None,
        "witness_script_size": None,
        "tapleaf_script_size": None,
        "tapscript_size": None,
        "control_block_size": None,
        "control_block_merkle_depth": None,
        "tapleaf_version": None,
        "annex_size": None,
    }


def classify_input(
    transaction_input: TransactionInput,
    prevout_script_pubkey: bytes | None,
) -> dict[str, Any]:
    """Classify only when prevout evidence makes the spend type objective."""

    result = _base_classification()
    if prevout_script_pubkey is None:
        return result

    result["classification_evidence"] = "prevout_script_pubkey"
    program = _witness_program(prevout_script_pubkey)
    wrapping = "native"
    script_sig_valid = len(transaction_input.script_sig) == 0
    if program is None:
        program = _p2sh_redeem_witness_program(
            transaction_input.script_sig,
            prevout_script_pubkey,
        )
        if program is None:
            result["spend_type"] = "non_witness_or_unknown"
            return result
        wrapping = "p2sh"
        script_sig_valid = True

    version, witness_program = program
    result["witness_program_wrapping"] = wrapping
    witness = transaction_input.witness.elements

    if version == 0 and len(witness_program) == 20:
        result["spend_type"] = "p2wpkh"
        result["structure_valid"] = script_sig_valid and len(witness) == 2
        return result

    if version == 0 and len(witness_program) == 32:
        result["spend_type"] = "p2wsh"
        result["structure_valid"] = script_sig_valid and len(witness) >= 1
        if witness:
            result["witness_script_size"] = len(witness[-1])
        return result

    if version == 1 and len(witness_program) == 32 and wrapping == "native":
        remaining = list(witness)
        if len(remaining) >= 2 and remaining[-1][:1] == b"\x50":
            result["annex_size"] = len(remaining.pop())

        if len(remaining) == 1:
            result["spend_type"] = "p2tr_key_path"
            result["structure_valid"] = script_sig_valid
            return result

        if len(remaining) >= 2:
            script = remaining[-2]
            control_block = remaining[-1]
            control_size = len(control_block)
            valid_control_size = (
                control_size >= 33
                and (control_size - 33) % 32 == 0
                and (control_size - 33) // 32 <= 128
            )
            leaf_version = control_block[0] & 0xFE if control_block else None
            result.update(
                {
                    "spend_type": "p2tr_script_path",
                    "structure_valid": script_sig_valid and valid_control_size,
                    "tapleaf_script_size": len(script),
                    "tapscript_size": len(script) if leaf_version == 0xC0 else None,
                    "control_block_size": control_size,
                    "control_block_merkle_depth": (
                        (control_size - 33) // 32 if valid_control_size else None
                    ),
                    "tapleaf_version": leaf_version,
                }
            )
            return result

        result["spend_type"] = "p2tr_invalid_structure"
        result["structure_valid"] = False
        return result

    result["spend_type"] = "witness_unknown"
    result["structure_valid"] = script_sig_valid
    return result

