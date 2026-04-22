#!/usr/bin/env python3
"""Generate workload-level CDF-style PEBS plots from *_script.txt logs.

The script scans a directory tree recursively, groups PEBS logs by
(directory, workload), and generates three plots per workload group in that
same directory:

- <workload>_cdf.png    : x=unique addresses seen so far, y=total events
- <workload>_local.png  : x=local accesses seen so far, y=total events
- <workload>_remote.png : x=remote accesses seen so far, y=total events

Each line in a plot corresponds to one memory setting, derived from file names
with format workload-memory_threads_script.txt.

Parsing is fully streaming and does not load whole logs into a DataFrame.
"""

from __future__ import annotations

import argparse
import os
import re
from array import array
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Tuple

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_script\.txt$"
)


@dataclass(frozen=True)
class ScriptFile:
    path: str
    directory: str
    workload: str
    memory: str
    threads: str


@dataclass
class FileCurves:
    memory: str
    total_events: int
    unique_hits: array
    local_hits: array
    remote_hits: array


def parse_addr(addr_token: str) -> int | None:
    tok = addr_token.strip().lower()
    if not tok:
        return None

    if tok.startswith("0x"):
        tok = tok[2:]

    try:
        return int(tok, 16)
    except ValueError:
        try:
            return int(tok, 10)
        except ValueError:
            return None


def parse_event_and_addr(line: str) -> tuple[str | None, int | None]:
    stripped = line.lstrip()
    if not stripped or not stripped[0].isdigit():
        return None, None

    first_colon = line.find(":")
    if first_colon < 0:
        return None, None

    second_colon = line.find(":", first_colon + 1)
    if second_colon < 0:
        return None, None

    event = line[first_colon + 1 : second_colon].strip()
    payload = line[second_colon + 1 :].strip()
    if not payload:
        return None, None

    parts = payload.split()
    if not parts:
        return None, None

    addr = parse_addr(parts[0])
    if addr is None:
        return None, None

    return event, addr


def process_script_file(
    path: str,
    local_prefix: str,
    remote_prefix: str,
    buffer_size: int,
) -> FileCurves:
    seen_addrs: set[int] = set()
    unique_hits = array("Q")
    local_hits = array("Q")
    remote_hits = array("Q")

    total_events = 0
    seen_addrs_add = seen_addrs.add
    unique_hits_append = unique_hits.append
    local_hits_append = local_hits.append
    remote_hits_append = remote_hits.append

    with open(path, "r", encoding="utf-8", errors="replace", buffering=buffer_size) as fh:
        for raw in fh:
            event, addr = parse_event_and_addr(raw)
            if event is None or addr is None:
                continue

            total_events += 1

            if event.startswith(local_prefix):
                local_hits_append(total_events)
            if event.startswith(remote_prefix):
                remote_hits_append(total_events)

            if addr not in seen_addrs:
                seen_addrs_add(addr)
                unique_hits_append(total_events)

    return FileCurves(
        memory="",
        total_events=total_events,
        unique_hits=unique_hits,
        local_hits=local_hits,
        remote_hits=remote_hits,
    )


def memory_sort_key(memory: str) -> tuple[int, float, str, str]:
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([a-zA-Z]+)?", memory)
    if match is None:
        return (1, 0.0, "", memory)

    number = float(match.group(1))
    suffix = match.group(2) or ""
    return (0, number, suffix, memory)


def to_plot_xy(hit_events: array, total_events: int) -> tuple[np.ndarray, np.ndarray]:
    if total_events <= 0:
        return np.array([0], dtype=np.uint64), np.array([0], dtype=np.uint64)

    if len(hit_events) == 0:
        return np.array([0, 0], dtype=np.uint64), np.array([0, total_events], dtype=np.uint64)

    x = np.arange(1, len(hit_events) + 1, dtype=np.uint64)
    y = np.frombuffer(hit_events, dtype=np.uint64).copy()

    x0 = np.array([0], dtype=np.uint64)
    y0 = np.array([0], dtype=np.uint64)
    x = np.concatenate((x0, x))
    y = np.concatenate((y0, y))

    if y[-1] < total_events:
        x = np.concatenate((x, np.array([x[-1]], dtype=np.uint64)))
        y = np.concatenate((y, np.array([total_events], dtype=np.uint64)))

    return x, y


