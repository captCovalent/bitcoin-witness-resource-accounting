# Protected monetary cohorts

Status: identification contract before hypothetical model implementation.

The research question is not whether a candidate can increase the weight of selected large-witness transactions. It is whether it can do so without imposing unacceptable costs on existing or plausible monetary use. Protected cohorts therefore act as falsification sets, not exceptions encoded into a model.

## Rules

1. A model never receives a cohort label as an input. Labels exist only for evaluation.
2. A transaction is never called an ordinary payment, Lightning transaction, CoinJoin, or arbitrary-data transaction solely from witness bytes or stack shape.
3. Identification method, provenance, confidence, exclusions, and overlap are exported with every cohort manifest.
4. Uncertain examples remain uncertain. They are not promoted to a stronger label to improve results.
5. Cohort definitions and manifests should be frozen before candidate parameters are tuned.
6. Results report the full distribution, worst affected examples, and lifecycle paths; averages alone are insufficient.

## Evidence levels

### Level A: objective protocol structure

These cohorts require only consensus-defined serialization plus verified prevouts. They include native or wrapped P2WPKH, P2WSH, P2TR key-path, P2TR script-path, witness versions, stack-element sizes, tapscript size, control-block size, annex size, input/output count, and numeric size/fee strata.

Level A does not establish application purpose. A P2WPKH spend is monetary-capable but is not automatically an "ordinary payment." These broad structural cohorts are nevertheless protected because a content-neutral model cannot know their application.

### Level B: primary provenance

These examples come from protocol repositories, published test vectors, operator-provided transaction IDs, protocol developers, or documented production incidents. The manifest records the primary source and the exact claimed path. Target paths include:

- Lightning cooperative closes, unilateral closes, timeout/success paths, revoked-state justice, anchor/package paths, and channel sweeps;
- wallet multisig, recovery, inheritance, vault, DLC, and threshold-signature paths;
- collaborative transactions and CoinJoin implementations whose coordinators or developers publish reproducible examples;
- large-script and proof systems such as BitVM-style constructions;
- plausible post-quantum signature/proof sizes as explicitly synthetic future scenarios.

Primary provenance protects against silently substituting a convenient heuristic for protocol truth. It does not prove that a historical transaction belongs to a person or reveal participant identity.

### Level C: documented heuristic

Heuristic cohorts may be useful for sensitivity analysis but remain separate from Level B. Every heuristic publishes its false-positive limitations. CoinJoin-style output patterns, suspected Lightning transactions, wallet fingerprints, or behavioral clusters must never be described as certain application identity.

## Required protected sets

The initial evaluation matrix must include:

| Set | Minimum coverage | Primary risk being tested |
|---|---|---|
| Broad history | Frozen whole-block sample, weighted by design | Population-wide false positives |
| Simple witness spends | P2WPKH and P2TR key path across input counts | Payment and consolidation costs |
| Script spends | P2WSH and P2TR script path across script/stack sizes | Complex custody and recovery |
| Multisig | Cooperative and recovery/failure paths | Signature and script growth |
| Lightning | Cooperative plus every material unilateral path available | Security-critical time-sensitive spends |
| Collaborative transactions | Primary-provenance and separately heuristic CoinJoin-style sets | Privacy and batching protocols |
| Large cryptographic witnesses | Current constructions and synthetic size sweeps | Future compatibility |
| High-input monetary-capable | Consolidation/batching structures | Input-count and aggregate-witness penalties |

## False-positive reporting

For each model and protected set, report baseline weight, candidate weight, absolute and relative delta, fee-rate transformation, affected fraction at every tested parameter, and the most affected independently verified examples. For Lightning and other state protocols, report whether the candidate changes standard relay or package feasibility for the failure path, not merely its fee.

No numerical "acceptable harm" threshold is chosen in this document. That is a normative decision and must not be reverse-engineered from a favored model's results.
