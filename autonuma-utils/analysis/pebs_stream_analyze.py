#!/usr/bin/env python3
"""Streaming PEBS text log analyzer.

Expected record format (2 lines per sample):
  <timestamp>:  <event>: <addr> <ip>
  <symbol/offset line>

The parser reads line-by-line (streaming) and never loads the entire file.
"""

from __future__ import annotations

import argparse
import heapq
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, TextIO


@dataclass(frozen=True)
class Insn:
    offset: int
    text: str
    function: str


def parse_event_and_ip(line: str) -> tuple[str | None, str | None]:
    """Extract event name and IP token from the first line of a PEBS record."""
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
        return event, None

    parts = payload.split()
    if not parts:
        return event, None

    # In observed logs, IP is the last token (<addr> <ip>). This is robust to spacing.
    ip = parts[-1]
    return event, ip


def add_record(
    ip_stats: Dict[str, list],
    event: str,
    ip: str,
    symbol: str,
    local_prefix: str,
    remote_prefix: str,
) -> tuple[int, int]:
    """Add a parsed sample record and return local/remote event deltas."""
    local_delta = 1 if event.startswith(local_prefix) else 0
    remote_delta = 1 if event.startswith(remote_prefix) else 0

    entry = ip_stats.get(ip)
    if entry is None:
        # entry layout: [total_count, {symbol_line: symbol_count}]
        ip_stats[ip] = [1, {symbol: 1}]
    else:
        entry[0] += 1
        sym_counts = entry[1]
        sym_counts[symbol] = sym_counts.get(symbol, 0) + 1

    return local_delta, remote_delta


def process_stream(
    fh: TextIO,
    local_prefix: str,
    remote_prefix: str,
    ip_stats: Dict[str, list],
) -> tuple[int, int, int, int]:
    """Process one PEBS file handle.

    Returns:
      (local_events, remote_events, total_samples, malformed_records)
    """
    local_events = 0
    remote_events = 0
    total_samples = 0
    malformed = 0
    pending: tuple[str, str] | None = None

    for raw in fh:
        event, ip = parse_event_and_ip(raw)
        if event is not None and ip is not None:
            # If the previous record had no symbol line, finalize it now and resync.
            if pending is not None:
                prev_event, prev_ip = pending
                dl, dr = add_record(
                    ip_stats,
                    prev_event,
                    prev_ip,
                    "<missing_symbol>",
                    local_prefix,
                    remote_prefix,
                )
                local_events += dl
                remote_events += dr
                total_samples += 1
                malformed += 1

            pending = (event, ip)
            continue

        if pending is None:
            # Stray line outside a record; track and continue scanning.
            malformed += 1
            continue

        symbol = raw.strip() or "<blank_symbol>"
        prev_event, prev_ip = pending
        dl, dr = add_record(
            ip_stats,
            prev_event,
            prev_ip,
            symbol,
            local_prefix,
            remote_prefix,
        )
        local_events += dl
        remote_events += dr
        total_samples += 1
        pending = None

    if pending is not None:
        prev_event, prev_ip = pending
        dl, dr = add_record(
            ip_stats,
            prev_event,
            prev_ip,
            "<missing_symbol>",
            local_prefix,
            remote_prefix,
        )
        local_events += dl
        remote_events += dr
        total_samples += 1
        malformed += 1

    return local_events, remote_events, total_samples, malformed


def write_ip_report(path: str, ip_stats: Dict[str, list], sort_output: bool) -> None:
    """Write per-IP and per-symbol counts to a TSV report."""
    with open(path, "w", encoding="utf-8", newline="") as out:
        out.write("ip\ttotal_events\tsymbol_offset\tsymbol_events\n")

        items: Iterable[tuple[str, list]] = ip_stats.items()
        if sort_output:
            items = sorted(items, key=lambda kv: kv[1][0], reverse=True)

        for ip, entry in items:
            total = entry[0]
            sym_counts = entry[1]
            sym_items: Iterable[tuple[str, int]] = sym_counts.items()
            if sort_output:
                sym_items = sorted(sym_items, key=lambda kv: kv[1], reverse=True)

            for symbol, count in sym_items:
                out.write(f"{ip}\t{total}\t{symbol}\t{count}\n")


