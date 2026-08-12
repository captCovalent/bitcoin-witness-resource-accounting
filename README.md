# Witness Resource Accounting Research

This repository investigates whether Bitcoin can account more accurately for unusually large witness or validation-resource consumption without interpreting transaction content. It is an empirical research project, not a BIP implementation, not an anti-data classifier, and not a claim that arbitrary data should be restricted.

The hypothesis is deliberately falsifiable:

> A content-neutral, policy-only accounting model may improve on BIP141 pricing for unusually resource-heavy transactions while preserving ordinary payments and legitimate advanced monetary protocols, remaining robust when adversaries restructure transactions to minimize cost.

A result showing that no such model survives counterexamples is a successful research outcome.

## Non-goals

- No semantic inspection or classification of witness bytes.
- No JPEG, inscription, CSAM, "spam", or application-content detector.
- No consensus changes, activation parameters, proof-of-work changes, or transaction bans.
- No preferred hypothetical model in the baseline phase.
- No claim that byte count is a complete proxy for validation, propagation, storage, or UTXO cost.

## Current phase

Phase 0 establishes the measurement baseline:

- byte-exact Bitcoin transaction decoding;
- stripped size and total serialized size;
- witness serialization size, witness stack payload size, and per-input witness measurements;
- BIP141 transaction weight and virtual size;
- `txid` and `wtxid` calculation;
- Bitcoin Core `getrawtransaction` acquisition with differential parity checks;
- prevout-backed P2WPKH, P2WSH, and P2TR key/script-path classification;
- reproducible JSON and CSV export;
- tests for legacy, mixed-input SegWit, CompactSize boundaries, and malformed encodings.

The baseline does **not** implement alternative accounting models. Research notes must be reviewed and the sampling plan frozen before those models are added.

## Quick start

The baseline has no runtime dependencies beyond Python 3.11 or later.

```sh
cd WitnessResourceResearch
make test
make analyze-example
```

Analyze a transaction directly:

```sh
PYTHONPATH=src python3 scripts/analyze_raw_transactions.py \
  --hex 02000000010000000000000000000000000000000000000000000000000000000000000000ffffffff00ffffffff0100000000000000000000000000
```

Fetch a transaction from Bitcoin Core using cookie authentication:

```sh
PYTHONPATH=src python3 scripts/analyze_raw_transactions.py \
  --rpc-txid TRANSACTION_ID \
  --rpc-cookie ~/.bitcoin/.cookie
```

If `-txindex` is disabled, pass `--block-hash` for a confirmed transaction. The RPC path requests `getrawtransaction` verbosity 2, uses returned prevouts for objective spend classification, and refuses output if Core's `size`, `vsize`, `weight`, `txid`, or witness hash disagrees with the local decoder. `BITCOIN_RPC_URL`, `BITCOIN_RPC_COOKIE`, or the paired `BITCOIN_RPC_USER` / `BITCOIN_RPC_PASSWORD` environment variables may also be used.

JSON Lines input uses one record per line:

```json
{"id":"sample-1","hex":"...","fee_sats":1234}
```

`fee_sats` is optional. When present, the baseline reports fee rate as fee divided by BIP141 virtual size. The analyzer never infers fees from transaction bytes because input values are not serialized in the spending transaction.

For a remote node reached through an SSH tunnel, keep credentials out of command history by using the interactive prompt:

```sh
PYTHONPATH=src python3 scripts/analyze_raw_transactions.py \
  --rpc-url http://127.0.0.1:19332 \
  --rpc-user umbrel \
  --prompt-rpc-password \
  --rpc-txid TRANSACTION_ID
```

Run the deterministic whole-block RPC pilot with one block from each of three protocol-era strata:

```sh
PYTHONPATH=src python3 scripts/collect_block_sample.py \
  --rpc-url http://127.0.0.1:19332 \
  --rpc-user umbrel \
  --prompt-rpc-password \
  --manifest-output data/manifests/rpc-pilot-v1.json \
  --transactions-output results/rpc-pilot-v1.transactions.jsonl
```