def plot_curve_family(
    out_path: str,
    title: str,
    x_label: str,
    curves: Iterable[tuple[str, int, array]],
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6), dpi=dpi)

    for memory, total_events, hit_events in curves:
        x, y = to_plot_xy(hit_events, total_events)
        ax.plot(x, y, linewidth=1.8, label=memory)

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel("Total Events")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.3)
    ax.legend(title="Memory", loc="best")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def discover_script_groups(
    input_dir: str,
    filename_re: re.Pattern[str],
) -> Dict[tuple[str, str], list[ScriptFile]]:
    groups: Dict[tuple[str, str], list[ScriptFile]] = {}

    for current_root, _dirs, files in os.walk(input_dir):
        for name in files:
            if not name.endswith("_script.txt"):
                continue

            match = filename_re.match(name)
            if match is None:
                continue

            workload = match.group("workload")
            memory = match.group("memory")
            threads = match.group("threads")

            path = os.path.join(current_root, name)
            sf = ScriptFile(
                path=path,
                directory=current_root,
                workload=workload,
                memory=memory,
                threads=threads,
            )

            key = (current_root, workload)
            group = groups.get(key)
            if group is None:
                groups[key] = [sf]
            else:
                group.append(sf)

    return groups


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively generate workload-level CDF plots from PEBS *_script.txt logs."
        )
    )
    parser.add_argument("input_dir", help="Root directory to scan recursively")
    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help=(
            "Regex used to parse basename; must define workload, memory, threads named groups."
        ),
    )
    parser.add_argument(
        "--local-prefix",
        default="local_dram",
        help="Event prefix treated as local (default: local_dram)",
    )
    parser.add_argument(
        "--remote-prefix",
        default="remote_dram",
        help="Event prefix treated as remote (default: remote_dram)",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=16 * 1024 * 1024,
        help="Read buffer size in bytes (default: 16 MiB)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Plot DPI (default: 150)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    if args.buffer_size < 1024:
        raise SystemExit("--buffer-size must be at least 1024")

    if args.dpi < 50:
        raise SystemExit("--dpi must be >= 50")

    try:
        filename_re = re.compile(args.filename_regex)
    except re.error as exc:
        raise SystemExit(f"Invalid --filename-regex: {exc}") from exc

    required = {"workload", "memory", "threads"}
    if not required.issubset(filename_re.groupindex.keys()):
        raise SystemExit(
            "--filename-regex must define named groups: workload, memory, threads"
        )

    groups = discover_script_groups(args.input_dir, filename_re)
    if not groups:
        raise SystemExit("No matching *_script.txt files found")

    generated = 0
    for (directory, workload), scripts in sorted(groups.items()):
        scripts.sort(key=lambda sf: memory_sort_key(sf.memory))

        series: list[FileCurves] = []
        for sf in scripts:
            result = process_script_file(
                path=sf.path,
                local_prefix=args.local_prefix,
                remote_prefix=args.remote_prefix,
                buffer_size=args.buffer_size,
            )
            result.memory = sf.memory
            series.append(result)

        cdf_curves = [(entry.memory, entry.total_events, entry.unique_hits) for entry in series]
        local_curves = [(entry.memory, entry.total_events, entry.local_hits) for entry in series]
        remote_curves = [(entry.memory, entry.total_events, entry.remote_hits) for entry in series]

        cdf_path = os.path.join(directory, f"{workload}_cdf.png")
        local_path = os.path.join(directory, f"{workload}_local.png")
        remote_path = os.path.join(directory, f"{workload}_remote.png")

        plot_curve_family(
            out_path=cdf_path,
            title=f"{workload}: Unique Address Progression",
            x_label="Unique Addresses Seen So Far",
            curves=cdf_curves,
            dpi=args.dpi,
        )
        plot_curve_family(
            out_path=local_path,
            title=f"{workload}: Local Access Progression",
            x_label="Local Accesses Seen So Far",
            curves=local_curves,
            dpi=args.dpi,
        )
        plot_curve_family(
            out_path=remote_path,
            title=f"{workload}: Remote Access Progression",
            x_label="Remote Accesses Seen So Far",
            curves=remote_curves,
            dpi=args.dpi,
        )

        generated += 3
        print(
            f"Generated workload plots: workload={workload} files={len(series)} dir={directory}"
        )

    print("Summary")
    print(f"  groups={len(groups)}")
    print(f"  generated_pngs={generated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
