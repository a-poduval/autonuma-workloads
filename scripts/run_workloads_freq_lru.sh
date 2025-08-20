#!/bin/bash
#==============================================================
# 4, 8, 16, 32 GB
#DRAM_SIZES=(4294967296)
#HEMEM_POL=(/mydata/hemem/src/libhemem.so)
#MIN_INTERPOSE_MEM_SIZE=33554432
MIN_INTERPOSE_MEM_SIZE=67108864
DRAM_SIZES=(2147483648)
HEMEM_POL=(/mydata/hemem/src/libhemem.so /mydata/hemem/src/libhemem-lru.so /mydata/hemem/src/libhemem-baseline.so)
N=0
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

cloverleaf_peak=$((9154748*1024))

liblinear_peak=$((74121965774)) #~69 GB?
DRAM_SIZES=(0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 0.1 1)
N=15
HEMEM_POL=(/mydata/hemem/src/libhemem.so /mydata/hemem/src/libhemem-lru.so /mydata/hemem/src/libhemem-baseline.so)
# May or may not work, lets run after other workloads are done that are more stable
for i in $(seq 4 $N); do
    for size in "${DRAM_SIZES[@]}"; do
        for pol in "${HEMEM_POL[@]}"; do
            MEM_USED=$(echo "$liblinear_peak * $size / 1" | bc)
            MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$MEM_USED ./run.sh -b liblinear -w liblinear -o results/test_${i}

            MEM_USED=$(echo "$cloverleaf_peak * $size / 1" | bc)
            MIN_INTERPOSE_MEM_SIZE=$MIN_INTERPOSE_MEM_SIZE HEMEMPOL=$pol DRAMSIZE=$MEM_USED ./run.sh -b cloverleaf -w cloverleaf -o results/test_${i}
        done
    done
done