The pilot uses `getblock` verbosity 3 for prevout-backed classification. It samples whole blocks by the lowest SHA256 height ranks under the published seed `wra-rpc-pilot-v1`, rechecks their hashes after collection, and exports no transaction hex or witness contents. Its purpose is to validate RPC compatibility, local/Core parity, provenance, and runtime—not to support a conclusion about an accounting model.

Verify the manifest checksum and produce a deterministic structural summary:

```sh
PYTHONPATH=src python3 scripts/summarize_results.py \
  --manifest data/manifests/rpc-pilot-v1.json \
  --transactions results/rpc-pilot-v1.transactions.jsonl \
  --output results/rpc-pilot-v1.summary.json
```

## Frozen general historical sample

The first evidentiary general-history plan is frozen in `data/sampling-plans/general-historical-v1.json` and explained in `docs/sampling-plan.md`. Validate it offline with:

```sh
PYTHONPATH=src python3 scripts/validate_sampling_plan.py \
  --plan data/sampling-plans/general-historical-v1.json
```

The selection seed is the future mainnet block hash at height 962,280. Collection is intentionally unavailable until the node tip reaches 962,380, giving that seed a minimum depth of 100 blocks. The large-sample collector streams transaction records atomically to disk rather than retaining the dataset in memory.

After collection and structural summarization, calculate exact stratum-weighted totals and deterministic block-cluster uncertainty intervals with:

```sh
PYTHONPATH=src python3 scripts/estimate_historical_sample.py \
  --plan data/sampling-plans/general-historical-v1.json \
  --summary results/general-historical-v1.summary.json \
  --bootstrap-replicates 2000 \
  --bootstrap-seed wra-design-bootstrap-v1 \
  --output results/general-historical-v1.inference.json
```

Transactions within a block are not treated as independent samples. See `docs/protected-cohorts.md` and `docs/adversarial-simulation-contract.md` for the falsification sets and transformation contract that must be in place before model implementation.

## Measurement terminology

- **Stripped size**: canonical transaction serialization without marker, flag, or per-input witnesses.
- **Total size**: canonical transaction serialization including witness serialization when present.
- **Witness serialization size**: `total_size - stripped_size`; this includes the two-byte marker/flag and all CompactSize witness framing.
- **Witness section size**: the sum of each input's serialized witness vector; excludes marker/flag.
- **Witness payload size**: the sum of raw witness stack-element lengths; excludes all framing.
- **BIP141 weight**: `stripped_size * 3 + total_size`.
- **Virtual size**: `ceil(weight / 4)`.

These distinctions are intentional. Referring to all three witness measurements as "witness bytes" would make later model comparisons ambiguous.

## Repository map

- `src/witness_resource_accounting/`: audited baseline decoder, accounting, and export code.
- `tests/`: synthetic boundary cases and primary-source transaction vectors.
- `scripts/`: reproducible command-line entry points.
- `docs/methodology.md`: research design, sampling, classification, and falsification criteria.
- `docs/research-notes.md`: primary-source review and open literature questions.
- `docs/protected-cohorts.md`: monetary and advanced-protocol protection contract.
- `docs/adversarial-simulation-contract.md`: required bypass search and lifecycle accounting.
- `docs/data-schema.md`: stable output fields and units.
- `data/`: dataset manifests and provenance only; raw payload corpora are excluded by default.
- `results/`: generated-result conventions; large outputs are ignored by Git.
- `findings.md`: living findings report, currently limited to baseline facts and unanswered questions.

## Source of truth

The implementation follows [BIP141](https://github.com/bitcoin/bips/blob/c38071c8c45a1fc50cecaac0d82d99e3bbd56911/bip-0141.mediawiki) and Bitcoin Core's transaction serialization and weight helpers at commit [`5d051c0`](https://github.com/bitcoin/bitcoin/commit/5d051c05629df6457047aa4315476105dcb27e08). The RPC acquisition path treats Bitcoin Core's decoded identifiers and accounting fields as a differential oracle and fails closed on disagreement.

## Research posture

Every proposed model must publish its cheapest known bypass, not merely its favorable examples. Results must separate externally sourced stress cohorts from randomly sampled historical blocks, and must report false-positive distributions for ordinary and advanced monetary use before discussing deterrence.
