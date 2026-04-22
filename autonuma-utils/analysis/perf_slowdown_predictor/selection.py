"""Curated file selection helpers.

Supports selecting files by:
- explicit path list from CLI
- manifest CSV (path, optional split, optional tag, optional rss)
"""

from __future__ import annotations

import csv
import os
import re

from .models import SelectedPerfPath
from .size_parsing import parse_size_to_gb


def _normalize_split(split: str | None, default_split: str) -> str:
    value = (split or "").strip()
    if not value:
        return default_split
    return value


def build_selected_from_paths(
    paths: list[str],
    default_split: str,
) -> list[SelectedPerfPath]:
    return [
        SelectedPerfPath(path=os.path.abspath(path), split=default_split, rss_gb=None)
        for path in paths
    ]


def load_manifest_selection(
    manifest_csv: str,
    default_split: str,
    manifest_root: str | None,
) -> list[SelectedPerfPath]:
    selected: list[SelectedPerfPath] = []
    manifest_path = os.path.abspath(manifest_csv)
    resolved_root = manifest_root
    if resolved_root is None:
        resolved_root = os.path.dirname(manifest_path)
    resolved_root = os.path.abspath(resolved_root)

    with open(manifest_path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        if "path" not in (reader.fieldnames or []):
            raise ValueError("Manifest must contain a 'path' column")

        for idx, row in enumerate(reader, start=2):
            raw_path = (row.get("path") or "").strip()
            if not raw_path:
                raise ValueError(f"Manifest row {idx}: empty path")

            if os.path.isabs(raw_path):
                full_path = raw_path
            else:
                full_path = os.path.join(resolved_root, raw_path)
            full_path = os.path.abspath(full_path)

            split = _normalize_split(row.get("split"), default_split)
            tag_raw = (row.get("tag") or "").strip()
            tag = tag_raw if tag_raw else None
            rss_raw = (row.get("rss") or "").strip()
            rss_gb: float | None = None
            if rss_raw:
                rss_gb = parse_size_to_gb(rss_raw, empty_unit_is_gb=True)
                if rss_gb is None or rss_gb <= 0.0:
                    raise ValueError(
                        f"Manifest row {idx}: invalid rss value '{rss_raw}'"
                    )

            selected.append(
                SelectedPerfPath(
                    path=full_path,
                    split=split,
                    selection_tag=tag,
                    rss_gb=rss_gb,
                )
            )

    return selected


def resolve_selected_matches(
    selected_paths: list[SelectedPerfPath],
    filename_re: re.Pattern[str],
    split_filter: set[str] | None,
):
    """Resolve selected files to regex matches and validate existence."""
    out = []
    for item in selected_paths:
        if split_filter is not None and item.split not in split_filter:
            continue

        if not os.path.isfile(item.path):
            raise ValueError(f"Selected file not found: {item.path}")

        basename = os.path.basename(item.path)
        match = filename_re.match(basename)
        if match is None:
            raise ValueError(
                "Selected file does not match filename regex: "
                f"{item.path}"
            )

        out.append((item.path, match, item.split, item.selection_tag, item.rss_gb))

    return out
