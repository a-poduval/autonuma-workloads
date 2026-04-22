"""Resolve selected perf files from scan, manifest, or explicit includes."""

from __future__ import annotations

import os

from .file_matching import iter_matching_files
from .selection import (
    build_selected_from_paths,
    load_manifest_selection,
    resolve_selected_matches,
)


def collect_selected_files(
    *,
    input_dir: str | None,
    manifest_csv: str | None,
    manifest_root: str | None,
    include_paths: list[str],
    default_split: str,
    split_filter: list[str],
    filename_re,
):
    split_filter_set = set(split_filter) if split_filter else None

    selected_paths = []
    if manifest_csv:
        selected_paths.extend(
            load_manifest_selection(
                manifest_csv=manifest_csv,
                default_split=default_split,
                manifest_root=manifest_root,
            )
        )
    if include_paths:
        selected_paths.extend(
            build_selected_from_paths(
                paths=include_paths,
                default_split=default_split,
            )
        )

    if selected_paths:
        selected = resolve_selected_matches(selected_paths, filename_re, split_filter_set)
    else:
        if not input_dir:
            raise ValueError(
                "Provide either input_dir, --manifest-csv, or --include-path"
            )
        if not os.path.isdir(input_dir):
            raise ValueError(f"Input directory not found: {input_dir}")

        selected = []
        for file_path, file_match in iter_matching_files(input_dir, filename_re):
            split = default_split
            if split_filter_set is not None and split not in split_filter_set:
                continue
            selected.append((file_path, file_match, split, None, None))

    dedup = {}
    for path, file_match, split, tag, rss_gb in selected:
        if path in dedup:
            raise ValueError(f"Duplicate selected file path: {path}")
        dedup[path] = (path, file_match, split, tag, rss_gb)

    return list(dedup.values())
