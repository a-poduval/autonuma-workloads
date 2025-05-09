#!/bin/bash

config_silo(){
    benchmark=tpcc
    sf=100
    ops=1000000
    num_threads=8
}

build_silo(){
    (cd $CUR_PATH/MERCI/4_performance_evaluation && make -j$(nproc))
}

run_silo(){
    taskset 0xFF $CUR_PATH/record_vma.sh $CUR_PATH/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench $benchmark --scale-factor $sf --ops-per-worker $ops --num-threads $num_threads
}

run_strace_silo(){
    strace -e mmap,munmap -o silo_silo_strace.log $CUR_PATH/silo/silo/out-perf.masstree/benchmarks/dbtest --verbose --bench $benchmark --scale-factor $sf --ops-per-worker $ops --num-threads $num_threads
}

clean_silo(){
    return
}
