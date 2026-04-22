"""Shared constants for perf parse/filter pipeline."""

from __future__ import annotations


DEFAULT_FILENAME_REGEX = (
    r"^(?P<workload>.+)-(?P<memory>[^_]+)_(?P<threads>[^_]+)_perf\.csv$"
)

REQUIRED_FILENAME_GROUPS = {"workload", "memory", "threads"}

EVENT_CYCLES = "cycles"
EVENT_OR_DEMAND = "offcore_requests.demand_data_rd"
EVENT_ORO_DEMAND = "offcore_requests_outstanding.demand_data_rd"
EVENT_LOCAL_DRAM = "mem_load_l3_miss_retired.local_dram"
EVENT_REMOTE_DRAM = "mem_load_l3_miss_retired.remote_dram"
EVENT_DTLB_WALK_PENDING = "dtlb_load_misses.walk_pending"
EVENT_DTLB_MISS_CAUSES_WALK = "dtlb_load_misses.miss_causes_a_walk"

DEFAULT_TRACKED_EVENTS = [
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
