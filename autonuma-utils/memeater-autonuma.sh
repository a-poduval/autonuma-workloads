#!/bin/bash

#set -euo pipefail # Fail on error, unset variables, or pipes errors

# Usage: ./run-autonuma.sh <application> <local size> <num threads> <log string>
if [ -z "$1" ]; then
    echo "Usage: $0 <application> <local tier size in bytes or k/K/m/M/g/G> <num_threads> <log string>"
    echo "Applications: spec_mcf spec_bwaves spec_lbm gapbs_bc gapbs_bfs gapbs_cc gapbs_pr flexkvs liblinear merci silo xsbench"
    exit 1
fi

# Set the application name and local tier size size
APP=$1
LSIZE=$2 # size of fast tier (MB)

# NUMA Node
NUM_THREADS=$3

# Unique log number to give some context
LOG_NUMBER=$4
NUM_COPIES=1

# GAPBS graph file name
GRAPH_NAME="twitter"
#GRAPH_NAME="urand"
#GRAPH_NAME="web"

# Set top-level directory in repository as home
HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${HOME}/autonuma_logs"
#PCM_DEB="${HOME}/pcm/pcm_0-0+1300.1_amd64.deb"

# Path to perf bin
#PERF_BIN="$HOME/colloid/tpp/linux-6.3/tools/perf/perf"

INTERVAL=0.5  # seconds between memory usage dumps

mkdir -p "$LOG_DIR"

# Take non-node 0 cores offline
echo 0 | sudo tee /sys/devices/system/node/node1/cpu*/online >/dev/null 2>&1
echo 1 | sudo tee /sys/devices/system/node/node1/cpu39/online  # Keep one core online for uncore readings for pcm
numactl -C 39 bash cpu_burner.sh & # CPU Burner script to keep node 1 core occupied

# Enable AutoNUMA balancing for tiered memory and configure local tier size
echo 1 | sudo tee /sys/kernel/mm/numa/demotion_enabled
echo 2 | sudo tee /proc/sys/kernel/numa_balancing
echo 1 | sudo tee /proc/sys/vm/zone_reclaim_mode
#sudo ./node0_size_control.sh set $LSIZE

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
    RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/benchmark/graphs/${GRAPH_NAME}.sg -n 16"
    if [[ "$WORKLOAD" == bfs ]]; then
        RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/benchmark/graphs/${GRAPH_NAME}.sg -n 512"
    fi
    if [[ "$WORKLOAD" == cc ]]; then
        RUN_CMD="$HOME/gapbs/${WORKLOAD} -f $HOME/gapbs/benchmark/graphs/${GRAPH_NAME}.sg -n 512"
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
    # Source SPEC
    #cd /home/ssd/cpu2017/
    #. /home/ssd/cpu2017/shrc
elif [[ "$APP" == flexkvs ]]; then
    SUITE="flexkvs"
    WORKLOAD="flexkvs"
    #cd $HOME/flexkvs
    RUN_CMD="$HOME/flexkvs/kvsbench -T 250 -w 20 -h 0.25 127.0.0.1:1211 -S 34359738368 -t $NUM_THREADS"
elif [[ "$APP" == gups ]]; then
    SUITE="gups"
    WORKLOAD="gups"
    # Reset size of fast tier, we are not using 4k pages for this workload
    #sudo $HOME/autonuma-utils/node0_size_control.sh reset
    #echo $LSIZE | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages
    #echo 20000 | sudo tee /sys/devices/system/node/node1/hugepages/hugepages-2048kB/nr_hugepages
    RUN_CMD="$HOME/gups_hemem/gups-hotset-move $NUM_THREADS 1000000000 35 8 33 n"
elif [[ "$APP" == liblinear ]]; then
    SUITE="liblinear"
    #WORKLOAD="liblinear"
    cd $HOME/liblinear-2.47
    RUN_CMD="$HOME/liblinear-2.47/train -s 6 -m $NUM_THREADS $HOME/liblinear-2.47/kddb"
