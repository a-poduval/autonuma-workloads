#!/usr/bin/env python3
"""Recursive PEBS text log analyzer.

Scans a directory tree for PEBS script files and writes one CSV row per file.

Default filename format:
  workload-memory_threads_script.txt

Supports both PEBS layouts:
  1) One-line record (new):
     <timestamp>:  <event>: <addr> <ip> <symbol>
  2) Two-line record (legacy):
     <timestamp>:  <event>: <addr> <ip>
     <symbol/offset line>

For each matching file, this script reports:
  workload, threads, memory, total_samples, local_dram_events,
  remote_dram_events, unique_ips, and top-5 symbol/count pairs.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator, TextIO


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_script\.txt$"
)


@dataclass
class FileStats:
    workload: str
    threads: str
    memory: str
    total_samples: int
    local_dram_events: int
    remote_dram_events: int
    unique_ips: int
    top_symbols: list[tuple[str, int]]
    path: str


def _looks_like_hex_token(token: str) -> bool:
    tok = token.lower().strip()
    if not tok:
        return False
    if tok.startswith("0x"):
        tok = tok[2:]
    return bool(re.fullmatch(r"[0-9a-f]+", tok))


def parse_event_ip_symbol(line: str) -> tuple[str | None, str | None, str | None]:
    """Extract event, ip, and optional symbol from one PEBS line.

    Returns:
      (event, ip, symbol)
      - For new one-line layout, symbol is non-None.
      - For legacy header-only line, symbol is None.
      - For non-record lines, all values are None.
    """
    stripped = line.lstrip()
    if not stripped or not stripped[0].isdigit():
        return None, None, None

    first_colon = line.find(":")
    if first_colon < 0:
        return None, None, None

    second_colon = line.find(":", first_colon + 1)
    if second_colon < 0:
        return None, None, None

    event = line[first_colon + 1 : second_colon].strip()
    payload = line[second_colon + 1 :].strip()
    if not payload:
        return event, None, None

    parts = payload.split()
    if len(parts) < 2:
        return event, None, None

    # New one-line format typically starts with <addr> <ip> then symbol tokens.
    if len(parts) >= 3 and _looks_like_hex_token(parts[0]) and _looks_like_hex_token(parts[1]):
        ip = parts[1]
        symbol = " ".join(parts[2:]).strip() or "<blank_symbol>"
        return event, ip, symbol

    # Legacy header line keeps only addr and ip; symbol comes on next line.
    return event, parts[-1], None


def _accumulate(
    event: str,
    ip: str,
    symbol: str,
    local_prefix: str,
    remote_prefix: str,
    ips: set[str],
    symbol_counts: Counter[str],
) -> tuple[int, int, int]:
    ips.add(ip)
    symbol_counts[symbol] += 1
    local_inc = 1 if event.startswith(local_prefix) else 0
    remote_inc = 1 if event.startswith(remote_prefix) else 0
    return 1, local_inc, remote_inc


def process_stream(
    fh: TextIO,
    local_prefix: str,
    remote_prefix: str,
) -> tuple[int, int, int, set[str], Counter[str]]:
    """Process one PEBS file stream and return counters.

    Returns:
      (total_samples, local_events, remote_events, unique_ip_set, symbol_counter)
    """
    total_samples = 0
    local_events = 0
    remote_events = 0
    ips: set[str] = set()
    symbol_counts: Counter[str] = Counter()

    pending: tuple[str, str] | None = None

    for raw in fh:
        event, ip, symbol = parse_event_ip_symbol(raw)

        if event is not None and ip is not None:
            # New one-line record: finalize immediately.
            if symbol is not None:
                if pending is not None:
                    p_event, p_ip = pending
                    t, l, r = _accumulate(
                        p_event,
                        p_ip,
                        "<missing_symbol>",
                        local_prefix,
                        remote_prefix,
                        ips,
                        symbol_counts,
                    )
                    total_samples += t
                    local_events += l
                    remote_events += r
                    pending = None

                t, l, r = _accumulate(
                    event,
                    ip,
                    symbol,
                    local_prefix,
                    remote_prefix,
                    ips,
                    symbol_counts,
                )
                total_samples += t
                local_events += l
                remote_events += r
                continue

            # Legacy header line, wait for symbol on next non-header line.
            if pending is not None:
                p_event, p_ip = pending
                t, l, r = _accumulate(
                    p_event,
                    p_ip,
                    "<missing_symbol>",
                    local_prefix,
                    remote_prefix,
                    ips,
                    symbol_counts,
                )
                total_samples += t
                local_events += l
                remote_events += r

            pending = (event, ip)
            continue

        if pending is None:
            continue

        symbol_line = raw.strip() or "<blank_symbol>"
        p_event, p_ip = pending
        t, l, r = _accumulate(
            p_event,
            p_ip,
            symbol_line,
            local_prefix,
            remote_prefix,
            ips,
            symbol_counts,
        )
        total_samples += t
        local_events += l
        remote_events += r
        pending = None

    if pending is not None:
        p_event, p_ip = pending
        t, l, r = _accumulate(
            p_event,
            p_ip,
            "<missing_symbol>",
            local_prefix,
            remote_prefix,
            ips,
            symbol_counts,
        )
        total_samples += t
        local_events += l
        remote_events += r

    return total_samples, local_events, remote_events, ips, symbol_counts


def iter_matching_files(root_dir: str, filename_re: re.Pattern[str]) -> Iterator[tuple[str, re.Match[str]]]:
    """Yield all files under root_dir with names matching filename_re."""
    for current_root, _, files in os.walk(root_dir):
        for name in files:
            match = filename_re.match(name)
            if match is None:
                continue
            yield os.path.join(current_root, name), match


def analyze_file(
    file_path: str,
    file_match: re.Match[str],
    local_prefix: str,
    remote_prefix: str,
    top_n: int,
    buffer_size: int,
) -> FileStats:
    """Analyze a single PEBS file and return row-ready stats."""
    with open(file_path, "r", encoding="utf-8", errors="replace", buffering=buffer_size) as fh:
        total_samples, local_events, remote_events, ips, symbol_counts = process_stream(
            fh,
            local_prefix=local_prefix,
            remote_prefix=remote_prefix,
        )

    return FileStats(
        workload=file_match.group("workload"),
        threads=file_match.group("threads"),
        memory=file_match.group("memory"),
        total_samples=total_samples,
        local_dram_events=local_events,
        remote_dram_events=remote_events,
        unique_ips=len(ips),
        top_symbols=symbol_counts.most_common(max(top_n, 0)),
        path=file_path,
    )


def write_csv(path: str, rows: Iterable[FileStats], top_n: int) -> None:
    """Write analysis rows to CSV with fixed top-N symbol columns."""
    header = [
        "workload",
        "threads",
        "memory",
        "total_samples",
        "local_dram_events",
        "remote_dram_events",
        "unique_ips",
    ]
    for idx in range(1, top_n + 1):
        header.append(f"top{idx}_count")
        header.append(f"top{idx}_symbol")

    with open(path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(header)

        for row in rows:
            csv_row: list[object] = [
                row.workload,
                row.threads,
                row.memory,
                row.total_samples,
                row.local_dram_events,
                row.remote_dram_events,
                row.unique_ips,
            ]

            for idx in range(top_n):
                if idx < len(row.top_symbols):
                    symbol, count = row.top_symbols[idx]
                    csv_row.extend([count, symbol])
                else:
                    csv_row.extend(["", ""])

            writer.writerow(csv_row)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively analyze PEBS script files and produce CSV summaries."
    )
    parser.add_argument("input_dir", help="Root directory to scan recursively")
    parser.add_argument(
        "--output",
        default="pebs_summary.csv",
        help="Output CSV path (default: pebs_summary.csv)",
    )
    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help=(
            "Regex used to identify PEBS files from basename. Must contain named "
            "groups: workload, memory, threads."
        ),
    )
    parser.add_argument(
        "--local-prefix",
        default="local_dram",
        help="Event prefix counted as local DRAM (default: local_dram)",
    )
    parser.add_argument(
        "--remote-prefix",
        default="remote_dram",
        help="Event prefix counted as remote DRAM (default: remote_dram)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top symbols to include in CSV (default: 5)",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=16 * 1024 * 1024,
        help="Read buffer size in bytes (default: 16 MiB)",
    )
    parser.add_argument(
        "--sort-by-path",
        action="store_true",
        help="Sort output rows by file path for deterministic CSV order",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    if args.top < 0:
        raise SystemExit("--top must be >= 0")

    try:
        filename_re = re.compile(args.filename_regex)
    except re.error as exc:
        raise SystemExit(f"Invalid --filename-regex: {exc}") from exc

    required = {"workload", "memory", "threads"}
    if not required.issubset(filename_re.groupindex.keys()):
        raise SystemExit(
            "--filename-regex must define named groups: workload, memory, threads"
        )

    rows: list[FileStats] = []
    for file_path, file_match in iter_matching_files(args.input_dir, filename_re):
        rows.append(
            analyze_file(
                file_path=file_path,
                file_match=file_match,
                local_prefix=args.local_prefix,
                remote_prefix=args.remote_prefix,
                top_n=args.top,
                buffer_size=args.buffer_size,
            )
        )

    if args.sort_by_path:
        rows.sort(key=lambda r: r.path)

    write_csv(args.output, rows, top_n=args.top)

    print("Summary")
    print(f"  input_dir={args.input_dir}")
    print(f"  matched_files={len(rows)}")
    print(f"  output_csv={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
