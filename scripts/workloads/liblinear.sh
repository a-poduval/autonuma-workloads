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
    taskset 0xFF $CUR_PATH/record_vma.sh $CUR_PATH/liblinear-2.47/train -s 6 -m $num_threads $dataset
}

run_strace_liblinear(){
    strace -e mmap,munmap -o liblinear_liblinear_strace.log $CUR_PATH/liblinear-2.47/train -s 6 -m $num_threads $dataset
}

clean_liblinear(){
    return
}
