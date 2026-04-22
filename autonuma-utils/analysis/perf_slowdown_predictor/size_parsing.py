"""Size parsing helpers."""

from __future__ import annotations

import re


SIZE_TOKEN_RE = re.compile(
    r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgtp]?)(?:i?b)?\s*",
    flags=re.IGNORECASE,
)


def parse_size_to_gb(value: str, *, empty_unit_is_gb: bool) -> float | None:
    """Parse human size token into GB.

    Examples:
    - 22GB -> 22
    - 4096MB -> 4
    - 22 (when empty_unit_is_gb=True) -> 22
    """
    match = SIZE_TOKEN_RE.fullmatch(value)
    if match is None:
        return None

    magnitude = float(match.group(1))
    suffix = match.group(2).lower()
    if suffix == "" and empty_unit_is_gb:
        suffix = "g"

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

    bytes_value = magnitude * (1024.0 ** power)
    return bytes_value / (1024.0 ** 3)


def memory_to_bytes(memory: str) -> float | None:
    match = SIZE_TOKEN_RE.fullmatch(memory)
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


def memory_to_gb(memory: str) -> float | None:
    return parse_size_to_gb(memory, empty_unit_is_gb=False)
