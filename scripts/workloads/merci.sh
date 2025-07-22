#!/bin/bash

config_merci(){
    num_threads=8
    num_reps=5
}

build_merci(){
    (cd $CUR_PATH/MERCI/4_performance_evaluation && make -j$(nproc))
}

run_merci(){
    local workload=$1
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        HOME=$CUR_PATH \
        $CUR_PATH/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r $num_reps -c $num_threads \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &

    workload_pid=$!
}

run_strace_merci(){
    HOME=$CUR_PATH strace -e mmap,munmap -o merci_merci_strace.log $CUR_PATH/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r $num_reps -c $num_threads
}

clean_merci(){
    return
}
