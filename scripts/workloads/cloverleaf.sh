#!/bin/bash

config_cloverleaf(){
    WORK_DIR=$CUR_PATH/CloverLeaf/CloverLeaf_OpenMP/
    num_threads=16
    cp $WORK_DIR/InputDecks/clover_bm16_short.in ./clover.in
}

build_cloverleaf(){
    pushd $WORK_DIR

    make COMPILER=GNU -j $(nproc)

    popd
}

run_cloverleaf(){
    local workload=$1
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        OMP_NUM_THREADS=$num_threads \
        $WORK_DIR/clover_leaf \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &
    workload_pid=$!
}

run_strace_cloverleaf(){
    return
}

clean_cloverleaf(){
    rm -f clover.in times.txt logs.txt stats.txt clover.in.tmp clover.out
    return
}
