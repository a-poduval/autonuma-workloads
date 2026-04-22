"""Read perf CSVs and apply runtime tail-window filtering."""

from __future__ import annotations

from .event_parsing import canonical_event_name, parse_event_from_fields
from .models import EpochSample
from .text_parsing import parse_count


def collect_epoch_samples(
    file_path: str,
    target_events: set[str],
) -> tuple[list[EpochSample], float | None]:
    """Collect per-timestamp event counts before window filtering."""
    by_ts: dict[float, dict[str, int]] = {}
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

            bucket = by_ts.get(ts)
            if bucket is None:
                bucket = {}
                by_ts[ts] = bucket
            bucket[event] = bucket.get(event, 0) + count

            if max_ts is None or ts > max_ts:
                max_ts = ts

    samples = [EpochSample(timestamp_s=ts, counts=by_ts[ts]) for ts in sorted(by_ts)]
    return samples, max_ts


def filter_tail_window(
    samples: list[EpochSample],
    max_ts: float | None,
    window_seconds: float | None,
) -> tuple[list[EpochSample], float | None]:
    """Keep only samples in the last window_seconds of the timeline."""
    if not samples or max_ts is None:
        return samples, None
    if window_seconds is None or window_seconds <= 0:
        return samples, None

    cutoff = max_ts - window_seconds
    filtered = [sample for sample in samples if sample.timestamp_s >= cutoff]
    applied_window = min(max_ts, window_seconds)
    return filtered, applied_window
