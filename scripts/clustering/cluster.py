# Given input data produce:
# - Cluster region figure
# - PEBs Access heatmap figure
# - csv with page stats and cluster labels

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import numpy as np
import sys
import os
import re
import argparse
import time
import joblib
from collections import Counter

# Used to accelerate plotting DAMON figures.
#from concurrent.futures import ProcessPoolExecutor
#import multiprocessing
from multiprocessing import Pool, cpu_count
from functools import partial

from matplotlib.colors import LogNorm, hsv_to_rgb

from sklearn.cluster import KMeans, DBSCAN, Birch
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA, IncrementalPCA

def apply_cluster(page_stat_df, birch=None, ipca=None):
    scaler = StandardScaler()
    #print(page_stat_df)
    # Collapsed Clustering===========================
    #features = page_stat_df.drop(columns=['PageFrame_-1', 'PageFrame', 'PageFrame_1', \
    #        'rno_-1', 'rno', 'rno_1', 'duty_cycle_sample_count_-1', \
    #        'duty_cycle_sample_count', 'duty_cycle_sample_count_1', \
    #        'duty_cycle_-1', 'duty_cycle', 'duty_cycle_1'])
    # Collapsed Clustering===========================
    features = page_stat_df.drop(columns=['PageFrame', 'rno', 'duty_cycle_sample_count', 'duty_cycle'])
    #print(features)
    scaled_features = scaler.fit_transform(features)

    #pca_col = ['pc1', 'pc2']

    #k = 4
    #kmeans = KMeans(n_clusters=k)
    #kmeans.fit(scaled_features)
    #kmeans.fit(pca_df)
    if not birch and not ipca:
        pca = PCA(n_components=0.95)
        pca_df = pd.DataFrame(pca.fit_transform(scaled_features))#, columns=pca_col)
        db = DBSCAN(eps=1.0, min_samples=5).fit(pca_df) # Density based clustering
        page_stat_df['cluster'] = db.labels_
    if ipca and not birch:
        ipca.partial_fit(scaled_features)
        pca_df = ipca.transform(scaled_features)
        db = DBSCAN(eps=1.0, min_samples=5).fit(pca_df) # Density based clustering
        page_stat_df['cluster'] = db.labels_
    else:
        ipca.partial_fit(scaled_features)
        pca_df = ipca.transform(scaled_features)
        birch.partial_fit(pca_df)
        page_stat_df['cluster'] = birch.predict(pca_df)

    page_stat_df['cluster'] = page_stat_df['cluster'].astype(int)

    region_counts = page_stat_df['cluster'].value_counts()
    small_regions = region_counts[region_counts < 1024].index
    small_id = -1
    page_stat_df['cluster'] = page_stat_df['cluster'].apply(lambda x: small_id if x in small_regions else x)

    #for df in page_stat_df address groups of 0.5 GB:
        #find last boundary change in 0.5 GB group
        #convert all rows up to that boundary to the majority class
    page_stat_df['window_base'] = (page_stat_df['PageFrame'] // (2**29)) * (2**29)
    for base_addr, group in page_stat_df.groupby('window_base'):
        cluster_seq = group['cluster'].values
        last_boundary = 0

        for i in range(1, len(cluster_seq)):
            if cluster_seq[i] != cluster_seq[i-1]:
                last_boundary = i

        if last_boundary == 0:
            continue

        majority_cluster = Counter(cluster_seq[:last_boundary+1]).most_common(1)[0][0]

        index_to_update = group.index[:last_boundary+1]
        page_stat_df.loc[index_to_update, 'cluster'] = majority_cluster

    return page_stat_df

def find_region_id(row, df2):
    #print(row)
    #time = row['time']
    addr = row['PageFrame']
    matches = df2[
            (df2['start'] <= addr) &
            (df2['end'] > addr)
            #(df2['start_addr'] <= addr) &
            #(df2['end_addr'] >= addr)
            ]
    if not matches.empty:
        return matches.iloc[0]['rno'].astype(int) # if multiple matches, take the first
    else:
        #print("Failed! time {} addr {}".format(time,addr))
        #exit()
        return None

# Prepare a df for given PEBS sample file
def prepare_pebs_df(file):
    # Read the file line by line
    with open(file) as f:
        rows = [line.strip().split() for line in f if line.strip()]

    # Find the maximum number of columns in any row
    max_cols = max(len(row) for row in rows)

    # Function to pad each row with the last recorded value
    def pad_row(row, target_length):
        if len(row) < target_length:
            last_value = row[-1]
            # Extend the row with the last_value until it reaches the target length
            row = row + [last_value] * (target_length - len(row))
        return row

    # Pad each row accordingly
    padded_rows = [pad_row(row, max_cols) for row in rows]

    # Create a DataFrame
    df = pd.DataFrame(padded_rows)

    # Rename columns: first column as 'PageFrame' and remaining as 'Epoch1', 'Epoch2', ...
    df.rename(columns={0: "PageFrame"}, inplace=True)
    df.columns = ["PageFrame"] + [f"Epoch_{i}" for i in range(1, max_cols)]

    df["PageFrame"] = df["PageFrame"].apply(lambda x: hex(int(x, 16))) #<< 21))

    # Convert epoch columns to numeric
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col])


    # Set PageFrame as index for easier time-series operations
    df.set_index("PageFrame", inplace=True)

    df = df.copy() # Improves performance? df is sparse otherwise

    # Compute the deltas across epochs
    delta_df = df.diff(axis=1)

    # For the first epoch, fill NaN with the original epoch value
    first_epoch = df.columns[0]
    delta_df[first_epoch] = df[first_epoch]

    # Reorder columns to ensure the first epoch is first
    delta_df = delta_df[df.columns]

    # Optional: Convert column names to a numeric index if desired
    # For plotting purposes, we can remove the 'Epoch_' prefix and convert to int
    delta_df.columns = [int(col.replace("Epoch_", ""))*0.5 for col in delta_df.columns]

    # If we want to use plt instead of sns, melt df into long form
    df_long = (
        delta_df
        .reset_index()
        .melt(id_vars=["PageFrame"], var_name="epoch", value_name="value")
    )
    df_long["PageFrame"] = df_long["PageFrame"].apply(lambda x: int(x,16))

    return df_long

