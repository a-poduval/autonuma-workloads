#!/usr/bin/env python3
"""Run pebs_access_plots.py for every PEBS script file under a directory tree.

This wrapper finds matching files recursively and invokes the single-file plotter
for each file, so you do not need to run it one-by-one.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import List


def find_script_files(
    root_dir: str,
    name_regex: str,
    follow_symlinks: bool,
) -> List[str]:
    pattern = re.compile(name_regex)
    matches: List[str] = []

    for current_root, _dirs, files in os.walk(root_dir, followlinks=follow_symlinks):
        for name in files:
            if pattern.match(name):
                matches.append(os.path.join(current_root, name))

    matches.sort()
    return matches


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively run pebs_access_plots.py on every *_script.txt file."
    )
    parser.add_argument(
        "input_dir",
        help="Root directory to scan recursively for PEBS script text files",
    )
    parser.add_argument(
        "--output-dir",
        default="pebs_acess_plots",
        help="Output directory passed to pebs_access_plots.py (default: pebs_acess_plots)",
    )
    parser.add_argument(
        "--name-regex",
        default=r"^.*_script\.txt$",
        help="Regex used to match candidate script file basenames (default: ^.*_script\\.txt$)",
    )
    parser.add_argument(
        "--plot-script",
        default="pebs_access_plots.py",
        help="Path to the single-file plot script (default: pebs_access_plots.py)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to run the plot script (default: current interpreter)",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinks while scanning directories",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Limit how many matched files are processed (0 means no limit)",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list matched files; do not run plotting",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately if one file fails",
    )
    parser.add_argument(
        "--extra-args",
        nargs=argparse.REMAINDER,
        default=[],
        help=(
            "Extra arguments forwarded to pebs_access_plots.py. "
            "Example: --extra-args --page-size 2m --address-space user"
        ),
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    if args.max_files < 0:
        raise SystemExit("--max-files must be >= 0")

    files = find_script_files(
        root_dir=args.input_dir,
        name_regex=args.name_regex,
        follow_symlinks=args.follow_symlinks,
    )

    if args.max_files > 0:
        files = files[: args.max_files]

    if not files:
        print("No matching script files found.")
        return 1

    print(f"Matched script files: {len(files)}")
    for idx, path in enumerate(files, start=1):
        print(f"  {idx:3d}. {path}")

    if args.list_only:
        return 0

    os.makedirs(args.output_dir, exist_ok=True)

    success = 0
    failures: List[tuple[str, int]] = []

    forwarded = list(args.extra_args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    for idx, path in enumerate(files, start=1):
        cmd = [
            args.python,
            args.plot_script,
            path,
            "--output-dir",
            args.output_dir,
            *forwarded,
        ]
        print(f"\n[{idx}/{len(files)}] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            success += 1
            continue

        failures.append((path, result.returncode))
        if args.stop_on_error:
            break

    print("\nBatch summary")
    print(f"  succeeded={success}")
    print(f"  failed={len(failures)}")
    if failures:
        for path, code in failures:
            print(f"  fail: code={code} file={path}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
