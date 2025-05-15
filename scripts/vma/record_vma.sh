#!/bin/bash

interval=2
output_file="memory_regions.csv"

    #smaps_file ~ /^[0-9a-f]/ {
record_memory_regions() {
    local pid=$1
    local epoch=$2

    awk -v epoch="$epoch" -v pid="$pid" '
    BEGIN {
        rno = 0;
        smaps_file = "/proc/" pid "/smaps";
    }
    $1 ~ /^[0-9a-f]/ {
        if (start) {
            if (perm !~ /---p/ && rss_kb != 0) {
                printf("%s,%d,%s,%s,%s,%s,%d,%d,%d,%d,%d\n", epoch, rno++, start, end, inode, pathname, size, rss_kb, pss_kb, pss_dirty, referenced)
            }
        }

        split($1, addrs, "-")
        start = addrs[1]
        end = addrs[2]
        perm = $2
        inode = $5
        rss_kb = 0
        size = 0
        pss_kb = 0
        pss_dirty = 0
        referenced = 0

        pathname = ""
        for (i = 6; i <= NF; i++) {
            pathname = pathname (i == 6 ? "" : " ") $i
        }
    }
    /^Size:/ {
        size = $2
    }
    /^Rss:/ {
        rss_kb = $2
    }
    /^Pss:/ {
        pss_kb = $2
    }
    /^Pss_Dirty:/ {
        pss_dirty = $2
    }
    /^Referenced:/ {
        referenced = $2
    }
    END {
        if (start && perm !~ /---p/ && rss_kb != 0) {
            printf("%s,%d,%s,%s,%s,%s,%d,%d,%d,%d,%d\n", epoch, rno++, start, end, inode, pathname, size, rss_kb, pss_kb, pss_dirty, referenced)
        }
    }
    ' "/proc/$pid/smaps"
}

main() {
    if [ $# -lt 1 ]; then
        echo "Usage: $0 <program> [args...]"
        exit 1
    fi

    echo "epoch,rno,start,end,inode,pathname,size,rss_kb,pss_kb,pss_dirty,referenced" > "$output_file"

    # Start target program in background
    "$@" &
    target_pid=$!

    #echo "Monitoring PID $target_pid"

    # Wait a moment to make sure the process starts
    sleep 0.1

    epoch=0
    while kill -0 "$target_pid" 2>/dev/null; do
        #epoch=$(date +%s)
        if [ -r "/proc/$target_pid/smaps" ]; then
            record_memory_regions "$target_pid" "$epoch" >> "$output_file"
        fi
	((epoch+=1))
        sleep "$interval"
    done

    #echo "Process $target_pid exited."
}

main "$@"
