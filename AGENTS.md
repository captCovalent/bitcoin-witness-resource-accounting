# Research agent guide

## Mission

Investigate content-neutral Bitcoin witness and validation-resource accounting. The goal is to falsify or validate candidate accounting models, not to justify a predetermined policy.

## Hard constraints

1. Never inspect, decode, label, hash-match, or classify the semantic meaning of transaction payload bytes.
2. Measure only serialized protocol structures, objective spend conditions, validation-relevant structure, and resource usage.
3. Do not use terms such as "JPEG detector", "inscription detector", "spam classifier", or equivalent as an implementation goal.
4. Do not introduce consensus changes, activation thresholds, proof-of-work changes, or transaction-content bans.
5. Do not implement a hypothetical accounting model until its formula, threat model, invariants, and falsification tests are documented.
6. Treat adversarial restructuring as the default case. Test input splitting, transaction splitting, stripped-data padding, UTXO manufacturing, witness-element splitting, script restructuring, and movement among witness structures.
7. Protect existing and plausible future monetary protocols. Include ordinary payments, multisig, Lightning, collaborative transactions, script-path protocols, recovery paths, and large cryptographic proofs in false-positive analysis.
8. Report counterexamples and negative results prominently. Never hide an attack because it weakens the preferred model.
9. Keep policy, consensus, and measurement claims explicitly separated.
10. Cite primary sources for protocol and Bitcoin Core behavior. Secondary sources may help discovery but are not authoritative.

## Classification rules

- A spending type may be identified only from the spent output's `scriptPubKey`, the spending input, and the applicable BIP rules.
- Witness shape alone is not enough to identify P2WPKH, P2WSH, or P2TR.
- Taproot key-path versus script-path classification requires a confirmed P2TR prevout and BIP341 witness parsing, including optional-annex removal.
- CoinJoin and Lightning labels are research strata, not consensus facts. Record the provenance and confidence of any external label; keep unclassified transactions in the main sample.
- A curated "known data" cohort may contain externally published transaction identifiers and provenance, but this software must not inspect or reproduce semantic payloads. Call it an externally sourced stress cohort, not a classifier ground truth.

## Engineering rules

- Python 3.11+; standard library only in the baseline phase.
- Use integer byte, weight-unit, virtual-byte, and satoshi values. Do not use floating point for consensus-size arithmetic.
- Preserve canonical CompactSize rules and reject malformed or trailing serialization.
- Keep raw transaction parsing independent from Bitcoin Core RPC transport.
- Keep model calculations pure and deterministic.
- Version all exported schemas.
- Never log RPC credentials, cookie contents, or full raw witness payloads.
- Unit tests must be offline, deterministic, and runnable with `make test`.
- Node-backed tests must be opt-in and must compare baseline fields against Bitcoin Core RPC results.
- Generated datasets and results need a manifest containing tool revision, Core version, chain, block range, sampling seed, RPC options, and UTC timestamp.

## Review checklist

Before merging an accounting model, answer:

- What protocol resource is the model claiming to proxy?
- Does the model depend on byte meaning, recognizers, or application conventions?
- Can adding inputs create discounted capacity?
- Can base padding reduce the marginal price of witness bytes?
- Can splitting elements, scripts, inputs, or transactions reduce total charge?
- Can payload move to another discounted structure?
- What is the cheapest UTXO-manufacturing path including setup transactions?
- What ordinary or advanced monetary transaction is the worst false positive found so far?
- Is the result policy-deployable without changing consensus validity?
- Is BIP141 still better after including bypass setup cost and legitimate-use impact?

