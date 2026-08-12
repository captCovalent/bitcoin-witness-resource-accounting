# Methodology

Status: baseline design, 2026-08-11. Hypothetical model parameters are intentionally absent.

## 1. Research question

Can a deterministic, content-neutral transaction resource-accounting function improve the economic pricing of unusually large witness/resource consumption relative to BIP141 while preserving ordinary and advanced monetary use and remaining robust to adversarial transaction restructuring?

"Improve" is not defined as merely assigning more weight to a hand-selected transaction. A candidate must simultaneously:

1. create a material cost difference for a broad, independently selected resource-heavy cohort;
2. keep false-positive cost changes acceptably small across ordinary and advanced monetary cohorts;
3. resist topology and encoding transformations that preserve an attacker's objective;
4. correspond to a stated node resource rather than content meaning;
5. remain expressible as policy without changing transaction or block consensus validity in the prototype phase.

If no candidate satisfies these conditions, the project should recommend abandoning this direction.

## 2. Baseline definitions

For a transaction `tx`:

- `stripped_size(tx)` is the canonical serialization size without witness data.
- `total_size(tx)` is the canonical serialization size with witness data.
- `witness_serialization_size(tx) = total_size(tx) - stripped_size(tx)`.
- `weight_141(tx) = 3 * stripped_size(tx) + total_size(tx)`.
- `vsize_141(tx) = ceil(weight_141(tx) / 4)`.

For witness transactions, witness serialization size includes marker, flag, each input's witness item count, and every item-length CompactSize prefix. Payload size excludes those framing bytes. Both are reported.

BIP141 is the control model. All comparisons report both absolute and percentage deltas against it.

## 3. Content neutrality

The analyzer must not parse application envelopes, MIME types, text, image signatures, ordinals numbering, token protocols, or content hashes. Candidate models may use only fields whose meaning is defined by Bitcoin serialization or consensus/policy rules, such as:

- stripped bytes and witness bytes;
- input/output counts;
- witness stack element boundaries and lengths;
- spent output script type, when the prevout is available;
- witness version;
- objectively located witness script, tapscript, control block, or annex under the relevant BIP;
- measured or reproducibly benchmarked validation/relay/storage resources.

An externally sourced stress-case cohort may be selected using published transaction identifiers. Its label records selection provenance only. Payload contents are neither inspected nor exported.

## 4. Objective spend classification

Raw spending transactions do not serialize their prevout `scriptPubKey` or value. Therefore:

- P2WPKH and P2WSH require the spent output or equivalent verified prevout data.
- P2TR requires a version-1, 32-byte witness program in the spent output.
- Once P2TR is established, remove an optional final annex as specified by BIP341. One remaining item indicates key path; two or more indicate script path. For script path, the second-to-last item is the script and the last is the control block.
- Shape-only guesses are prohibited. Unknown prevouts remain `unknown`.

RPC verbosity 2, block data, or an independently verified UTXO/transaction source may provide prevouts. The source and Core version must be recorded.

## 5. Cohorts

The evaluation dataset will contain disjoint or explicitly overlapping strata:

1. Uniform or reproducibly pseudorandom historical block samples across multiple eras.
2. Ordinary payments, stratified by confirmed prevout/output types.
3. P2WPKH, P2WSH, P2TR key-path, and P2TR script-path spends.
4. Multisig and complex script spends identified from executed/revealed protocol structure.
5. Lightning-related transactions with published identification methodology and confidence.
6. CoinJoin-style transactions with published heuristic/provenance and confidence; results must not imply participant identity.
7. Large-witness/resource-heavy transactions selected by neutral numeric thresholds.
8. Externally sourced stress-case transaction identifiers with citation and no semantic payload processing.
9. Synthetic adversarial transactions generated from documented templates.

Hand-selected cases are diagnostic, never the sole evidence. Sampling seeds, block ranges, exclusions, missing-data counts, and duplicate handling must be published.

### 5.1 RPC plumbing pilot

Before freezing an evidentiary sampling plan, run a deliberately small whole-block pilot. Version 1 selects one height from each of three disjoint ranges: SegWit activation through the block before Taproot activation (`481824..709631`), Taproot activation through the block before the fourth halving (`709632..839999`), and the fourth halving through the captured tip (`840000..tip`). These boundaries exercise distinct protocol eras; they are not claimed to be statistically representative.

For each stratum and height, compute `SHA256("sha256-height-rank-v1\\n" || seed || "\\n" || stratum_name || "\\n" || decimal_height || "\\n")` and select the requested number of lowest digests. The manifest publishes every range, count, digest, height, block hash, seed, and UTC acquisition interval. Sampling is therefore independent of transaction content and reproducible without relying on a language runtime's pseudorandom-number implementation.

The pilot retrieves the selected active-chain blocks with `getblock` verbosity 3, requires transaction-level parity with the local BIP141 implementation, and re-resolves every selected height after collection to detect a reorganization. It exports structural measurements and transaction identifiers, never raw witness elements. Pilot results may reveal acquisition or measurement defects but cannot answer the research hypothesis.

### 5.2 Frozen general historical sample

The primary general-history design is specified in `data/sampling-plans/general-historical-v1.json` and `docs/sampling-plan.md`. It covers all 480,312 active-chain blocks from height 481,824 through 962,135 using 16 contiguous near-equal height strata and 16 whole-block selections per stratum. The seed is derived from the hash of future block 962,280 only after a minimum depth of 100 blocks. This design was frozen before the seed existed and before any selected transactions were known.

