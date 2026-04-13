#!/usr/bin/env python3
"""Recursive perf CSV analyzer.

Scans a directory tree for perf files and writes one summary CSV row per file.

Default filename format:
  workload-memory_threads_perf.csv

Each perf file is expected to contain repeated timestamp rows where each row
corresponds to one event. This script pivots/aggregates those rows into a
single row with one column per target event.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_perf\.csv$"
)

# Default event mapping for the observed Skylake perf files in this workspace.
DEFAULT_EVENT_ORDER: list[tuple[str, str]] = [
    ("cycles", "cycles"),
    ("l3_miss_stalls", "cpu/event=0xa3,umask=0x06,cmask=0x6/"),
    ("outstanding_demand_reads", "cpu/event=0x60,umask=0x01/"),
    ("memory_active_cycles", "cpu/event=0x60,umask=0x01,cmask=0x01/"),
    ("store_buffer_full_stalls", "cpu/event=0xa6,umask=0x40/"),
    ("lfb_hits", "cpu/event=0xd1,umask=0x40/"),
]


@dataclass
class PerfSummaryRow:
    workload: str
    threads: str
    memory: str
    path: str
    totals: dict[str, int]


def parse_count(value: str) -> int | None:
    """Parse perf count field into int, returning None for non-numeric rows."""
    text = value.strip()
    if not text:
        return None

    text = text.replace(" ", "")
    if text in {"<notcounted>", "<notsupported>", "<notcounted>", "nan"}:
        return None

    try:
        return int(float(text))
    except ValueError:
        return None


def parse_event_from_fields(fields: list[str]) -> str | None:
    """Parse event token from a split perf CSV line.

    For raw events, perf stores the event with commas unquoted:
      cpu/event=0xa3,umask=0x06,cmask=0x6/
    so the event spans multiple CSV fields.
    """
    if len(fields) < 4:
        return None

    start = fields[3].strip()
    if not start:
        return None

    if start == "cycles":
        return "cycles"

    if not start.startswith("cpu/event="):
        return start

    parts = [start]
    idx = 4
    while idx < len(fields):
        part = fields[idx].strip()
        if not part:
            break
        parts.append(part)
        if part.endswith("/"):
            break
        idx += 1

    return ",".join(parts)


def summarize_perf_file(file_path: str, target_events: set[str]) -> dict[str, int]:
    """Aggregate total counts per target event for one perf CSV file."""
    totals = {event: 0 for event in target_events}

    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split(",")
            if len(fields) < 4:
                continue

            count = parse_count(fields[1])
            if count is None:
                continue

            event = parse_event_from_fields(fields)
            if event is None or event not in totals:
                continue

            totals[event] += count

    return totals


def iter_matching_files(root_dir: str, filename_re: re.Pattern[str]):
    for current_root, _, files in os.walk(root_dir):
        for name in files:
            match = filename_re.match(name)
            if match is None:
                continue
            yield os.path.join(current_root, name), match


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively summarize perf CSV files into event columns."
    )
    parser.add_argument("input_dir", help="Root directory to scan recursively")
    parser.add_argument(
        "--output",
        default="perf_summary.csv",
        help="Output CSV path (default: perf_summary.csv)",
    )
    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help=(
            "Regex used to identify perf files from basename. Must contain named "
            "groups: workload, memory, threads."
        ),
    )
    parser.add_argument(
        "--sort-by-path",
        action="store_true",
        help="Sort rows by file path for deterministic output order",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    try:
        filename_re = re.compile(args.filename_regex)
    except re.error as exc:
        raise SystemExit(f"Invalid --filename-regex: {exc}") from exc

    required = {"workload", "memory", "threads"}
    if not required.issubset(filename_re.groupindex.keys()):
        raise SystemExit(
            "--filename-regex must define named groups: workload, memory, threads"
        )

    event_columns = [name for name, _ in DEFAULT_EVENT_ORDER]
    target_events = {event for _, event in DEFAULT_EVENT_ORDER}
    event_to_col = {event: col for col, event in DEFAULT_EVENT_ORDER}

    rows: list[PerfSummaryRow] = []
    for file_path, file_match in iter_matching_files(args.input_dir, filename_re):
        totals_by_event = summarize_perf_file(file_path, target_events)
        totals_by_col = {
            event_to_col[event]: value for event, value in totals_by_event.items()
        }

        rows.append(
            PerfSummaryRow(
                workload=file_match.group("workload"),
                threads=file_match.group("threads"),
                memory=file_match.group("memory"),
                path=file_path,
                totals=totals_by_col,
            )
        )

    if args.sort_by_path:
        rows.sort(key=lambda r: r.path)

    with open(args.output, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["workload", "threads", "memory", *event_columns])
        for row in rows:
            writer.writerow(
                [
                    row.workload,
                    row.threads,
                    row.memory,
                    *[row.totals.get(col, 0) for col in event_columns],
                ]
            )

    print("Summary")
    print(f"  input_dir={args.input_dir}")
    print(f"  matched_files={len(rows)}")
    print(f"  output_csv={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