elif [[ "$APP" == merci ]]; then
    SUITE="merci"
    WORKLOAD="ER"
    #cd $HOME/MERCI
    RUN_CMD="$HOME/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r 30 -c $NUM_THREADS"
elif [[ "$APP" == silo ]]; then
    SUITE="silo"
    WORKLOAD="silo"
    #cd $HOME/silo
    RUN_CMD="$HOME/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench tpcc --scale-factor 100 --ops-per-worker 1000000 --num-threads $NUM_THREADS"
elif [[ "$APP" == xsbench ]]; then
    SUITE="xsbench"
    WORKLOAD="xsbench"
    #cd $HOME/XSBench
    RUN_CMD="$HOME/XSBench/openmp-threading/XSBench -p 30000000 -g 65000 -t $NUM_THREADS"
else
    echo "Unknown application suite. Must start with 'gapbs_' or 'spec_'."
    exit 1
fi

# Make a subdirectory for suite
mkdir -p "$LOG_DIR/$SUITE"

# Dump pgpromote and demote stats at start
echo "Start" &> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_procfs.txt"
cat /proc/vmstat | grep "pgpromote\|pgdemote\|pgmigrate" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_procfs.txt"
#cat /proc/zoneinfo | grep "Node\|nr_\|workingset\|pgpromote\|pgdemote\|numa" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_procfs.txt"

# Slow uncore frequencies
sudo wrmsr --processor 39 0x620 0x707

# Start Intel PCM in background and record in csv
# Throws an error with cores offline, disabling for now
sudo pcm-memory $INTERVAL -csv="$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_pcm_memory.csv" &
PCM_MEM_PID=$!

# Capture performance counter data
#$PERF_BIN stat -C 0-9,10-19 -I 2000 -e cycles,uops_retired.cycles,exe_activity.bound_on_loads,exe_activity.bound_on_stores,memory_activity.stalls_l1d_miss,memory_activity.stalls_l2_miss,memory_activity.stalls_l3_miss -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_perf.csv -x, &
#PERF_PID=$!

# Pin tasks to cores for determinism in performance
if [[ ${NUM_THREADS} -lt 10 ]]; then
    PINNING="taskset -c 1-${NUM_THREADS}"
elif [[ ${NUM_THREADS} -eq 10 ]]; then
    PINNING="taskset -c 1-9,20"
else
    PINNING="taskset -c 1-9,20-$((NUM_THREADS + 10))"
fi

# 020002a3 = CYCLE_ACTIVITY.CYCLES_L3_MISS
# 060006a3 = CYCLE_ACTIVITY.STALLS_L3_MISS

# Launch workload with memory interleaved from the specified NUMA node
PIDS=()
for i in $(seq 1 $NUM_COPIES); do
    #/usr/bin/time -v -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_time.txt ${HOME}/numactl-2.0.19/numactl -m 2,$NUMA_NODE -C 49-60\
    #     -- $RUN_CMD &
    ${PINNING} /usr/bin/time -v -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_time.txt perf stat -o $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_perf.txt -I 1000 -e cycles -e r020002a3 -e r060006a3 $RUN_CMD &> $LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_output.log &
    PIDS+=($!)
done

