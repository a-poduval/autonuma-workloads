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
    local workload=$1
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        $CUR_PATH/flexkvs/kvsbench -t $num_threads -T $run_time -w $warmup_time -h 0.25 127.0.0.1:1211 -S $kv_size \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &
    workload_pid=$!
}

run_strace_flexkvs(){
    strace -e mmap,munmap -o flexkvs_flexkvs_strace.log $CUR_PATH/flexkvs/kvsbench -t $num_threads -T $run_time -w $warmup_time -h 0.25 127.0.0.1:1211 -S $kv_size
}

clean_flexkvs(){
    return
}
