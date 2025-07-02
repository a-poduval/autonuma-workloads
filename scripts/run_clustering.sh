#!/bin/bash
set -x

n=2
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/graph500_graph500_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/liblinear_liblinear_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/flexkvs_flexkvs_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/merci_merci_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_bc_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_pr_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_pr_spmv_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_cc_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_cc_sv_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_bfs_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_sssp_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_tc_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --birch --birch_model birch_lite.model
done

n=1
for i in $(seq 1 $n); do
    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/omp-csr_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/graph500_graph500_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/train_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/liblinear_liblinear_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/kvsbench_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/flexkvs_flexkvs_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/eval_baseline_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/merci_merci_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/bc_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_bc_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/pr_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_pr_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/pr_spmv_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_pr_spmv_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/cc_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_cc_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/cc_sv_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_cc_sv_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/bfs_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_bfs_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/sssp_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_sssp_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model

    python scripts/clustering/cluster.py ./results/results_pebs_20k_1s_lite/tc_memory_regions_smap_deduplicated.csv ./results/results_pebs_20k_1s_lite/gapbs_tc_20000_samples.dat   --time_bin 20  --pebs_rate 20000 --fig --birch --birch_model birch_lite.model
done
