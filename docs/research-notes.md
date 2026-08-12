# Primary-source research notes

Status: initial review, 2026-08-11. This is a starting bibliography, not a claim of exhaustive literature coverage.

Source snapshot: Bitcoin Core [`5d051c05629df6457047aa4315476105dcb27e08`](https://github.com/bitcoin/bitcoin/commit/5d051c05629df6457047aa4315476105dcb27e08) and the BIPs repository [`c38071c8c45a1fc50cecaac0d82d99e3bbd56911`](https://github.com/bitcoin/bips/commit/c38071c8c45a1fc50cecaac0d82d99e3bbd56911). Forum and mailing-list links were accessed on 2026-08-11.

## BIP141 baseline

[BIP141](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0141.mediawiki) defines base size as serialization with witness stripped, total size as serialization including witness, transaction weight as `base_size * 3 + total_size`, and virtual size as weight divided by four and rounded up. It also specifies that every input has a serialized witness field in a witness transaction, including a zero-item vector for a non-witness input.

[BIP144](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0144.mediawiki) defines peer transaction serialization using marker `0x00`, flag `0x01`, and per-input witness vectors. The baseline counts marker/flag and CompactSize framing because Bitcoin Core's total-versus-stripped serialization counts them.

Bitcoin Core's [`GetTransactionWeight`](https://github.com/bitcoin/bitcoin/blob/5d051c05629df6457047aa4315476105dcb27e08/src/consensus/validation.h) implements the equivalent formula `stripped_size * (WITNESS_SCALE_FACTOR - 1) + total_size`. Core's [`GetVirtualTransactionSize`](https://github.com/bitcoin/bitcoin/blob/5d051c05629df6457047aa4315476105dcb27e08/src/policy/policy.cpp) rounds adjusted weight upward by the witness scale factor; sigop-adjusted vsize is a policy concept distinct from raw BIP141 transaction vsize and must be labeled when used.

Core's [`transaction.h`](https://github.com/bitcoin/bitcoin/blob/5d051c05629df6457047aa4315476105dcb27e08/src/primitives/transaction.h) is the serialization reference: only flag bit 0 is currently understood, all input witness vectors are serialized, unknown flags fail, and an extended transaction with all-empty witnesses is rejected as a superfluous witness record. The baseline mirrors these behaviors and rejects non-canonical CompactSize encodings and trailing bytes.

Current policy constants are separate from consensus accounting. At the time of review, [`policy.h`](https://github.com/bitcoin/bitcoin/blob/5d051c05629df6457047aa4315476105dcb27e08/src/policy/policy.h) defines `MAX_STANDARD_TX_WEIGHT = 400000` WU and distinct P2WSH/tapscript stack and script limits. These values describe default relay/mining policy, not BIP141 validity.

Bitcoin Core's [`decoderawtransaction`](https://bitcoincore.org/en/doc/30.0.0/rpc/rawtransactions/decoderawtransaction/) and [`getrawtransaction`](https://bitcoincore.org/en/doc/30.0.0/rpc/rawtransactions/getrawtransaction/) expose total size, vsize, weight, witness elements, and—at verbosity 2—prevout information and fee. They will be the differential oracle for node-backed integration tests.

## Objective witness structure

[BIP141](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0141.mediawiki) defines P2WPKH and P2WSH from the spent witness program, not from witness-stack shape. P2WPKH uses a version-0 20-byte program and exactly two witness items. P2WSH uses a version-0 32-byte program and treats the last witness item as the witness script.

[BIP341](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0341.mediawiki) defines P2TR as a version-1 32-byte witness program. After optional annex removal, one remaining witness item is key path; two or more are script path, with the second-to-last item as script and the last as a control block of length `33 + 32m`, `0 <= m <= 128`. This makes tapscript and control-block sizes structurally measurable, but only after the prevout establishes P2TR.

[BIP342](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0342.mediawiki) defines tapscript validation and its resource rules. Later work must keep raw byte accounting separate from execution cost, signature-operation cost, and validation budget.

## BIP110 contrast

[BIP110](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0110.md), "Reduced Data Temporary Softfork," is currently closed. Its specification proposes temporary consensus restrictions including size limits for scriptPubKeys, pushes, script-argument witness items, Taproot control blocks, and restrictions on annexes, undefined witness/tapleaf versions, OP_SUCCESS opcodes, and executed `OP_IF`/`OP_NOTIF`, with grandfathering for earlier UTXOs.

This project studies a different question. It does not evaluate payload meaning, propose invalidity rules, or inherit BIP110's deployment design. BIP110 remains relevant as a concrete list of structures and monetary-protocol compatibility claims that a neutral accounting approach must test rather than assume.

## Weight, standardness, and non-confiscation discussions

Vojtěch Strnad's [Non-confiscatory Transaction Weight Limit](https://delvingbitcoin.org/t/non-confiscatory-transaction-weight-limit/1732) examines a consensus transaction-weight limit with exceptions intended to avoid making large spends impossible. The discussion highlights large ordinary transactions, BitVM-style protocols, block-template optimization, coinbase escape routes, MEV, and height-based grandfathering. It is not an alternative witness-pricing formula, but its counterexamples and non-confiscation framing are directly relevant.

The 2025 Bitcoin-Dev thread [Relax OP_RETURN standardness restrictions](https://groups.google.com/g/bitcoindev/c/d6ZO7gXGYbQ) contains primary arguments about policy versus consensus, the incentive to place data in discounted/prunable witness rather than outputs, the ineffectiveness of semantic filters against adversarial encoding, and why removing the discount interacts with block capacity and potentially confiscatory limits. Claims in that thread are positions to test, not settled findings.

The earlier [dynamic block-size-limit draft](https://github.com/luke-jr/bips/blob/bip-blksize/bip-blksize.mediawiki) combined weight with an additional byte ceiling. It is relevant as prior dual-resource accounting, but it changes consensus capacity and therefore lies outside the current implementation scope.

The 2025 Bitcoin-Dev [segOP proposal thread](https://groups.google.com/g/bitcoindev/c/uhnM_EC0AQA) proposes a structured, full-weight data lane. It relies on distinguishing a new data structure and a consensus extension, so it does not satisfy this project's present constraints. Its fee-fairness assertions require independent empirical support.

No primary source for the exact fixed per-input bounded-discount formula supplied in this project's initial hypothesis has yet been identified. Until one is found, the idea is documented as an internally analyzed candidate rather than attributed to prior art. Literature search terms, repositories, and negative search results should be preserved when this review is expanded.

## Current witness-costing pressure

The 2026 Delving discussion [Defining `0x50 0x00` as unstructured taproot annex data](https://delvingbitcoin.org/t/defining-0x50-0x00-as-unstructured-taproot-annex-data/2620) explicitly notes the economic incentive created by lower witness weight and raises multiparty witness-inflation concerns. It also reinforces that annex bytes are signed, counted in transaction weight, and otherwise ignored by current Taproot validation.

The 2026 draft [Witness Version 3: ML-DSA-65 Post-Quantum Key-Path Spending](https://delvingbitcoin.org/t/bip-draft-witness-version-3-ml-dsa-65-post-quantum-key-path-spending/2422) illustrates why large witnesses cannot be presumed non-monetary: proposed post-quantum public keys and signatures are measured in kilobytes and have different validation costs. Any progressive or structural model must include such future-facing counterexamples.

The Bitcoin-Dev discussion [Aligning privacy incentives in P2MR](https://groups.google.com/g/bitcoindev/c/p8AVEmAtWdA) discusses possible additional witness discounts for elliptic-curve spends in a post-quantum-capable construction. This is evidence that witness pricing affects upgrade and privacy incentives, not evidence for a particular factor.

## Sampling and uncertainty

[Rao and Wu (1988)](https://doi.org/10.1080/01621459.1988.10478591) introduce resampling inference for complex survey designs and require rescaling so bootstrap variance reduces to the standard variance estimator for linear statistics. [Rao, Wu, and Yue (1992)](https://www150.statcan.gc.ca/n1/en/catalogue/12-001-X199200214486) review the extension and empirical behavior for stratified simple random sampling and non-smooth statistics. These sources support resampling primary sampling units within strata rather than treating transactions nested inside one selected block as independent.

The project's reference estimator uses exact stratified SRSWOR linearization variance with the finite-population correction as the primary uncertainty calculation. Its deterministic `n_h - 1` rescaled block bootstrap provides companion equal-tailed percentile intervals for totals and ratios. It does not claim a studentized bootstrap interval or general multistage-survey implementation.

## Open literature tasks before models

- Trace the complete history of bounded or capped witness-discount proposals, including mailing-list posts, PRs, and unpublished drafts.
- Separate proposals that change the 4 MWU consensus capacity from policy-only effective-feerate proposals.
- Review historical rationale for the 4:1 scale factor and quantify which resource ratios it was intended to approximate.
- Review Core's present block-relay, validation, UTXO, sigop, and script-cost bottlenecks before claiming that byte weight is "accurate" resource pricing.
- Collect primary protocol documents and real transaction manifests for Lightning, collaborative transactions, BitVM-style constructions, vaults, DLCs, and post-quantum proposals.
- Define a principled treatment of fees and miner selection when hypothetical effective weight differs from consensus weight but block capacity does not.
