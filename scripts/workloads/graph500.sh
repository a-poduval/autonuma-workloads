#!/bin/bash

config_graph500(){
    num_threads=8
    size=26
    skip_validation=1
}

build_graph500(){
    pushd $CUR_PATH/graph500 > /dev/null

    git checkout master

    cp make-incs/make.inc-gcc make.inc
    
    #Change makefile gcc version and enable openmp
    sed -i -e 's/^CC = gcc-4.6/CC = gcc/' \
        -e 's/^# \(BUILD_OPENMP = Yes\)/\1/' \
        -e 's/^# \(CFLAGS_OPENMP = -fopenmp\)/\1/' make.inc

    (make -j$(nproc))

    popd
}

run_graph500(){
    SKIP_VALIDATION=$skip_validation OMP_NUM_THREADS=$num_threads taskset 0xFF \
        $CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR $CUR_PATH/graph500/omp-csr/omp-csr -s $size -V
}

run_strace_graph500(){
    SKIP_VALIDATION=$skip_validation OMP_NUM_THREADS=$num_threads taskset 0xFF \
        strace -e mmap,munmap -o graph500_xsbench_strace.log $CUR_PATH/graph500/omp-csr/omp-csr -s $size -V
}

clean_graph500(){
    return
}
