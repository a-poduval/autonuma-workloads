"""Low-level parsing helpers for text tokens."""

from __future__ import annotations


def parse_count(value: str) -> int | None:
    """Parse perf count fields; return None for unsupported rows."""
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


def parse_duration_to_seconds(token: str) -> float | None:
    """Parse h:mm:ss, m:ss, or seconds into seconds."""
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
