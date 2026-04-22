"""CSV outputs for training/prediction stage."""

from __future__ import annotations

import csv

from .evaluation import FilePredictionSummary
from .feature_engineering import EpochFeatureRow


def write_epoch_prediction_csv(path: str, rows: list[EpochFeatureRow]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "split",
                "selection_tag",
                "workload",
                "threads",
                "memory",
                "path",
                "epoch_index",
                "timestamp_s",
                "rel_timestamp_s",
                "rss_gb",
                "fast_gb",
                "total_accesses",
                "dtlb_walks",
                "unique_accesses",
                "unique_fraction",
                "hotness",
                "hotness_ema_prev",
                "hotness_delta",
                "cum_unique_to_fast_capacity",
                "mem_latency_cycles",
                "tlb_latency_cycles",
                "local_accesses_actual",
                "remote_accesses_actual",
                "remote_share_actual",
                "pred_remote_share",
                "pred_remote_accesses",
                "pred_local_accesses",
                "err_remote_accesses",
                "err_local_accesses",
            ]
        )

        for row in rows:
            writer.writerow(
                [
                    row.split,
                    row.selection_tag,
                    row.workload,
                    row.threads,
                    row.memory,
                    row.path,
                    row.epoch_index,
                    row.timestamp_s,
                    row.rel_timestamp_s,
                    row.rss_gb,
                    row.fast_gb,
                    row.total_accesses,
                    row.dtlb_walks,
                    row.unique_accesses,
                    row.unique_fraction,
                    row.hotness,
                    row.hotness_ema_prev,
                    row.hotness_delta,
                    row.cum_unique_to_fast_capacity,
                    row.mem_latency_cycles,
                    row.tlb_latency_cycles,
                    row.local_accesses_actual,
                    row.remote_accesses_actual,
                    row.remote_share_actual,
                    row.pred_remote_share,
                    row.pred_remote_accesses,
                    row.pred_local_accesses,
                    row.err_remote_accesses,
                    row.err_local_accesses,
                ]
            )


def write_file_prediction_csv(path: str, rows: list[FilePredictionSummary]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "split",
                "selection_tag",
                "workload",
                "threads",
                "memory",
                "path",
                "epochs",
                "total_accesses_sum",
                "actual_remote_sum",
                "actual_local_sum",
                "pred_remote_sum",
                "pred_local_sum",
                "actual_remote_share",
                "pred_remote_share",
                "remote_sum_error",
                "local_sum_error",
            ]
        )

        for row in rows:
            writer.writerow(
                [
                    row.split,
                    row.selection_tag,
                    row.workload,
                    row.threads,
                    row.memory,
                    row.path,
                    row.epochs,
                    row.total_accesses_sum,
                    row.actual_remote_sum,
                    row.actual_local_sum,
                    row.pred_remote_sum,
                    row.pred_local_sum,
                    row.actual_remote_share,
                    row.pred_remote_share,
                    row.remote_sum_error,
                    row.local_sum_error,
                ]
            )


def write_split_metrics_csv(path: str, metrics: list[dict[str, float | int | str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "split",
                "epochs",
                "remote_mae",
                "remote_rmse",
                "local_mae",
                "local_rmse",
                "remote_share_mae",
                "remote_share_rmse",
            ]
        )
        for row in metrics:
            writer.writerow(
                [
                    row.get("split"),
                    row.get("epochs"),
                    row.get("remote_mae"),
                    row.get("remote_rmse"),
                    row.get("local_mae"),
                    row.get("local_rmse"),
                    row.get("remote_share_mae"),
                    row.get("remote_share_rmse"),
                ]
            )
