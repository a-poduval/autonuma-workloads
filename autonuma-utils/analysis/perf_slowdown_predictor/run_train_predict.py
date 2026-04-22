#!/usr/bin/env python3
"""Train and evaluate per-epoch remote/local predictor on curated perf logs."""

from __future__ import annotations

import argparse
from collections import Counter

import numpy as np

from .constants import DEFAULT_FILENAME_REGEX, DEFAULT_TRACKED_EVENTS
from .evaluation import apply_predictions, build_file_summaries, compute_split_metrics
from .feature_engineering import (
    DEFAULT_FEATURE_COLUMNS,
    FAST_GB_SOURCE_ARG,
    FAST_GB_SOURCE_FILENAME_MEMORY,
    RSS_GB_SOURCE_ARG,
    RSS_GB_SOURCE_MANIFEST,
    TOTAL_ACCESS_SOURCE_LOCAL_REMOTE,
    TOTAL_ACCESS_SOURCE_OR_DEMAND,
    build_epoch_feature_rows,
)
from .file_matching import compile_filename_regex
from .input_resolution import collect_selected_files
from .model_ridge import RidgeShareModel
from .pipeline import build_windowed_file_result
from .prediction_outputs import (
    write_epoch_prediction_csv,
    write_file_prediction_csv,
    write_split_metrics_csv,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train on curated perf logs and predict remote/local accesses per epoch "
            "from total+unique/history+latency features."
        )
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
        "--manifest-csv",
        default=None,
        help="Curated selection manifest CSV (path, optional split, optional tag)",
    )
    parser.add_argument(
        "--manifest-root",
        default=None,
        help="Base directory for relative manifest paths",
    )
    parser.add_argument(
        "--include-path",
        action="append",
        default=[],
        help="Explicit perf file to include (repeatable)",
    )
    parser.add_argument(
        "--default-split",
        default="unspecified",
        help="Split label assigned to scan/include files",
    )
    parser.add_argument(
        "--split-filter",
        action="append",
        default=[],
        help="If set, keep only these split labels (repeatable)",
    )

    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help="Filename regex with named groups workload/memory/threads",
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
        help="Sort parsed files by path",
    )

    parser.add_argument(
        "--rss-source",
        choices=[RSS_GB_SOURCE_ARG, RSS_GB_SOURCE_MANIFEST],
        default=RSS_GB_SOURCE_ARG,
        help="RSS source for features: global arg or per-row manifest rss",
    )
    parser.add_argument(
        "--rss-gb",
        type=float,
        default=None,
        help="Explicit workload RSS in GB when --rss-source=arg",
    )
    parser.add_argument(
        "--fast-gb-source",
        choices=[FAST_GB_SOURCE_FILENAME_MEMORY, FAST_GB_SOURCE_ARG],
        default=FAST_GB_SOURCE_FILENAME_MEMORY,
        help="Fast-tier size source for features",
    )
    parser.add_argument(
        "--fast-gb",
        type=float,
        default=None,
        help="Explicit fast-tier GB when --fast-gb-source=arg",
    )
    parser.add_argument(
        "--total-access-source",
        choices=[TOTAL_ACCESS_SOURCE_LOCAL_REMOTE, TOTAL_ACCESS_SOURCE_OR_DEMAND],
        default=TOTAL_ACCESS_SOURCE_LOCAL_REMOTE,
        help="Definition of total accesses used for prediction target decomposition",
    )
    parser.add_argument(
        "--ema-alpha",
        type=float,
        default=0.2,
        help="EMA alpha for historic hotness feature",
    )
    parser.add_argument(
        "--ridge-alpha",
        type=float,
        default=1.0,
        help="Ridge regularization strength",
    )
    parser.add_argument(
        "--train-split",
        action="append",
        default=[],
        help="Split label used for training (repeatable, default: train)",
    )
    parser.add_argument(
        "--predict-split",
        action="append",
        default=[],
        help="If set, only output predictions for these split labels",
    )
    parser.add_argument(
        "--feature-columns",
        default=",".join(DEFAULT_FEATURE_COLUMNS),
        help="Comma-separated feature column names",
    )

    parser.add_argument(
        "--epoch-output",
        default="perf_epoch_predictions.csv",
        help="Epoch-level prediction output CSV",
    )
    parser.add_argument(
        "--file-output",
        default="perf_file_predictions.csv",
        help="Per-file total prediction output CSV",
    )
    parser.add_argument(
        "--metrics-output",
        default="perf_split_metrics.csv",
        help="Split-level metrics output CSV",
    )

    return parser


def _parse_feature_columns(text: str) -> list[str]:
    cols = [col.strip() for col in text.split(",") if col.strip()]
    if not cols:
        raise ValueError("feature column list cannot be empty")
    return cols


