"""Validation and future-block seed resolution for frozen sampling plans."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .rpc import BitcoinRPCClient, BitcoinRPCError
from .sampling import HeightStratum


@dataclass(frozen=True, slots=True)
class SamplingPlan:
    document: dict[str, Any]
    source_path: Path
    source_sha256: str
    strata: tuple[HeightStratum, ...]

    @property
    def plan_id(self) -> str:
        return self.document["plan_id"]


@dataclass(frozen=True, slots=True)
class ResolvedSamplingPlan:
    plan: SamplingPlan
    seed: str
    seed_block_height: int
    seed_block_hash: str
    tip_height: int


def load_sampling_plan(path: Path) -> SamplingPlan:
    source = path.read_bytes()
    document = json.loads(source)
    if not isinstance(document, dict) or document.get("plan_version") != 1:
        raise ValueError("sampling plan must be a version-1 JSON object")
    if not isinstance(document.get("plan_id"), str) or not document["plan_id"]:
        raise ValueError("sampling plan requires a non-empty plan_id")
    if document.get("chain") != "main":
        raise ValueError("sampling plan currently requires Bitcoin mainnet")

    universe = document.get("universe")
    if not isinstance(universe, dict):
        raise ValueError("sampling plan requires a universe object")
    start = universe.get("start_height")
    end = universe.get("end_height")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start:
        raise ValueError("sampling plan has an invalid height universe")
    if universe.get("block_count") != end - start + 1:
        raise ValueError("sampling plan universe block_count is inconsistent")

    raw_strata = document.get("strata")
    if not isinstance(raw_strata, list) or not raw_strata:
        raise ValueError("sampling plan requires strata")
    strata: list[HeightStratum] = []
    for raw in raw_strata:
        if not isinstance(raw, dict):
            raise ValueError("sampling plan stratum must be an object")
        try:
            stratum = HeightStratum(
                raw["name"], raw["start_height"], raw["end_height"], raw["sample_count"]
            )
        except KeyError as error:
            raise ValueError(f"sampling plan stratum lacks {error.args[0]}") from error
        stratum.validate()
        strata.append(stratum)

    ordered = sorted(strata, key=lambda item: item.start_height)
    if ordered[0].start_height != start or ordered[-1].end_height != end:
        raise ValueError("sampling plan strata do not span the declared universe")
    for left, right in zip(ordered, ordered[1:]):
        if right.start_height != left.end_height + 1:
            raise ValueError("sampling plan strata contain a gap or overlap")
    if len({item.name for item in strata}) != len(strata):
        raise ValueError("sampling plan stratum names must be unique")
    declared_count = document.get("total_sampled_blocks")
    if declared_count != sum(item.sample_count for item in strata):
        raise ValueError("sampling plan total_sampled_blocks is inconsistent")

    seed = document.get("seed")
    if not isinstance(seed, dict) or seed.get("method") != "future_bitcoin_block_hash":
        raise ValueError("sampling plan requires a future Bitcoin block-hash seed")
    seed_height = seed.get("height")
    minimum_depth = seed.get("minimum_depth")
    domain = seed.get("domain")
    if not isinstance(seed_height, int) or seed_height <= end:
        raise ValueError("seed height must follow the sampled universe")
    if not isinstance(minimum_depth, int) or minimum_depth < 0:
        raise ValueError("seed minimum_depth must be non-negative")
    if not isinstance(domain, str) or not domain:
        raise ValueError("seed domain must be a non-empty string")

    return SamplingPlan(document, path, sha256(source).hexdigest(), tuple(strata))


def resolve_sampling_plan(
    client: BitcoinRPCClient,
    plan: SamplingPlan,
) -> ResolvedSamplingPlan:
    info = client.get_blockchain_info()
    if info.get("chain") != plan.document["chain"]:
        raise BitcoinRPCError("node chain does not match sampling plan")
    tip_height = client.get_block_count()
    seed_specification = plan.document["seed"]
    seed_height = seed_specification["height"]
    required_tip = seed_height + seed_specification["minimum_depth"]
    if tip_height < required_tip:
        raise BitcoinRPCError(
            f"sampling seed is not mature: tip {tip_height}, required {required_tip} "
            f"({required_tip - tip_height} blocks remaining)"
        )
    seed_hash = client.get_block_hash(seed_height)
    resolved_seed = f"{seed_specification['domain']}:{seed_hash}"
    return ResolvedSamplingPlan(plan, resolved_seed, seed_height, seed_hash, tip_height)
