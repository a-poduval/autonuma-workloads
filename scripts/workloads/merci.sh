#!/bin/bash

config_merci(){
    num_threads=8
    num_reps=5
}

build_merci(){
    (cd $CUR_PATH/MERCI/4_performance_evaluation && make -j$(nproc))
}

run_merci(){
    HOME=$CUR_PATH taskset 0xFF $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r $num_reps -c $num_threads &

    workload_pid=$!
}

run_strace_merci(){
    HOME=$CUR_PATH strace -e mmap,munmap -o merci_merci_strace.log $CUR_PATH/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r $num_reps -c $num_threads
}

clean_merci(){
    return
}
