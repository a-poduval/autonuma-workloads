"""Perf event parsing and canonicalization."""

from __future__ import annotations

import re

from .constants import (
    EVENT_CODE_MAP,
    EVENT_CYCLES,
    EVENT_DTLB_MISS_CAUSES_WALK,
    EVENT_DTLB_WALK_PENDING,
    EVENT_LOCAL_DRAM,
    EVENT_OR_DEMAND,
    EVENT_ORO_DEMAND,
    EVENT_REMOTE_DRAM,
)


def parse_event_from_fields(fields: list[str]) -> str | None:
    """Parse event token from a split perf CSV line."""
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
