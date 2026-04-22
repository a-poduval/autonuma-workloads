"""Data models used by the parse/filter pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkloadMetrics:
    throughput: float | None = None
    runtime: float | None = None
    execution_seconds: float | None = None


@dataclass
class EpochSample:
    timestamp_s: float
    counts: dict[str, int]


@dataclass
class SelectedPerfPath:
    path: str
    split: str
    selection_tag: str | None = None
    rss_gb: float | None = None


@dataclass
class ParsedPerfFile:
    workload: str
    threads: str
    memory: str
    path: str
    split: str
    selection_tag: str | None
    rss_gb: float | None
    metrics: WorkloadMetrics
    requested_window_seconds: float | None
    applied_window_seconds: float | None
    max_timestamp_s: float | None
    samples: list[EpochSample]
