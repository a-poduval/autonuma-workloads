"""Parse/filter pipeline orchestration for one perf file."""

from __future__ import annotations

from .log_metrics import parse_metrics_from_logs
from .models import ParsedPerfFile
from .perf_csv import collect_epoch_samples, filter_tail_window


def build_windowed_file_result(
    file_path: str,
    file_match,
    split: str,
    selection_tag: str | None,
    rss_gb: float | None,
    target_events: set[str],
    safety_margin_sec: float,
    disable_runtime_window: bool,
) -> ParsedPerfFile:
    workload = file_match.group("workload")
    threads = file_match.group("threads")
    memory = file_match.group("memory")

    base_path = file_path[: -len("_perf.csv")]
    output_path = f"{base_path}_output.log"
    time_path = f"{base_path}_time.txt"
    metrics = parse_metrics_from_logs(workload, output_path, time_path)

    requested_window: float | None = None
    if not disable_runtime_window and metrics.execution_seconds is not None:
        requested_window = metrics.execution_seconds + safety_margin_sec

    all_samples, max_ts = collect_epoch_samples(file_path, target_events)
    filtered_samples, applied_window = filter_tail_window(
        all_samples,
        max_ts,
        requested_window,
    )

    return ParsedPerfFile(
        workload=workload,
        threads=threads,
        memory=memory,
        path=file_path,
        split=split,
        selection_tag=selection_tag,
        rss_gb=rss_gb,
        metrics=metrics,
        requested_window_seconds=requested_window,
        applied_window_seconds=applied_window,
        max_timestamp_s=max_ts,
        samples=filtered_samples,
    )
