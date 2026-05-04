#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./damon_ctrl.sh start [quota_space] [promotion_access_lower]
#   ./damon_ctrl.sh stop
#   ./damon_ctrl.sh status
#
# Examples:
#   ./damon_ctrl.sh start
#   ./damon_ctrl.sh start 500MB 1
#   ./damon_ctrl.sh start 1GB 10%
#   ./damon_ctrl.sh stop

HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DAMO_BIN="${DAMO_BIN:-$HOME/damo/damo}"

ACTION="${1:-}"
QUOTA_SPACE="${2:-200MB}"
PROMO_ACCESS_LOWER="${3:-5}"

usage() {
    cat <<EOF
Usage:
  $0 start [quota_space] [promotion_access_lower]
  $0 stop
  $0 status

Defaults:
  quota_space             = 200MB
  promotion_access_lower  = 5

Examples:
  $0 start
  $0 start 500MB 1
  $0 start 1GB 10%
  $0 stop

Environment:
  DAMO_BIN=/path/to/damo
EOF
}

need_damo() {
    if ! command -v "$DAMO_BIN" >/dev/null 2>&1; then
        echo "ERROR: '$DAMO_BIN' not found. Set DAMO_BIN=/path/to/damo or add damo to PATH." >&2
        exit 1
    fi
}

normalize_promo_access() {
    local v="$1"

    # Accept either "5" or "5%".
    if [[ "$v" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        echo "${v}%"
    elif [[ "$v" =~ ^[0-9]+([.][0-9]+)?%$ ]]; then
        echo "$v"
    else
        echo "ERROR: promotion_access_lower must look like '5' or '5%'." >&2
        exit 1
    fi
}

start_damon() {
    need_damo
    sudo -v

    local promo_access
    promo_access="$(normalize_promo_access "$PROMO_ACCESS_LOWER")"

    echo "Starting DAMON tiering:"
    echo "  fast node:                 0"
    echo "  slow node:                 1"
    echo "  quota space per scheme:    $QUOTA_SPACE / 1s"
    echo "  promotion access rate:     $promo_access max"
    echo

    sudo "$DAMO_BIN" start \
        \
        --numa_node 0 --monitoring_intervals_goal 4% 3 5ms 10s \
            --damos_action migrate_cold 1 \
            --damos_access_rate 0% 0% \
            --damos_apply_interval 1s \
            --damos_filter reject young \
            --damos_quota_interval 1s \
            --damos_quota_space "$QUOTA_SPACE" \
            --damos_quota_goal node_mem_free_bp 0.5% 0 \
        \
        --numa_node 1 --monitoring_intervals_goal 4% 3 5ms 10s \
            --damos_action migrate_hot 0 \
            --damos_access_rate "$promo_access" max \
            --damos_apply_interval 1s \
            --damos_filter allow young \
            --damos_quota_interval 1s \
            --damos_quota_space "$QUOTA_SPACE" \
            --damos_quota_goal node_mem_used_bp 99.7% 0 \
        \
        --damos_nr_quota_goals 1 1 \
        --damos_nr_filters 1 1 \
        --nr_targets 1 1 \
        --nr_schemes 1 1 \
        --nr_ctxs 1 1
}

stop_damon() {
    need_damo
    sudo -v

    echo "Stopping DAMON..."
    sudo "$DAMO_BIN" stop || true
}

status_damon() {
    need_damo
    sudo -v

    sudo "$DAMO_BIN" status || true
    echo
    sudo "$DAMO_BIN" report damon || true
}

case "$ACTION" in
    start)
        start_damon
        ;;
    stop)
        stop_damon
        ;;
    status)
        status_damon
        ;;
    -h|--help|help|"")
        usage
        ;;
    *)
        echo "ERROR: unknown action '$ACTION'" >&2
        usage
        exit 1
        ;;
esac
