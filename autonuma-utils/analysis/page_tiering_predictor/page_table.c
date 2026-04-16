#include "page_table.h"

#include <stdlib.h>
#include <string.h>

#define PAGE_TABLE_MIN_CAPACITY 1024U
#define PAGE_TABLE_LOAD_NUMERATOR 7U
#define PAGE_TABLE_LOAD_DENOMINATOR 10U

static uint64_t hash_u64(uint64_t x)
{
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

static void update_running_mean(double *mean, uint64_t sample_count, double sample)
{
    if (sample_count == 1) {
        *mean = sample;
        return;
    }

    *mean += (sample - *mean) / (double)sample_count;
}

static size_t next_power_of_two(size_t x)
{
    if (x <= 2) {
        return 2;
    }

    x--;
    for (size_t shift = 1; shift < sizeof(size_t) * 8; shift <<= 1) {
        x |= (x >> shift);
    }
    return x + 1;
}

static bool should_grow(const page_table_t *table, size_t prospective_size)
{
    return prospective_size * PAGE_TABLE_LOAD_DENOMINATOR >= table->capacity * PAGE_TABLE_LOAD_NUMERATOR;
}

static page_table_entry_t *find_slot(page_table_entry_t *entries, size_t capacity, uint64_t pfn, bool *found)
{
    size_t mask = capacity - 1;
    size_t idx = (size_t)(hash_u64(pfn) & (uint64_t)mask);

    for (;;) {
        page_table_entry_t *entry = &entries[idx];
        if (!entry->occupied) {
            *found = false;
            return entry;
        }
        if (entry->key_pfn == pfn) {
            *found = true;
            return entry;
        }
        idx = (idx + 1) & mask;
    }
}

static int page_table_rehash(page_table_t *table, size_t new_capacity)
{
    page_table_entry_t *new_entries = (page_table_entry_t *)calloc(new_capacity, sizeof(*new_entries));
    if (new_entries == NULL) {
        return -1;
    }

    for (size_t i = 0; i < table->capacity; ++i) {
        page_table_entry_t *old = &table->entries[i];
        if (!old->occupied) {
            continue;
        }

        bool found = false;
        page_table_entry_t *dest = find_slot(new_entries, new_capacity, old->key_pfn, &found);
        (void)found;
        *dest = *old;
    }

    free(table->entries);
    table->entries = new_entries;
    table->capacity = new_capacity;
    return 0;
}

int page_table_init(page_table_t *table, size_t initial_capacity)
{
    if (table == NULL) {
        return -1;
    }

    memset(table, 0, sizeof(*table));

    size_t capacity = initial_capacity;
    if (capacity < PAGE_TABLE_MIN_CAPACITY) {
        capacity = PAGE_TABLE_MIN_CAPACITY;
    }
    capacity = next_power_of_two(capacity);

    table->entries = (page_table_entry_t *)calloc(capacity, sizeof(*table->entries));
    if (table->entries == NULL) {
        return -1;
    }

    table->capacity = capacity;
    table->size = 0;
    return 0;
}

void page_table_destroy(page_table_t *table)
{
    if (table == NULL) {
        return;
    }

    free(table->entries);
    table->entries = NULL;
    table->capacity = 0;
    table->size = 0;
}

page_state_t *page_table_get_or_insert(page_table_t *table, uint64_t pfn, bool *was_inserted)
{
    if (table == NULL || table->entries == NULL || table->capacity == 0) {
        return NULL;
    }

    bool found = false;
    page_table_entry_t *entry = find_slot(table->entries, table->capacity, pfn, &found);
    if (found) {
        if (was_inserted != NULL) {
            *was_inserted = false;
        }
        return &entry->state;
    }

    if (should_grow(table, table->size + 1)) {
        if (page_table_rehash(table, table->capacity * 2) != 0) {
            return NULL;
        }
        entry = find_slot(table->entries, table->capacity, pfn, &found);
        if (found) {
            if (was_inserted != NULL) {
                *was_inserted = false;
            }
            return &entry->state;
        }
    }

    entry->occupied = true;
    entry->key_pfn = pfn;
    memset(&entry->state, 0, sizeof(entry->state));
    entry->state.pfn = pfn;
    table->size++;

    if (was_inserted != NULL) {
        *was_inserted = true;
    }
    return &entry->state;
}

size_t page_table_size(const page_table_t *table)
{
    if (table == NULL) {
        return 0;
    }
    return table->size;
}

void page_state_record_access(page_state_t *state,
                              const trace_event_t *event,
                              uint64_t global_access_counter,
                              uint64_t unique_counter_actual,
                              uint64_t unique_counter_predicted,
                              access_observation_t *observation)
{
    if (state == NULL || event == NULL) {
        return;
    }

    if (observation != NULL) {
        memset(observation, 0, sizeof(*observation));
    }

    if (state->access_count > 0) {
        uint64_t reuse_distance_global = global_access_counter - state->last_global_access_counter;
        uint64_t reuse_distance_unique_actual = unique_counter_actual - state->last_unique_actual_counter;
        uint64_t reuse_distance_unique_predicted = unique_counter_predicted - state->last_unique_predicted_counter;

        state->reuse_samples++;
        update_running_mean(&state->mean_reuse_distance_global,
                            state->reuse_samples,
                            (double)reuse_distance_global);
        update_running_mean(&state->mean_reuse_distance_unique_actual,
                            state->reuse_samples,
                            (double)reuse_distance_unique_actual);
        update_running_mean(&state->mean_reuse_distance_unique_predicted,
                            state->reuse_samples,
                            (double)reuse_distance_unique_predicted);

        if (observation != NULL) {
            observation->has_reuse = true;
            observation->reuse_distance_global = reuse_distance_global;
            observation->reuse_distance_unique_actual = reuse_distance_unique_actual;
            observation->reuse_distance_unique_predicted = reuse_distance_unique_predicted;
        }
    }

    if (state->has_last_timestamp && event->has_timestamp) {
        double delta = event->timestamp - state->last_timestamp;
        state->time_delta_samples++;
        update_running_mean(&state->mean_time_delta, state->time_delta_samples, delta);

        if (observation != NULL) {
            observation->has_time_delta = true;
            observation->time_delta = delta;
        }
    }

    state->access_count++;
    state->last_global_access_counter = global_access_counter;
    state->last_unique_actual_counter = unique_counter_actual;
    state->last_unique_predicted_counter = unique_counter_predicted;

    if (event->has_timestamp) {
        state->last_timestamp = event->timestamp;
        state->has_last_timestamp = true;
    }
}
