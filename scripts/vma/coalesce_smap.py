import pandas as pd
import sys

file_name = sys.argv[1]

# Load the smap CSV file
df = pd.read_csv(file_name)

# Convert addresses to integers for comparison
df['start'] = df['start'].apply(lambda x: int(str(x), 16))
df['end'] = df['end'].apply(lambda x: int(str(x), 16))

# Sort for consistent deduplication
df = df.sort_values(by=['start', 'end', 'rss_kb'], ascending=[True, True, False])

# Step 1: Remove duplicate 'start' addresses, keeping the one with highest rss_kb
df = df.drop_duplicates(subset='start', keep='first')

# Step 2: Remove duplicate 'end' addresses, again keeping highest rss_kb
df = df.sort_values(by=['end', 'rss_kb'], ascending=[True, False])
df = df.drop_duplicates(subset='end', keep='first')

# Optional: Sort back by epoch and rno or address for readability
df = df.sort_values(by=['start', 'end'])

# Convert start and end back to hex
df['start'] = df['start'].apply(lambda x: hex(x))
df['end'] = df['end'].apply(lambda x: hex(x))

# Write to a new CSV
df.to_csv("smap_deduplicated.csv", index=False)
