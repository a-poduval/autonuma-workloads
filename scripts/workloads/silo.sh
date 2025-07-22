#!/bin/bash

config_silo(){
    benchmark=tpcc
    sf=200
    ops=2000000
    num_threads=8
}

build_silo(){
    (cd $CUR_PATH/MERCI/4_performance_evaluation && MODE=perf make -j dbtest)
}

run_silo(){
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        $CUR_PATH/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench $benchmark --scale-factor $sf --ops-per-worker $ops --num-threads $num_threads \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &
    #taskset 0xFF $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench $benchmark --scale-factor $sf --ops-per-worker $ops --num-threads $num_threads &
    workload_pid=$!
}

run_strace_silo(){
    strace -e mmap,munmap -o silo_silo_strace.log $CUR_PATH/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench $benchmark --scale-factor $sf --ops-per-worker $ops --num-threads $num_threads
}

clean_silo(){
    return
}
