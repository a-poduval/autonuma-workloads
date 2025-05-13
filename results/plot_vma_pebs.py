import os
import csv
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLOT_SCRIPT = os.path.join(BASE_DIR, 'vis-region.py')

for entry in os.listdir(BASE_DIR):
    suite_path = os.path.join(BASE_DIR, entry)
    if os.path.isdir(suite_path) and entry.startswith("results_"):
        csv_files = [f for f in os.listdir(suite_path) if f.endswith("vma.csv")]
        dat_files = [f for f in os.listdir(suite_path) if f.endswith(".dat")]
        csv_file = os.path.join(suite_path, csv_files[0])
        dat_file = os.path.join(suite_path, dat_files[0])
        #csv_file = os.path.join(suite_path, f"{entry[8:]}_vma.csv")
        #dat_file = os.path.join(suite_path, f"{entry[8:]}_samples.dat")

        if not os.path.exists(csv_file) or not os.path.exists(dat_file):
            continue

        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start = int(row['start'], 16)
                    end = int(row['end'], 16)
                    size = end - start
                    rss_kb = int(row['rss_kb'])

                    if size >= 2048 and rss_kb >= 2048:
                        out_file = os.path.join(
                            suite_path,
                            f"{hex(start)}_{hex(end)}_vma.png".replace("0x", "")
                        )
                        cmd = [
                            "python3", PLOT_SCRIPT,
                            "-i", dat_file,
                            "-s", hex(start),
                            "-e", hex(end),
                            "-o", out_file
                        ]
                        print("Running:", " ".join(cmd))
                        subprocess.run(cmd, check=True)

                except Exception as e:
                    print(f"Error processing row {row}: {e}")
    #sys.exit()