def print_top_ips(ip_stats: Dict[str, list], top_n: int) -> None:
    if top_n <= 0 or not ip_stats:
        return

    print(f"Top {top_n} IPs by total events:")
    top_items = heapq.nlargest(top_n, ip_stats.items(), key=lambda kv: kv[1][0])
    for idx, (ip, entry) in enumerate(top_items, start=1):
        total = entry[0]
        sym_counts = entry[1]
        top_symbol, top_symbol_count = max(sym_counts.items(), key=lambda kv: kv[1])
        print(
            f"  {idx:2d}. ip={ip} total={total} "
            f"top_symbol={top_symbol} ({top_symbol_count})"
        )


def parse_symbol_offset(symbol: str) -> int | None:
    match = re.search(r"\[([0-9a-fA-F]+)\]", symbol)
    if not match:
        return None
    return int(match.group(1), 16)


def split_mnemonic_operands(text: str) -> tuple[str, List[str]]:
    text = text.strip()
    if not text:
        return "", []
    parts = text.split(None, 1)
    mnemonic = parts[0].lower()
    operands = []
    if len(parts) > 1:
        raw_ops = parts[1]
        cur: List[str] = []
        depth = 0
        for ch in raw_ops:
            if ch == "(":
                depth += 1
                cur.append(ch)
                continue
            if ch == ")":
                depth = max(0, depth - 1)
                cur.append(ch)
                continue
            if ch == "," and depth == 0:
                item = "".join(cur).strip()
                if item:
                    operands.append(item)
                cur = []
                continue
            cur.append(ch)

        tail = "".join(cur).strip()
        if tail:
            operands.append(tail)
    return mnemonic, operands


def canonical_reg(reg: str) -> str:
    reg = reg.lower().lstrip("%")
    alias = {
        "eax": "rax",
        "ebx": "rbx",
        "ecx": "rcx",
        "edx": "rdx",
        "esi": "rsi",
        "edi": "rdi",
        "ebp": "rbp",
        "esp": "rsp",
    }
    if reg in alias:
        return alias[reg]
    if re.fullmatch(r"r1?[0-5]d", reg):
        return reg[:-1]
    if re.fullmatch(r"r1?[0-5][wb]", reg):
        return reg[:-1]
    return reg


def regs_in_operand(op: str) -> Set[str]:
    regs = set()
    for token in re.findall(r"%[a-zA-Z0-9]+", op):
        regs.add(canonical_reg(token))
    return regs


def writes_and_reads(mnemonic: str, operands: List[str]) -> tuple[Set[str], Set[str]]:
    if not operands:
        return set(), set()

    reads: Set[str] = set()
    writes: Set[str] = set()

    if mnemonic in {"cmp", "test"}:
        for op in operands:
            reads |= regs_in_operand(op)
        return writes, reads

    if mnemonic.startswith("j"):
        return writes, reads

    if mnemonic in {"call", "ret", "nop", "nopl", "nopw"}:
        return writes, reads

    if len(operands) == 1:
        op = operands[0]
        reads |= regs_in_operand(op)
        if op.startswith("%"):
            writes.add(canonical_reg(op))
        return writes, reads

    src = operands[0]
    dst = operands[-1]
    reads |= regs_in_operand(src)
    reads |= regs_in_operand(dst)

    if dst.startswith("%"):
        writes.add(canonical_reg(dst))

    return writes, reads


def memory_operand_role(mnemonic: str, operands: List[str]) -> tuple[str, str | None]:
    if not operands:
        return "none", None

    mem_ops = [op for op in operands if "(" in op and ")" in op]
    if not mem_ops:
        return "none", None

    if len(operands) >= 2:
        src = operands[0]
        dst = operands[-1]
        src_mem = "(" in src and ")" in src
        dst_mem = "(" in dst and ")" in dst
        if src_mem and not dst_mem:
            return "load", src
        if not src_mem and dst_mem:
            return "store", dst
        if src_mem and dst_mem:
            return "memory-to-memory", src

    if mnemonic.startswith("mov") or mnemonic.startswith("vmov"):
        return "load", mem_ops[0]

    return "memory-op", mem_ops[0]


