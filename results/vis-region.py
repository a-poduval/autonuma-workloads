# Python script for visualizing results of test scripts.
# WIP and very unstable. - Hayden Coffey
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
import gc
import argparse

from matplotlib.colors import LogNorm

outputimg = 'output.png'

def prepare_pebs_df(file, start_addr, end_addr):
    # Read the file line by line
    #with open(file) as f:
    #    rows = [line.strip().split() for line in f if line.strip()]

    # Read the file line by line
    rows = []
    with open(file, 'r') as f:
        for raw in f:
            if not raw.strip():
                continue

            # obtain fist element, i.e. address
            first, sep, rest = raw.partition(' ')
            addr = int(first, 16)

            if addr < start_addr:
                continue
            if addr >= end_addr:
                break

            parts = [first] + rest.split() if sep else [first.rstrip()]
            rows.append(parts)

    # Find the maximum number of columns in any row
    max_cols = max(len(row) for row in rows)

    # Pad each row so all have the same length
    #padded_rows = [row + [np.nan]*(max_cols - len(row)) for row in rows]

    # Function to pad each row with the last recorded value
    def pad_row(row, target_length):
        if len(row) < target_length:
            last_value = row[-1]
            # Extend the row with the last_value until it reaches the target length
            row = row + [last_value] * (target_length - len(row))
        return row

    # Pad each row accordingly
    #padded_rows = [pad_row(row, max_cols) for row in rows]
    padded_rows = []
    for row in rows:
        padded_rows.append(pad_row(row, max_cols))
        del row
        #gc.collect()

    # Create a DataFrame
    df = pd.DataFrame(padded_rows)

    # Rename columns: first column as 'PageFrame' and remaining as 'Epoch1', 'Epoch2', ...
    df.rename(columns={0: "PageFrame"}, inplace=True)
    df.columns = ["PageFrame"] + [f"Epoch_{i}" for i in range(1, max_cols)]

    # Convert epoch columns to numeric
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col])

    # Set PageFrame as index for easier time-series operations
    df.set_index("PageFrame", inplace=True)

    # Compute the deltas across epochs
    delta_df = df.diff(axis=1)

    # For the first epoch, fill NaN with the original epoch value
    first_epoch = df.columns[0]
    delta_df[first_epoch] = df[first_epoch]

    # Reorder columns to ensure the first epoch is first
    delta_df = delta_df[df.columns]

    # Optional: Convert column names to a numeric index if desired
    # For plotting purposes, we can remove the 'Epoch_' prefix and convert to int
    delta_df.columns = [int(col.replace("Epoch_", "")) for col in delta_df.columns]

    return delta_df

def prepare_damon_df(file):
    #file="gapbs_bc_damon.txt"

    print(file)
    data = pd.read_csv(file, header=None, delim_whitespace=True, names=['time', 'address', 'frequency'])
    data['address'] = data['address'].apply(lambda x: hex(x))

    data = data.pivot(index='address', columns='time', values='frequency')

    return data
    #sns.heatmap(data, cmap='viridis', norm=LogNorm())
    #plt.show()
    #print(data)


def view(directory, file, start, end, pebs=True):
    df = None
    if pebs:
        df = prepare_pebs_df(file, start, end)
        subdirectory="pebs"
    else:
        df = prepare_damon_df(file)
        subdirectory="damon"

    #output_dir = os.path.join(directory, subdirectory)
    #if not os.path.exists(output_dir):
    #    os.makedirs(output_dir)

    #file_name=(file.split('/')[-1].split('.')[0])
    #output_path = os.path.join(output_dir, file_name + "_heatmap.png")

    plt.figure(figsize=(12, 6))
    sns.heatmap(df, cmap="viridis", cbar=True, norm=LogNorm())
    plt.xlabel("Epoch")
    plt.ylabel("Page Frame")
    plt.title(file + ": Access Counts Over Time")

    #plt.savefig(file_name + "_heatmap.png", dpi=300, bbox_inches="tight")
    #plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(outputimg, dpi=300, bbox_inches="tight")
    #plt.show()

def auto_int(value: str) -> int:
    """
    Convert a string to int, accepting 0x-prefixed hex or plain decimal.
    argparse will call this for the two address arguments.
    """
    try:
        return int(value, 0)      # base-0 = “auto”: 0xAB = hex, else decimal
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value}") from e

def main():
    # Parse arguments
    p = argparse.ArgumentParser(description="Plot the PEBS access pattern for a subset of the data file, in an address range specified by start and end address")
    #p.add_argument("-i", "--input-file", required=True, type=Path, help="input file (sorted by address)")
    p.add_argument("-i", "--input-file", required=True, help="input file (sorted by address)")
    p.add_argument(
        "-s", "--start-addr", required=True, type=auto_int,
        help="inclusive lower bound (hex like 0x1000 or decimal)"
    )
    p.add_argument(
        "-e", "--end-addr", required=True, type=auto_int,
        help="exclusive upper bound (hex like 0x2000 or decimal)"
    )
    p.add_argument("-o", "--output-file", help="input file (sorted by address)")
    args = p.parse_args()
    if args.output_file:
        global outputimg
        outputimg = args.output_file
    directory = 1
    view(directory, args.input_file, args.start_addr, args.end_addr, True)

if __name__ == "__main__":
    main()
