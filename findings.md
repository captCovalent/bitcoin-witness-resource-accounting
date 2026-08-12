# Findings

Status: baseline phase; no hypothetical model has been evaluated.

## Established baseline facts

1. BIP141 transaction weight is exactly reproducible from canonical stripped and total serialization: `3 * stripped_size + total_size`.
2. The economically discounted portion is not identical to the sum of witness element contents. It also includes marker/flag and CompactSize witness framing.
3. A witness transaction serializes one witness vector for every input, including empty vectors for inputs without witness items.
4. Raw witness shape does not objectively identify the spent output type. Prevout evidence is required before classifying P2WPKH, P2WSH, or P2TR.
5. For an established P2TR prevout, BIP341 permits objective key-path/script-path, tapscript, control-block, and annex measurements.
6. Existing discussions provide concrete reasons to treat large monetary witnesses and future cryptographic proofs as mandatory counterexamples.

## RPC pilot observations

The `wra-rpc-pilot-v1` run completed on 2026-08-12 against Bitcoin Knots 29.3.0. Its three content-neutral height samples contained 7,896 unique transactions and 19,155 inputs. The transaction JSONL checksum matched its manifest, every transaction passed local-versus-node parity for size, virtual size, weight, txid, and wtxid, and no raw transaction hex or witness contents were exported. Prevout-backed classification covered every non-coinbase input; the only three `unknown` inputs were the three coinbases.

This pilot is not statistically representative and evaluates no hypothetical accounting model. It therefore provides no answer to the research hypothesis. It does establish that the acquisition, decoding, BIP141 accounting, prevout classification, provenance, and reproducibility path works on real historical blocks.

One immediate counterexample target is transaction `6d0159a2cbfd1c348251687487ae4d74246b14877ac8f130218ed0c5e9b8884f`: it has 936 prevout-backed P2WPKH inputs and 100,622 bytes of witness serialization, the pilot maximum. Its application purpose is deliberately not inferred. Its structure demonstrates that a transaction-level large-witness threshold could reach high-input monetary-capable transactions and must not be treated as content-specific.

The pilot also contains repeated one-input P2TR script-path transactions with 96,008 bytes of witness serialization, including a 95,901-byte tapscript. These are numeric stress observations only; no payload meaning was inspected. Whether a candidate can price this shape without harming legitimate large scripts remains unanswered.

## Candidate warning already identified

A fixed discounted allowance per input creates an allowance-manufacturing incentive through additional inputs. A transaction-level proportional allowance creates an apparent base-padding incentive. Neither will be implemented as a favored model without a new argument that survives lifecycle-cost analysis.

## Required final answers

No evidence-based answer is available yet for:

1. false-positive impact on ordinary Bitcoin use;
2. effect on neutral large-resource and externally sourced stress cohorts;
3. cheapest adversarial bypass for each model;
4. impact on legitimate advanced protocols;
5. whether any model meaningfully improves on BIP141;
6. whether this research direction should be abandoned.

These questions must remain explicitly unanswered until representative data and adversarial simulations exist.
