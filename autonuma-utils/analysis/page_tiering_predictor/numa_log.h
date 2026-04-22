#ifndef NUMA_LOG_H
#define NUMA_LOG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    bool available;
    int fast_node;
    int slow_node;

    size_t sample_count;
    double first_timestamp;
    double last_timestamp;
    double steady_timestamp;

    uint64_t initial_fast_free_kb;
    uint64_t min_fast_free_kb;

    uint64_t initial_fast_used_kb;
    uint64_t steady_fast_used_kb;
    uint64_t final_fast_used_kb;

    uint64_t initial_slow_used_kb;
    uint64_t steady_slow_used_kb;
    uint64_t final_slow_used_kb;
} numa_log_summary_t;

int numa_log_load_summary(const char *path,
                          int fast_node,
                          int slow_node,
                          numa_log_summary_t *out,
                          char *error_buf,
                          size_t error_buf_len);

#endif
