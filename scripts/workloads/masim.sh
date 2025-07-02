#!/bin/bash

config_masim(){
    return
}

build_masim(){
    (cd $CUR_PATH/masim && make -j$(nproc))
}

run_masim(){
    local workload=$1

    /usr/bin/time -v -o ${OUTPUT_DIR}/${workload}_time.txt \
        taskset 0xFF \
        $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR \
        $CUR_PATH/masim/$1 $CUR_PATH/masim/configs/hc.cfg -c 2 &
    workload_pid=$!

}

run_strace_masim(){
    return
}

clean_masim(){
    return
}
