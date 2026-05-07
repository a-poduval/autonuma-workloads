#!/bin/bash

#set -euo pipefail # Fail on error, unset variables, or pipes errors

# Usage: ./run-damon.sh <application> <local size> <num threads> <log string>
if [ -z "$1" ]; then
    echo "Usage: $0 <application> <local tier size in bytes or k/K/m/M/g/G> <num_threads> <log string>"
    echo "Applications: spec_mcf spec_bwaves spec_lbm gapbs_bc gapbs_bfs gapbs_cc gapbs_pr flexkvs liblinear merci silo xsbench"
    exit 1
fi

PIDS=()
DAMON_STAT_PID=""
PERF_PID=""
PCM_MEM_PID=""

cleanup() {
    status=$?

    for pid in "${PIDS[@]:-}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done

    if [[ -n "${DAMON_STAT_PID:-}" ]]; then
        kill "$DAMON_STAT_PID" 2>/dev/null || true
        wait "$DAMON_STAT_PID" 2>/dev/null || true
    fi

    if [[ -n "${PERF_PID:-}" ]]; then
        kill "$PERF_PID" 2>/dev/null || true
        wait "$PERF_PID" 2>/dev/null || true
    fi

    if [[ -n "${PCM_MEM_PID:-}" ]]; then
        sudo -n kill "$PCM_MEM_PID" 2>/dev/null || true
        wait "$PCM_MEM_PID" 2>/dev/null || true
    fi

    exit "$status"
}

trap cleanup EXIT INT TERM

# Set the application name and local tier size size
APP=$1
LSIZE=$2 # size of fast tier (MB)

# NUMA Node
NUM_THREADS=$3

# Unique log number to give some context
LOG_NUMBER=$4
NUM_COPIES=1

# Damon controls
QUOTA_SPACE="${5:-200MB}"
PROMO_LB="${6:-5}"

# GAPBS graph file name
GRAPH_NAME="twitter"
#GRAPH_NAME="urand"
#GRAPH_NAME="web"

# Set top-level directory in repository as home
HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${HOME}/logs_damon"

# Path to perf bin
#PERF_BIN="$HOME/colloid/tpp/linux-6.3/tools/perf/perf"

INTERVAL=1  # seconds between memory usage dumps, must be at least 1 second for amd uprof pcm

mkdir -p "$LOG_DIR"

# Take non-node 0 cores offline
#echo 0 | sudo tee /sys/devices/system/node/node1/cpu*/online >/dev/null 2>&1

# Enable DAMON tiering
./damon_ctrl.sh start $QUOTA_SPACE $PROMO_LB

# Enable THP for parity with Memtis
#echo "always" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
#echo "always" | sudo tee /sys/kernel/mm/transparent_hugepage/defrag

# restrict fast tier size with memeater
NODE0SZ=$(numactl -H | grep "node 0 free" | awk '{print $4}')
sudo insmod $HOME/colloid/tpp/memeater/memeater.ko sizeMiB=$((NODE0SZ-LSIZE))

# Drop the page cache to get consistent application performance measurements
sudo sync; echo 1 | sudo tee /proc/sys/vm/drop_caches

# Parse application name
# Parse SUITE and WORKLOAD
if [[ "$APP" == gapbs_* ]]; then
    SUITE="gapbs"
    WORKLOAD="${APP#gapbs_}"
    #cd $HOME/gapbs
    export OMP_NUM_THREADS=$NUM_THREADS
    #RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/benchmark/graphs/${GRAPH_NAME}.sg -n 16"
    RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/kron29.sg -n 8"
    if [[ "$WORKLOAD" == bfs ]]; then
        RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/kron29.sg -n 64"
    fi
    if [[ "$WORKLOAD" == cc ]]; then
        RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/kron29.sg -n 64"
    fi
elif [[ "$APP" == spec_* ]]; then
    SUITE="spec"
    WORKLOAD="${APP#spec_}"
    if [[ "$WORKLOAD" == mcf ]]; then
        RUN_CMD="runcpu --config marvell --copies=12 --iterations 1 --tune=base 505.${WORKLOAD}_r"
    elif [[ "$WORKLOAD" == bwaves ]]; then
        RUN_CMD="runcpu --config marvell --copies=12 --iterations 1 --tune=base 503.${WORKLOAD}_r"
    elif [[ "$WORKLOAD" == lbm ]]; then
        RUN_CMD="runcpu --config marvell --copies=12 --iterations 1 --tune=base 519.${WORKLOAD}_r"
    fi
    numactl --membind=1 cat $HOME/gapbs/kron29.sg > /dev/null
    # Source SPEC
    #cd /home/ssd/cpu2017/
    #. /home/ssd/cpu2017/shrc
