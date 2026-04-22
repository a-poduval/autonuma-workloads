#!/usr/bin/env python3
"""Generate workload-level perf trend plots from pebs-perf-slowdown logs.

This script scans a directory tree for ``*_perf.csv`` files, groups them by
workload subdirectory, and emits one 2x2 trend plot per workload group.

Subplots:
  1) cycles
    2) local/remote access share (local_share=solid, remote_share=dashed)
  3) average outstanding read miss cycles (ORO.DDR / OR.DDR)
  4) average DTLB walk cycles (DLM.WP / DLM.MCW)

Supported event spellings include both raw perf encodings
(``cpu/event=0x..,umask=0x../``) and symbolic names when present.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass

import matplotlib
import numpy as np
from matplotlib.lines import Line2D

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_NAME_REGEX = r"^.*_perf\.csv$"
DEFAULT_FILE_PARSE_REGEX = (
    r"^(?P<base>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_perf\.csv$"
)

# Canonical metric keys used internally.
KEY_CYCLES = "cycles"
KEY_OR_DDR = "offcore_requests_demand_data_rd"
KEY_ORO_DDR = "offcore_requests_outstanding_demand_data_rd"
KEY_LOCAL_DRAM = "mem_load_l3_miss_retired_local_dram"
KEY_REMOTE_DRAM = "mem_load_l3_miss_retired_remote_dram"
KEY_DTLB_WP = "dtlb_misses_walk_pending"
KEY_DTLB_MCW = "dtlb_misses_miss_causes_a_walk"

TRACKED_KEYS = (
    KEY_CYCLES,
    KEY_OR_DDR,
    KEY_ORO_DDR,
    KEY_LOCAL_DRAM,
    KEY_REMOTE_DRAM,
    KEY_DTLB_WP,
    KEY_DTLB_MCW,
)


@dataclass
class PerfSeries:
    path: str
    label: str
    time_s: np.ndarray
    cycles: np.ndarray
    local_dram: np.ndarray
    remote_dram: np.ndarray
    avg_read_miss_cycles: np.ndarray
    avg_dtlb_walk_cycles: np.ndarray


@dataclass(frozen=True)
class PerfFileEntry:
    path: str
    suite: str
    workload: str
    config_label: str


@dataclass(frozen=True)
class ShareComparability:
    totals_by_config: list[tuple[str, float]]
    min_total: float
    median_total: float
    max_total: float
    max_min_ratio: float
    comparable: bool


def parse_count(value: str) -> float | None:
    text = value.strip().lower().replace(" ", "")
    if not text:
        return None

    if text in {"<notcounted>", "<notsupported>", "nan"}:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def parse_event_from_fields(fields: list[str]) -> str | None:
    """Extract event token from a perf ``-x,`` CSV line.

    Raw event strings are unquoted and can span multiple comma-separated fields.
    """
    if len(fields) < 4:
        return None

    start = fields[3].strip()
    if not start:
        return None

    if start == "cycles":
        return "cycles"

    if not (
        start.startswith("cpu/event=")
        or start.startswith("{cpu/event=")
        or start.startswith("offcore_")
        or start.startswith("mem_load_")
        or start.startswith("dtlb_")
    ):
        return start

    if start.startswith("offcore_") or start.startswith("mem_load_") or start.startswith("dtlb_"):
        return start

    parts = [start]
    idx = 4
    while idx < len(fields):
        token = fields[idx].strip()
        if not token:
            break
        parts.append(token)
        if token.endswith("/") or token.endswith("/}"):
            break
        idx += 1

    return ",".join(parts)


def canonical_event(raw_event: str) -> str | None:
    text = raw_event.strip().lower().replace(" ", "")
    if not text:
        return None

    text = text.replace("{", "").replace("}", "")

    if text == "cycles":
        return KEY_CYCLES

    if "offcore_requests_outstanding.demand_data_rd" in text:
        return KEY_ORO_DDR
    if "offcore_requests.demand_data_rd" in text:
        return KEY_OR_DDR

    if "mem_load_l3_miss_retired.local_dram" in text:
        return KEY_LOCAL_DRAM
    if "mem_load_l3_miss_retired.remote_dram" in text:
        return KEY_REMOTE_DRAM

    if "dtlb" in text and "walk_pending" in text:
        return KEY_DTLB_WP
    if "dtlb" in text and "miss_causes_a_walk" in text:
        return KEY_DTLB_MCW

    code_match = re.search(r"cpu/event=0x([0-9a-f]+).*?umask=0x([0-9a-f]+)", text)
    if code_match is None:
        return None

    event_sel = int(code_match.group(1), 16)
    umask = int(code_match.group(2), 16)

    code_map = {
        (0xB0, 0x01): KEY_OR_DDR,
        (0x60, 0x01): KEY_ORO_DDR,
        (0xD3, 0x01): KEY_LOCAL_DRAM,
        (0xD3, 0x02): KEY_REMOTE_DRAM,
        (0x08, 0x10): KEY_DTLB_WP,
        (0x08, 0x01): KEY_DTLB_MCW,
    }
    return code_map.get((event_sel, umask))


def safe_divide(numer: np.ndarray, denom: np.ndarray) -> np.ndarray:
    out = np.full(numer.shape, np.nan, dtype=float)
    valid = np.isfinite(numer) & np.isfinite(denom) & (denom > 0)
    out[valid] = numer[valid] / denom[valid]
    return out


def smooth_nan(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return values

    if values.size == 0:
        return values

    kernel = np.ones(window, dtype=float)
    clean = np.nan_to_num(values, nan=0.0)
    weights = np.isfinite(values).astype(float)

    summed = np.convolve(clean, kernel, mode="same")
    weight_summed = np.convolve(weights, kernel, mode="same")

    out = np.full(values.shape, np.nan, dtype=float)
    valid = weight_summed > 0
    out[valid] = summed[valid] / weight_summed[valid]
    return out


def total_local_remote_accesses(series: PerfSeries) -> float:
    local = np.nan_to_num(series.local_dram, nan=0.0)
    remote = np.nan_to_num(series.remote_dram, nan=0.0)
    return float(np.sum(local + remote))


def evaluate_share_comparability(
    series_list: list[PerfSeries],
    max_ratio: float,
) -> ShareComparability:
    totals: list[tuple[str, float]] = []
    for series in series_list:
        totals.append((series.label, total_local_remote_accesses(series)))

    totals.sort(key=lambda item: natural_sort_key(item[0]))
    values = np.array([total for _, total in totals], dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return ShareComparability(
            totals_by_config=totals,
            min_total=float("nan"),
            median_total=float("nan"),
            max_total=float("nan"),
            max_min_ratio=float("inf"),
            comparable=False,
        )

    min_total = float(np.min(values))
    median_total = float(np.median(values))
    max_total = float(np.max(values))

    if min_total <= 0:
        ratio = float("inf")
    else:
        ratio = max_total / min_total

    comparable = np.isfinite(ratio) and ratio <= max_ratio
    return ShareComparability(
        totals_by_config=totals,
        min_total=min_total,
        median_total=median_total,
        max_total=max_total,
        max_min_ratio=ratio,
        comparable=comparable,
    )


def natural_sort_key(text: str) -> list[int | float | str]:
    tokens = re.split(r"(\d+(?:\.\d+)?)", text.lower())
    key: list[int | float | str] = []
    for tok in tokens:
        if not tok:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", tok):
            key.append(float(tok))
        else:
            key.append(tok)
    return key


def parse_perf_file(file_path: str, series_label: str) -> PerfSeries | None:
    rows_by_time: dict[float, dict[str, float]] = {}

    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split(",")
            if len(fields) < 4:
                continue

            try:
                ts = float(fields[0].strip())
            except ValueError:
                continue

            count = parse_count(fields[1])
            if count is None:
                continue

            raw_event = parse_event_from_fields(fields)
            if raw_event is None:
                continue

            event_key = canonical_event(raw_event)
            if event_key is None or event_key not in TRACKED_KEYS:
                continue

            bucket = rows_by_time.get(ts)
            if bucket is None:
                bucket = {}
                rows_by_time[ts] = bucket

            bucket[event_key] = bucket.get(event_key, 0.0) + count

    if not rows_by_time:
        return None

    timestamps = np.array(sorted(rows_by_time.keys()), dtype=float)
    if timestamps.size == 0:
        return None

    rel_time = timestamps - timestamps[0]

    arrays: dict[str, np.ndarray] = {}
    for key in TRACKED_KEYS:
        arr = np.full(timestamps.shape, np.nan, dtype=float)
        for idx, ts in enumerate(timestamps):
            value = rows_by_time[ts].get(key)
            if value is not None:
                arr[idx] = value
        arrays[key] = arr

    avg_read_miss_cycles = safe_divide(arrays[KEY_ORO_DDR], arrays[KEY_OR_DDR])
    avg_dtlb_walk_cycles = safe_divide(arrays[KEY_DTLB_WP], arrays[KEY_DTLB_MCW])

    return PerfSeries(
        path=file_path,
        label=series_label,
        time_s=rel_time,
        cycles=arrays[KEY_CYCLES],
        local_dram=arrays[KEY_LOCAL_DRAM],
        remote_dram=arrays[KEY_REMOTE_DRAM],
        avg_read_miss_cycles=avg_read_miss_cycles,
        avg_dtlb_walk_cycles=avg_dtlb_walk_cycles,
    )


def parse_perf_file_entry(
    current_root: str,
    file_name: str,
    file_parse_regex: re.Pattern[str],
) -> PerfFileEntry | None:
    match = file_parse_regex.match(file_name)
    if match is None:
        return None

    base = match.group("base")
    memory = match.group("memory")
    threads = match.group("threads")

    suite = os.path.basename(current_root.rstrip(os.sep))
    workload = base

    # GAPBS files are named gapbs_<benchmark>-<memory>_<threads>_perf.csv.
    # Split by benchmark so bc/cc/pr/bfs each get their own figure.
    if base.startswith("gapbs_"):
        suite = "gapbs"
        workload = base.split("_", 1)[1]

    config_label = f"{memory}_{threads}"
    return PerfFileEntry(
        path=os.path.join(current_root, file_name),
        suite=suite,
        workload=workload,
        config_label=config_label,
    )


def discover_perf_groups(
    input_dir: str,
    name_regex: str,
    file_parse_regex: str,
    follow_symlinks: bool,
) -> dict[tuple[str, str, str], list[PerfFileEntry]]:
    pattern = re.compile(name_regex)
    parse_pattern = re.compile(file_parse_regex)
    groups: dict[tuple[str, str, str], list[PerfFileEntry]] = {}

    for current_root, _dirs, files in os.walk(input_dir, followlinks=follow_symlinks):
        parsed_entries: list[PerfFileEntry] = []
        for name in files:
            if not pattern.match(name):
                continue

            entry = parse_perf_file_entry(current_root, name, parse_pattern)
            if entry is None:
                continue

            parsed_entries.append(entry)

        if not parsed_entries:
            continue

        parsed_entries.sort(key=lambda e: natural_sort_key(os.path.basename(e.path)))
        for entry in parsed_entries:
            key = (entry.suite, entry.workload, current_root)
            bucket = groups.get(key)
            if bucket is None:
                groups[key] = [entry]
            else:
                bucket.append(entry)

    return groups


def configure_axis(ax: plt.Axes, title: str, y_label: str) -> None:
    ax.set_title(title)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)


def flatten_finite(values: list[np.ndarray], positive_only: bool) -> np.ndarray:
    pieces: list[np.ndarray] = []
    for arr in values:
        if arr.size == 0:
            continue
        cur = arr[np.isfinite(arr)]
        if positive_only:
            cur = cur[cur > 0]
        if cur.size > 0:
            pieces.append(cur)

    if not pieces:
        return np.array([], dtype=float)
    return np.concatenate(pieces)


def apply_robust_ylim(
    ax: plt.Axes,
    values: list[np.ndarray],
    low_pct: float,
    high_pct: float,
    *,
    positive_only: bool,
    clamp_zero: bool,
) -> None:
    flat = flatten_finite(values, positive_only=positive_only)
    if flat.size == 0:
        return

    low, high = np.percentile(flat, [low_pct, high_pct])
    if not np.isfinite(low) or not np.isfinite(high):
        return

    if high <= low:
        low = float(np.min(flat))
        high = float(np.max(flat))
        if high <= low:
            return

    if positive_only:
        low = max(low, np.finfo(float).tiny)
        high = max(high, low * 1.000001)

        # For log-scale data, pad multiplicatively in log space.
        log_low = np.log10(low)
        log_high = np.log10(high)
        log_span = max(log_high - log_low, 1e-9)
        log_pad = log_span * 0.08

        lo = 10 ** (log_low - log_pad)
        hi = 10 ** (log_high + log_pad)
    else:
        span = high - low
        pad = max(span * 0.08, 1e-12)
        lo = low - pad
        hi = high + pad

        if clamp_zero:
            lo = max(0.0, lo)

    if hi <= lo:
        return

    ax.set_ylim(lo, hi)


def choose_dtlb_ylim(
    values: list[np.ndarray],
    *,
    base_upper: float,
    trigger_percentile: float,
    tail_percentile: float,
) -> tuple[float, float, float, float]:
    flat = flatten_finite(values, positive_only=False)
    if flat.size == 0:
        return base_upper, float("nan"), float("nan"), float("nan")

    p90 = float(np.percentile(flat, trigger_percentile))
    p95 = float(np.percentile(flat, 95.0))
    p99 = float(np.percentile(flat, 99.0))

    if p90 <= base_upper:
        return base_upper, p90, p95, p99

    upper = float(np.percentile(flat, tail_percentile))
    upper = max(base_upper, upper)
    return upper, p90, p95, p99


def build_output_name(input_dir: str, workload_dir: str, suite: str, workload: str) -> str:
    rel_dir = os.path.relpath(workload_dir, input_dir)
    rel_tag = rel_dir if rel_dir != "." else os.path.basename(input_dir)
    rel_tag = rel_tag.replace(os.sep, "__")
    rel_tag = re.sub(r"[^a-zA-Z0-9_.-]", "_", rel_tag)
    return f"{rel_tag}__{suite}__{workload}__perf_trends.png"


def plot_workload_group(
    suite: str,
    workload: str,
    workload_dir: str,
    series_list: list[PerfSeries],
    output_path: str,
    smooth_window: int,
    dpi: int,
    colormap: str,
    local_remote_mode: str,
    share_comparable_max_ratio: float,
    use_log_local_remote: bool,
    robust_ylim: bool,
    ylim_low_pct: float,
    ylim_high_pct: float,
    avg_read_ymax: float,
    dtlb_base_ymax: float,
    dtlb_trigger_percentile: float,
    dtlb_tail_percentile: float,
) -> None:
    series_list.sort(key=lambda s: natural_sort_key(s.label))

    share_check = evaluate_share_comparability(
        series_list,
        max_ratio=share_comparable_max_ratio,
    )

    print(
        "Share denominator check: "
        f"suite={suite} workload={workload} "
        f"min_total={share_check.min_total:.6g} "
        f"median_total={share_check.median_total:.6g} "
        f"max_total={share_check.max_total:.6g} "
        f"max_min_ratio={share_check.max_min_ratio:.4f} "
        f"threshold={share_comparable_max_ratio:.4f} "
        f"comparable={share_check.comparable}"
    )
    for label, total in share_check.totals_by_config:
        print(f"  total_local_plus_remote[{label}]={total:.6g}")

    fig, axes = plt.subplots(2, 2, figsize=(18, 10), dpi=dpi, sharex=True)
    ax_cycles = axes[0, 0]
    ax_local_remote = axes[0, 1]
    ax_avg_read = axes[1, 0]
    ax_avg_dtlb = axes[1, 1]

    configure_axis(ax_cycles, "Cycles", "cycles / 100ms")
    if local_remote_mode == "share":
        share_title = "Local/Remote Access Share"
        if not share_check.comparable:
            share_title += " (non-comparable totals)"
        configure_axis(
            ax_local_remote,
            share_title,
            "share of (local + remote)",
        )
    else:
        configure_axis(
            ax_local_remote,
            "Local/Remote Accesses",
            "events / 100ms",
        )
    configure_axis(
        ax_avg_read,
        "Average Outstanding Read Miss Cycles",
        "ORO.DDR / OR.DDR",
    )
    configure_axis(
        ax_avg_dtlb,
        "Average DTLB Walk Cycles",
        "DLM.WP / DLM.MCW",
    )

    max_time = 0.0
    for series in series_list:
        if series.time_s.size == 0:
            continue
        cur_max = float(np.nanmax(series.time_s))
        if np.isfinite(cur_max) and cur_max > max_time:
            max_time = cur_max

    cmap = plt.get_cmap(colormap)
    cmap_size = getattr(cmap, "N", max(1, len(series_list)))

    config_handles: list[Line2D] = []
    config_labels: list[str] = []
    cycles_vals: list[np.ndarray] = []
    local_remote_vals: list[np.ndarray] = []
    avg_read_vals: list[np.ndarray] = []
    avg_dtlb_vals: list[np.ndarray] = []

    for idx, series in enumerate(series_list):
        color = cmap(idx % cmap_size)

        x = series.time_s
        y_cycles = smooth_nan(series.cycles, smooth_window)
        y_local = smooth_nan(series.local_dram, smooth_window)
        y_remote = smooth_nan(series.remote_dram, smooth_window)
        y_avg_read = smooth_nan(series.avg_read_miss_cycles, smooth_window)
        y_avg_dtlb = smooth_nan(series.avg_dtlb_walk_cycles, smooth_window)

        if local_remote_mode == "share":
            denom = y_local + y_remote
            y_local_plot = safe_divide(y_local, denom)
            y_remote_plot = safe_divide(y_remote, denom)
        else:
            if use_log_local_remote:
                # Log scale cannot represent zeros; keep them as NaN gaps.
                y_local_plot = np.where(y_local > 0, y_local, np.nan)
                y_remote_plot = np.where(y_remote > 0, y_remote, np.nan)
            else:
                y_local_plot = y_local
                y_remote_plot = y_remote

        ax_cycles.plot(x, y_cycles, color=color, linewidth=1.7, alpha=0.95)
        ax_local_remote.plot(x, y_local_plot, color=color, linewidth=1.6, linestyle="-")
        ax_local_remote.plot(x, y_remote_plot, color=color, linewidth=1.6, linestyle="--")
        ax_avg_read.plot(x, y_avg_read, color=color, linewidth=1.6, alpha=0.95)
        ax_avg_dtlb.plot(x, y_avg_dtlb, color=color, linewidth=1.6, alpha=0.95)

        cycles_vals.append(y_cycles)
        local_remote_vals.append(y_local_plot)
        local_remote_vals.append(y_remote_plot)
        avg_read_vals.append(y_avg_read)
        avg_dtlb_vals.append(y_avg_dtlb)

        config_handles.append(Line2D([0], [0], color=color, linewidth=2.0))
        config_labels.append(series.label)

    # Set x-limits after plotting; setting limits before plotting can pin axes to [0, 1].
    x_upper = max_time if max_time > 0 else 1.0
    for ax in [ax_cycles, ax_local_remote, ax_avg_read, ax_avg_dtlb]:
        ax.set_xlim(0.0, x_upper)

    axes[1, 0].set_xlabel("time since start (s)")
    axes[1, 1].set_xlabel("time since start (s)")

    if local_remote_mode == "share":
        ax_local_remote.set_ylim(0.0, 1.0)
    elif use_log_local_remote:
        ax_local_remote.set_yscale("log")
        ax_local_remote.set_ylabel("events / 100ms (log scale)")

    if robust_ylim:
        apply_robust_ylim(
            ax_cycles,
            cycles_vals,
            ylim_low_pct,
            ylim_high_pct,
            positive_only=False,
            clamp_zero=False,
        )
        if local_remote_mode == "absolute":
            apply_robust_ylim(
                ax_local_remote,
                local_remote_vals,
                ylim_low_pct,
                ylim_high_pct,
                positive_only=use_log_local_remote,
                clamp_zero=not use_log_local_remote,
            )

    # Explicit y-axis behavior requested by user.
    #ax_avg_read.set_ylim(0.0, avg_read_ymax)

    dtlb_upper, dtlb_p90, dtlb_p95, dtlb_p99 = choose_dtlb_ylim(
        avg_dtlb_vals,
        base_upper=dtlb_base_ymax,
        trigger_percentile=dtlb_trigger_percentile,
        tail_percentile=dtlb_tail_percentile,
    )
    #ax_avg_dtlb.set_ylim(0.0, dtlb_upper)

    if local_remote_mode == "share":
        metric_handles = [
            Line2D([0], [0], color="black", linewidth=2.0, linestyle="-", label="local_share"),
            Line2D([0], [0], color="black", linewidth=2.0, linestyle="--", label="remote_share"),
        ]
    else:
        metric_handles = [
            Line2D([0], [0], color="black", linewidth=2.0, linestyle="-", label="local"),
            Line2D([0], [0], color="black", linewidth=2.0, linestyle="--", label="remote"),
        ]
    ax_local_remote.legend(handles=metric_handles, loc="upper right", title="Line Style")

    fig.suptitle(f"{suite}/{workload}: perf trends ({len(series_list)} configs)")
    fig.legend(
        handles=config_handles,
        labels=config_labels,
        title="Config",
        loc="center left",
        bbox_to_anchor=(0.86, 0.5),
        frameon=False,
    )

    print(
        "Final axis limits: "
        f"suite={suite} workload={workload} "
        f"x={ax_cycles.get_xlim()} "
        f"cycles={ax_cycles.get_ylim()} "
        f"local_remote={ax_local_remote.get_ylim()} "
        f"avg_read={ax_avg_read.get_ylim()} "
        f"avg_dtlb={ax_avg_dtlb.get_ylim()} "
        f"dtlb_p90={dtlb_p90:.6g} "
        f"dtlb_p95={dtlb_p95:.6g} "
        f"dtlb_p99={dtlb_p99:.6g}"
    )

    fig.tight_layout(rect=(0.0, 0.0, 0.84, 0.95))
    fig.savefig(output_path)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively generate workload-level perf trend plots from *_perf.csv logs."
        )
    )
    parser.add_argument(
        "input_dir",
        help="Root directory containing workload subdirectories with *_perf.csv logs",
    )
    parser.add_argument(
        "--output-dir",
        default="perf_trend_plots",
        help="Directory where output PNGs are written (default: perf_trend_plots)",
    )
    parser.add_argument(
        "--name-regex",
        default=DEFAULT_NAME_REGEX,
        help="Regex used to identify perf files by basename (default: ^.*_perf\\.csv$)",
    )
    parser.add_argument(
        "--file-parse-regex",
        default=DEFAULT_FILE_PARSE_REGEX,
        help=(
            "Regex used to parse basename into base/memory/threads named groups "
            "(default: ^(?P<base>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_perf\\.csv$)"
        ),
    )
    parser.add_argument(
        "--smooth-window",
        type=int,
        default=5,
        help="Centered moving-average window in samples; 1 disables smoothing (default: 5)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Figure DPI (default: 150)",
    )
    parser.add_argument(
        "--colormap",
        default="tab20",
        help="Matplotlib colormap for config lines (default: tab20)",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinks while walking directories",
    )
    parser.add_argument(
        "--max-files-per-workload",
        type=int,
        default=0,
        help="Optional cap on files per workload group for quick previews (0 = no cap)",
    )
    parser.add_argument(
        "--log-local-remote",
        action="store_false",
        help=(
            "Use log y-axis for Local/Remote subplot when --local-remote-mode=absolute "
            "(ignored in share mode)"
        ),
    )
    parser.add_argument(
        "--local-remote-mode",
        choices=("share", "absolute"),
        default="absolute",
        help="Plot local/remote as share or absolute events (default: share)",
    )
    parser.add_argument(
        "--share-comparable-max-ratio",
        type=float,
        default=1.5,
        help=(
            "Max allowed (max_total/min_total) across config totals for share comparability "
            "(default: 1.5)"
        ),
    )
    parser.add_argument(
        "--full-range-y",
        action="store_true",
        help="Disable robust percentile y-limits for cycles subplot",
    )
    parser.add_argument(
        "--ylim-low-pct",
        type=float,
        default=5.0,
        help="Lower percentile for robust y-limits (default: 5.0)",
    )
    parser.add_argument(
        "--ylim-high-pct",
        type=float,
        default=95.0,
        help="Upper percentile for robust y-limits (default: 95.0)",
    )
    parser.add_argument(
        "--avg-read-ymax",
        type=float,
        default=200.0,
        help="Fixed upper y-limit for average read miss cycles subplot (default: 200)",
    )
    parser.add_argument(
        "--dtlb-base-ymax",
        type=float,
        default=60.0,
        help="Default upper y-limit for average dtlb walk cycles subplot (default: 60)",
    )
    parser.add_argument(
        "--dtlb-trigger-percentile",
        type=float,
        default=90.0,
        help=(
            "If this percentile of dtlb walk cycles exceeds --dtlb-base-ymax, "
            "use --dtlb-tail-percentile as upper limit source (default trigger: 90)"
        ),
    )
    parser.add_argument(
        "--dtlb-tail-percentile",
        type=float,
        choices=(95.0, 99.0),
        default=95.0,
        help="Tail percentile used for dtlb upper y-limit when trigger trips (95 or 99)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    if args.smooth_window < 1:
        raise SystemExit("--smooth-window must be >= 1")

    if args.dpi < 50:
        raise SystemExit("--dpi must be >= 50")

    try:
        re.compile(args.name_regex)
    except re.error as exc:
        raise SystemExit(f"Invalid --name-regex: {exc}") from exc

    try:
        parse_re = re.compile(args.file_parse_regex)
    except re.error as exc:
        raise SystemExit(f"Invalid --file-parse-regex: {exc}") from exc

    required_groups = {"base", "memory", "threads"}
    if not required_groups.issubset(parse_re.groupindex.keys()):
        raise SystemExit(
            "--file-parse-regex must define named groups: base, memory, threads"
        )

    if not (0.0 <= args.ylim_low_pct < args.ylim_high_pct <= 100.0):
        raise SystemExit("Require 0 <= --ylim-low-pct < --ylim-high-pct <= 100")

    if args.share_comparable_max_ratio <= 1.0:
        raise SystemExit("--share-comparable-max-ratio must be > 1.0")

    if args.avg_read_ymax <= 0:
        raise SystemExit("--avg-read-ymax must be > 0")

    if args.dtlb_base_ymax <= 0:
        raise SystemExit("--dtlb-base-ymax must be > 0")

    if not (0.0 < args.dtlb_trigger_percentile < 100.0):
        raise SystemExit("--dtlb-trigger-percentile must be in (0, 100)")

    os.makedirs(args.output_dir, exist_ok=True)

    groups = discover_perf_groups(
        input_dir=args.input_dir,
        name_regex=args.name_regex,
        file_parse_regex=args.file_parse_regex,
        follow_symlinks=args.follow_symlinks,
    )

    if not groups:
        raise SystemExit("No matching perf files were found")

    total_groups = 0
    total_figures = 0
    total_files = 0
    skipped_files = 0

    for (suite, workload, workload_dir), entries in sorted(groups.items()):
        total_groups += 1

        if args.max_files_per_workload > 0:
            entries = entries[: args.max_files_per_workload]

        series_list: list[PerfSeries] = []
        for entry in entries:
            parsed = parse_perf_file(entry.path, entry.config_label)
            if parsed is None:
                skipped_files += 1
                continue
            series_list.append(parsed)

        if not series_list:
            print(f"Skipping workload={workload} dir={workload_dir}: no parsable series")
            continue

        total_files += len(series_list)
        output_name = build_output_name(args.input_dir, workload_dir, suite, workload)
        output_path = os.path.join(args.output_dir, output_name)

        plot_workload_group(
            suite=suite,
            workload=workload,
            workload_dir=workload_dir,
            series_list=series_list,
            output_path=output_path,
            smooth_window=args.smooth_window,
            dpi=args.dpi,
            colormap=args.colormap,
            local_remote_mode=args.local_remote_mode,
            share_comparable_max_ratio=args.share_comparable_max_ratio,
            use_log_local_remote=args.log_local_remote,
            robust_ylim=not args.full_range_y,
            ylim_low_pct=args.ylim_low_pct,
            ylim_high_pct=args.ylim_high_pct,
            avg_read_ymax=args.avg_read_ymax,
            dtlb_base_ymax=args.dtlb_base_ymax,
            dtlb_trigger_percentile=args.dtlb_trigger_percentile,
            dtlb_tail_percentile=args.dtlb_tail_percentile,
        )

        total_figures += 1
        print(
            f"Generated plot: suite={suite} workload={workload} files={len(series_list)} output={output_path}"
        )

    print("Summary")
    print(f"  workload_groups_seen={total_groups}")
    print(f"  workload_figures_generated={total_figures}")
    print(f"  parsed_files={total_files}")
    print(f"  skipped_files={skipped_files}")
    print(f"  output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
