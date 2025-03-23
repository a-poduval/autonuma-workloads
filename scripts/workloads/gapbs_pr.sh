#!/bin/bash

config_gapbs_pr(){
    num_threads=8
    num_rep=5
    num_iter=5
    graph_path=$CUR_PATH/gapbs/benchmark/graphs/twitter.sg
}

build_gapbs_pr(){
    (cd $CUR_PATH/gapbs && make && make bench-run)
}

run_gapbs_pr(){
    OMP_NUM_THREADS=$num_threads taskset 0xFF \
        $CUR_PATH/gapbs/pr -n $num_rep -i $num_iter -f $graph_path
}