Blocks are sampling clusters. Aggregate estimates must use exact stratum inclusion weights, and uncertainty calculations must resample blocks within strata rather than treating transactions from one block as independent observations.

The reference inference implementation reports stratified simple-random-sampling-without-replacement totals, finite-population linearization standard errors, and deterministic within-stratum rescaled `n_h - 1` block-cluster bootstrap intervals. Ratio estimands are ratios of design-weighted totals. SHA256 counter/rejection sampling fixes bootstrap draws across runtimes. The linearization estimator is primary; equal-tailed bootstrap percentile intervals are a companion sensitivity result and are not studentized intervals. These are descriptive estimates for the frozen historical universe, not forecasts of future transaction demand.

This implementation follows the rescaled-bootstrap construction introduced by Rao and Wu and the subsequent survey-methodology treatment of `n_h - 1` resampling. The application here is single-stage stratified SRSWOR with whole blocks as sampled units: [Rao and Wu (1988)](https://doi.org/10.1080/01621459.1988.10478591), [Rao, Wu, and Yue (1992)](https://www150.statcan.gc.ca/n1/en/catalogue/12-001-X199200214486).

## 6. Adversarial transformations

Each candidate model must be minimized over at least these transformations:

- input splitting within one transaction;
- transaction splitting across independently mineable transactions;
- stripped-data padding;
- UTXO manufacturing, including the full setup and spend lifecycle;
- witness-element splitting and CompactSize boundary manipulation;
- equivalent script restructuring;
- moving bytes among script arguments, witness scripts, tapscripts, control-block-compatible structure, annexes, and other available witness structures where consensus permits;
- batching versus unbatching;
- mixed-input transactions that combine favored and disfavored structures.

The comparison unit must state whether it prices only the final transaction, the full setup lifecycle, or steady-state repeated operation. At least one lifecycle analysis is required for every claimed deterrence result.

### Previously rejected simple allowance

A fixed discounted-witness allowance `A` per input appears to let an adversary manufacture allowance by adding inputs. With an approximate marginal native-SegWit input base cost of 164 WU before witness, the payload price approaches:

`1 + 164 / A WU per payload byte`.

For `A = 64, 128, 256, 512`, this is approximately `3.56, 2.28, 1.64, 1.32 WU/B`. Requiring at least full non-witness weight pushes `A` to roughly 55 bytes or less, below ordinary 64/65-byte Taproot signatures. This candidate remains rejected unless a later analysis finds a missing constraint or lifecycle cost that changes the result.

A transaction-level proportional allowance is also presumed vulnerable to stripped-data padding. It must not be revived without an explicit padding minimization analysis.

## 7. Metrics

For each transaction and cohort, report:

- BIP141 weight and vsize;
- candidate effective weight and effective vsize;
- absolute and relative changes;
- fee rate under the baseline and candidate when fee is known;
- stripped size, total witness serialization size, witness payload size;
- per-input witness serialization and element-size distributions;
- input/output and spend-type composition;
- missing-prevout and unclassified rates.

For cohorts, report count, total, mean, median, standard deviation where useful, p50/p75/p90/p95/p99, maximum, and bootstrap confidence intervals for key deltas. Heavy-tailed data must not be summarized by means alone.

## 8. False positives and protocol protection

"False positive" means extra effective weight imposed on a transaction in a protected monetary cohort; it does not assert semantic truth about any transaction. Report the full distribution and the worst independently verified examples.

Advanced protocols must be evaluated on realistic failure/unilateral paths, not only cooperative happy paths. Large cryptographic witnesses, recovery scripts, vaults, DLCs, Lightning force closes/justice transactions, multisig, CoinJoin, BitVM-style constructions, and plausible post-quantum witnesses are explicit counterexample targets.

The evidence tiers, required protected sets, and reporting rules are frozen in `docs/protected-cohorts.md` before model parameters exist. The required adversarial objectives, transformations, validity labels, lifecycle boundaries, and rejection conditions are defined in `docs/adversarial-simulation-contract.md`.

## 9. Reproducibility

Every result bundle must include:

- analyzer Git commit or source archive hash;
- exported schema version;
- Bitcoin Core version and commit when applicable;
- chain and RPC configuration relevant to availability (`txindex`, pruning);
- block heights/hashes or transaction manifest;
- sampling algorithm and seed;
- UTC acquisition time;
- model name, version, and exact parameters;
- command line and environment summary;
- checksums for input manifests and generated tables.

Raw witness payloads should not be copied into published result bundles. Transaction identifiers and reproducible retrieval instructions are sufficient unless a minimal byte fixture is necessary for a protocol test.

## 10. Decision table

The findings report will answer:

1. What is the false-positive impact on ordinary Bitcoin use?
2. What is the impact on neutral large-resource cohorts and externally sourced stress cases?
3. What is the cheapest adversarial bypass for each model, including setup cost?
4. What is the impact on legitimate advanced and future protocols?
5. Does any model materially improve on BIP141 after accounting for bypasses and harms?
6. Should the research direction be abandoned?

No activation recommendation follows automatically from a positive result. Policy implementation, network effects, miner incentives, and consensus compatibility would require separate review.
