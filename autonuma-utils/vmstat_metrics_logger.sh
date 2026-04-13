#!/bin/bash
# os_metrics_logger.sh

#LOG_FILE="os_metrics_log.csv"
PID=$1

# Print CSV header
echo "Timestamp,numa_pte_updates,numa_hint_faults,numa_hint_faults_local,pgpromote_success,pgpromote_candidate,pgdemote_kswapd,pgdemote_direct,pgdemote_khugepaged,pgmigrate_success,pgmigrate_fail,tlb_shootdowns" #> $LOG_FILE

while true; do
    TS=$(date +%s)
    
    # Extract NUMA balancing and migration stats from vmstat
    VMSTAT_DATA=$(cat /proc/vmstat)
    NUMA_PTE=$(echo "$VMSTAT_DATA" | grep numa_pte_updates | awk '{print $2}')
    NUMA_HINT=$(echo "$VMSTAT_DATA" | grep "numa_hint_faults " | awk '{print $2}')
    NUMA_HINT_LOCAL=$(echo "$VMSTAT_DATA" | grep "numa_hint_faults_local " | awk '{print $2}')
    PROM_SUCC=$(echo "$VMSTAT_DATA" | grep pgpromote_success | awk '{print $2}')
    PROM_CAND=$(echo "$VMSTAT_DATA" | grep pgpromote_candidate | awk '{print $2}')
    DEMO_KSWP=$(echo "$VMSTAT_DATA" | grep pgdemote_kswapd | awk '{print $2}')
    DEMO_DIR=$(echo "$VMSTAT_DATA" | grep pgdemote_direct | awk '{print $2}')
    DEMO_KHUG=$(echo "$VMSTAT_DATA" | grep pgdemote_khugepaged | awk '{print $2}')
    MIG_SUCC=$(echo "$VMSTAT_DATA" | grep pgmigrate_success | awk '{print $2}')
    MIG_FAIL=$(echo "$VMSTAT_DATA" | grep pgmigrate_fail | awk '{print $2}')
    
    # Extract TLB Shootdowns (CAL: Function call interrupts) across all CPUs
    #TLB_SHOOTDOWNS=$(grep 'TLB:' /proc/interrupts | awk '{sum=0; for(i=2; i<=NF-1; i++) sum+=$i; print sum}')
    # We only want TLB shootdowns for the 8 CPUs on which we are running the workload
    TLB_SHOOTDOWNS=$(grep 'TLB:' /proc/interrupts | awk '{sum=0; for(i=3; i<=10; i++) sum+=$i; print sum}')
    
    # Log to CSV
    echo "$TS,$NUMA_PTE,$NUMA_HINT,$NUMA_HINT_LOCAL,$PROM_SUCC,$PROM_CAND,$DEMO_KSWP,$DEMO_DIR,$DEMO_KHUG,$MIG_SUCC,$MIG_FAIL,$TLB_SHOOTDOWNS" #>> $LOG_FILE
    
    sleep 1
done
