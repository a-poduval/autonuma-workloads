#!/usr/bin/env python3
"""Run parse/filter stage for perf slowdown predictor.

This stage only does:
- perf CSV parsing
- runtime window extraction from sibling logs
- tail-window filtering
- CSV emission of file metadata + filtered epochs
"""

from __future__ import annotations

import argparse
import os
from collections import Counter

from .constants import DEFAULT_FILENAME_REGEX, DEFAULT_TRACKED_EVENTS
from .file_matching import compile_filename_regex
from .input_resolution import collect_selected_files
from .outputs import write_epoch_csv, write_file_summary_csv
from .pipeline import build_windowed_file_result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse + runtime-filter perf logs into modular CSV outputs."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        help=(
            "Root directory to scan recursively. Optional when using "
            "--manifest-csv or --include-path."
        ),
    )
    parser.add_argument(
        "--file-output",
        default="perf_parse_filter_files.csv",
        help="Output CSV for per-file parse/filter metadata",
    )
    parser.add_argument(
        "--epoch-output",
        default="perf_parse_filter_epochs.csv",
        help="Output CSV for per-epoch filtered rows",
    )
    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help="Filename regex with named groups workload/memory/threads",
    )
    parser.add_argument(
        "--manifest-csv",
        default=None,
        help=(
            "Curated selection manifest CSV with column 'path' and optional "
            "columns 'split' and 'tag'."
        ),
    )
    parser.add_argument(
        "--manifest-root",
        default=None,
        help="Base directory used to resolve relative paths from --manifest-csv",
    )
    parser.add_argument(
        "--include-path",
        action="append",
        default=[],
        help="Explicit perf file path to include (repeatable)",
    )
    parser.add_argument(
        "--default-split",
        default="unspecified",
        help="Split label used for scan/include files (default: unspecified)",
    )
    parser.add_argument(
        "--split-filter",
        action="append",
        default=[],
        help="If set, keep only rows with these split labels (repeatable)",
    )
    parser.add_argument(
        "--safety-margin-sec",
        type=float,
        default=3.0,
        help="Extra seconds added to execution window",
    )
    parser.add_argument(
        "--disable-runtime-window",
        action="store_true",
        help="Disable runtime tail-window filtering and keep full timeline",
    )
    parser.add_argument(
        "--sort-by-path",
        action="store_true",
        help="Sort rows by path for deterministic output",
    )
    return parser
def main() -> int:
    args = build_arg_parser().parse_args()

    if args.safety_margin_sec < 0:
        raise SystemExit("--safety-margin-sec must be >= 0")

    try:
        filename_re = compile_filename_regex(args.filename_regex)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    try:
        selected_files = collect_selected_files(
            input_dir=args.input_dir,
            manifest_csv=args.manifest_csv,
            manifest_root=args.manifest_root,
            include_paths=args.include_path,
            default_split=args.default_split,
            split_filter=args.split_filter,
            filename_re=filename_re,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    target_events = set(DEFAULT_TRACKED_EVENTS)

    rows = [
        build_windowed_file_result(
            file_path=file_path,
            file_match=file_match,
            split=split,
            selection_tag=tag,
            rss_gb=rss_gb,
            target_events=target_events,
            safety_margin_sec=args.safety_margin_sec,
            disable_runtime_window=args.disable_runtime_window,
        )
        for file_path, file_match, split, tag, rss_gb in selected_files
    ]

    if args.sort_by_path:
        rows.sort(key=lambda item: item.path)

    write_file_summary_csv(args.file_output, rows)
    write_epoch_csv(args.epoch_output, rows, DEFAULT_TRACKED_EVENTS)

    windowed_files = sum(1 for row in rows if row.applied_window_seconds is not None)
    split_counts = Counter(row.split for row in rows)

    print("Summary")
    if args.input_dir:
        print(f"  input_dir={args.input_dir}")
    if args.manifest_csv:
        print(f"  manifest_csv={args.manifest_csv}")
    if args.include_path:
        print(f"  include_paths={len(args.include_path)}")
    print(f"  matched_files={len(rows)}")
    print(f"  windowed_files={windowed_files}")
    print(f"  split_counts={dict(split_counts)}")
    print(f"  file_output={args.file_output}")
    print(f"  epoch_output={args.epoch_output}")

    # Placeholder for next step (no implementation):
    # - Decide exact total_accesses definition for modeling features.
    # - Use miss_causes_a_walk explicitly as walk-count signal in feature derivation.
    # - Add explicit RSS + fast-tier inputs to downstream feature set.
    # - Build sequence dataset for LSTM training/evaluation.
    # - Add inference mode from one fast-memory reference run.
    # - Restrict prediction target to non-reference splits.

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