elif [[ "$APP" == flexkvs ]]; then
    SUITE="flexkvs"
    WORKLOAD="flexkvs"
    #cd $HOME/flexkvs
    RUN_CMD="$HOME/flexkvs/kvsbench -T 400 -w 20 -h 0.25 127.0.0.1:1211 -S $((2 * 34359738368)) -t $NUM_THREADS"
elif [[ "$APP" == gups ]]; then
    SUITE="gups"
    WORKLOAD="gups"
    RUN_CMD="$HOME/gups_hemem/gups-hotset-move $NUM_THREADS 1000000000 35 8 33 n"
elif [[ "$APP" == liblinear ]]; then
    SUITE="liblinear"
    #WORKLOAD="liblinear"
    cd $HOME/liblinear-2.47
    RUN_CMD="$HOME/liblinear-2.47/train -s 6 -m $NUM_THREADS $HOME/liblinear-2.47/kdd12"
    numactl --membind=1 cat $HOME/liblinear-2.47/kdd12 > /dev/null
elif [[ "$APP" == merci ]]; then
    SUITE="merci"
    WORKLOAD="ER"
    #cd $HOME/MERCI
    RUN_CMD="$HOME/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r 20 -c $NUM_THREADS"
elif [[ "$APP" == silo ]]; then
    SUITE="silo"
    WORKLOAD="silo"
    #cd $HOME/silo
    RUN_CMD="$HOME/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench tpcc --scale-factor 400 --ops-per-worker 4000000 --num-threads $NUM_THREADS"
    #RUN_CMD="$HOME/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench tpcc --scale-factor 600 --ops-per-worker 4000000 --num-threads $NUM_THREADS"
elif [[ "$APP" == xsbench ]]; then
    SUITE="xsbench"
    WORKLOAD="xsbench"
    #cd $HOME/XSBench
    RUN_CMD="$HOME/XSBench/openmp-threading/XSBench -p 30000000 -g 130000 -t $NUM_THREADS"
else
    echo "Unknown application suite. Must start with 'gapbs_' or 'spec_'."
    exit 1
fi

# Make a subdirectory for suite
mkdir -p "$LOG_DIR/$SUITE"

# Start AMD PCM in background and record in csv
# Unlike Intel, doesn't throw an error with cores offline, just doesn't emit any data for them
sudo env "PATH=$PATH" AMDuProfPcm -m memory -a -A system,package -I $((INTERVAL * 1000)) --collect-pcie -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_uprof_pcm_memory.csv &
PCM_MEM_PID=$!

# Capture performance counter data
# L3 Cache PMCs 0xAC (XiSampledLatency) and 0xAD (XiSampledLatencyRequests): AC*10/AD gives average sampled memory latency in ns
# Local DRAM: cpu/event=0x43,umask=0x08/, Remote DRAM: cpu/event=0x43,umask=0x40/, CXL/Extension Memory: cpu/event=0x43,umask=0x80/
# L1 DTLB Reloads: PMCx045 with UnitMask 0xF0
#$PERF_BIN stat -C 0-9,10-19 -I 2000 -e cycles,uops_retired.cycles,exe_activity.bound_on_loads,exe_activity.bound_on_stores,memory_activity.stalls_l1d_miss,memory_activity.stalls_l2_miss,memory_activity.stalls_l3_miss -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_perf.csv -x, &
#sudo perf stat -C 1-8 -I $((INTERVAL * 1000)) -e cycles -e "{amd_l3/event=0xac,umask=0xff,enallcores=1,enallslices=1,sliceid=3,threadmask=3/,amd_l3/event=0xad,umask=0xff,enallcores=1,enallslices=1,sliceid=3,threadmask=3/}" -e "{cpu/event=0x43,umask=0x08/,cpu/event=0x43,umask=0x40/,cpu/event=0x43,umask=0x80/}" -e "{cpu/event=0x45,umask=0xf0/}" -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_perf.csv -x, &
sudo perf stat -C 1-8 -I $((INTERVAL * 1000)) -e cycles -e "{amd_l3/event=0xac,umask=0x20,enallcores=1,enallslices=1,sliceid=3,threadmask=3/,amd_l3/event=0xad,umask=0x20,enallcores=1,enallslices=1,sliceid=3,threadmask=3/,amd_l3/event=0xac,umask=0x01,enallcores=1,enallslices=1,sliceid=3,threadmask=3/,amd_l3/event=0xad,umask=0x01,enallcores=1,enallslices=1,sliceid=3,threadmask=3/}" -e "{cpu/event=0x43,umask=0x08/,cpu/event=0x43,umask=0x40/,cpu/event=0x43,umask=0x80/}" -e "{cpu/event=0x45,umask=0xf0/}" -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_perf.csv -x, &
PERF_PID=$!

