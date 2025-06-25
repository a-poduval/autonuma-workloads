#!/bin/bash

config_gapbs(){
    num_threads=8
    num_rep=5
    num_iter=5
    graph_path=$CUR_PATH/gapbs/benchmark/graphs/twitterU.sg
    w_graph_path=$CUR_PATH/gapbs/benchmark/graphs/twitter.wsg
}

build_gapbs(){
    (cd $CUR_PATH/gapbs && make -j$(nproc) && make bench-graphs -j$(nproc))
}

run_gapbs(){
    local workload=$1

    if [ $workload == "cc" ] || [ $workload == "cc_sv" ] || [ $workload == "bfs" ] || [ $workload == "tc" ]; then
        OMP_NUM_THREADS=$num_threads \
            /usr/bin/time -v -o ${OUTPUT_DIR}/${workload}_time.txt \
            taskset 0xFF \
            $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
            #$CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
    elif [ $workload == "sssp" ]; then
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            /usr/bin/time -v -o ${OUTPUT_DIR}/${workload}_time.txt \
            $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/gapbs/$1 -n $num_rep -f $w_graph_path &
            #$CUR_PATH/gapbs/$1 -n $num_rep -f $w_graph_path &
    else
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            /usr/bin/time -v -o ${OUTPUT_DIR}/${workload}_time.txt \
            $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
            #$CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
    fi

    workload_pid=$!
}

run_strace_gapbs(){
    local workload=$1

    if [ $workload == "cc" ] || [ $workload == "cc_sv" ] || [ $workload == "bfs" ] || [ $workload == "tc" ]; then
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            strace -e mmap,munmap -o gapbs_$1_strace.log $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
    elif [ $workload == "sssp" ]; then
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            strace -e mmap,munmap -o gapbs_$1_strace.log $CUR_PATH/gapbs/$1 -n $num_rep -f $w_graph_path &
    else
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            strace -e mmap,munmap -o gapbs_$1_strace.log $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
    fi

    workload_pid=$!
}

clean_gapbs(){
    return
}
