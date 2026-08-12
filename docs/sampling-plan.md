# General historical sampling plan

Status: frozen before the seed block, 2026-08-12.

The machine-readable source of truth is `data/sampling-plans/general-historical-v1.json`. This document explains its rationale and limitations.

## Population and selection

The primary general-history population is every active-chain block from SegWit activation at height 481,824 through the already recorded research snapshot at height 962,135, inclusive: 480,312 blocks. The range is divided into 16 contiguous strata of 30,019 or 30,020 blocks. Within every stratum, 16 whole blocks are selected by the lowest `sha256-height-rank-v1` digests, for 256 blocks total.

All transactions in a selected block are retained. Selection never examines transaction count, fees, witness presence, witness size, script type, application protocol, or payload bytes. There are no replacement selections or discretionary exclusions.

## Future public seed

The seed source is the mainnet block hash at height 962,280, a height that had not been mined when this plan was frozen. Collection refuses to resolve the seed until the node tip is at least height 962,380, giving the seed block a minimum depth of 100 blocks. The sampler's actual seed string is `wra-general-historical-v1:<blockhash>`.

This construction does not make the sample metaphysically manipulation-proof, but it prevents the researchers from repeatedly choosing seeds after observing the selected transactions. The plan file hash and repository history should be published with results.

## Statistical use

Blocks are cluster-sampling units. Transactions within one block are not independent observations. Results will be reported per stratum and as aggregates weighted by each stratum's exact block inclusion probability. Confidence intervals will resample selected blocks within strata, not individual transactions.

This sample estimates the historical distribution of numeric transaction structures. It is not sufficient on its own for rare advanced-protocol cohorts, failure-path transactions, externally sourced stress cases, or adversarial constructions. Those cohorts remain separate and must never be blended into the general sample without explicit labels and weights.

## Power and limitations

The choice of 256 blocks is an engineering compromise made before inspecting the selected transactions. It should yield hundreds of thousands of transactions while keeping raw structural output manageable on the research node. Cluster correlation, historical nonstationarity, and rare-event sparsity mean a nominal transaction count cannot be treated as an equivalent simple random sample size.

No accounting model will be accepted or rejected solely from this sample. Candidate evaluation also requires protected monetary cohorts and adversarial lifecycle minimization.
