"""Parse workload runtime/throughput from sibling output/time logs."""

from __future__ import annotations

import os
import re

from .models import WorkloadMetrics
from .text_parsing import parse_duration_to_seconds, parse_float_token


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

            trial_values = [
                val
                for val in (
                    parse_float_token(raw)
                    for raw in re.findall(
                        r"Trial\s+Time:\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
                        output_text,
                        flags=re.IGNORECASE,
                    )
                )
                if val is not None
            ]
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

            repeat_values_ms = [
                val
                for val in (
                    parse_float_token(raw)
                    for raw in re.findall(
                        r"REPEAT\s*#\s*\d+\s+Baseline\s+Total\s+time\s*:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*ms",
                        output_text,
                        flags=re.IGNORECASE,
                    )
                )
                if val is not None
            ]
            if repeat_values_ms:
                metrics.execution_seconds = sum(repeat_values_ms) / 1000.0
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