def parse_objdump(path: str) -> tuple[List[Insn], Dict[int, int]]:
    label_re = re.compile(r"^([0-9a-fA-F]+)\s+<([^>]+)>:")
    insn_re = re.compile(r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}(?:\s+[0-9a-fA-F]{2})*\s+)?(\S.*)$")

    current_func = "<unknown>"
    insns: List[Insn] = []
    by_offset: Dict[int, int] = {}

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            label_match = label_re.match(line)
            if label_match:
                current_func = label_match.group(2)
                continue

            insn_match = insn_re.match(line)
            if not insn_match:
                continue

            off = int(insn_match.group(1), 16)
            text = insn_match.group(2).strip()
            idx = len(insns)
            insns.append(Insn(offset=off, text=text, function=current_func))
            by_offset[off] = idx

    return insns, by_offset


def classify_access_pattern(insn_text: str, window: List[Insn]) -> str:
    mnemonic, operands = split_mnemonic_operands(insn_text)
    role, mem_op = memory_operand_role(mnemonic, operands)
    if role == "none" or mem_op is None:
        return "not-a-memory-access"

    if "," in mem_op:
        return "indexed/gather-like address computation"

    base_regs = regs_in_operand(mem_op)
    if not base_regs:
        return "absolute-address memory access"

    nearby_same_base_loads = 0
    for w in window:
        w_mn, w_ops = split_mnemonic_operands(w.text)
        w_role, w_mem = memory_operand_role(w_mn, w_ops)
        if w_role != "load" or w_mem is None:
            continue
        if regs_in_operand(w_mem) & base_regs:
            nearby_same_base_loads += 1

    if nearby_same_base_loads >= 3:
        return "structure/array-of-struct field loads from same base"
    return "single-base memory access"


def loop_likelihood(insns: List[Insn], idx: int, radius: int = 40) -> bool:
    start = max(0, idx - radius)
    end = min(len(insns), idx + radius + 1)
    for j in range(start, end):
        mn, ops = split_mnemonic_operands(insns[j].text)
        if not mn.startswith("j") or mn in {"jmpq", "jmpl"}:
            continue
        if not ops:
            continue
        target = ops[0].split()[0]
        if re.fullmatch(r"[0-9a-fA-F]+", target):
            target_off = int(target, 16)
            if target_off < insns[j].offset:
                return True
    return False


