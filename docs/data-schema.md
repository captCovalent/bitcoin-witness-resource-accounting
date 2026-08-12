# Baseline export schema

Schema version: `1`

The JSON export contains transaction-level metrics plus per-input and per-output structure. CSV is a flattened transaction-level projection.

## Transaction fields

| Field | Type | Unit / meaning |
|---|---:|---|
| `schema_version` | integer | Export schema, currently `1` |
| `id` | string or null | Caller-supplied stable identifier |
| `txid` | string | Double-SHA256 of stripped serialization, displayed byte-reversed |
| `wtxid` | string | Double-SHA256 of total serialization, displayed byte-reversed |
| `version` | integer | Serialized transaction version |
| `lock_time` | integer | Serialized lock time |
| `input_count` | integer | Number of transaction inputs |
| `output_count` | integer | Number of transaction outputs |
| `has_witness` | boolean | Whether canonical extended serialization is used |
| `stripped_size` | integer | Bytes |
| `total_size` | integer | Bytes |
| `witness_serialization_size` | integer | Bytes; total minus stripped, including marker/flag |
| `witness_section_size` | integer | Bytes; serialized per-input witness vectors, excluding marker/flag |
| `witness_payload_size` | integer | Bytes; sum of stack-element contents only |
| `bip141_weight` | integer | Weight units |
| `bip141_vsize` | integer | Virtual bytes, rounded up |
| `fee_sats` | integer or null | Caller-supplied fee in satoshis |
| `bip141_feerate_sat_vb` | number or null | `fee_sats / bip141_vsize`; presentation value only |

RPC whole-block collection adds a `source` object containing RPC method and verbosity, stratum, block height/hash/time, and transaction index. These fields establish provenance and do not alter transaction measurements. The associated manifest records the sampling algorithm, seed, strata, acquisition interval, selected block ranks/hashes, transaction count, and SHA256 checksum of the JSONL output.

The structural summary's per-block entries include transaction, witness-transaction, and input counts plus stripped bytes, witness serialization bytes, BIP141 weight, and the block's maximum transaction witness size. The inference output records the sampling-plan hash, stratum inclusion probabilities/design weights, estimated universe totals, finite-population standard errors, and rescaled block-bootstrap intervals.

Adversarial construction schema version 1 records transformation, objective, declared opaque capacity, validity level and limitations, exact parameters, lifecycle stages, transaction identifiers, structural sizes, witness element sizes, BIP141 weight, and weight per opaque byte. `candidate_model` is null in the baseline suite. Transaction hex and opaque element contents are excluded.

## Per-input fields

Each `inputs` entry contains its index, displayed prevout transaction ID, prevout output index, scriptSig size, sequence, base serialized size, and witness metrics. `witness.element_sizes` preserves element boundaries without exporting element contents.

`witness.serialized_size` includes the item-count CompactSize and each item-length CompactSize. It is one byte for an empty vector.

`classification` remains `unknown` without prevout data. With a verified prevout script it may report P2WPKH, P2WSH, P2TR key path, P2TR script path, an unknown witness version, or non-witness/unknown. Structural fields cover witness scripts, tapleaf scripts, tapscripts, control blocks, Merkle depth, leaf version, and annexes where the BIPs locate them objectively. `structure_valid` is a narrow layout check, not full script or signature validation.

## Per-output fields

Each `outputs` entry contains its index, signed 64-bit serialized value, scriptPubKey size, and base serialized size. Output script classification is intentionally deferred.

## Stability

Fields are additive within a schema version. Removing, renaming, changing units, or changing semantics requires a new `schema_version` and migration note.
