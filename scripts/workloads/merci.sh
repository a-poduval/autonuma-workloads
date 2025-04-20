#!/bin/bash

config_merci(){
    num_threads=8
    num_reps=10
}

build_merci(){
    (cd $CUR_PATH/MERCI/4_performance_evaluation && make -j$(nproc))
}

run_merci(){
    HOME=$CUR_PATH $CUR_PATH/record_vma.sh $CUR_PATH/MERCI/4_performance_evaluation/bin/eval_baseline --dataset amazon_All -r $num_reps -c $num_threads
}

clean_merci(){
    return
}
