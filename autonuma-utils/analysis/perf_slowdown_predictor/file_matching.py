"""File discovery and filename regex validation."""

from __future__ import annotations

import os
import re

from .constants import REQUIRED_FILENAME_GROUPS


def compile_filename_regex(pattern: str) -> re.Pattern[str]:
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid filename regex: {exc}") from exc

    if not REQUIRED_FILENAME_GROUPS.issubset(compiled.groupindex.keys()):
        raise ValueError(
            "Filename regex must define named groups: workload, memory, threads"
        )

    return compiled


def iter_matching_files(root_dir: str, filename_re: re.Pattern[str]):
    for current_root, _, files in os.walk(root_dir):
        for name in files:
            match = filename_re.match(name)
            if match is None:
                continue
            yield os.path.join(current_root, name), match
