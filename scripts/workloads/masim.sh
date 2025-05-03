#!/bin/bash

config_masim(){
    return
}

build_masim(){
    (cd $CUR_PATH/masim && make -j$(nproc))
}

run_masim(){
    local workload=$1
    cd $CUR_PATH/masim

    $CUR_PATH/masim/$1 $CUR_PATH/masim/configs/hc.cfg -c 10 &
    workload_pid=$!

    cd $CUR_PATH
}

clean_masim(){
    return
}
