#!/bin/bash
#==============================================================
# 4, 8, 16, 32 GB
#DRAM_SIZES=(4294967296)
#HEMEM_POL=(/mydata/hemem/src/libhemem.so)
#MIN_INTERPOSE_MEM_SIZE=33554432
MIN_INTERPOSE_MEM_SIZE=67108864
DRAM_SIZES=(2147483648 4294967296 8589934592 17179869184 34359738368)
HEMEM_POL=(/mydata/hemem/src/libhemem.so /mydata/hemem/src/libhemem-lru.so)
N=5
for i in $(seq 1 $N); do
    for size in "${DRAM_SIZES[@]}"; do
        for pol in "${HEMEM_POL[@]}"; do

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b xsbench -w xsbench -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b silo -w silo -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b liblinear -w liblinear -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b flexkvs -w flexkvs -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b graph500 -w graph500 -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w bc -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w pr -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w pr_spmv -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w cc -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w cc_sv -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w bfs -o results/results_freq_lru_${i}

           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w sssp -o results/results_freq_lru_${i}

            # ======================
            # gapbs tc takes too long (~2 hours per run)
            #HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b gapbs -w tc -o results/results_freq_lru_${i}

            #MERCI doesn't work with HEMEM
            #HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b merci -w merci -o results/results_freq_lru_${i}

        done
    done
done

N=3
# May or may not work, lets run after other workloads are done that are more stable
for i in $(seq 1 $N); do
    for size in "${DRAM_SIZES[@]}"; do
        for pol in "${HEMEM_POL[@]}"; do
           MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$size ./run.sh -b memcached -w memcached -o results/results_freq_lru_${i}
        done
    done
done
