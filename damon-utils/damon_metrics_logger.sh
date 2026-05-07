#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./damon_stat_logger.sh <output.csv> [interval_sec]
#
# Example:
#   ./damon_stat_logger.sh damon.csv 1

OUT="${1:-}"
INTERVAL="${2:-1}"
BASE="${DAMON_SYSFS:-/sys/kernel/mm/damon/admin}"

if [[ -z "$OUT" ]]; then
    echo "Usage: $0 <output.csv> [interval_sec]" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUT")"

if [[ ! -d "$BASE" ]]; then
    echo "ERROR: DAMON sysfs admin path not found: $BASE" >&2
    exit 1
fi

# If the caller did not run as root, re-exec with sudo.
# This avoids permission failures on kdamond state updates.
if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -E "$0" "$OUT" "$INTERVAL"
fi

shopt -s nullglob

echo "timestamp,kdamond,context,scheme,action,target_nid,max_nr_snapshots,nr_snapshots,nr_tried,sz_tried,sz_ops_filter_passed,nr_applied,sz_applied,qt_exceeds,effective_bytes,quota_bytes,quota_interval_ms" > "$OUT"

read_file_or_zero() {
    local f="$1"
    if [[ -r "$f" ]]; then
        cat "$f"
    else
        echo 0
    fi
}

read_file_or_na() {
    local f="$1"
    if [[ -r "$f" ]]; then
        cat "$f"
    else
        echo "NA"
    fi
}

# Ask kernel to periodically refresh stats instead of us issuing synchronous
# update_schemes_stats on every loop.
for kd_path in "$BASE"/kdamonds/[0-9]*; do
    [[ -d "$kd_path" ]] || continue
    echo "$((INTERVAL * 1000))" > "$kd_path/refresh_ms" 2>/dev/null || true
done

while true; do
    ts="$(date +%s.%N)"

    for kd_path in "$BASE"/kdamonds/[0-9]*; do
        [[ -d "$kd_path" ]] || continue
        kd="$(basename "$kd_path")"

        for ctx_path in "$kd_path"/contexts/[0-9]*; do
            [[ -d "$ctx_path" ]] || continue
            ctx="$(basename "$ctx_path")"

            for scheme_path in "$ctx_path"/schemes/[0-9]*; do
                [[ -d "$scheme_path" ]] || continue
                scheme="$(basename "$scheme_path")"

                action="$(read_file_or_na "$scheme_path/action")"
                target_nid="$(read_file_or_na "$scheme_path/target_nid")"

                max_nr_snapshots="$(read_file_or_zero "$scheme_path/stats/max_nr_snapshots")"
                nr_snapshots="$(read_file_or_zero "$scheme_path/stats/nr_snapshots")"
                nr_tried="$(read_file_or_zero "$scheme_path/stats/nr_tried")"
                sz_tried="$(read_file_or_zero "$scheme_path/stats/sz_tried")"
                sz_ops_filter_passed="$(read_file_or_zero "$scheme_path/stats/sz_ops_filter_passed")"
                nr_applied="$(read_file_or_zero "$scheme_path/stats/nr_applied")"
                sz_applied="$(read_file_or_zero "$scheme_path/stats/sz_applied")"
                qt_exceeds="$(read_file_or_zero "$scheme_path/stats/qt_exceeds")"

                effective_bytes="$(read_file_or_zero "$scheme_path/quotas/effective_bytes")"
                quota_bytes="$(read_file_or_zero "$scheme_path/quotas/bytes")"
                quota_interval_ms="$(read_file_or_zero "$scheme_path/quotas/reset_interval_ms")"

                echo "$ts,$kd,$ctx,$scheme,$action,$target_nid,$max_nr_snapshots,$nr_snapshots,$nr_tried,$sz_tried,$sz_ops_filter_passed,$nr_applied,$sz_applied,$qt_exceeds,$effective_bytes,$quota_bytes,$quota_interval_ms" >> "$OUT"
            done
        done
    done

    sleep "$INTERVAL"
done
