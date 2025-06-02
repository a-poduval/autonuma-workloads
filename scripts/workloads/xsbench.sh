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
    OMP_NUM_THREADS=$num_threads taskset 0xFF \
        $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/XSBench/openmp-threading/XSBench -t $num_threads -p $particles -g $gridpoints

    workload_pid=$!
}

run_strace_xsbench(){
    OMP_NUM_THREADS=$num_threads taskset 0xFF \
        strace -e mmap,munmap -o xsbench_xsbench_strace.log $CUR_PATH/XSBench/openmp-threading/XSBench -t $num_threads -p $particles -g $gridpoints
}

clean_xsbench(){
    return
}