$HOME/damon-utils/damon_metrics_logger.sh $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_damon.csv $INTERVAL &
DAMON_STAT_PID=$!

# Pin tasks to cores for determinism in performance
PINNING="taskset -c 1-${NUM_THREADS}"

# 020002a3 = CYCLE_ACTIVITY.CYCLES_L3_MISS
# 060006a3 = CYCLE_ACTIVITY.STALLS_L3_MISS
# 01b0     = OFFCORE_REQUESTS.DEMAND_DATA_RD
# 01000160 = OFFCORE_REQUESTS_OUTSTANDING.CYCLES_WITH_DEMAND_DATA_RD

# Launch workload with memory interleaved from the specified NUMA node
PIDS=()
for i in $(seq 1 $NUM_COPIES); do
    #/usr/bin/time -v -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_time.txt ${HOME}/numactl-2.0.19/numactl -m 2,$NUMA_NODE -C 49-60\
    #     -- $RUN_CMD &
    #${PINNING} /usr/bin/time -v -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_time.txt perf stat -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_perf.txt -I 1000 -e cycles -e r020002a3 -e r060006a3 -e r01b0 -e r01000160 $RUN_CMD &> $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_output.log &
    ${PINNING} /usr/bin/time -v -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_time.txt $RUN_CMD &> $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_output.log &
    PIDS+=($!)
done

# Monitor NUMA memory usage while workloads are running
#echo "timestamp,node0_free_kb,node1_free_kb,node2_free_kb,node3_free_kb,node4_free_kb,node5_free_kb,node6_free_kb,node7_free_kb,node0_used_kb,node1_used_kb,node2_used_kb,node3_used_kb,node4_used_kb,node5_used_kb,node6_used_kb,node7_used_kb" > "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
#echo "timestamp,node0_free_kb,node1_free_kb,node0_2M_free,node1_2M_free,node0_used_kb,node1_used_kb,node0_2M_total,node1_2M_total" > "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
echo "timestamp,node0_free_kb,node1_free_kb,node0_used_kb,node1_used_kb" > "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
while true; do
    RUNNING=0
    for pid in "${PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            RUNNING=1
            break
        fi
    done

    if [ $RUNNING -eq 0 ]; then
        break
    fi

    TIMESTAMP=$(date +%s)
    NODE0=$(grep MemFree /sys/devices/system/node/node0/meminfo | awk '{print $4}')
    NODE1=$(grep MemFree /sys/devices/system/node/node1/meminfo | awk '{print $4}')
    echo -n "$TIMESTAMP,$NODE0,$NODE1" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    NODE0=$(grep MemUsed /sys/devices/system/node/node0/meminfo | awk '{print $4}')
    NODE1=$(grep MemUsed /sys/devices/system/node/node1/meminfo | awk '{print $4}')
    echo ",$NODE0,$NODE1" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    sleep $INTERVAL
done

# Wait for all workload copies to finish
for pid in "${PIDS[@]}"; do
    wait $pid
done

# Kill vmstat logger
sudo kill $DAMON_STAT_PID
# Kill Perf
sudo kill $PERF_PID
#pkill -f perf
# Kill PCM
sudo kill $PCM_MEM_PID
#pkill -f AMDuProfPcm

# Reset THP
#echo "madvise" | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
#echo "madvise" | sudo tee /sys/kernel/mm/transparent_hugepage/defrag

# Ensure damon sysfs lock is no longer held
for s in /sys/kernel/mm/damon/admin/kdamonds/[0-9]*/state; do
    ok=0

    for i in $(seq 1 10); do
        if echo off | sudo tee "$s" >/dev/null; then
            ok=1
            break
        fi

        echo "WARN: failed to write off to $s, retry $i/10" >&2
        sleep 1
    done

    if ((ok == 0)); then
        echo "ERROR: failed to stop $s after 10 retries" >&2
        exit 1
    fi
done

# Disable DAMON tiering
./damon_ctrl.sh stop

# disable memeater
sudo rmmod $HOME/colloid/tpp/memeater/memeater.ko

# Bring all cores online
#echo 1 | sudo tee /sys/devices/system/cpu/cpu*/online >/dev/null 2>&1

echo "Monitoring complete. Logs saved in $LOG_DIR"
