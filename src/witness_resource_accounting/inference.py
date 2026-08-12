"""Design-based inference for the frozen stratified whole-block sample."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import math
from statistics import mean, variance
from typing import Any, Sequence

from .sample_plan import SamplingPlan


DEFAULT_BLOCK_METRICS = (
    "transaction_count",
    "witness_transaction_count",
    "input_count",
    "total_stripped_bytes",
    "total_witness_serialization_bytes",
    "total_bip141_weight",
)

RATIO_ESTIMANDS = {
    "witness_transaction_share": ("witness_transaction_count", "transaction_count"),
    "witness_serialization_bytes_per_transaction": (
        "total_witness_serialization_bytes",
        "transaction_count",
    ),
    "bip141_weight_per_transaction": ("total_bip141_weight", "transaction_count"),
    "inputs_per_transaction": ("input_count", "transaction_count"),
}


class _HashCounterRNG:
    """Cross-runtime deterministic rejection sampler over SHA256 outputs."""

    def __init__(self, seed: str) -> None:
        self._seed = seed.encode("utf-8")
        self._counter = 0

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper_bound must be positive")
        modulus = 1 << 256
        limit = modulus - modulus % upper_bound
        while True:
            material = (
                b"sha256-counter-rejection-v1\n"
                + self._seed
                + b"\n"
                + str(self._counter).encode("ascii")
                + b"\n"
            )
            self._counter += 1
            value = int.from_bytes(sha256(material).digest(), "big")
            if value < limit:
                return value % upper_bound


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile of an empty sequence")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between zero and one")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _validate_blocks(
    plan: SamplingPlan,
    blocks: Sequence[dict[str, Any]],
    metrics: Sequence[str],
) -> dict[str, list[dict[str, Any]]]:
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_heights: set[int] = set()
    plan_strata = {item.name: item for item in plan.strata}
    for block in blocks:
        stratum_name = block.get("stratum")
        height = block.get("height")
        if stratum_name not in plan_strata:
            raise ValueError(f"block uses unknown stratum {stratum_name!r}")
        if not isinstance(height, int):
            raise ValueError("block height must be an integer")
        stratum = plan_strata[stratum_name]
        if not stratum.start_height <= height <= stratum.end_height:
            raise ValueError(f"block height {height} is outside stratum {stratum_name}")
        if height in seen_heights:
            raise ValueError(f"duplicate sampled block height {height}")
        seen_heights.add(height)
        for metric in metrics:
            value = block.get(metric)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValueError(f"block {height} has invalid metric {metric}")
        by_stratum[stratum_name].append(block)

    for stratum in plan.strata:
        observed = len(by_stratum[stratum.name])
        if observed != stratum.sample_count:
            raise ValueError(
                f"stratum {stratum.name} has {observed} sampled blocks; "
                f"expected {stratum.sample_count}"
            )
        if observed < 2:
            raise ValueError(
                f"stratum {stratum.name} needs at least two sampled blocks for variance estimation"
            )
    return by_stratum


def estimate_stratified_blocks(
    plan: SamplingPlan,
    blocks: Sequence[dict[str, Any]],
    *,
    metrics: Sequence[str] = DEFAULT_BLOCK_METRICS,
    bootstrap_replicates: int = 2_000,
    bootstrap_seed: str = "wra-design-bootstrap-v1",
) -> dict[str, Any]:
    """Estimate universe totals using stratified SRSWOR whole-block clusters.

    The bootstrap is a rescaled within-stratum bootstrap. Each replicate draws
    n_h - 1 sampled blocks with replacement and scales its displacement from
    the observed mean by sqrt(1 - n_h / N_h), preserving the SRSWOR
    finite-population variance for a stratum mean.
    """
    if bootstrap_replicates < 100:
        raise ValueError("bootstrap_replicates must be at least 100")
    if not bootstrap_seed:
        raise ValueError("bootstrap_seed cannot be empty")
    if not metrics or len(set(metrics)) != len(metrics):
        raise ValueError("metrics must be a non-empty unique sequence")

    by_stratum = _validate_blocks(plan, blocks, metrics)
    universe_block_count = sum(
        item.end_height - item.start_height + 1 for item in plan.strata
    )
    stratum_results: list[dict[str, Any]] = []
    totals = {metric: 0.0 for metric in metrics}
    total_variances = {metric: 0.0 for metric in metrics}

    for stratum in plan.strata:
        observations = by_stratum[stratum.name]
        population_count = stratum.end_height - stratum.start_height + 1
        sample_count = len(observations)
        sampling_fraction = sample_count / population_count
        metric_results: dict[str, Any] = {}
        for metric in metrics:
            values = [float(block[metric]) for block in observations]
            sample_mean = mean(values)
            estimated_total = population_count * sample_mean
            sample_variance = variance(values)
            variance_total = (
                population_count**2
                * (1 - sampling_fraction)
                * sample_variance
                / sample_count
            )
            totals[metric] += estimated_total
            total_variances[metric] += variance_total
            metric_results[metric] = {
                "sample_mean_per_block": sample_mean,
                "sample_variance_between_blocks": sample_variance,
                "estimated_total": estimated_total,
                "estimated_total_standard_error": math.sqrt(variance_total),
            }
        stratum_results.append(
            {
                "name": stratum.name,
                "population_block_count": population_count,
                "sampled_block_count": sample_count,
                "block_inclusion_probability": sampling_fraction,
                "block_design_weight": population_count / sample_count,
                "metrics": metric_results,
            }
        )

    rng = _HashCounterRNG(bootstrap_seed)
    replicate_totals = {metric: [] for metric in metrics}
    replicate_ratios = {name: [] for name in RATIO_ESTIMANDS}
    for _ in range(bootstrap_replicates):
        replicate = {metric: 0.0 for metric in metrics}
        for stratum in plan.strata:
            observations = by_stratum[stratum.name]
            population_count = stratum.end_height - stratum.start_height + 1
            sample_count = len(observations)
            resample = [observations[rng.randbelow(sample_count)] for _ in range(sample_count - 1)]
            scale = math.sqrt(1 - sample_count / population_count)
            for metric in metrics:
                observed_mean = mean(float(block[metric]) for block in observations)
                resampled_mean = mean(float(block[metric]) for block in resample)
                replicate_mean = observed_mean + scale * (resampled_mean - observed_mean)
                replicate[metric] += population_count * replicate_mean
        for metric in metrics:
            replicate_totals[metric].append(replicate[metric])
        for ratio_name, (numerator, denominator) in RATIO_ESTIMANDS.items():
            if numerator in replicate and denominator in replicate and replicate[denominator] > 0:
                replicate_ratios[ratio_name].append(
                    replicate[numerator] / replicate[denominator]
                )

    aggregate_metrics: dict[str, Any] = {}
    for metric in metrics:
        standard_error = math.sqrt(total_variances[metric])
        aggregate_metrics[metric] = {
            "estimated_universe_total": totals[metric],
            "estimated_mean_per_block": totals[metric] / universe_block_count,
            "linearization_standard_error_total": standard_error,
            "linearization_normal_95_interval_total": [
                totals[metric] - 1.96 * standard_error,
                totals[metric] + 1.96 * standard_error,
            ],
            "rescaled_bootstrap_95_interval_total": [
                _percentile(replicate_totals[metric], 0.025),
                _percentile(replicate_totals[metric], 0.975),
            ],
        }

    ratios: dict[str, Any] = {}
    for ratio_name, (numerator, denominator) in RATIO_ESTIMANDS.items():
        if numerator not in totals or denominator not in totals or totals[denominator] <= 0:
            continue
        ratios[ratio_name] = {
            "numerator": numerator,
            "denominator": denominator,
            "estimate": totals[numerator] / totals[denominator],
            "rescaled_bootstrap_95_interval": [
                _percentile(replicate_ratios[ratio_name], 0.025),
                _percentile(replicate_ratios[ratio_name], 0.975),
            ],
        }

    return {
        "inference_version": 1,
        "scope": "stratified_whole_block_design_based_estimates",
        "sampling_plan_id": plan.plan_id,
        "sampling_plan_sha256": plan.source_sha256,
        "population_block_count": universe_block_count,
        "sampled_block_count": len(blocks),
        "variance_sampling_unit": "block",
        "bootstrap": {
            "method": "within_stratum_rescaled_n_minus_1_cluster_bootstrap",
            "interval": "equal_tailed_percentile_companion_interval",
            "random_generator": "sha256-counter-rejection-v1",
            "replicates": bootstrap_replicates,
            "seed": bootstrap_seed,
        },
        "strata": stratum_results,
        "aggregate_metrics": aggregate_metrics,
        "ratio_estimands": ratios,
    }
