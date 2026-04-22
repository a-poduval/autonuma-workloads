"""Evaluation helpers for per-epoch and per-file prediction quality."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .feature_engineering import EpochFeatureRow


@dataclass
class FilePredictionSummary:
    split: str
    selection_tag: str | None
    workload: str
    threads: str
    memory: str
    path: str
    epochs: int
    total_accesses_sum: float
    actual_remote_sum: float
    actual_local_sum: float
    pred_remote_sum: float
    pred_local_sum: float
    actual_remote_share: float
    pred_remote_share: float
    remote_sum_error: float
    local_sum_error: float


def apply_predictions(rows: list[EpochFeatureRow], pred_remote_share: list[float]) -> None:
    if len(rows) != len(pred_remote_share):
        raise ValueError("Prediction length does not match row count")

    for row, pred_share in zip(rows, pred_remote_share):
        share = max(0.0, min(1.0, float(pred_share)))
        pred_remote = row.total_accesses * share
        pred_local = row.total_accesses - pred_remote

        row.pred_remote_share = share
        row.pred_remote_accesses = pred_remote
        row.pred_local_accesses = pred_local
        row.err_remote_accesses = pred_remote - row.remote_accesses_actual
        row.err_local_accesses = pred_local - row.local_accesses_actual


def build_file_summaries(rows: list[EpochFeatureRow]) -> list[FilePredictionSummary]:
    grouped: dict[str, list[EpochFeatureRow]] = {}
    for row in rows:
        grouped.setdefault(row.path, []).append(row)

    out: list[FilePredictionSummary] = []
    for _, file_rows in grouped.items():
        first = file_rows[0]

        total_accesses_sum = sum(r.total_accesses for r in file_rows)
        actual_remote_sum = sum(r.remote_accesses_actual for r in file_rows)
        actual_local_sum = sum(r.local_accesses_actual for r in file_rows)
        pred_remote_sum = sum((r.pred_remote_accesses or 0.0) for r in file_rows)
        pred_local_sum = sum((r.pred_local_accesses or 0.0) for r in file_rows)

        actual_remote_share = (
            (actual_remote_sum / total_accesses_sum) if total_accesses_sum > 0.0 else 0.0
        )
        pred_remote_share = (
            (pred_remote_sum / total_accesses_sum) if total_accesses_sum > 0.0 else 0.0
        )

        out.append(
            FilePredictionSummary(
                split=first.split,
                selection_tag=first.selection_tag,
                workload=first.workload,
                threads=first.threads,
                memory=first.memory,
                path=first.path,
                epochs=len(file_rows),
                total_accesses_sum=total_accesses_sum,
                actual_remote_sum=actual_remote_sum,
                actual_local_sum=actual_local_sum,
                pred_remote_sum=pred_remote_sum,
                pred_local_sum=pred_local_sum,
                actual_remote_share=actual_remote_share,
                pred_remote_share=pred_remote_share,
                remote_sum_error=pred_remote_sum - actual_remote_sum,
                local_sum_error=pred_local_sum - actual_local_sum,
            )
        )

    out.sort(key=lambda item: item.path)
    return out


def _mae(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(abs(v) for v in values) / len(values)


def _rmse(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def compute_split_metrics(rows: list[EpochFeatureRow]):
    grouped: dict[str, list[EpochFeatureRow]] = {}
    for row in rows:
        grouped.setdefault(row.split, []).append(row)

    metrics = []
    for split, split_rows in sorted(grouped.items()):
        remote_errors = [r.err_remote_accesses or 0.0 for r in split_rows]
        local_errors = [r.err_local_accesses or 0.0 for r in split_rows]
        share_errors = [
            (r.pred_remote_share or 0.0) - r.remote_share_actual for r in split_rows
        ]

        metrics.append(
            {
                "split": split,
                "epochs": len(split_rows),
                "remote_mae": _mae(remote_errors),
                "remote_rmse": _rmse(remote_errors),
                "local_mae": _mae(local_errors),
                "local_rmse": _rmse(local_errors),
                "remote_share_mae": _mae(share_errors),
                "remote_share_rmse": _rmse(share_errors),
            }
        )

    return metrics
