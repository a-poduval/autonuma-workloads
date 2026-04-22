#!/usr/bin/env python3
"""Simple workflow entrypoint for training and prediction.

Examples:
  python main.py --train /path/train_logs --val /path/val_logs
  python main.py --predict /path/log_dir_or_file
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter

import numpy as np


if __package__ in {None, ""}:
    import sys

    this_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(this_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from perf_slowdown_predictor.constants import DEFAULT_FILENAME_REGEX, DEFAULT_TRACKED_EVENTS
    from perf_slowdown_predictor.evaluation import (
        apply_predictions,
        build_file_summaries,
        compute_split_metrics,
    )
    from perf_slowdown_predictor.feature_engineering import (
        DEFAULT_FEATURE_COLUMNS,
        FAST_GB_SOURCE_ARG,
        FAST_GB_SOURCE_FILENAME_MEMORY,
        RSS_GB_SOURCE_MANIFEST,
        TOTAL_ACCESS_SOURCE_LOCAL_REMOTE,
        TOTAL_ACCESS_SOURCE_OR_DEMAND,
        build_epoch_feature_rows,
    )
    from perf_slowdown_predictor.file_matching import compile_filename_regex, iter_matching_files
    from perf_slowdown_predictor.input_resolution import collect_selected_files
    from perf_slowdown_predictor.model_ridge import RidgeShareModel
    from perf_slowdown_predictor.models import ParsedPerfFile
    from perf_slowdown_predictor.pipeline import build_windowed_file_result
    from perf_slowdown_predictor.prediction_outputs import (
        write_epoch_prediction_csv,
        write_file_prediction_csv,
        write_split_metrics_csv,
    )
    from perf_slowdown_predictor.size_parsing import memory_to_gb
else:
    from .constants import DEFAULT_FILENAME_REGEX, DEFAULT_TRACKED_EVENTS
    from .evaluation import apply_predictions, build_file_summaries, compute_split_metrics
    from .feature_engineering import (
        DEFAULT_FEATURE_COLUMNS,
        FAST_GB_SOURCE_ARG,
        FAST_GB_SOURCE_FILENAME_MEMORY,
        RSS_GB_SOURCE_MANIFEST,
        TOTAL_ACCESS_SOURCE_LOCAL_REMOTE,
        TOTAL_ACCESS_SOURCE_OR_DEMAND,
        build_epoch_feature_rows,
    )
    from .file_matching import compile_filename_regex, iter_matching_files
    from .input_resolution import collect_selected_files
    from .model_ridge import RidgeShareModel
    from .models import ParsedPerfFile
    from .pipeline import build_windowed_file_result
    from .prediction_outputs import (
        write_epoch_prediction_csv,
        write_file_prediction_csv,
        write_split_metrics_csv,
    )
    from .size_parsing import memory_to_gb


MODEL_STATE_FILENAME = "model_state.json"


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


def _collect_dir_selected(
    directory: str,
    split: str,
    filename_re,
) -> list[tuple[str, object, str, str | None, float | None]]:
    if not os.path.isdir(directory):
        raise ValueError(f"Directory not found: {directory}")

    out = []
    for file_path, file_match in iter_matching_files(directory, filename_re):
        out.append((file_path, file_match, split, None, None))
    return out


def _collect_predict_selected(
    predict_path: str,
    filename_re,
) -> list[tuple[str, object, str, str | None, float | None]]:
    if os.path.isdir(predict_path):
        return _collect_dir_selected(predict_path, "predict", filename_re)

    if os.path.isfile(predict_path):
        basename = os.path.basename(predict_path)
        match = filename_re.match(basename)
        if match is None:
            raise ValueError(
                "Predict file does not match filename regex: "
                f"{predict_path}"
            )
        return [(os.path.abspath(predict_path), match, "predict", None, None)]

    raise ValueError(f"Predict path not found: {predict_path}")


def _resolve_rss_by_workload(
    parsed_files: list[ParsedPerfFile],
    rss_gb_arg: float | None,
) -> dict[str, float]:
    if rss_gb_arg is not None:
        if rss_gb_arg <= 0.0:
            raise ValueError("--rss-gb must be > 0")
        return {p.workload: rss_gb_arg for p in parsed_files}

    rss_by_workload: dict[str, float] = {}

    # Prefer manifest RSS when present; otherwise infer from max memory token.
    for parsed in parsed_files:
        if parsed.rss_gb is not None and parsed.rss_gb > 0.0:
            prev = rss_by_workload.get(parsed.workload)
            if prev is None or parsed.rss_gb > prev:
                rss_by_workload[parsed.workload] = parsed.rss_gb

    for parsed in parsed_files:
        if parsed.workload in rss_by_workload:
            continue

        inferred = memory_to_gb(parsed.memory)
        if inferred is None or inferred <= 0.0:
            raise ValueError(
                "Unable to infer RSS from memory token and no manifest/rss arg for file: "
                f"{parsed.path}"
            )
        prev = rss_by_workload.get(parsed.workload)
        if prev is None or inferred > prev:
            rss_by_workload[parsed.workload] = inferred

    return rss_by_workload


def _assign_rss_to_files(
    parsed_files: list[ParsedPerfFile],
    rss_by_workload: dict[str, float],
) -> None:
    for parsed in parsed_files:
        rss = rss_by_workload.get(parsed.workload)
        if rss is None or rss <= 0.0:
            raise ValueError(f"Missing RSS for workload: {parsed.workload}")
        parsed.rss_gb = rss


def _save_model_state(
    path: str,
    model: RidgeShareModel,
    *,
    feature_columns: list[str],
    ema_alpha: float,
    total_access_source: str,
    fast_gb_source: str,
    fast_gb_arg: float | None,
    safety_margin_sec: float,
    disable_runtime_window: bool,
    filename_regex: str,
    rss_by_workload: dict[str, float],
) -> None:
    if model._mean is None or model._std is None or model._weights is None:
        raise ValueError("Cannot save model before fit")

    state = {
        "model_type": "ridge_remote_share",
        "ridge_alpha": model.ridge_alpha,
        "feature_columns": feature_columns,
        "ema_alpha": ema_alpha,
        "total_access_source": total_access_source,
        "fast_gb_source": fast_gb_source,
        "fast_gb_arg": fast_gb_arg,
        "safety_margin_sec": safety_margin_sec,
        "disable_runtime_window": disable_runtime_window,
        "filename_regex": filename_regex,
        "rss_by_workload_gb": rss_by_workload,
        "mean": model._mean.tolist(),
        "std": model._std.tolist(),
        "weights": model._weights.tolist(),
    }

    with open(path, "w", encoding="utf-8") as out:
        json.dump(state, out, indent=2, sort_keys=True)


def _load_model_state(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _restore_model_from_state(state: dict) -> RidgeShareModel:
    model = RidgeShareModel(ridge_alpha=float(state["ridge_alpha"]))
    model._mean = np.array(state["mean"], dtype=float)
    model._std = np.array(state["std"], dtype=float)
    model._weights = np.array(state["weights"], dtype=float)
    return model


def _prepare_parsed_files(
    selected_files,
    *,
    target_events: set[str],
    safety_margin_sec: float,
    disable_runtime_window: bool,
    sort_by_path: bool,
) -> list[ParsedPerfFile]:
    parsed_files = [
        build_windowed_file_result(
            file_path=file_path,
            file_match=file_match,
            split=split,
            selection_tag=tag,
            rss_gb=rss_gb,
            target_events=target_events,
            safety_margin_sec=safety_margin_sec,
            disable_runtime_window=disable_runtime_window,
        )
        for file_path, file_match, split, tag, rss_gb in selected_files
    ]

    if sort_by_path:
        parsed_files.sort(key=lambda item: item.path)
    return parsed_files


def _train_mode(args) -> int:
    filename_re = compile_filename_regex(args.filename_regex)
    target_events = set(DEFAULT_TRACKED_EVENTS)

    if args.manifest_csv:
        selected_files = collect_selected_files(
            input_dir=None,
            manifest_csv=args.manifest_csv,
            manifest_root=args.manifest_root,
            include_paths=[],
            default_split="unspecified",
            split_filter=[],
            filename_re=filename_re,
        )
    else:
        if not args.train:
            raise ValueError("--train is required unless --manifest-csv is provided")

        selected_files = []
        selected_files.extend(_collect_dir_selected(args.train, "train", filename_re))
        if args.val:
            selected_files.extend(_collect_dir_selected(args.val, "val", filename_re))
        if args.reference:
            selected_files.extend(_collect_dir_selected(args.reference, "reference", filename_re))

    parsed_files = _prepare_parsed_files(
        selected_files,
        target_events=target_events,
        safety_margin_sec=args.safety_margin_sec,
        disable_runtime_window=args.disable_runtime_window,
        sort_by_path=args.sort_by_path,
    )

    rss_by_workload = _resolve_rss_by_workload(parsed_files, args.rss_gb)
    _assign_rss_to_files(parsed_files, rss_by_workload)

    feature_columns = _parse_feature_columns(args.feature_columns)
    epoch_rows = build_epoch_feature_rows(
        parsed_files,
        rss_gb_source=RSS_GB_SOURCE_MANIFEST,
        rss_gb_arg=None,
        fast_gb_source=args.fast_gb_source,
        fast_gb_arg=args.fast_gb,
        total_access_source=args.total_access_source,
        ema_alpha=args.ema_alpha,
    )

    train_rows = [row for row in epoch_rows if row.split == "train" and row.trainable == 1]
    if not train_rows:
        raise ValueError("No trainable rows found in split=train")

    model = RidgeShareModel(ridge_alpha=args.ridge_alpha)
    model.fit(_rows_to_matrix(train_rows, feature_columns), _target_remote_share(train_rows))

    pred_share = model.predict(_rows_to_matrix(epoch_rows, feature_columns))
    apply_predictions(epoch_rows, pred_share.tolist())

    file_summaries = build_file_summaries(epoch_rows)
    split_metrics = compute_split_metrics(epoch_rows)
    _append_overall_metric(split_metrics, epoch_rows)

    os.makedirs(args.debug_dir, exist_ok=True)
    epoch_output = os.path.join(args.debug_dir, "train_epoch_predictions.csv")
    file_output = os.path.join(args.debug_dir, "train_file_predictions.csv")
    metrics_output = os.path.join(args.debug_dir, "train_split_metrics.csv")
    model_output = args.model_path or os.path.join(args.debug_dir, MODEL_STATE_FILENAME)

    write_epoch_prediction_csv(epoch_output, epoch_rows)
    write_file_prediction_csv(file_output, file_summaries)
    write_split_metrics_csv(metrics_output, split_metrics)
    _save_model_state(
        model_output,
        model,
        feature_columns=feature_columns,
        ema_alpha=args.ema_alpha,
        total_access_source=args.total_access_source,
        fast_gb_source=args.fast_gb_source,
        fast_gb_arg=args.fast_gb,
        safety_margin_sec=args.safety_margin_sec,
        disable_runtime_window=args.disable_runtime_window,
        filename_regex=args.filename_regex,
        rss_by_workload=rss_by_workload,
    )

    split_counts = Counter(row.split for row in epoch_rows)
    print("Training complete")
    print(f"  files={len(parsed_files)}")
    print(f"  epochs={len(epoch_rows)}")
    print(f"  train_epochs={len(train_rows)}")
    print(f"  split_counts={dict(split_counts)}")
    print(f"  debug_dir={args.debug_dir}")
    print(f"  model={model_output}")
    print(f"  epoch_output={epoch_output}")
    print(f"  file_output={file_output}")
    print(f"  metrics_output={metrics_output}")

    return 0


def _predict_mode(args) -> int:
    model_path = args.model_path or os.path.join(args.debug_dir, MODEL_STATE_FILENAME)
    if not os.path.isfile(model_path):
        raise ValueError(f"Model state file not found: {model_path}")

    state = _load_model_state(model_path)
    filename_re = compile_filename_regex(state.get("filename_regex", DEFAULT_FILENAME_REGEX))
    target_events = set(DEFAULT_TRACKED_EVENTS)

    selected_files = _collect_predict_selected(args.predict, filename_re)
    parsed_files = _prepare_parsed_files(
        selected_files,
        target_events=target_events,
        safety_margin_sec=float(state.get("safety_margin_sec", 3.0)),
        disable_runtime_window=bool(state.get("disable_runtime_window", False)),
        sort_by_path=args.sort_by_path,
    )

    saved_rss = {
        str(k): float(v)
        for k, v in dict(state.get("rss_by_workload_gb", {})).items()
    }

    # Override all workloads if explicitly provided.
    if args.rss_gb is not None:
        if args.rss_gb <= 0.0:
            raise ValueError("--rss-gb must be > 0")
        rss_by_workload = {p.workload: args.rss_gb for p in parsed_files}
    else:
        rss_by_workload = dict(saved_rss)
        for parsed in parsed_files:
            if parsed.workload in rss_by_workload:
                continue
            inferred = memory_to_gb(parsed.memory)
            if inferred is None or inferred <= 0.0:
                raise ValueError(
                    "Cannot infer RSS for workload and none saved in model: "
                    f"{parsed.workload}"
                )
            prev = rss_by_workload.get(parsed.workload)
            if prev is None or inferred > prev:
                rss_by_workload[parsed.workload] = inferred

    _assign_rss_to_files(parsed_files, rss_by_workload)

    feature_columns = list(state["feature_columns"])
    epoch_rows = build_epoch_feature_rows(
        parsed_files,
        rss_gb_source=RSS_GB_SOURCE_MANIFEST,
        rss_gb_arg=None,
        fast_gb_source=str(state.get("fast_gb_source", FAST_GB_SOURCE_FILENAME_MEMORY)),
        fast_gb_arg=state.get("fast_gb_arg"),
        total_access_source=str(
            state.get("total_access_source", TOTAL_ACCESS_SOURCE_LOCAL_REMOTE)
        ),
        ema_alpha=float(state.get("ema_alpha", 0.2)),
    )

    model = _restore_model_from_state(state)
    pred_share = model.predict(_rows_to_matrix(epoch_rows, feature_columns))
    apply_predictions(epoch_rows, pred_share.tolist())

    file_summaries = build_file_summaries(epoch_rows)
    split_metrics = compute_split_metrics(epoch_rows)
    _append_overall_metric(split_metrics, epoch_rows)

    os.makedirs(args.debug_dir, exist_ok=True)
    epoch_output = os.path.join(args.debug_dir, "predict_epoch_predictions.csv")
    file_output = os.path.join(args.debug_dir, "predict_file_predictions.csv")
    metrics_output = os.path.join(args.debug_dir, "predict_split_metrics.csv")

    write_epoch_prediction_csv(epoch_output, epoch_rows)
    write_file_prediction_csv(file_output, file_summaries)
    write_split_metrics_csv(metrics_output, split_metrics)

    split_counts = Counter(row.split for row in epoch_rows)
    print("Prediction complete")
    print(f"  files={len(parsed_files)}")
    print(f"  epochs={len(epoch_rows)}")
    print(f"  split_counts={dict(split_counts)}")
    print(f"  debug_dir={args.debug_dir}")
    print(f"  model={model_path}")
    print(f"  epoch_output={epoch_output}")
    print(f"  file_output={file_output}")
    print(f"  metrics_output={metrics_output}")

    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Simple perf slowdown workflow: train with --train/--val (or optional "
            "manifest), then run --predict on a log dir or file."
        )
    )

    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument(
        "--train",
        help="Directory containing training logs",
    )
    mode.add_argument(
        "--predict",
        help="Directory or single perf CSV for inference",
    )

    parser.add_argument(
        "--val",
        default=None,
        help="Directory containing validation logs (optional)",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Directory containing reference logs (optional)",
    )

    parser.add_argument(
        "--manifest-csv",
        default=None,
        help=(
            "Optional curated manifest for training. If set, --train/--val/--reference "
            "directories are ignored for selection."
        ),
    )
    parser.add_argument(
        "--manifest-root",
        default=None,
        help="Base directory for relative manifest paths",
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
        help="Extra seconds added to runtime-window filtering",
    )
    parser.add_argument(
        "--disable-runtime-window",
        action="store_true",
        help="Disable runtime-window filtering",
    )
    parser.add_argument(
        "--sort-by-path",
        action="store_true",
        help="Sort files by path",
    )

    parser.add_argument(
        "--rss-gb",
        type=float,
        default=None,
        help=(
            "Optional RSS override in GB. If omitted in training, RSS is inferred from "
            "manifest rss column (if present) or max memory per workload."
        ),
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
        help="Fast-tier size in GB when --fast-gb-source=arg",
    )
    parser.add_argument(
        "--total-access-source",
        choices=[TOTAL_ACCESS_SOURCE_LOCAL_REMOTE, TOTAL_ACCESS_SOURCE_OR_DEMAND],
        default=TOTAL_ACCESS_SOURCE_LOCAL_REMOTE,
        help="Definition of total accesses",
    )
    parser.add_argument(
        "--ema-alpha",
        type=float,
        default=0.2,
        help="EMA alpha for hotness history",
    )
    parser.add_argument(
        "--ridge-alpha",
        type=float,
        default=1.0,
        help="Ridge regularization strength",
    )
    parser.add_argument(
        "--feature-columns",
        default=",".join(DEFAULT_FEATURE_COLUMNS),
        help="Comma-separated feature list",
    )

    parser.add_argument(
        "--debug-dir",
        default="debug",
        help="Folder for CSV outputs and model state",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help=(
            "Path for model state JSON. Default: debug/model_state.json. "
            "Used in both training save and predict load."
        ),
    )

    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    try:
        if args.predict:
            if args.train or args.val or args.reference or args.manifest_csv:
                raise ValueError(
                    "--predict cannot be combined with training selection options"
                )
            return _predict_mode(args)

        if not args.train and not args.manifest_csv:
            raise ValueError(
                "Training requires --train <dir> or --manifest-csv <file>"
            )

        return _train_mode(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
