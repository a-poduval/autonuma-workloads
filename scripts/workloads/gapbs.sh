#!/bin/bash

config_gapbs(){
    num_threads=8
    num_rep=5
    num_iter=5
    graph_path=$CUR_PATH/gapbs/benchmark/graphs/twitter.sg
}

build_gapbs(){
    (cd $CUR_PATH/gapbs && make -j$(nproc) && make bench-run -j$(nproc))
}

run_gapbs(){
    local workload=$1

    if [[ $workload == "sssp" ]]; then
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            $CUR_PATH/gapbs/$1 -n $num_rep -f $graph_path
    else
        OMP_NUM_THREADS=$num_threads taskset 0xFF \
            $CUR_PATH/gapbs/$1 -n $num_rep -i $num_iter -f $graph_path
    fi
}

clean_gapbs(){
    return
}
