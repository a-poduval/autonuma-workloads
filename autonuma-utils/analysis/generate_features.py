import sys
import csv
import math
from collections import defaultdict

def process_pebs_log(log_path, fast_memory_val, output_csv):
    # Dictionary to hold page-level statistics
    # Structure: page_id -> stats_dict
    pages = defaultdict(lambda: {
        'access_count': 0,
        'remote_count': 0,
        'ip_counts': defaultdict(int),
        'last_timestamp': None,
        
        # Welford's algorithm state for inter-arrival time deltas
        'delta_count': 0,
        'mean_delta': 0.0,
        'm2_delta': 0.0  # Sum of squared differences from the mean
    })

    print(f"Parsing PEBS log: {log_path}...")
    
    # Pass 1: Parse the log in O(N) time and O(1) memory per event
    with open(log_path, 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            
            try:
                # Parse log components
                timestamp = float(parts[0].strip(':'))
                event_type = parts[1].strip(':')
                
                # Shift address by 12 bits to get the 4KB Page Frame Number
                page = int(parts[2], 16) >> 12 
                symbol = parts[4] if len(parts) > 4 else parts[3]
                
                # Update basic stats
                p_data = pages[page]
                p_data['access_count'] += 1
                p_data['ip_counts'][symbol] += 1
                
                if 'remote' in event_type:
                    p_data['remote_count'] += 1

                # Update inter-arrival time (Burstiness tracking)
                if p_data['last_timestamp'] is not None:
                    delta = timestamp - p_data['last_timestamp']
                    p_data['delta_count'] += 1
                    
                    # Welford's algorithm for streaming variance
                    prev_mean = p_data['mean_delta']
                    p_data['mean_delta'] += (delta - prev_mean) / p_data['delta_count']
                    p_data['m2_delta'] += (delta - prev_mean) * (delta - p_data['mean_delta'])
                
                p_data['last_timestamp'] = timestamp

            except ValueError:
                # Skip malformed lines
                continue

    print(f"Extracted {len(pages)} unique pages. Calculating derived features...")

    # Pass 2: Calculate derived metrics and output to CSV in O(P) time
    with open(output_csv, 'w', newline='') as csvfile:
        fieldnames = [
            'Page_ID_Hex', 'Access_Count', 'Remote_Ratio', 
            'Unique_IPs', 'Dominant_Symbol', 
            'Avg_Time_Delta', 'Burstiness_CV', 
            'Spatial_Density_Score', 'Available_Fast_Memory'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for page, data in pages.items():
            # 1. Target Variable: Ratio of accesses that fell to the slow tier
            remote_ratio = data['remote_count'] / data['access_count']

            # 2. IP / Prefetcher Behavior
            unique_ips = len(data['ip_counts'])
            dominant_symbol = max(data['ip_counts'], key=data['ip_counts'].get)

            # 3. Burstiness / Temporal Locality
            avg_time_delta = data['mean_delta']
            burstiness_cv = 0.0
            
            if data['delta_count'] > 1 and avg_time_delta > 0:
                variance = data['m2_delta'] / data['delta_count']
                std_dev = math.sqrt(variance)
                # CV = StdDev / Mean. Higher CV = More bursty
                burstiness_cv = std_dev / avg_time_delta

            # 4. Spatial Locality: Check if neighboring pages were also accessed
            neighbors_present = sum([
                1 if (page - 1) in pages else 0,
                1 if (page + 1) in pages else 0
            ])
            spatial_density = neighbors_present / 2.0  # 0.0, 0.5, or 1.0

            writer.writerow({
                'Page_ID_Hex': hex(page),
                'Access_Count': data['access_count'],
                'Remote_Ratio': round(remote_ratio, 4),
                'Unique_IPs': unique_ips,
                'Dominant_Symbol': dominant_symbol,
                'Avg_Time_Delta': round(avg_time_delta, 6),
                'Burstiness_CV': round(burstiness_cv, 4),
                'Spatial_Density_Score': spatial_density,
                'Available_Fast_Memory': fast_memory_val
            })

    print(f"Success! Features written to {output_csv}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python generate_features.py <pebs_log_file> <available_fast_memory_GB> <output_csv_file>")
        sys.exit(1)
        
    log_file = sys.argv[1]
    fast_mem = sys.argv[2]
    out_file = sys.argv[3]
    
    process_pebs_log(log_file, fast_mem, out_file)
