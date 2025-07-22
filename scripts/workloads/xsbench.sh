#!/bin/bash

config_xsbench(){
    num_threads=8
    particles=20000000 # Should take about 64G
    gridpoints=130000
}

build_xsbench(){
    (cd $CUR_PATH/XSBench/openmp-threading && make -j$(nproc))
}

run_xsbench(){
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        OMP_NUM_THREADS=$num_threads \
        $CUR_PATH/XSBench/openmp-threading/XSBench -t $num_threads -p $particles -g $gridpoints \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &

    workload_pid=$!
}

run_strace_xsbench(){
    OMP_NUM_THREADS=$num_threads taskset 0xFF \
        strace -e mmap,munmap -o xsbench_xsbench_strace.log $CUR_PATH/XSBench/openmp-threading/XSBench -t $num_threads -p $particles -g $gridpoints
}

clean_xsbench(){
    return
}
