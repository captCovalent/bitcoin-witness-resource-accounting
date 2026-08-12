# Adversarial simulation contract

Status: transformation and reporting contract before hypothetical model implementation.

Every candidate accounting model will be evaluated against an adversary who knows the model and restructures transactions to minimize effective cost. The simulator does not generate or classify application content. Its payload is an opaque deterministic byte count placed only where Bitcoin's transaction and witness structures permit.

## Comparison objectives

Every experiment declares one of these objectives:

- **single-spend capacity:** place a declared number of opaque bytes in one valid spend;
- **independently mineable capacity:** place the bytes across transactions that can be mined independently;
- **lifecycle capacity:** include setup outputs, UTXO manufacture, payload-bearing spends, and required cleanup;
- **steady-state capacity:** amortize reusable setup only where consensus and ownership assumptions genuinely allow reuse.

Results from different objectives are never compared as if they measure the same attack cost.

## Required transformations

For each candidate, search at least:

1. input splitting inside a transaction;
2. transaction splitting and rebatching;
3. stripped-data padding, including added inputs and outputs;
4. UTXO manufacturing with explicit setup weight and fees;
5. witness-element splitting across CompactSize boundaries;
6. equivalent script restructuring where validity permits;
7. movement among arguments, witness scripts, tapscripts, annexes, and other available witness structures;
8. mixed favored/disfavored input types;
9. batching versus unbatching of monetary outputs;
10. boundary searches around every discontinuity in the model.

## Invariants and constraints

Each simulated transformation records:

- validity domain: serialization-only, consensus-valid, standard-policy-valid, or empirically relayed;
- opaque byte capacity achieved;
- setup, payload, and cleanup transactions separately;
- BIP141 weight and candidate weight for every transaction;
- input/output value conservation and assumed fee funding;
- number and type of prerequisite UTXOs;
- signature, script, hash/preimage, control-block, and timelock constraints;
- whether transactions are independently mineable or package-dependent;
- assumptions about key ownership, cooperation, and reusable state.

Serialization-only constructions cannot be presented as deployable bypasses. Conversely, policy-nonstandard but consensus-valid constructions remain relevant to miner-direct and consensus-level economic claims and must be labeled accurately.

## Minimization target

The primary adversarial score is total effective weight per achieved opaque byte over the declared objective. Secondary scores include transaction count, BIP141 weight, setup UTXO count, latency/dependency depth, and fee at specified feerates. Search output must include the cheapest discovered construction and enough parameters to reproduce it.

The simulator must also optimize protected monetary templates. A transformation that lowers the cost for a stress construction may lower or raise costs for payment batching, multisig, or Lightning failure paths; both sides are reported.

## Candidate rejection

A model is rejected or materially weakened when any of these hold:

- its cheapest bypass approaches BIP141 pricing after realistic setup amortization;
- it creates unbounded allowance through inputs, outputs, transactions, or padding;
- it moves the cheapest encoding into a structure with worse validation, relay, UTXO, or future-compatibility consequences;
- protected monetary or security-critical paths suffer comparable penalties;
- its claimed resource proxy has no reproducible relationship to node cost;
- its result depends on semantic selection or a hand-picked dataset.

Failure is a valid result. No simulator parameter is an activation recommendation or consensus proposal.

## Version 1 implementation status

The initial engine generates canonical serialization-only constructions for input splitting, transaction splitting, batching/unbatching, witness-element splitting, stripped-output padding, UTXO manufacture plus spend, and witness-structure movement. It reports exact BIP141 stage/lifecycle weight and weight per achieved opaque byte. Dummy outpoints, values, scripts, commitments, and signatures prevent any stronger validity claim. Promotion to `consensus_valid` or `standard_policy_valid` requires executable regtest fixtures and node verification, not a label change.
