#ifndef PAGE_TABLE_H
#define PAGE_TABLE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "trace_parser.h"

typedef struct {
    uint64_t pfn;
    uint64_t access_count;
    uint64_t last_global_access_counter;
    uint64_t last_unique_actual_counter;
    uint64_t last_unique_predicted_counter;
    uint64_t reuse_samples;
    double mean_reuse_distance_global;
    double mean_reuse_distance_unique_actual;
    double mean_reuse_distance_unique_predicted;
    uint64_t time_delta_samples;
    double mean_time_delta;
    double last_timestamp;
    bool has_last_timestamp;
    bool has_predicted_state;
    bool predicted_remote_state;
} page_state_t;

typedef struct {
    bool has_reuse;
    uint64_t reuse_distance_global;
    uint64_t reuse_distance_unique_actual;
    uint64_t reuse_distance_unique_predicted;
    bool has_time_delta;
    double time_delta;
} access_observation_t;

typedef struct {
    uint64_t key_pfn;
    page_state_t state;
    bool occupied;
} page_table_entry_t;

typedef struct {
    page_table_entry_t *entries;
    size_t capacity;
    size_t size;
} page_table_t;

int page_table_init(page_table_t *table, size_t initial_capacity);
void page_table_destroy(page_table_t *table);

page_state_t *page_table_get_or_insert(page_table_t *table, uint64_t pfn, bool *was_inserted);
size_t page_table_size(const page_table_t *table);

void page_state_record_access(page_state_t *state,
                              const trace_event_t *event,
                              uint64_t global_access_counter,
                              uint64_t unique_counter_actual,
                              uint64_t unique_counter_predicted,
                              access_observation_t *observation);

#endif