def get_reuse_distance_df(df):
    df_zero_streak_sorted = df.sort_values(by=['PageFrame', 'epoch']).reset_index(drop=True)

    # Container for results
    results = []

    grouped = df_zero_streak_sorted.groupby('PageFrame')
    # Group by PageFrame
    for pf, group in grouped:
        # Mark where value == 0
        zero_mask = group['value'] == 0

        # Identify start of new streaks using the change in zero_mask
        streak_id = (zero_mask != zero_mask.shift()).cumsum()

        # For value == 0 streaks only, compute their lengths
        zero_streaks = group[zero_mask].groupby(streak_id).size()

        # Get the max streak length (0 if none)
        max_streak = zero_streaks.max() if not zero_streaks.empty else 0

        results.append({'PageFrame': pf, 'reuse_distance': max_streak})

    # Create a new dataframe
    streak_df = pd.DataFrame(results)
    return streak_df

def calculate_duty_cycle(df):
    # Calculate Duty Cycle
    non_zero_df = df[df['value'] != 0]
    counts = non_zero_df.groupby('PageFrame').size()
    counts.name = 'duty_cycle'
    df = df.merge(counts, on='PageFrame', how='left')
    df['duty_cycle'] = df['duty_cycle'].fillna(0).astype(int)
    df['duty_cycle_sample_count'] = len(df['epoch'].unique())
    df['duty_cycle_percent'] = (df['duty_cycle'] / len(df['epoch'].unique())*100).astype(int)
    return df