def _rows_to_matrix(rows, feature_columns: list[str]) -> np.ndarray:
    return np.array(
        [[float(getattr(row, col)) for col in feature_columns] for row in rows],
        dtype=float,
    )


def _target_remote_share(rows) -> np.ndarray:
    return np.array([float(row.remote_share_actual) for row in rows], dtype=float)


def _append_overall_metric(metrics: list[dict[str, float | int | str]], rows) -> None:
    if not rows:
        return

    remote_errors = [row.err_remote_accesses or 0.0 for row in rows]
    local_errors = [row.err_local_accesses or 0.0 for row in rows]
    share_errors = [(row.pred_remote_share or 0.0) - row.remote_share_actual for row in rows]

    def mae(values):
        return sum(abs(v) for v in values) / len(values)

    def rmse(values):
        return float(np.sqrt(sum(v * v for v in values) / len(values)))

    metrics.append(
        {
            "split": "__all__",
            "epochs": len(rows),
            "remote_mae": mae(remote_errors),
            "remote_rmse": rmse(remote_errors),
            "local_mae": mae(local_errors),
            "local_rmse": rmse(local_errors),
            "remote_share_mae": mae(share_errors),
            "remote_share_rmse": rmse(share_errors),
        }
    )


def main() -> int:
    args = build_arg_parser().parse_args()

    if args.safety_margin_sec < 0.0:
        raise SystemExit("--safety-margin-sec must be >= 0")
    if args.rss_source == RSS_GB_SOURCE_ARG:
        if args.rss_gb is None or args.rss_gb <= 0.0:
            raise SystemExit("--rss-gb must be > 0 when --rss-source=arg")
    if args.rss_source == RSS_GB_SOURCE_MANIFEST and not args.manifest_csv:
        raise SystemExit("--rss-source=manifest requires --manifest-csv")

    try:
        feature_columns = _parse_feature_columns(args.feature_columns)
        filename_re = compile_filename_regex(args.filename_regex)
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
    parsed_files = [
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
        parsed_files.sort(key=lambda item: item.path)

    epoch_rows = build_epoch_feature_rows(
        parsed_files,
        rss_gb_source=args.rss_source,
        rss_gb_arg=args.rss_gb,
        fast_gb_source=args.fast_gb_source,
        fast_gb_arg=args.fast_gb,
        total_access_source=args.total_access_source,
        ema_alpha=args.ema_alpha,
    )

    predict_splits = set(args.predict_split) if args.predict_split else None
    if predict_splits is not None:
        epoch_rows = [row for row in epoch_rows if row.split in predict_splits]

    train_splits = set(args.train_split) if args.train_split else {"train"}
    train_rows = [
        row for row in epoch_rows if row.split in train_splits and row.trainable == 1
    ]
    if not train_rows:
        raise SystemExit(
            "No trainable rows found for training split(s): "
            f"{sorted(train_splits)}"
        )

    x_train = _rows_to_matrix(train_rows, feature_columns)
    y_train = _target_remote_share(train_rows)

    model = RidgeShareModel(ridge_alpha=args.ridge_alpha)
    model.fit(x_train, y_train)

    x_all = _rows_to_matrix(epoch_rows, feature_columns)
    pred_share = model.predict(x_all)
    apply_predictions(epoch_rows, pred_share.tolist())

    file_summaries = build_file_summaries(epoch_rows)
    split_metrics = compute_split_metrics(epoch_rows)
    _append_overall_metric(split_metrics, epoch_rows)

    write_epoch_prediction_csv(args.epoch_output, epoch_rows)
    write_file_prediction_csv(args.file_output, file_summaries)
    write_split_metrics_csv(args.metrics_output, split_metrics)

    split_counts = Counter(row.split for row in epoch_rows)
    print("Summary")
    if args.input_dir:
        print(f"  input_dir={args.input_dir}")
    if args.manifest_csv:
        print(f"  manifest_csv={args.manifest_csv}")
    print(f"  selected_files={len(parsed_files)}")
    print(f"  epoch_rows={len(epoch_rows)}")
    print(f"  train_rows={len(train_rows)}")
    print(f"  rss_source={args.rss_source}")
    if args.rss_source == RSS_GB_SOURCE_ARG:
        print(f"  rss_gb={args.rss_gb}")
    print(f"  split_counts={dict(split_counts)}")
    print(f"  feature_columns={feature_columns}")
    print(f"  epoch_output={args.epoch_output}")
    print(f"  file_output={args.file_output}")
    print(f"  metrics_output={args.metrics_output}")

    print("Split metrics")
    for metric in split_metrics:
        print(
            "  "
            f"{metric['split']}: epochs={metric['epochs']} "
            f"remote_mae={metric['remote_mae']:.6f} "
            f"local_mae={metric['local_mae']:.6f} "
            f"share_mae={metric['remote_share_mae']:.6f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
