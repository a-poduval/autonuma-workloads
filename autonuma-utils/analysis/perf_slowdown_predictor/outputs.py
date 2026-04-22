"""CSV output writers for parse/filter stage."""

from __future__ import annotations

import csv

from .models import ParsedPerfFile


def write_file_summary_csv(path: str, rows: list[ParsedPerfFile]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "split",
                "selection_tag",
                "rss_gb",
                "workload",
                "threads",
                "memory",
                "path",
                "throughput",
                "runtime",
                "execution_seconds",
                "requested_window_seconds",
                "applied_window_seconds",
                "max_timestamp_s",
                "epochs",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.split,
                    row.selection_tag,
                    row.rss_gb,
                    row.workload,
                    row.threads,
                    row.memory,
                    row.path,
                    row.metrics.throughput,
                    row.metrics.runtime,
                    row.metrics.execution_seconds,
                    row.requested_window_seconds,
                    row.applied_window_seconds,
                    row.max_timestamp_s,
                    len(row.samples),
                ]
            )


def write_epoch_csv(
    path: str,
    rows: list[ParsedPerfFile],
    event_columns: list[str],
) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "split",
                "selection_tag",
                "rss_gb",
                "workload",
                "threads",
                "memory",
                "path",
                "timestamp_s",
                "rel_timestamp_s",
                *event_columns,
            ]
        )

        for row in rows:
            if not row.samples:
                continue
            base_ts = row.samples[0].timestamp_s
            for sample in row.samples:
                writer.writerow(
                    [
                        row.split,
                        row.selection_tag,
                        row.rss_gb,
                        row.workload,
                        row.threads,
                        row.memory,
                        row.path,
                        sample.timestamp_s,
                        sample.timestamp_s - base_ts,
                        *[sample.counts.get(event, 0) for event in event_columns],
                    ]
                )
