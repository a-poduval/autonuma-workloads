#!/bin/bash

config_gapbs(){
    num_threads=8
    num_rep=5
    num_iter=5
    graph_path=$CUR_PATH/gapbs/benchmark/graphs/twitter.sg
    w_graph_path=$CUR_PATH/gapbs/benchmark/graphs/twitter.wsg
}

build_gapbs(){
    (cd $CUR_PATH/gapbs && make -j$(nproc) && make bench-run -j$(nproc))
}

run_gapbs(){
    local workload=$1

    if [ $workload == "cc" ] || [ $workload == "cc_sv" ] || [ $workload == "bfs" ] || [ $workload == "tc" ]; then
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            $CUR_PATH/record_vma.sh $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
    elif [ $workload == "sssp" ]; then
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            $CUR_PATH/record_vma.sh $CUR_PATH/gapbs/$1 -n $num_rep -f $w_graph_path &
    else
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            #$CUR_PATH/record_vma.sh $CUR_PATH/gapbs/$1 -n $num_rep -i $num_iter -f $graph_path &
            $CUR_PATH/record_vma.sh $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path &
    fi
    $CUR_PATH/largest_vma.sh -i memory_regions.csv -o $CUR_PATH/results/results_gapbs/gapbs_$1_vma.csv

    workload_pid=$!
}

clean_gapbs(){
    return
}
