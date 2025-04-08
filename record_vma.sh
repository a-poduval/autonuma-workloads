#!/bin/bash

# Default parameters
WORKLOAD_PATH="$1"
shift
ARGS="$@"
INTERVAL=5 # Default interval in seconds
CSV_FILE="memory_regions.csv"

# Ensure workload path is provided
if [ -z "$WORKLOAD_PATH" ]; then
  echo "Usage: $0 <workload_path> <args...>"
  exit 1
fi

# Start the workload in the background
$WORKLOAD_PATH $ARGS &
WORKLOAD_PID=$!

# Wait a bit for the workload to start
sleep 1

# Initialize epoch counter and CSV file
epoch=0
echo "epoch,rno,start,end,inode,pathname" > $CSV_FILE

# Function to check and record memory regions from /proc/PID/maps
record_memory_regions() {
  local pid=$1
  local epoch=$2
  local csv_file=$3

  # Get memory regions from /proc/PID/maps
  if [ -e "/proc/$pid/maps" ]; then
    # Read the memory regions and parse the start, end addresses, and pathname
    awk -v epoch=$epoch '
      BEGIN { rno=0 }
      {
        # Parse the start and end addresses
        split($1, addr, "-");
        start = addr[1];
        end = addr[2];

        # Get the inode (second last field)
        inode = $5;
        if (inode == "") {
          inode = "N/A";  # Handle case with no pathname
        }

        # Get the pathname (last field)
        pathname = $6;
        if (pathname == "") {
          pathname = "N/A";  # Handle case with no pathname
        }

        # Print epoch, region number, start and end addresses, and pathname
        print epoch "," rno "," start "," end "," inode "," pathname;
        rno++;
      }
    ' /proc/$pid/maps >> "$csv_file"
  fi
}

# Monitor the workload's memory regions at periodic intervals
while kill -0 $WORKLOAD_PID 2>/dev/null; do
  # Record memory regions at the current epoch
  record_memory_regions $WORKLOAD_PID $epoch $CSV_FILE

  # Increment epoch
  epoch=$((epoch + 1))

  # Sleep for the defined interval
  sleep $INTERVAL
done

# Final record (in case the workload exits)
record_memory_regions $WORKLOAD_PID $epoch $CSV_FILE

echo "Memory region data recorded to $CSV_FILE"
