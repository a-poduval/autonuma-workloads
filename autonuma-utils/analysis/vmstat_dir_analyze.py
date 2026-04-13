#!/usr/bin/env python3
"""Recursive vmstat CSV analyzer.

Scans a directory tree for vmstat files and writes one summary CSV row per file.

Default filename format:
  workload-memory_threads_vmstat.csv

For each matching file, this script computes column-wise:
  delta = last_row_value - first_row_value
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from dataclasses import dataclass


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_vmstat\.csv$"
)


@dataclass
class VmstatSummaryRow:
    workload: str
    threads: str
    memory: str
    path: str
    deltas: list[float | int]


def parse_number(value: str) -> float | int:
    """Parse a CSV cell into int when possible, otherwise float."""
    text = value.strip()
    if text == "":
        return 0

    try:
        return int(text)
    except ValueError:
        return float(text)


def compute_deltas(file_path: str) -> tuple[list[str], list[float | int]]:
    """Return (header, last_minus_first_deltas) for a vmstat CSV file."""
    with open(file_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("empty CSV") from exc

        first_row: list[str] | None = None
        last_row: list[str] | None = None

        for row in reader:
            if not row:
                continue
            if first_row is None:
                first_row = row
            last_row = row

    if first_row is None or last_row is None:
        raise ValueError("CSV has no data rows")

    if len(first_row) != len(header) or len(last_row) != len(header):
        raise ValueError("row length does not match header length")

    deltas: list[float | int] = []
    for first_val, last_val in zip(first_row, last_row):
        delta = parse_number(last_val) - parse_number(first_val)
        if isinstance(delta, float) and delta.is_integer():
            deltas.append(int(delta))
        else:
            deltas.append(delta)

    return header, deltas


def iter_matching_files(root_dir: str, filename_re: re.Pattern[str]):
    for current_root, _, files in os.walk(root_dir):
        for name in files:
            match = filename_re.match(name)
            if match is None:
                continue
            yield os.path.join(current_root, name), match


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively summarize vmstat CSV files using last-minus-first deltas."
    )
    parser.add_argument("input_dir", help="Root directory to scan recursively")
    parser.add_argument(
        "--output",
        default="vmstat_summary.csv",
        help="Output CSV path (default: vmstat_summary.csv)",
    )
    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help=(
            "Regex used to identify vmstat files from basename. Must contain named "
            "groups: workload, memory, threads."
        ),
    )
    parser.add_argument(
        "--sort-by-path",
        action="store_true",
        help="Sort rows by file path for deterministic output order",
    )
    parser.add_argument(
        "--include-id-columns",
        action="store_true",
        default=True,
        help="Prepend workload/threads/memory columns before vmstat columns",
    )
    parser.add_argument(
        "--vmstat-only-columns",
        action="store_true",
        help="Write only vmstat columns (no workload/threads/memory)",
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

    rows: list[VmstatSummaryRow] = []
    vmstat_header: list[str] | None = None
    skipped = 0

    for file_path, file_match in iter_matching_files(args.input_dir, filename_re):
        try:
            header, deltas = compute_deltas(file_path)
        except ValueError as exc:
            skipped += 1
            print(f"Skipping {file_path}: {exc}")
            continue

        if vmstat_header is None:
            vmstat_header = header
        elif vmstat_header != header:
            skipped += 1
            print(f"Skipping {file_path}: header mismatch")
            continue

        rows.append(
            VmstatSummaryRow(
                workload=file_match.group("workload"),
                threads=file_match.group("threads"),
                memory=file_match.group("memory"),
                path=file_path,
                deltas=deltas,
            )
        )

    if vmstat_header is None:
        vmstat_header = []

    if args.sort_by_path:
        rows.sort(key=lambda r: r.path)

    include_id_columns = args.include_id_columns and not args.vmstat_only_columns

    with open(args.output, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        if include_id_columns:
            writer.writerow(["workload", "threads", "memory", *vmstat_header])
        else:
            writer.writerow(vmstat_header)

        for row in rows:
            if include_id_columns:
                writer.writerow([row.workload, row.threads, row.memory, *row.deltas])
            else:
                writer.writerow(row.deltas)

    print("Summary")
    print(f"  input_dir={args.input_dir}")
    print(f"  matched_files={len(rows)}")
    print(f"  skipped_files={skipped}")
    print(f"  output_csv={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
