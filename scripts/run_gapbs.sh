#!/bin/bash

./run.sh -b gapbs -w bc -o results/results_gapbs
./run.sh -b gapbs -w bfs -o results/results_gapbs
./run.sh -b gapbs -w cc -o results/results_gapbs
./run.sh -b gapbs -w cc_sv -o results/results_gapbs
./run.sh -b gapbs -w pr -o results/results_gapbs
./run.sh -b gapbs -w pr_spmv -o results/results_gapbs
./run.sh -b gapbs -w tc -o results/results_gapbs

#sssp Requires different arguments
#./run.sh -b gapbs -w sssp -o results/results_gapbs
