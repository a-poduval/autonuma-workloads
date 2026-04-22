"""Feature extraction for per-epoch remote/local prediction."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .constants import (
    EVENT_DTLB_MISS_CAUSES_WALK,
    EVENT_DTLB_WALK_PENDING,
    EVENT_LOCAL_DRAM,
    EVENT_OR_DEMAND,
    EVENT_ORO_DEMAND,
    EVENT_REMOTE_DRAM,
)
from .models import ParsedPerfFile
from .size_parsing import memory_to_gb

TOTAL_ACCESS_SOURCE_LOCAL_REMOTE = "local_plus_remote"
TOTAL_ACCESS_SOURCE_OR_DEMAND = "or_demand"

FAST_GB_SOURCE_FILENAME_MEMORY = "filename_memory"
FAST_GB_SOURCE_ARG = "arg"
RSS_GB_SOURCE_ARG = "arg"
RSS_GB_SOURCE_MANIFEST = "manifest"

DEFAULT_FEATURE_COLUMNS = [
    "total_accesses",
    "unique_accesses",
    "unique_fraction",
    "hotness",
    "hotness_ema_prev",
    "hotness_delta",
    "cum_unique_to_fast_capacity",
    "rss_gb",
    "fast_gb",
    "fast_to_rss",
    "tier_pressure",
    "or_demand_accesses",
    "oro_demand_cycles",
    "mem_latency_cycles",
    "tlb_latency_cycles",
]


@dataclass
class EpochFeatureRow:
    split: str
    selection_tag: str | None
    workload: str
    threads: str
    memory: str
    path: str
    epoch_index: int
    timestamp_s: float
    rel_timestamp_s: float
    rss_gb: float
    fast_gb: float
    fast_to_rss: float
    tier_pressure: float
    total_accesses: float
    dtlb_walks: float
    unique_accesses: float
    unique_fraction: float
    hotness: float
    hotness_ema_prev: float
    hotness_delta: float
    cum_unique_to_fast_capacity: float
    or_demand_accesses: float
    oro_demand_cycles: float
    mem_latency_cycles: float
    tlb_latency_cycles: float
    local_accesses_actual: float
    remote_accesses_actual: float
    remote_share_actual: float
    trainable: int
    pred_remote_share: float | None = None
    pred_remote_accesses: float | None = None
    pred_local_accesses: float | None = None
    err_remote_accesses: float | None = None
    err_local_accesses: float | None = None


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(value, hi))


def safe_ratio(numer: float, denom: float) -> float:
    if denom <= 0.0:
        return 0.0
    return numer / denom


def _resolve_fast_gb(
    memory_token: str,
    fast_gb_source: str,
    fast_gb_arg: float | None,
) -> float:
    if fast_gb_source == FAST_GB_SOURCE_ARG:
        if fast_gb_arg is None or fast_gb_arg <= 0.0:
            raise ValueError("--fast-gb must be > 0 when --fast-gb-source=arg")
        return fast_gb_arg

    parsed = memory_to_gb(memory_token)
    if parsed is None or parsed <= 0.0:
        raise ValueError(
            "Cannot parse fast-tier size from memory token in filename: "
            f"{memory_token}"
        )
    return parsed


def _resolve_rss_gb(
    parsed: ParsedPerfFile,
    rss_gb_source: str,
    rss_gb_arg: float | None,
) -> float:
    if rss_gb_source == RSS_GB_SOURCE_ARG:
        if rss_gb_arg is None or rss_gb_arg <= 0.0:
            raise ValueError("--rss-gb must be > 0 when --rss-source=arg")
        return rss_gb_arg

    if rss_gb_source == RSS_GB_SOURCE_MANIFEST:
        if parsed.rss_gb is None or parsed.rss_gb <= 0.0:
            raise ValueError(
                "Missing/invalid manifest rss for file: "
                f"{parsed.path}. Add rss column in manifest or use --rss-source arg."
            )
        return parsed.rss_gb

    raise ValueError(f"Unsupported rss_gb_source: {rss_gb_source}")


def _resolve_total_accesses(counts: dict[str, int], total_access_source: str) -> float:
    local = float(counts.get(EVENT_LOCAL_DRAM, 0))
    remote = float(counts.get(EVENT_REMOTE_DRAM, 0))

    if total_access_source == TOTAL_ACCESS_SOURCE_LOCAL_REMOTE:
        return local + remote
    if total_access_source == TOTAL_ACCESS_SOURCE_OR_DEMAND:
        return float(counts.get(EVENT_OR_DEMAND, 0))

    raise ValueError(f"Unsupported total_access_source: {total_access_source}")


def build_epoch_feature_rows(
    parsed_files: list[ParsedPerfFile],
    *,
    rss_gb_source: str,
    rss_gb_arg: float | None,
    fast_gb_source: str,
    fast_gb_arg: float | None,
    total_access_source: str,
    ema_alpha: float,
) -> list[EpochFeatureRow]:
    if not (0.0 < ema_alpha <= 1.0):
        raise ValueError("ema_alpha must be in (0,1]")

    rows: list[EpochFeatureRow] = []

    for parsed in parsed_files:
        rss_gb = _resolve_rss_gb(parsed, rss_gb_source, rss_gb_arg)
        fast_gb = _resolve_fast_gb(parsed.memory, fast_gb_source, fast_gb_arg)
        fast_to_rss = safe_ratio(fast_gb, rss_gb)
        tier_pressure = clamp((rss_gb - fast_gb) / rss_gb, 0.0, 1.0)
        fast_capacity_pages = (fast_gb * (1024.0**3)) / 4096.0

        hotness_ema = 1.0
        cumulative_unique = 0.0
        base_ts = parsed.samples[0].timestamp_s if parsed.samples else 0.0

        for idx, sample in enumerate(parsed.samples):
            counts = sample.counts

            local_actual = float(counts.get(EVENT_LOCAL_DRAM, 0))
            remote_actual = float(counts.get(EVENT_REMOTE_DRAM, 0))

            total_accesses = _resolve_total_accesses(counts, total_access_source)

            dtlb_walks = float(counts.get(EVENT_DTLB_MISS_CAUSES_WALK, 0))
            unique_accesses = min(total_accesses, dtlb_walks)
            unique_fraction = safe_ratio(unique_accesses, total_accesses)

            hotness = safe_ratio(total_accesses, unique_accesses)
            hotness_delta = hotness - hotness_ema

            cumulative_unique += unique_accesses
            cum_unique_to_fast_capacity = safe_ratio(cumulative_unique, fast_capacity_pages)

            or_demand = float(counts.get(EVENT_OR_DEMAND, 0))
            oro_demand = float(counts.get(EVENT_ORO_DEMAND, 0))
            dtlb_walk_pending = float(counts.get(EVENT_DTLB_WALK_PENDING, 0))

            mem_latency = safe_ratio(oro_demand, or_demand)
            tlb_latency = safe_ratio(dtlb_walk_pending, dtlb_walks)

            remote_share_actual = safe_ratio(remote_actual, total_accesses)
            trainable = 1 if total_accesses > 0.0 and math.isfinite(remote_share_actual) else 0

            rows.append(
                EpochFeatureRow(
                    split=parsed.split,
                    selection_tag=parsed.selection_tag,
                    workload=parsed.workload,
                    threads=parsed.threads,
                    memory=parsed.memory,
                    path=parsed.path,
                    epoch_index=idx,
                    timestamp_s=sample.timestamp_s,
                    rel_timestamp_s=sample.timestamp_s - base_ts,
                    rss_gb=rss_gb,
                    fast_gb=fast_gb,
                    fast_to_rss=fast_to_rss,
                    tier_pressure=tier_pressure,
                    total_accesses=total_accesses,
                    dtlb_walks=dtlb_walks,
                    unique_accesses=unique_accesses,
                    unique_fraction=unique_fraction,
                    hotness=hotness,
                    hotness_ema_prev=hotness_ema,
                    hotness_delta=hotness_delta,
                    cum_unique_to_fast_capacity=cum_unique_to_fast_capacity,
                    or_demand_accesses=or_demand,
                    oro_demand_cycles=oro_demand,
                    mem_latency_cycles=mem_latency,
                    tlb_latency_cycles=tlb_latency,
                    local_accesses_actual=local_actual,
                    remote_accesses_actual=remote_actual,
                    remote_share_actual=clamp(remote_share_actual, 0.0, 1.0),
                    trainable=trainable,
                )
            )

            hotness_ema = ema_alpha * hotness + (1.0 - ema_alpha) * hotness_ema

    return rows
