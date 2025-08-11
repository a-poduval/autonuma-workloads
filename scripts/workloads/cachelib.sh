#!/bin/bash

config_cachelib(){
    #TODO: Update test config, this one is too small.
    cachelib_json=$CUR_PATH/CacheLib/cachelib/cachebench/test_configs/simple_test.json
    return
}

build_cachelib(){
    pushd $CUR_PATH/CacheLib

    # CacheLib needs fastfloat installed to run.
    #git clone https://github.com/fastfloat/fast_float.git
    #pushd fast_float
    #cmake -B build -DFASTFLOAT_TEST=OFF
    #sudo cmake --build build --target install
    #popd

    ./contrib/build.sh -j -T

    popd
}

run_cachelib(){
    local workload=$1
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        $CUR_PATH/CacheLib/opt/cachelib/bin/cachebench \
        --json_test_config $cachelib_json \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &
        #$CUR_PATH/scripts/vma/record_vma.sh $OUTPUT_DIR \
    workload_pid=$!
}

run_strace_cachelib(){
    return
}

clean_cachelib(){
    rm logs.txt stats.txt times.txt
    return
}
