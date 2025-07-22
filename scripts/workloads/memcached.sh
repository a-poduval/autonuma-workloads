
#!/bin/bash
set -x
config_memcached(){
    client_threads=16
    server_threads=4
}

build_memcached(){
    # Build memcached
    pushd $CUR_PATH/memcached > /dev/null

    ./autogen.sh
    ./configure
    (make -j$(nproc))

    popd

    # Build YCSB with memcached bindings
    pushd $CUR_PATH/YCSB > /dev/null

    mvn -pl site.ycsb:memcached-binding -am clean package

    popd

}

run_memcached(){
    local workload=$1

    # Start memcached server (64 GB), bind to NUMA node 0
    numactl --cpunodebind=0 --membind=0 \
        sudo LD_PRELOAD=$HEMEMPOL DRAMSIZE=$DRAMSIZE MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE \
        $CUR_PATH/memcached/memcached -u $(whoami) -d -p 11211 -m 67108864 -t $server_threads

    sleep 5

    pushd $CUR_PATH/YCSB > /dev/null

    # SETUP: Load data into data base.
    ./bin/ycsb load memcached -s -P $CUR_PATH/YCSB/workloads/workloada \
        -p "memcached.hosts=127.0.0.1" -threads $client_threads

    sleep 5

    # RUN: Record performance
    /usr/bin/time -v -o "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_time.txt" \
        numactl --cpunodebind=1 --membind=1 \
        ./bin/ycsb run memcached -s -P $CUR_PATH/YCSB/workloads/workloada \
        -p "memcached.hosts=127.0.0.1" -threads $client_threads \
        1> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stdout.txt" \
        2> "${OUTPUT_DIR}/${SUITE}_${WORKLOAD}_${hemem_policy}_${DRAMSIZE}_stderr.txt" &
    workload_pid=$!

    popd
}

run_strace_memcached(){
    return
}

clean_memcached(){
    echo "Cleaning up."
    sudo killall memcached
    return
}
