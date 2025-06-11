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

# Used to accelerate plotting DAMON figures.
#from concurrent.futures import ProcessPoolExecutor
#import multiprocessing
from multiprocessing import Pool, cpu_count
from functools import partial

from matplotlib.colors import LogNorm, hsv_to_rgb

from sklearn.cluster import KMeans, DBSCAN, Birch
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

def apply_cluster(page_stat_df):
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
    pca = PCA(n_components=0.95)
    pca_df = pd.DataFrame(pca.fit_transform(scaled_features))#, columns=pca_col)
    
    #k = 4
    #kmeans = KMeans(n_clusters=k)
    #kmeans.fit(scaled_features)
    #kmeans.fit(pca_df)
    db = DBSCAN(eps=1.0, min_samples=5).fit(pca_df) # Density based clustering
    #db = DBSCAN(eps=1.0, min_samples=1) # Density based clustering

    #birch = Birch(n_clusters=None, threshold=2).fit(pca_df) # Density based clustering
    #print(birch.labels_)
    #db = HDBSCAN(min_cluster_size=2).fit(pca_df) # Density based clustering
    
    #page_stat_df['cluster'] = kmeans.labels_
    #page_stat_df['cluster'] = birch.labels_
    page_stat_df['cluster'] = db.labels_
    page_stat_df['cluster'] = page_stat_df['cluster'].astype(int)

    page_stat_df_merged = (pd.concat([page_stat_df, pca_df], axis=1))
    page_stat_df_merged['start_epoch'] = 0

    # Return new df with cluster labels and pca values
    return page_stat_df_merged

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
    
    # Group by PageFrame
    for pf, group in df_zero_streak_sorted.groupby('PageFrame'):
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

def process_interval(df, split_vma_df):
    time_bin_df = df.copy()

    duty_df = calculate_duty_cycle(time_bin_df)
    duty_df = duty_df.drop_duplicates(subset='PageFrame')[['PageFrame', 'duty_cycle', 'duty_cycle_sample_count', 'duty_cycle_percent']]

    streak_df = get_reuse_distance_df(time_bin_df)
    time_bin_df = time_bin_df.merge(streak_df, on='PageFrame', how='left')

    page_stat_df = time_bin_df.groupby('PageFrame').agg(
        {
            'value': ['mean', 'std', 'min', 'max'],
            'reuse_distance': ['mean']
        }
    )

    page_stat_df.columns = ['_'.join(col) for col in page_stat_df.columns]
    page_stat_df = page_stat_df.merge(duty_df, on='PageFrame', how='left')
    page_stat_df = page_stat_df.reset_index(drop=True)

    page_stat_df['rno'] = page_stat_df.apply(lambda row: find_region_id(row, split_vma_df), axis=1)
    page_stat_df = page_stat_df.dropna().reset_index(drop=True)

    page_stat_df = page_stat_df[page_stat_df['value_mean'] != 0.0]

    if page_stat_df.empty:
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
    clustered_df = apply_cluster(page_stat_df.copy())

    time_bin_df = time_bin_df.merge(
        clustered_df[['PageFrame', 'cluster']].drop_duplicates('PageFrame'),
        on='PageFrame',
        how='left'
    )
    time_bin_df = time_bin_df.dropna()

    return time_bin_df

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("smap_file_path")
    parser.add_argument("pebs_file_path")
    args = parser.parse_args()
    smap_file = args.smap_file_path
    pebs_file = args.pebs_file_path

    #smap_file = '../../results/results_vma_cluster/eval_baseline_memory_regions_smap_deduplicated.csv'
    #pebs_file = '../../results/results_vma_cluster/merci_merci_samples.dat'

    base,_ = os.path.splitext(pebs_file)
    N = 20 # Bin length in seconds
    csv_output_file = base + "_" + str(N) + "_cluster.csv"
    cluster_fig_output_file = base + "_" + str(N) + "_cluster.png"

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
    i = 0
    print("Applying cluster labels to epochs...")
    dfs = list(dfs_by_interval.values())
    partial_func = partial(process_interval, split_vma_df=split_vma_df)

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(partial_func, dfs)

    # Filter out None results
    labeled_dfs = [df for df in results if df is not None]

    print("Generating cluster figure...")

    # Show clustered page region map
    final_df = pd.concat(labeled_dfs, ignore_index=True)
    final_df = final_df[final_df['cluster'] != -1.0] # Remove unclustered data points
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
    final_df.to_csv(csv_output_file)
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