def process_interval(df, split_vma_df, birch=None, ipca=None):
    preproc_time1_start = time.time()
    time_bin_df = df.copy()

    d_start = time.time()
    duty_df = calculate_duty_cycle(time_bin_df)
    d_end = time.time()
    duty_df = duty_df.drop_duplicates(subset='PageFrame')[['PageFrame', 'duty_cycle', 'duty_cycle_sample_count', 'duty_cycle_percent']]

    s_start = time.time()
    #streak_df = get_reuse_distance_df(time_bin_df)
    s_end = time.time()
    #time_bin_df = time_bin_df.merge(streak_df, on='PageFrame', how='left')

    v_start = time.time()
    page_stat_df = time_bin_df.groupby('PageFrame').agg(
        {
            'value': ['mean', 'std', 'min', 'max'],
            #'reuse_distance': ['mean']
        }
    )
    v_end = time.time()
    preproc_time1_end = time.time()
    print("preproc1 done : {} s".format(preproc_time1_end - preproc_time1_start))
    print("\td : {} s".format(d_end - d_start))
    print("\ts : {} s".format(s_end - s_start))
    print("\tv : {} s".format(v_end - v_start))

    preproc_time2_start = time.time()
    page_stat_df.columns = ['_'.join(col) for col in page_stat_df.columns]
    page_stat_df = page_stat_df.merge(duty_df, on='PageFrame', how='left')
    page_stat_df = page_stat_df.reset_index(drop=True)

    page_stat_df['rno'] = page_stat_df.apply(lambda row: find_region_id(row, split_vma_df), axis=1)
    page_stat_df = page_stat_df.dropna().reset_index(drop=True)

    page_stat_df = page_stat_df[page_stat_df['value_mean'] != 0.0]
    preproc_time2_end = time.time()
    print("preproc2 done : {} s", preproc_time2_end - preproc_time2_start)

    if page_stat_df.empty or len(page_stat_df) == 1:
        return None

    # Collapsed Clustering===========================
    #page_stat_df = page_stat_df.reset_index(drop=True)
    ## Shifted versions of the DataFrame
    #prev = page_stat_df.shift(1).add_suffix('_-1')
    #curr = page_stat_df.copy()
    #next_ = page_stat_df.shift(-1).add_suffix('_1')

    ## Concatenate them horizontally
    #expanded = pd.concat([prev, curr, next_], axis=1)

    ## Drop rows where we don't have full context (optional)
    ##expanded = expanded.dropna().reset_index(drop=True)
    #for col in page_stat_df.columns:
    #    expanded[f'{col}_-1'] = expanded[f'{col}_-1'].fillna(expanded[f'{col}'])
    #    expanded[f'{col}_1'] = expanded[f'{col}_1'].fillna(expanded[f'{col}'])
    ##print(expanded)
    ##assert False
    #
    #page_stat_df = expanded
    # Collapsed Clustering===========================

    #page_stat_df['rno'] = page_stat_df['rno'].astype(int)
    cluster_time_start = time.time()
    clustered_df = apply_cluster(page_stat_df.copy(), birch, ipca)
    cluster_time_end = time.time()
    print("Cluster done : {} s", cluster_time_end - cluster_time_start)

    time_bin_df = time_bin_df.merge(
        clustered_df.drop_duplicates('PageFrame'),
        on='PageFrame',
        how='left'
    )
    time_bin_df = time_bin_df.dropna()

    return time_bin_df

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("smap_file_path")
    parser.add_argument("pebs_file_path")
    parser.add_argument('--birch', default=False, action='store_true')
    args = parser.parse_args()
    smap_file = args.smap_file_path
    pebs_file = args.pebs_file_path
    is_birch = args.birch

    #smap_file = '../../results/results_vma_cluster/eval_baseline_memory_regions_smap_deduplicated.csv'
    #pebs_file = '../../results/results_vma_cluster/merci_merci_samples.dat'

    base,_ = os.path.splitext(pebs_file)
    N = 20 # Bin length in seconds

    if not is_birch:
        csv_output_file = base + "_" + str(N) + "_cluster.csv"
        cluster_fig_output_file = base + "_" + str(N) + "_cluster.png"
    else:
        csv_output_file = base + "_" + str(N) + "_birch_cluster.csv"
        cluster_fig_output_file = base + "_" + str(N) + "_birch_cluster.png"


    # Read in VMA smap data. Really just used to filter out memory addresses we don't want to examine (libraries etc.)
    vma_df = (pd.read_csv(smap_file))

    next_rno = vma_df['rno'].max() + 1 # When we split up large regions, start indexing new rno from here.

    vma_df['start'] = vma_df['start'].apply(lambda x: int(x,16))
    vma_df['end'] = vma_df['end'].apply(lambda x: int(x,16))
    print(vma_df)

    # Get only vma with no pathname (anon region) and a size over 2 MB
    filtered_vma_df = (vma_df[pd.isna(vma_df['pathname']) & (vma_df['size'] >= (1<<21))])

    def split_large_rows(df, next_rno, size_threshold=(1<<20)):
        new_rows = []

        for _, row in df.iterrows():
            if row['size'] > size_threshold:
                # Calculate number of chunks needed
                num_chunks = int(row['size'] // size_threshold)
                last_chunk_size = row['size'] % size_threshold

                # Split into chunks
                start = row['start']
                for i in range(num_chunks):
                    new_row = row.copy()
                    new_row['rno'] = next_rno
                    new_row['start'] = start
                    new_row['end'] = start + size_threshold * (1<<10)
                    new_row['size'] = size_threshold
                    new_rows.append(new_row)
                    start += size_threshold * (1<<10)
                    next_rno += 1

                # Last chunk (if any remainder)
                if last_chunk_size > 0:
                    new_row = row.copy()
                    new_row['rno'] = next_rno
                    new_row['start'] = start
                    new_row['end'] = start + last_chunk_size * (1<<10)
                    new_row['size'] = last_chunk_size
                    new_rows.append(new_row)
                    next_rno += 1
            else:
                new_rows.append(row)

        return pd.DataFrame(new_rows)

    split_vma_df = (split_large_rows(filtered_vma_df, next_rno)).reset_index(drop=True)
    print(split_vma_df)

    # Read in pebs data and bin in N second intervals
    df = prepare_pebs_df(pebs_file)
    df['time_bin'] = (df['epoch'] // N).astype(int)
    print(df)
    dfs_by_interval = {
        f"{N * bin}s_to_{N * (bin + 1)}s": group.drop(columns='time_bin')
        for bin, group in df.groupby('time_bin')
    }

    # Apply cluster labels in parallel for each binned df
    labeled_dfs = []
    print("Applying cluster labels to epochs...")
    dfs = list(dfs_by_interval.values())

    if not is_birch:
        # Parallel
        partial_func = partial(process_interval, split_vma_df=split_vma_df)
        with Pool(processes=cpu_count()) as pool:
            results = pool.map(partial_func, dfs)
    else:
        # Iterative online learning with birch
        # Load BIRCH and IPCA models if present, otherwise create
        birch_path='birch_model.joblib'
        ipca_path='ipca_model.joblib'
        if os.path.exists(birch_path):
            birch = joblib.load(birch_path)
        else:
            birch = Birch(n_clusters=None, threshold=1)
        if os.path.exists(ipca_path):
            ipca = joblib.load(ipca_path)
        else:
            ipca = IncrementalPCA(n_components=2)

        # Begin iterative online clustering
        i = 0
        results = []
        for df in dfs:
            start = time.time()
            results.append(process_interval(df, split_vma_df, birch, ipca))
            end = time.time()
            print("{}/{} : {} s".format(i, len(dfs)-1, end-start))
            i+=1

        # Save BIRCH and IPCA models
        joblib.dump(birch, birch_path)
        joblib.dump(ipca, ipca_path)

    # Filter out None results
    labeled_dfs = [df for df in results if df is not None]
    i = 0
    for df in labeled_dfs:
        df['cluster_epoch'] = i
        i+=1

    print("Generating cluster figure...")

    # Show clustered page region map
    final_df = pd.concat(labeled_dfs, ignore_index=True)

    if not is_birch:
        # Remove unclustered data points, if using DBSCAN
        final_df = final_df[final_df['cluster'] != -1.0]

    print(final_df)
    plt.figure(figsize=(12, 12))
    plt.scatter(final_df['epoch'], final_df['PageFrame'], c=final_df['cluster'], s=50, edgecolor='none', rasterized=True, alpha=0.7, marker='.')

    xmin = final_df['epoch'].min()
    xmax = final_df['epoch'].max()
    ymin = final_df['PageFrame'].min() + (1<<30)
    ax = plt.gca()

    # 1) Define a hex‐formatter: takes a float x and returns e.g. '0x1a3f'
    hex_formatter = FuncFormatter(lambda x, pos: hex(int(x)))

    # 2) Install it on the y‐axis
    ax.yaxis.set_major_formatter(hex_formatter)
    ax.invert_yaxis()

    #plt.show()
    plt.xlabel("Time (s)")
    plt.ylabel("Page Frame")
    plt.title(base + ": Clusters (N = " + str(N) + ")")
    plt.savefig(cluster_fig_output_file, dpi=300, bbox_inches="tight")
    final_df.to_csv(csv_output_file, index=False)
    #==================================

    # TODO fix pebs generation
    def generate_pebs_figure(file):
        base,_ = os.path.splitext(file)
        output_file = base + "_pebs_heatmap.png"
        print("Checking {}".format(output_file))

        if os.path.isfile(output_file):
            print("Skipping {}".format(output_file))
            return

        df = prepare_pebs_df(file)
        plt.figure(figsize=(12, 12))
        #sns.heatmap(df, cmap="viridis", cbar=True, norm=LogNorm())

        #xmin = df['epoch'].min()
        #xmax = df['epoch'].max()

        # Draw a horizontal line at y = some_value
        ymax = final_df['PageFrame'].max()
        ymin = final_df['PageFrame'].min()
        #plt.hlines(y=ymax, xmin=xmin, xmax=xmax, colors='red', linestyles='dashed')
        #plt.hlines(y=ymin, xmin=xmin, xmax=xmax, colors='red', linestyles='dashed')

        df = df[df['PageFrame'] >= ymin]
        df = df[df['PageFrame'] <= ymax]
        # If we want to use plt instead of sns
        plt.scatter(df['epoch'], df['PageFrame'], c=df['value'], s=50, norm=LogNorm(), edgecolor='none', rasterized=True, alpha=0.7, marker='.')

        ax = plt.gca()
        ## 1) Define a hex‐formatter: takes a float x and returns e.g. '0x1a3f'
        hex_formatter = FuncFormatter(lambda x, pos: hex(int(x)))

        ## 2) Install it on the y‐axis
        ax.yaxis.set_major_formatter(hex_formatter)
        ax.invert_yaxis()

        plt.xlabel("Time (s)")
        plt.ylabel("Page Frame")
        plt.title(file + ": PEBS")
        #plt.show()
        plt.savefig(output_file, dpi=300, bbox_inches="tight")

    generate_pebs_figure(pebs_file)
