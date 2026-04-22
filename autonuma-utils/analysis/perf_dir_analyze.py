#!/usr/bin/env python3
"""Recursive perf CSV analyzer with workload-aware runtime slicing.

Scans a directory tree for perf files and writes one summary CSV row per file.

Default filename format:
  workload-memory_threads_perf.csv

For workloads that report a runtime/throughput marker in ``*_output.log``,
perf totals are computed only from the tail of the perf timeline that should
cover execution (runtime + safety margin).
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
from dataclasses import dataclass, field


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_perf\.csv$"
)

EVENT_CYCLES = "cycles"
EVENT_OR_DEMAND = "offcore_requests.demand_data_rd"
EVENT_ORO_DEMAND = "offcore_requests_outstanding.demand_data_rd"
EVENT_LOCAL_DRAM = "mem_load_l3_miss_retired.local_dram"
EVENT_REMOTE_DRAM = "mem_load_l3_miss_retired.remote_dram"
EVENT_DTLB_WALK_PENDING = "dtlb_load_misses.walk_pending"
EVENT_DTLB_MISS_CAUSES_WALK = "dtlb_load_misses.miss_causes_a_walk"

# Canonical columns emitted to CSV. Names match the perfmon event naming used
# in pebs-perf-slowdown.sh comments.
DEFAULT_EVENT_COLUMNS: list[str] = [
    EVENT_CYCLES,
    EVENT_OR_DEMAND,
    EVENT_ORO_DEMAND,
    EVENT_LOCAL_DRAM,
    EVENT_REMOTE_DRAM,
    EVENT_DTLB_WALK_PENDING,
    EVENT_DTLB_MISS_CAUSES_WALK,
]

EVENT_CODE_MAP: dict[tuple[int, int], str] = {
    (0xB0, 0x01): EVENT_OR_DEMAND,
    (0x60, 0x01): EVENT_ORO_DEMAND,
    (0xD3, 0x01): EVENT_LOCAL_DRAM,
    (0xD3, 0x02): EVENT_REMOTE_DRAM,
    (0x08, 0x10): EVENT_DTLB_WALK_PENDING,
    (0x08, 0x01): EVENT_DTLB_MISS_CAUSES_WALK,
}

DERIVED_CYCLES_PER_WALK = "cycles_per_walk"
DERIVED_CYCLES_PER_MEMORY_OFFCORE_REQUEST = "cycles_per_memory_offcore_request"

RELATIVE_PREFIX = "relative_increase_"


@dataclass
class PerfSummaryRow:
    workload: str
    threads: str
    memory: str
    path: str
    throughput: float | None
    runtime: float | None
    execution_seconds: float | None
    perf_window_seconds: float | None
    totals: dict[str, int]
    cycles_per_walk: float | None
    cycles_per_memory_offcore_request: float | None
    slowdown: float | None = None
    relative_slowdown: float | None = None
    relative_increase_by_metric: dict[str, float | None] = field(default_factory=dict)


@dataclass
class WorkloadMetrics:
    throughput: float | None = None
    runtime: float | None = None
    execution_seconds: float | None = None


@dataclass
class WorkloadCorrelationRow:
    workload: str
    threads: str
    configs: int
    correlation_by_metric: dict[str, float | None] = field(default_factory=dict)
    pairs_by_metric: dict[str, int] = field(default_factory=dict)


def parse_count(value: str) -> int | None:
    """Parse perf count field into int, returning None for non-numeric rows."""
    text = value.strip().lower()
    if not text:
        return None

    text = text.replace(" ", "")
    if text in {"<notcounted>", "<notsupported>", "nan"}:
        return None

    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def parse_float_token(value: str) -> float | None:
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
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

    if not (start.startswith("cpu/event=") or start.startswith("{cpu/event=")):
        return start

    parts = [start]
    idx = 4
    while idx < len(fields):
        part = fields[idx].strip()
        if not part:
            break
        parts.append(part)
        if part.endswith("/") or part.endswith("/}"):
            break
        idx += 1

    return ",".join(parts)


def canonical_event_name(raw_event: str) -> str | None:
    text = raw_event.strip().lower().replace(" ", "")
    if not text:
        return None

    text = text.replace("{", "").replace("}", "")

    if text == "cycles":
        return EVENT_CYCLES

    if "offcore_requests_outstanding.demand_data_rd" in text:
        return EVENT_ORO_DEMAND
    if "offcore_requests.demand_data_rd" in text:
        return EVENT_OR_DEMAND

    if "mem_load_l3_miss_retired.local_dram" in text:
        return EVENT_LOCAL_DRAM
    if "mem_load_l3_miss_retired.remote_dram" in text:
        return EVENT_REMOTE_DRAM

    if "dtlb_load_misses.walk_pending" in text:
        return EVENT_DTLB_WALK_PENDING
    if "dtlb_load_misses.miss_causes_a_walk" in text:
        return EVENT_DTLB_MISS_CAUSES_WALK
    if "dtlb" in text and "walk_pending" in text:
        return EVENT_DTLB_WALK_PENDING
    if "dtlb" in text and "miss_causes" in text:
        return EVENT_DTLB_MISS_CAUSES_WALK

    code_match = re.search(r"cpu/event=0x([0-9a-f]+).*?umask=0x([0-9a-f]+)", text)
    if code_match is None:
        return None

    event_sel = int(code_match.group(1), 16)
    umask = int(code_match.group(2), 16)
    return EVENT_CODE_MAP.get((event_sel, umask))


def safe_ratio(numer: float | int | None, denom: float | int | None) -> float | None:
    if numer is None or denom is None:
        return None
    if denom == 0:
        return None
    return float(numer) / float(denom)


def parse_duration_to_seconds(token: str) -> float | None:
    value = token.strip()
    if not value:
        return None

    parts = value.split(":")
    try:
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return hours * 3600.0 + minutes * 60.0 + seconds
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60.0 + seconds
        return float(value)
    except ValueError:
        return None


def read_text_if_exists(path: str) -> str | None:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def workload_family(workload: str) -> str:
    if workload.startswith("gapbs_"):
        return "gapbs"
    return workload.split("_", 1)[0].lower()


def parse_wall_clock_elapsed_seconds(time_text: str | None) -> float | None:
    if not time_text:
        return None

    match = re.search(
        r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([^\n]+)",
        time_text,
    )
    if match is None:
        return None
    return parse_duration_to_seconds(match.group(1))


def parse_repeat_count_from_time_command(time_text: str | None) -> int | None:
    if not time_text:
        return None

    command_match = re.search(r"Command being timed:\s*\"([^\"]+)\"", time_text)
    if command_match is None:
        return None

    command = command_match.group(1)
    repeat_match = re.search(r"(?:^|\s)-r\s+(\d+)(?:\s|$)", command)
    if repeat_match is None:
        return None

    try:
        return int(repeat_match.group(1))
    except ValueError:
        return None


def parse_throughput_to_mops(value: float, unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized in {"", "mops", "mop/s", "mopsec", "mop"}:
        return value
    if normalized in {"ops", "op/s"}:
        return value / 1_000_000.0
    if normalized in {"kops", "kop/s"}:
        return value / 1_000.0
    if normalized in {"gops", "gop/s"}:
        return value * 1_000.0
    return value


def parse_metrics_from_logs(
    workload: str,
    output_path: str,
    time_path: str,
) -> WorkloadMetrics:
    metrics = WorkloadMetrics()

    output_text = read_text_if_exists(output_path)
    time_text = read_text_if_exists(time_path)

    family = workload_family(workload)

    if output_text:
        if family == "flexkvs":
            run_match = re.search(
                r"Running\s+for\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s+seconds",
                output_text,
                flags=re.IGNORECASE,
            )
            if run_match is not None:
                metrics.execution_seconds = parse_float_token(run_match.group(1))

            tp_match = re.search(
                r"Final\s+throughput\s*=\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-zA-Z/]+)?",
                output_text,
                flags=re.IGNORECASE,
            )
            if tp_match is not None:
                tp_value = parse_float_token(tp_match.group(1))
                unit = tp_match.group(2) or "mops"
                if tp_value is not None:
                    metrics.throughput = parse_throughput_to_mops(tp_value, unit)

        elif family == "gapbs":
            avg_match = re.search(
                r"Average\s+Time:\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
                output_text,
                flags=re.IGNORECASE,
            )
            if avg_match is not None:
                metrics.runtime = parse_float_token(avg_match.group(1))

            trial_times = [
                parse_float_token(raw)
                for raw in re.findall(
                    r"Trial\s+Time:\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
                    output_text,
                    flags=re.IGNORECASE,
                )
            ]
            trial_values = [v for v in trial_times if v is not None]
            if trial_values:
                metrics.execution_seconds = sum(trial_values)
            elif metrics.runtime is not None:
                metrics.execution_seconds = metrics.runtime

        elif family == "merci":
            avg_match = re.search(
                r"Average\s+Time:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*ms",
                output_text,
                flags=re.IGNORECASE,
            )
            if avg_match is not None:
                avg_ms = parse_float_token(avg_match.group(1))
                if avg_ms is not None:
                    metrics.runtime = avg_ms / 1000.0

            repeat_times_ms = [
                parse_float_token(raw)
                for raw in re.findall(
                    r"REPEAT\s*#\s*\d+\s+Baseline\s+Total\s+time\s*:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*ms",
                    output_text,
                    flags=re.IGNORECASE,
                )
            ]
            repeat_values = [v for v in repeat_times_ms if v is not None]
            if repeat_values:
                metrics.execution_seconds = sum(repeat_values) / 1000.0
            elif metrics.runtime is not None:
                repeat_count = parse_repeat_count_from_time_command(time_text)
                if repeat_count is not None and repeat_count > 0:
                    metrics.execution_seconds = metrics.runtime * repeat_count
                else:
                    metrics.execution_seconds = metrics.runtime

        elif family == "liblinear":
            elapsed_match = re.search(
                r"Elapsed\s+time:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*seconds",
                output_text,
                flags=re.IGNORECASE,
            )
            if elapsed_match is not None:
                elapsed = parse_float_token(elapsed_match.group(1))
                metrics.runtime = elapsed
                metrics.execution_seconds = elapsed

        elif family == "silo":
            runtime_match = re.search(
                r"runtime:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*sec",
                output_text,
                flags=re.IGNORECASE,
            )
            if runtime_match is not None:
                runtime = parse_float_token(runtime_match.group(1))
                metrics.runtime = runtime
                metrics.execution_seconds = runtime

        elif family == "xsbench":
            runtime_match = re.search(
                r"Runtime:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*seconds",
                output_text,
                flags=re.IGNORECASE,
            )
            if runtime_match is not None:
                runtime = parse_float_token(runtime_match.group(1))
                metrics.runtime = runtime
                metrics.execution_seconds = runtime

    wall_clock = parse_wall_clock_elapsed_seconds(time_text)
    if metrics.execution_seconds is None:
        metrics.execution_seconds = wall_clock

    if metrics.runtime is None and family != "flexkvs":
        metrics.runtime = wall_clock

    return metrics


def summarize_perf_file(
    file_path: str,
    target_events: set[str],
    window_seconds: float | None,
) -> tuple[dict[str, int], float | None]:
    """Aggregate total counts per target event for one perf CSV file.

    If ``window_seconds`` is provided, only events in the last N seconds of the
    perf timeline are counted.
    """
    totals = {event: 0 for event in target_events}
    samples: list[tuple[float, str, int]] = []
    max_ts: float | None = None

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

            event = canonical_event_name(raw_event)
            if event is None or event not in target_events:
                continue

            samples.append((ts, event, count))
            if max_ts is None or ts > max_ts:
                max_ts = ts

    if not samples:
        return totals, max_ts

    cutoff: float | None = None
    if window_seconds is not None and window_seconds > 0 and max_ts is not None:
        cutoff = max_ts - window_seconds

    for ts, event, count in samples:
        if cutoff is not None and ts < cutoff:
            continue
        totals[event] += count

    return totals, max_ts


def memory_to_bytes(memory: str) -> float | None:
    match = re.fullmatch(
        r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?)(?:i?b)?\s*",
        memory,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None

    magnitude = float(match.group(1))
    suffix = match.group(2).lower()
    power = {
        "": 0,
        "k": 1,
        "m": 2,
        "g": 3,
        "t": 4,
        "p": 5,
    }.get(suffix)
    if power is None:
        return None

    return magnitude * (1024.0 ** power)


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


def row_metric_value(row: PerfSummaryRow, metric_name: str) -> float | int | None:
    if metric_name == "throughput":
        return row.throughput
    if metric_name == "runtime":
        return row.runtime
    if metric_name == DERIVED_CYCLES_PER_WALK:
        return row.cycles_per_walk
    if metric_name == DERIVED_CYCLES_PER_MEMORY_OFFCORE_REQUEST:
        return row.cycles_per_memory_offcore_request
    return row.totals.get(metric_name)


def relative_delta(value: float | int | None, baseline: float | int | None) -> float | None:
    if value is None or baseline is None:
        return None
    baseline_f = float(baseline)
    if baseline_f == 0:
        return None
    return (float(value) - baseline_f) / baseline_f


def compute_baselines(rows: list[PerfSummaryRow]) -> dict[tuple[str, str], PerfSummaryRow]:
    groups: dict[tuple[str, str], list[PerfSummaryRow]] = {}
    for row in rows:
        groups.setdefault((row.workload, row.threads), []).append(row)

    baselines: dict[tuple[str, str], PerfSummaryRow] = {}
    for key, group_rows in groups.items():
        baselines[key] = max(
            group_rows,
            key=lambda r: (
                1 if memory_to_bytes(r.memory) is not None else 0,
                memory_to_bytes(r.memory) or 0.0,
                natural_sort_key(r.memory),
            ),
        )
    return baselines


def annotate_relative_metrics(rows: list[PerfSummaryRow], metric_columns: list[str]) -> None:
    baselines = compute_baselines(rows)

    for row in rows:
        baseline = baselines[(row.workload, row.threads)]

        if (
            row.throughput is not None
            and baseline.throughput is not None
            and baseline.throughput > 0
        ):
            row.slowdown = baseline.throughput - row.throughput
            row.relative_slowdown = row.slowdown / baseline.throughput
        elif (
            row.runtime is not None
            and baseline.runtime is not None
            and baseline.runtime > 0
        ):
            row.slowdown = row.runtime - baseline.runtime
            row.relative_slowdown = row.slowdown / baseline.runtime
        else:
            row.slowdown = None
            row.relative_slowdown = None

        for metric in metric_columns:
            row.relative_increase_by_metric[metric] = relative_delta(
                row_metric_value(row, metric),
                row_metric_value(baseline, metric),
            )


def pearson_correlation(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None

    x_vals = [x for x, _ in pairs]
    y_vals = [y for _, y in pairs]

    mean_x = sum(x_vals) / len(x_vals)
    mean_y = sum(y_vals) / len(y_vals)

    numer = 0.0
    denom_x = 0.0
    denom_y = 0.0
    for x_val, y_val in pairs:
        dx = x_val - mean_x
        dy = y_val - mean_y
        numer += dx * dy
        denom_x += dx * dx
        denom_y += dy * dy

    if denom_x <= 0.0 or denom_y <= 0.0:
        return None

    return numer / math.sqrt(denom_x * denom_y)


def build_workload_correlations(
    rows: list[PerfSummaryRow],
    metric_columns: list[str],
) -> list[WorkloadCorrelationRow]:
    workload_groups: dict[str, list[PerfSummaryRow]] = {}
    for row in rows:
        workload_groups.setdefault(row.workload, []).append(row)

    correlation_rows: list[WorkloadCorrelationRow] = []
    for workload in sorted(workload_groups.keys(), key=natural_sort_key):
        group_rows = workload_groups[workload]
        thread_values = sorted({r.threads for r in group_rows}, key=natural_sort_key)
        thread_label = thread_values[0] if len(thread_values) == 1 else "mixed"

        corr_row = WorkloadCorrelationRow(
            workload=workload,
            threads=thread_label,
            configs=len(group_rows),
        )

        for metric in metric_columns:
            pairs: list[tuple[float, float]] = []
            for row in group_rows:
                x_raw = row.relative_slowdown
                y_raw = row.relative_increase_by_metric.get(metric)
                if x_raw is None or y_raw is None:
                    continue

                x_val = float(x_raw)
                y_val = float(y_raw)
                if not (math.isfinite(x_val) and math.isfinite(y_val)):
                    continue

                pairs.append((x_val, y_val))

            corr_row.pairs_by_metric[metric] = len(pairs)
            corr_row.correlation_by_metric[metric] = pearson_correlation(pairs)

        correlation_rows.append(corr_row)

    return correlation_rows


def write_correlation_csv(
    output_path: str,
    correlation_rows: list[WorkloadCorrelationRow],
    metric_columns: list[str],
) -> None:
    corr_columns = [f"corr_{RELATIVE_PREFIX}{metric}" for metric in metric_columns]
    pairs_columns = [f"pairs_{RELATIVE_PREFIX}{metric}" for metric in metric_columns]

    with open(output_path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["workload", "threads", "configs", *corr_columns, *pairs_columns])

        for row in correlation_rows:
            writer.writerow(
                [
                    row.workload,
                    row.threads,
                    row.configs,
                    *[row.correlation_by_metric.get(metric) for metric in metric_columns],
                    *[row.pairs_by_metric.get(metric, 0) for metric in metric_columns],
                ]
            )


def print_correlation_table(
    correlation_rows: list[WorkloadCorrelationRow],
    metric_columns: list[str],
) -> None:
    print("Correlation table (per workload): relative_slowdown vs relative metrics")
    print("  workload,threads,metric,pearson_r,n_pairs")

    for row in correlation_rows:
        for metric in metric_columns:
            corr = row.correlation_by_metric.get(metric)
            pairs = row.pairs_by_metric.get(metric, 0)
            if corr is None:
                continue
            print(
                f"  {row.workload},{row.threads},"
                f"{RELATIVE_PREFIX}{metric},{corr:.6f},{pairs}"
            )


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
    parser.add_argument(
        "--safety-margin-sec",
        type=float,
        default=3.0,
        help=(
            "Extra seconds added to detected execution time when slicing perf "
            "samples from the tail (default: 3.0)"
        ),
    )
    parser.add_argument(
        "--disable-runtime-window",
        action="store_true",
        help="Aggregate full perf logs without runtime-window slicing",
    )
    parser.add_argument(
        "--correlation-output",
        default="perf_correlation_summary.csv",
        help=(
            "Output CSV path for per-workload correlations between "
            "relative_slowdown and relative metrics "
            "(default: perf_correlation_summary.csv)"
        ),
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

    if args.safety_margin_sec < 0:
        raise SystemExit("--safety-margin-sec must be >= 0")

    event_columns = list(DEFAULT_EVENT_COLUMNS)
    target_events = set(event_columns)

    metric_columns = [
        "throughput",
        "runtime",
        *event_columns,
        DERIVED_CYCLES_PER_WALK,
        DERIVED_CYCLES_PER_MEMORY_OFFCORE_REQUEST,
    ]
    relative_columns = [f"{RELATIVE_PREFIX}{name}" for name in metric_columns]

    rows: list[PerfSummaryRow] = []
    windowed_files = 0
    for file_path, file_match in iter_matching_files(args.input_dir, filename_re):
        workload = file_match.group("workload")

        base_path = file_path[: -len("_perf.csv")]
        output_path = f"{base_path}_output.log"
        time_path = f"{base_path}_time.txt"
        metrics = parse_metrics_from_logs(workload, output_path, time_path)

        requested_window: float | None = None
        if not args.disable_runtime_window and metrics.execution_seconds is not None:
            requested_window = metrics.execution_seconds + args.safety_margin_sec

        totals_by_event, max_ts = summarize_perf_file(
            file_path,
            target_events,
            requested_window,
        )

        applied_window: float | None = None
        if requested_window is not None and max_ts is not None:
            applied_window = min(max_ts, requested_window)
            windowed_files += 1

        cycles_per_walk = safe_ratio(
            totals_by_event.get(EVENT_DTLB_WALK_PENDING),
            totals_by_event.get(EVENT_DTLB_MISS_CAUSES_WALK),
        )
        cycles_per_memory_offcore_request = safe_ratio(
            totals_by_event.get(EVENT_ORO_DEMAND),
            totals_by_event.get(EVENT_OR_DEMAND),
        )

        rows.append(
            PerfSummaryRow(
                workload=workload,
                threads=file_match.group("threads"),
                memory=file_match.group("memory"),
                path=file_path,
                throughput=metrics.throughput,
                runtime=metrics.runtime,
                execution_seconds=metrics.execution_seconds,
                perf_window_seconds=applied_window,
                totals=totals_by_event,
                cycles_per_walk=cycles_per_walk,
                cycles_per_memory_offcore_request=cycles_per_memory_offcore_request,
            )
        )

    annotate_relative_metrics(rows, metric_columns)
    correlation_rows = build_workload_correlations(rows, metric_columns)

    if args.sort_by_path:
        rows.sort(key=lambda r: r.path)

    with open(args.output, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "workload",
                "threads",
                "memory",
                "throughput",
                "runtime",
                "execution_seconds",
                "perf_window_seconds",
                *event_columns,
                DERIVED_CYCLES_PER_WALK,
                DERIVED_CYCLES_PER_MEMORY_OFFCORE_REQUEST,
                "slowdown",
                "relative_slowdown",
                *relative_columns,
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.workload,
                    row.threads,
                    row.memory,
                    row.throughput,
                    row.runtime,
                    row.execution_seconds,
                    row.perf_window_seconds,
                    *[row.totals.get(col, 0) for col in event_columns],
                    row.cycles_per_walk,
                    row.cycles_per_memory_offcore_request,
                    row.slowdown,
                    row.relative_slowdown,
                    *[row.relative_increase_by_metric.get(col) for col in metric_columns],
                ]
            )

    write_correlation_csv(args.correlation_output, correlation_rows, metric_columns)
    print_correlation_table(correlation_rows, metric_columns)

    print("Summary")
    print(f"  input_dir={args.input_dir}")
    print(f"  matched_files={len(rows)}")
    print(f"  windowed_files={windowed_files}")
    print(f"  output_csv={args.output}")
    print(f"  correlation_csv={args.correlation_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
