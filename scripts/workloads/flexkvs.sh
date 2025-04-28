#!/bin/bash

config_flexkvs(){
    num_threads=8
    kv_size=$((32*1024*1024*1024))
    warmup_time=20
    run_time=100
}

build_flexkvs(){
    (cd $CUR_PATH/flexkvs && make -j$(nproc))
}

run_flexkvs(){
    taskset 0xFF $CUR_PATH/record_vma.sh $CUR_PATH/flexkvs/kvsbench -t $num_threads -T $run_time -w $warmup_time -h 0.25 127.0.0.1:1211 -S $kv_size
}

run_strace_flexkvs(){
    strace -e mmap,munmap -o flexkvs_flexkvs_strace.log $CUR_PATH/flexkvs/kvsbench -t $num_threads -T $run_time -w $warmup_time -h 0.25 127.0.0.1:1211 -S $kv_size
}

clean_flexkvs(){
    return
}
