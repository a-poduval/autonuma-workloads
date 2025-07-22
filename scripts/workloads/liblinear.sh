#!/bin/bash

#TODO: Where to get dataset?
config_liblinear(){
    num_threads=8
    dataset=$CUR_PATH/liblinear-2.47/kdd12
}

build_liblinear(){
    (cd $CUR_PATH/liblinear-2.47 && make -j$(nproc))
}

run_liblinear(){
    local workload=$1
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        $CUR_PATH/liblinear-2.47/train -s 6 -m $num_threads $dataset \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &
        #$CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR \
    workload_pid=$!
}

run_strace_liblinear(){
    strace -e mmap,munmap -o liblinear_liblinear_strace.log $CUR_PATH/liblinear-2.47/train -s 6 -m $num_threads $dataset
}

clean_liblinear(){
    return
}
