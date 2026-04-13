#!/usr/bin/env python3
"""Fast PEBS heatmap plotter for very large script logs.

Supports both PEBS layouts:
  1) One-line record (new):
      <timestamp>:  <event>: <addr> <ip> <symbol>
  2) Two-line record (legacy):
      <timestamp>:  <event>: <addr> <ip>
      <symbol/offset line>

This tool generates 12 heatmaps in the output directory:
  workload-memory-threads-all-total.png
  workload-memory-threads-all-local.png
  workload-memory-threads-all-remote.png
  workload-memory-threads-1-total.png
  ...
  workload-memory-threads-3-remote.png

Group 0 ("all") includes all events.
Groups 1..3 correspond to top-3 (ip, symbol/offset) pairs by total accesses.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from typing import Dict, Iterable, TextIO

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_script\.txt$"
)

CATEGORY_NAMES = ("total", "local", "remote")
USER_SPACE_MAX = 0x0000800000000000


@dataclass(frozen=True)
class HeaderRecord:
    ts: float
    event: str
    addr: int
    ip: str
    inline_symbol: str | None = None


@dataclass(frozen=True)
class AddressMapper:
    page_shift: int
    pages: list[int]
    page_to_idx: Dict[int, int]

    def bin_index(self, addr: int) -> int | None:
        page = addr >> self.page_shift
        return self.page_to_idx.get(page)

    def representative_addr(self, row: int) -> int:
        if not self.pages:
            return 0
        row = max(0, min(len(self.pages) - 1, row))
        return self.pages[row] << self.page_shift


def build_address_mapper(
    page_shift: int,
    pages: list[int],
) -> AddressMapper:
    return AddressMapper(
        page_shift=page_shift,
        pages=pages,
        page_to_idx={page: idx for idx, page in enumerate(pages)},
    )


def select_pages_for_plot(
    page_counts: Dict[int, int],
    full_page_space: bool,
    min_page_count: int,
    max_pages: int,
    coverage: float,
) -> list[int]:
    if not page_counts:
        return []

    if full_page_space:
        return sorted(page_counts.keys())

    capped_max_pages = max(1, max_pages)
    target_coverage = min(1.0, max(0.0, coverage))
    min_count = max(1, min_page_count)

    eligible = [(page, cnt) for page, cnt in page_counts.items() if cnt >= min_count]
    if not eligible:
        eligible = list(page_counts.items())

    eligible.sort(key=lambda kv: kv[1], reverse=True)
    total = sum(cnt for _page, cnt in page_counts.items())
    cumulative = 0
    selected: list[int] = []

    for page, cnt in eligible:
        if len(selected) >= capped_max_pages:
            break
        selected.append(page)
        cumulative += cnt
        if total > 0 and cumulative / total >= target_coverage:
            break

    # Keep vertical axis monotonic by address.
    selected.sort()
    return selected


def parse_timestamp_seconds(ts: str) -> float | None:
    ts = ts.strip()
    if not ts:
        return None

    # Fast path for integer timestamp token.
    if ts.isdigit():
        return float(int(ts))

    # General float parse for decimal timestamps.
    try:
        return float(ts)
    except ValueError:
        return None


def parse_addr(addr_token: str) -> int | None:
    tok = addr_token.strip().lower()
    if not tok:
        return None

    if tok.startswith("0x"):
        tok = tok[2:]

    # Typical PEBS addresses are hex; allow decimal fallback for robustness.
    try:
        return int(tok, 16)
    except ValueError:
        try:
            return int(tok, 10)
        except ValueError:
            return None


def _looks_like_hex_token(token: str) -> bool:
    tok = token.lower().strip()
    if not tok:
        return False
    if tok.startswith("0x"):
        tok = tok[2:]
    return bool(re.fullmatch(r"[0-9a-f]+", tok))


def parse_header(line: str) -> HeaderRecord | None:
    stripped = line.lstrip()
    if not stripped or not stripped[0].isdigit():
        return None

    first_colon = line.find(":")
    if first_colon < 0:
        return None

    second_colon = line.find(":", first_colon + 1)
    if second_colon < 0:
        return None

    ts = parse_timestamp_seconds(line[:first_colon])
    if ts is None:
        return None

    event = line[first_colon + 1 : second_colon].strip()
    payload = line[second_colon + 1 :].strip()
    if not payload:
        return None

    parts = payload.split()
    if len(parts) < 2:
        return None

    # New one-line format starts with <addr> <ip> and carries inline symbol tokens.
    if len(parts) >= 3 and _looks_like_hex_token(parts[0]) and _looks_like_hex_token(parts[1]):
        addr = parse_addr(parts[0])
        if addr is None:
            return None
        ip = parts[1]
        inline_symbol = " ".join(parts[2:]).strip() or "<blank_symbol>"
        return HeaderRecord(ts=ts, event=event, addr=addr, ip=ip, inline_symbol=inline_symbol)

    # Legacy two-line format keeps symbol on the following line.
    addr = parse_addr(parts[-2])
    if addr is None:
        return None

    ip = parts[-1]
    return HeaderRecord(ts=ts, event=event, addr=addr, ip=ip)


def iter_records(
    fh: TextIO,
    local_prefix: str,
    remote_prefix: str,
) -> Iterable[tuple[float, int, str, str, str, int, int]]:
    """Yield finalized records: (timestamp, addr, event, ip, symbol, is_local, is_remote)."""
    pending: HeaderRecord | None = None

    for raw in fh:
        header = parse_header(raw)
        if header is not None:
            if pending is not None:
                is_local = 1 if pending.event.startswith(local_prefix) else 0
                is_remote = 1 if pending.event.startswith(remote_prefix) else 0
                yield (
                    pending.ts,
                    pending.addr,
                    pending.event,
                    pending.ip,
                    "<missing_symbol>",
                    is_local,
                    is_remote,
                )

            if header.inline_symbol is not None:
                is_local = 1 if header.event.startswith(local_prefix) else 0
                is_remote = 1 if header.event.startswith(remote_prefix) else 0
                yield (
                    header.ts,
                    header.addr,
                    header.event,
                    header.ip,
                    header.inline_symbol,
                    is_local,
                    is_remote,
                )
                pending = None
            else:
                pending = header
            continue

        if pending is None:
            continue

        symbol = raw.strip() or "<blank_symbol>"
        is_local = 1 if pending.event.startswith(local_prefix) else 0
        is_remote = 1 if pending.event.startswith(remote_prefix) else 0
        yield (
            pending.ts,
            pending.addr,
            pending.event,
            pending.ip,
            symbol,
            is_local,
            is_remote,
        )
        pending = None

    if pending is not None:
        is_local = 1 if pending.event.startswith(local_prefix) else 0
        is_remote = 1 if pending.event.startswith(remote_prefix) else 0
        yield (
            pending.ts,
            pending.addr,
            pending.event,
            pending.ip,
            "<missing_symbol>",
            is_local,
            is_remote,
        )


def output_prefix_from_path(path: str, filename_regex: str) -> str:
    base = os.path.basename(path)
    match = re.match(filename_regex, base)
    if match is None:
        stem = base
        if stem.endswith(".txt"):
            stem = stem[:-4]
        if stem.endswith("_script"):
            stem = stem[:-7]
        return stem

    workload = match.group("workload")
    memory = match.group("memory")
    threads = match.group("threads")
    return f"{workload}-{memory}-{threads}"


def make_heatmap(
    data: np.ndarray,
    mapper: AddressMapper,
    out_path: str,
    title: str,
    ts_min: float,
    time_bin_seconds: float,
    color_scale: str,
    colormap: str,
) -> None:
    fig, ax = plt.subplots(figsize=(13, 6), dpi=140)
    time_bins = data.shape[1]
    extent = [0.0, time_bins * time_bin_seconds, 0, max(1, len(mapper.pages))]

    show_data = data
    cbar_label = "Access count"
    if color_scale == "log1p":
        show_data = np.log1p(data.astype(np.float64))
        cbar_label = "log1p(access count)"

    # Keep true zero-access bins as white so faint activity stands out.
    masked = np.ma.masked_less_equal(show_data, 0)
    if colormap == "wbpv-bands":
        # Cold -> warm -> hot: light green -> blue -> violet.
        cmap = ListedColormap([
            "#d7f5d8",  # very low
            "#9ee8aa",
            "#62c8c9",
            "#3f95de",
            "#3e58c9",
            "#6b3ecf",
            "#8c2fb6",  # hottest
        ])
        positive = show_data[show_data > 0]
        if positive.size > 0:
            # Quantile-based bands improve contrast for skewed access distributions.
            qs = np.array([0.0, 0.15, 0.35, 0.55, 0.72, 0.86, 0.94, 1.0])
            bounds = np.quantile(positive, qs)
            bounds = np.maximum.accumulate(bounds)
            # Ensure strictly increasing boundaries for BoundaryNorm.
            for i in range(1, bounds.size):
                if bounds[i] <= bounds[i - 1]:
                    bounds[i] = bounds[i - 1] + 1e-9
            norm = BoundaryNorm(bounds, cmap.N, clip=True)
        else:
            norm = None
    else:
        cmap = plt.get_cmap(colormap).copy()
        norm = None
    cmap.set_bad("white")

    im = ax.imshow(
        masked,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
        norm=norm,
        extent=extent,
    )
    ax.set_xlabel("Time Since Start (seconds)")
    ax.set_ylabel("Address")
    ax.set_title(title)
    tick_count = 8
    row_count = max(1, len(mapper.pages))
    ticks = np.linspace(0, row_count - 1, num=tick_count, dtype=int)
    labels = [f"0x{mapper.representative_addr(int(row)):x}" for row in ticks]
    ax.set_yticks(ticks + 0.5)
    ax.set_yticklabels(labels)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(cbar_label)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def debug_print_structures(
    heatmaps: np.ndarray,
    ts_min: float,
    time_bin_seconds: float,
    epoch_page_counts: Dict[int, Dict[int, int]],
    page_shift: int,
    max_epochs: int,
    max_addresses: int,
) -> None:
    all_total = heatmaps[0, 0]
    page_bins, time_bins = all_total.shape

    print("DEBUG: core matrix structure")
    print(f"  heatmaps_shape={tuple(heatmaps.shape)}")
    print(f"  all_total_shape=(pages={page_bins}, time_bins={time_bins})")

    print("DEBUG: sparse epoch->page->count structure (truncated)")
    shown = 0
    for epoch in sorted(epoch_page_counts.keys()):
        if shown >= max_epochs:
            break
        page_map = epoch_page_counts[epoch]
        top_pages = sorted(page_map.items(), key=lambda kv: kv[1], reverse=True)[:max_addresses]
        pretty = {f"0x{(p << page_shift):x}": c for p, c in top_pages}
        rel_t = epoch * time_bin_seconds
        abs_t = ts_min + rel_t
        print(f"  epoch={epoch} rel_t={rel_t:.3f}s abs_t={abs_t:.3f} page_counts={pretty}")
        shown += 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate PEBS address-vs-time heatmaps (all + top-3 ip/symbol hotspots)."
    )
    parser.add_argument("file", help="PEBS script text input file")
    parser.add_argument(
        "--output-dir",
        default="pebs_access_plots",
        help="Directory for output PNGs (default: pebs_access_plots)",
    )
    parser.add_argument(
        "--filename-regex",
        default=DEFAULT_FILENAME_REGEX,
        help=(
            "Regex for deriving workload-memory-threads from input basename. "
            "Must provide named groups: workload, memory, threads."
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
        default=3,
        help="Number of top (ip,symbol) hotspots to plot (default: 3)",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=16 * 1024 * 1024,
        help="Read buffer size in bytes (default: 16 MiB)",
    )
    parser.add_argument(
        "--address-space",
        choices=("user", "all", "kernel"),
        default="user",
        help=(
            "Address space to include: user ignores kernel addresses, all includes both, "
            "kernel includes only kernel addresses (default: user)."
        ),
    )
    parser.add_argument(
        "--page-size",
        choices=("4k", "2m"),
        default="2m",
        help="Page granularity for page-based heatmaps (default: 2m)",
    )
    parser.add_argument(
        "--time-bin-seconds",
        type=float,
        default=1.0,
        help="Time bin width in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--color-scale",
        choices=("linear", "log1p"),
        default="linear",
        help="Color scaling for heatmaps (default: linear)",
    )
    parser.add_argument(
        "--colormap",
        default="wbpv-bands",
        help=(
            "Colormap name. Use wbpv-bands for white->green->blue->violet banded map "
            "(default), or any Matplotlib colormap."
        ),
    )
    parser.add_argument(
        "--full-page-space",
        action="store_true",
        help="Disable default hot-page filtering and include all pages",
    )
    parser.add_argument(
        "--min-page-count",
        type=int,
        default=2,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=4096,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--coverage",
        type=float,
        default=0.995,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--debug-print-structures",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--debug-max-epochs",
        type=int,
        default=6,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--debug-max-addresses",
        type=int,
        default=8,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--debug-max-nonzero-per-address",
        type=int,
        default=12,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--debug-capture-epochs",
        type=int,
        default=64,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def is_selected_address(addr: int, address_space: str) -> bool:
    is_user = addr < USER_SPACE_MAX
    if address_space == "user":
        return is_user
    if address_space == "kernel":
        return not is_user
    return True


def page_shift_from_size(page_size: str) -> int:
    if page_size == "4k":
        return 12
    if page_size == "2m":
        return 21
    raise ValueError(f"Unsupported page size: {page_size}")


def main() -> int:
    args = build_arg_parser().parse_args()

    if args.top < 1:
        raise SystemExit("--top must be >= 1")
    if args.time_bin_seconds <= 0:
        raise SystemExit("--time-bin-seconds must be > 0")
    if args.debug_max_epochs < 1:
        raise SystemExit("--debug-max-epochs must be >= 1")
    if args.debug_max_addresses < 1:
        raise SystemExit("--debug-max-addresses must be >= 1")
    if args.debug_max_nonzero_per_address < 1:
        raise SystemExit("--debug-max-nonzero-per-address must be >= 1")
    if args.debug_capture_epochs < 1:
        raise SystemExit("--debug-capture-epochs must be >= 1")
    if args.min_page_count < 1:
        raise SystemExit("--min-page-count must be >= 1")
    if args.max_pages < 1:
        raise SystemExit("--max-pages must be >= 1")
    if not (0.0 < args.coverage <= 1.0):
        raise SystemExit("--coverage must be in (0, 1]")

    page_shift = page_shift_from_size(args.page_size)

    pair_stats: Dict[tuple[str, str], list[int]] = {}
    ts_min: float | None = None
    ts_max: float | None = None
    addr_min: int | None = None
    addr_max: int | None = None
    page_counts: Dict[int, int] = {}
    dropped_by_space = 0
    kept_records = 0

    # Pass 1: discover ranges and top hotspots.
    with open(args.file, "r", encoding="utf-8", errors="replace", buffering=args.buffer_size) as fh:
        for ts, addr, _event, ip, symbol, is_local, is_remote in iter_records(
            fh, args.local_prefix, args.remote_prefix
        ):
            if not is_selected_address(addr, args.address_space):
                dropped_by_space += 1
                continue

            kept_records += 1
            if ts_min is None or ts < ts_min:
                ts_min = ts
            if ts_max is None or ts > ts_max:
                ts_max = ts
            if addr_min is None or addr < addr_min:
                addr_min = addr
            if addr_max is None or addr > addr_max:
                addr_max = addr

            page = addr >> page_shift
            page_counts[page] = page_counts.get(page, 0) + 1

            key = (ip, symbol)
            stats = pair_stats.get(key)
            if stats is None:
                pair_stats[key] = [1, is_local, is_remote]
            else:
                stats[0] += 1
                stats[1] += is_local
                stats[2] += is_remote

    if ts_min is None or ts_max is None or addr_min is None or addr_max is None:
        raise SystemExit(
            "No valid PEBS records found after address-space filtering; "
            "try --address-space all"
        )

    top_items = sorted(pair_stats.items(), key=lambda kv: kv[1][0], reverse=True)[: args.top]
    top_keys = [item[0] for item in top_items]

    # Keep exactly 3 hotspot groups in filenames; missing groups remain zero-filled.
    while len(top_keys) < 3:
        top_keys.append(("<none>", f"<none_{len(top_keys) + 1}>") )

    time_bins = int((ts_max - ts_min) / args.time_bin_seconds) + 1
    pages = select_pages_for_plot(
        page_counts=page_counts,
        full_page_space=args.full_page_space,
        min_page_count=args.min_page_count,
        max_pages=args.max_pages,
        coverage=args.coverage,
    )
    if not pages:
        raise SystemExit("No pages collected after filtering")
    mapper = build_address_mapper(
        page_shift=page_shift,
        pages=pages,
    )

    # heatmaps[group_index][category][page_index][time_index]
    heatmaps = np.zeros((4, 3, len(pages), time_bins), dtype=np.uint32)
    epoch_page_counts: Dict[int, Dict[int, int]] = {}

    top_lookup = {key: idx + 1 for idx, key in enumerate(top_keys[:3])}

    # Pass 2: fill dense arrays with direct integer indexing.
    with open(args.file, "r", encoding="utf-8", errors="replace", buffering=args.buffer_size) as fh:
        for ts, addr, _event, ip, symbol, is_local, is_remote in iter_records(
            fh, args.local_prefix, args.remote_prefix
        ):
            if not is_selected_address(addr, args.address_space):
                continue

            t_idx = int((ts - ts_min) / args.time_bin_seconds)
            if t_idx < 0:
                t_idx = 0
            elif t_idx >= time_bins:
                t_idx = time_bins - 1
            a_idx = mapper.bin_index(addr)
            if a_idx is None:
                continue

            if args.debug_print_structures:
                if t_idx in epoch_page_counts or len(epoch_page_counts) < args.debug_capture_epochs:
                    page = addr >> page_shift
                    ep = epoch_page_counts.get(t_idx)
                    if ep is None:
                        ep = {}
                        epoch_page_counts[t_idx] = ep
                    ep[page] = ep.get(page, 0) + 1

            heatmaps[0, 0, a_idx, t_idx] += 1
            if is_local:
                heatmaps[0, 1, a_idx, t_idx] += 1
            if is_remote:
                heatmaps[0, 2, a_idx, t_idx] += 1

            group = top_lookup.get((ip, symbol))
            if group is None:
                continue

            heatmaps[group, 0, a_idx, t_idx] += 1
            if is_local:
                heatmaps[group, 1, a_idx, t_idx] += 1
            if is_remote:
                heatmaps[group, 2, a_idx, t_idx] += 1

    os.makedirs(args.output_dir, exist_ok=True)
    out_prefix = output_prefix_from_path(args.file, args.filename_regex)

    all_stats_total = int(heatmaps[0, 0].sum())
    all_stats_local = int(heatmaps[0, 1].sum())
    all_stats_remote = int(heatmaps[0, 2].sum())

    all_titles = (
        f"all accesses | total={all_stats_total} local={all_stats_local} remote={all_stats_remote}",
        f"all accesses | local DRAM only | count={all_stats_local}",
        f"all accesses | remote DRAM only | count={all_stats_remote}",
    )

    if args.debug_print_structures:
        debug_print_structures(
            heatmaps=heatmaps,
            ts_min=ts_min,
            time_bin_seconds=args.time_bin_seconds,
            epoch_page_counts=epoch_page_counts,
            page_shift=page_shift,
            max_epochs=args.debug_max_epochs,
            max_addresses=args.debug_max_addresses,
        )

    if not args.skip_plots:
        for cat_idx, cat_name in enumerate(CATEGORY_NAMES):
            out_name = f"{out_prefix}-all-{cat_name}.png"
            make_heatmap(
                heatmaps[0, cat_idx],
                mapper,
                os.path.join(args.output_dir, out_name),
                all_titles[cat_idx],
                ts_min,
                args.time_bin_seconds,
                args.color_scale,
                args.colormap,
            )

        for rank in range(1, 4):
            ip, symbol = top_keys[rank - 1]
            pair_key = (ip, symbol)
            stats = pair_stats.get(pair_key, [0, 0, 0])
            total, local, remote = stats

            titles = (
                f"rank {rank} | {symbol} | ip={ip} | total={total} local={local} remote={remote}",
                f"rank {rank} | {symbol} | ip={ip} | local={local}",
                f"rank {rank} | {symbol} | ip={ip} | remote={remote}",
            )

            for cat_idx, cat_name in enumerate(CATEGORY_NAMES):
                out_name = f"{out_prefix}-{rank}-{cat_name}.png"
                make_heatmap(
                    heatmaps[rank, cat_idx],
                    mapper,
                    os.path.join(args.output_dir, out_name),
                    titles[cat_idx],
                    ts_min,
                    args.time_bin_seconds,
                    args.color_scale,
                    args.colormap,
                )

    print("Generated heatmaps:")
    print(f"  output_dir={args.output_dir}")
    print(f"  prefix={out_prefix}")
    print(f"  time_range=[{ts_min:.6f}, {ts_max:.6f}] bins={time_bins}")
    print(f"  normalized_time_range=[0.000000, {ts_max - ts_min:.6f}] bins={time_bins}")
    print(f"  addr_range=[0x{addr_min:x}, 0x{addr_max:x}] pages={len(pages)} page_size={args.page_size}")
    if args.full_page_space:
        print("  page_selection=all-pages")
    else:
        dropped_pages = max(0, len(page_counts) - len(pages))
        print(
            f"  page_selection=hot-pages coverage={args.coverage:.3f} "
            f"min_page_count={args.min_page_count} selected={len(pages)} dropped={dropped_pages}"
        )
    print(f"  address_space={args.address_space} kept={kept_records} dropped={dropped_by_space}")
    print("  address_mapping=page-index")
    print(f"  time_bin_seconds={args.time_bin_seconds}")
    print(f"  color_scale={args.color_scale}")
    print(f"  colormap={args.colormap}")
    for rank in range(1, 4):
        ip, symbol = top_keys[rank - 1]
        stats = pair_stats.get((ip, symbol), [0, 0, 0])
        print(
            f"  top{rank}: ip={ip} symbol={symbol} "
            f"total={stats[0]} local={stats[1]} remote={stats[2]}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