def build_hotspot_mlp_notes(
    ip_stats: Dict[str, list],
    objdump_path: str,
    top_n: int,
) -> List[str]:
    insns, by_offset = parse_objdump(objdump_path)
    top_items = heapq.nlargest(top_n, ip_stats.items(), key=lambda kv: kv[1][0])
    notes: List[str] = []

    for rank, (ip, entry) in enumerate(top_items, start=1):
        total = entry[0]
        sym_counts = entry[1]
        top_symbol, top_symbol_count = max(sym_counts.items(), key=lambda kv: kv[1])
        offset = parse_symbol_offset(top_symbol)
        if offset is None:
            notes.append(
                f"  {rank}. ip={ip} total={total} symbol={top_symbol}: no offset in symbol"
            )
            continue

        idx = by_offset.get(offset)
        if idx is None:
            notes.append(
                f"  {rank}. ip={ip} total={total} symbol={top_symbol}: offset 0x{offset:x} not found in objdump"
            )
            continue

        insn = insns[idx]
        window_start = max(0, idx - 6)
        window_end = min(len(insns), idx + 7)
        window = insns[window_start:window_end]

        mnemonic, operands = split_mnemonic_operands(insn.text)
        role, mem_op = memory_operand_role(mnemonic, operands)
        access_pattern = classify_access_pattern(insn.text, window)

        writes, _ = writes_and_reads(mnemonic, operands)
        addr_regs = regs_in_operand(mem_op or "")

        depends_on_prior_mem = False
        for j in range(max(0, idx - 8), idx):
            pmn, pops = split_mnemonic_operands(insns[j].text)
            prow, pmem = memory_operand_role(pmn, pops)
            pwrites, _ = writes_and_reads(pmn, pops)
            if prow == "load" and (pwrites & addr_regs):
                depends_on_prior_mem = True
                break

        first_use_distance = None
        independent_loads_before_use = 0
        for j in range(idx + 1, min(len(insns), idx + 12)):
            nmn, nops = split_mnemonic_operands(insns[j].text)
            nrole, _ = memory_operand_role(nmn, nops)
            nwrites, nreads = writes_and_reads(nmn, nops)

            if writes and (nreads & writes):
                first_use_distance = j - idx
                break

            if nrole == "load" and not (nreads & writes) and not (nwrites & writes):
                independent_loads_before_use += 1

        in_loop = loop_likelihood(insns, idx)

        if role not in {"load", "store", "memory-op", "memory-to-memory"}:
            mlp = "not-applicable"
        elif first_use_distance is not None and first_use_distance <= 1 and independent_loads_before_use == 0:
            mlp = "low"
        elif in_loop and independent_loads_before_use >= 1:
            mlp = "medium-high"
        elif depends_on_prior_mem:
            mlp = "low-medium"
        else:
            mlp = "medium"

        dep_note = "addr depends on earlier load" if depends_on_prior_mem else "addr available from ALU/loop index path"
        use_note = (
            f"first_use_dist={first_use_distance}"
            if first_use_distance is not None
            else "first_use_dist=>10"
        )
        loop_note = "loop-body" if in_loop else "non-loop/unclear"

        notes.append(
            "  "
            f"{rank}. ip={ip} total={total} symbol={top_symbol} ({top_symbol_count}) "
            f"func={insn.function} off=0x{insn.offset:x} insn='{insn.text}' "
            f"role={role} pattern={access_pattern} mlp={mlp} "
            f"[{dep_note}; {use_note}; indep_loads_before_use={independent_loads_before_use}; {loop_note}]"
        )

    return notes


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stream and analyze PEBS script text files without loading into memory."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more PEBS script text files (e.g., xsbench-32GB_8t_script.txt)",
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
        help="Print top-N IPs by event count (default: 5; 0 disables)",
    )
    parser.add_argument(
        "--ip-report",
        default="",
        help="Optional TSV output path for full IP->symbol breakdown",
    )
    parser.add_argument(
        "--sort-report",
        action="store_true",
        help="Sort report and symbol lists by descending counts (slower)",
    )
    parser.add_argument(
        "--buffer-size",
        type=int,
        default=16 * 1024 * 1024,
        help="Read buffer size in bytes (default: 16 MiB)",
    )
    parser.add_argument(
        "--objdump",
        default="",
        help="Optional objdump text path; adds hotspot memory-pattern and MLP notes",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    ip_stats: Dict[str, list] = {}

    total_local = 0
    total_remote = 0
    total_samples = 0
    total_malformed = 0

    for path in args.files:
        with open(path, "r", encoding="utf-8", errors="replace", buffering=args.buffer_size) as fh:
            local, remote, samples, malformed = process_stream(
                fh,
                local_prefix=args.local_prefix,
                remote_prefix=args.remote_prefix,
                ip_stats=ip_stats,
            )
            total_local += local
            total_remote += remote
            total_samples += samples
            total_malformed += malformed

    print("Summary")
    print(f"  files={len(args.files)}")
    print(f"  total_samples={total_samples}")
    print(f"  local_dram_events={total_local}")
    print(f"  remote_dram_events={total_remote}")
    print(f"  unique_ips={len(ip_stats)}")
    print(f"  malformed_records={total_malformed}")

    print_top_ips(ip_stats, args.top)

    if args.objdump:
        print("MLP/Access notes (objdump-guided):")
        try:
            notes = build_hotspot_mlp_notes(ip_stats, args.objdump, args.top)
            if notes:
                for note in notes:
                    print(note)
            else:
                print("  no hotspots to analyze")
        except OSError as exc:
            print(f"  objdump analysis skipped: {exc}")

    if args.ip_report:
        write_ip_report(args.ip_report, ip_stats, args.sort_report)
        print(f"Wrote IP report: {args.ip_report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
