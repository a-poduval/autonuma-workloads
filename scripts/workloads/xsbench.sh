#!/bin/bash 

config_xsbench(){
    num_threads=8
    particles=20000000 # Should take about 64G
    gridpoints=1300
}

build_xsbench(){
    (cd $CUR_PATH/XSBench/openmp-threading && make -j$(nproc))
}

run_xsbench(){
    OMP_NUM_THREADS=$num_threads taskset 0xFF \
        $CUR_PATH/record_vma.sh $CUR_PATH/XSBench/openmp-threading/XSBench -t $num_threads -p $particles -g $gridpoints
}

clean_xsbench(){
    return
}
