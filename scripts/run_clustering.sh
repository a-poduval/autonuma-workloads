#!/bin/bash
# Training
n=0
for i in $(seq 1 $n); do
    echo "${i} ======================================"
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --birch_model birch_10.model
done

n=0
for i in $(seq 1 $n); do
    echo "${i} ======================================"
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --birch_model birch_5.model
done

n=0
for i in $(seq 1 $n); do
    echo "${i} ======================================"
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --birch_model birch_1.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/graph500_graph500_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/liblinear_liblinear_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/flexkvs_flexkvs_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/merci_merci_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_bc_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_pr_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_pr_spmv_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_cc_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_cc_sv_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_bfs_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_sssp_samples.dat --birch --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_tc_samples.dat --birch --birch_model birch_2k_1.model
done

# Plotting Figures
n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/graph500_graph500_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/liblinear_liblinear_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/flexkvs_flexkvs_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/merci_merci_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_bc_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_pr_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_pr_spmv_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_cc_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_cc_sv_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_bfs_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_sssp_samples.dat --birch --fig --birch_model birch_2k_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_tc_samples.dat --birch --fig --birch_model birch_2k_1.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/graph500_graph500_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/liblinear_liblinear_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/flexkvs_flexkvs_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/merci_merci_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_bc_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_pr_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_pr_spmv_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_cc_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_cc_sv_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_bfs_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_sssp_samples.dat --birch --fig --birch_model birch_2k_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_2k_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_2k_1s/gapbs_tc_samples.dat --birch --fig --birch_model birch_2k_0.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --fig --birch_model birch_1.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --fig --birch_model birch_1.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --fig --birch_model birch_5.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --fig --birch_model birch_5.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --fig --birch_model birch_0.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --fig --birch_model birch_0.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/graph500_graph500_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/liblinear_liblinear_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/flexkvs_flexkvs_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/merci_merci_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bc_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_pr_spmv_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_cc_sv_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_bfs_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_sssp_samples.dat --birch --fig --birch_model birch_10.model

    python scripts/clustering/cluster.py ./results/results_pebs_500_1s/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_500_1s/gapbs_tc_samples.dat --birch --fig --birch_model birch_10.model
done