# Monitor NUMA memory usage while workloads are running
#echo "timestamp,node0_free_kb,node1_free_kb,node2_free_kb,node3_free_kb,node4_free_kb,node5_free_kb,node6_free_kb,node7_free_kb,node0_used_kb,node1_used_kb,node2_used_kb,node3_used_kb,node4_used_kb,node5_used_kb,node6_used_kb,node7_used_kb" > "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
echo "timestamp,node0_free_kb,node1_free_kb,node0_2M_free,node1_2M_free,node0_used_kb,node1_used_kb,node0_2M_total,node1_2M_total" > "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
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
    NODE2=$(grep HugePages_Free /sys/devices/system/node/node0/meminfo | awk '{print $4}')
    NODE3=$(grep HugePages_Free /sys/devices/system/node/node1/meminfo | awk '{print $4}')
    #NODE4=$(grep MemFree /sys/devices/system/node/node4/meminfo | awk '{print $4}')
    #NODE5=$(grep MemFree /sys/devices/system/node/node5/meminfo | awk '{print $4}')
    #NODE6=$(grep MemFree /sys/devices/system/node/node6/meminfo | awk '{print $4}')
    #NODE7=$(grep MemFree /sys/devices/system/node/node7/meminfo | awk '{print $4}')
    #echo -n "$TIMESTAMP,$NODE0,$NODE1,$NODE2,$NODE3,$NODE4,$NODE5" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    #echo -n "$TIMESTAMP,$NODE0,$NODE1,$NODE2,$NODE3,$NODE4,$NODE5,$NODE6,$NODE7" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    echo -n "$TIMESTAMP,$NODE0,$NODE1,$NODE2,$NODE3" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    NODE0=$(grep MemUsed /sys/devices/system/node/node0/meminfo | awk '{print $4}')
    NODE1=$(grep MemUsed /sys/devices/system/node/node1/meminfo | awk '{print $4}')
    NODE2=$(grep HugePages_Total /sys/devices/system/node/node0/meminfo | awk '{print $4}')
    NODE3=$(grep HugePages_Total /sys/devices/system/node/node1/meminfo | awk '{print $4}')
    #NODE4=$(grep MemUsed /sys/devices/system/node/node4/meminfo | awk '{print $4}')
    #NODE5=$(grep MemUsed /sys/devices/system/node/node5/meminfo | awk '{print $4}')
    #NODE6=$(grep MemUsed /sys/devices/system/node/node6/meminfo | awk '{print $4}')
    #NODE7=$(grep MemUsed /sys/devices/system/node/node7/meminfo | awk '{print $4}')
    #echo ",$NODE0,$NODE1,$NODE2,$NODE3,$NODE4,$NODE5" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    #echo ",$NODE0,$NODE1,$NODE2,$NODE3,$NODE4,$NODE5,$NODE6,$NODE7" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    echo ",$NODE0,$NODE1,$NODE2,$NODE3" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_numa_meminfo.csv"
    sleep $INTERVAL
done

# Wait for all workload copies to finish
for pid in "${PIDS[@]}"; do
    wait $pid
done

# Kill Perf
#kill $PERF_PID
# Kill PCM
sudo kill $PCM_MEM_PID
pkill -f pcm-memory

# Dump pgpromote and demote stats at start
echo "End" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_procfs.txt"
cat /proc/vmstat | grep "pgpromote\|pgdemote\|pgmigrate" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_procfs.txt"
#cat /proc/zoneinfo | grep "Node\|nr_\|workingset\|pgpromote\|pgdemote\|numa" >> "$LOG_DIR/$SUITE/${LOG_NUMBER}_${NUM_THREADS}t_procfs.txt"

# Reset AutoNUMA balancing and local tier size
echo 0 | sudo tee /sys/kernel/mm/numa/demotion_enabled
echo 1 | sudo tee /proc/sys/kernel/numa_balancing
echo 0 | sudo tee /proc/sys/vm/zone_reclaim_mode
#sudo $HOME/autonuma-utils/node0_size_control.sh reset

# disable memeater
sudo rmmod $HOME/colloid/tpp/memeater/memeater.ko

# Reset uncore frequencies
sudo wrmsr --processor 39 0x620 0xc14

# Kill CPU burner script
pkill -f cpu_burner.sh

# Bring all cores online
echo 1 | sudo tee /sys/devices/system/cpu/cpu*/online >/dev/null 2>&1

# Reset huge pages
echo 0 | sudo tee /sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages
echo 0 | sudo tee /sys/devices/system/node/node1/hugepages/hugepages-2048kB/nr_hugepages

echo "Monitoring complete. Logs saved in $LOG_DIR"
