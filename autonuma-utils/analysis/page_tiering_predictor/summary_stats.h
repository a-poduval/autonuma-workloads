#ifndef SUMMARY_STATS_H
#define SUMMARY_STATS_H

#include <stdint.h>

#include "trace_parser.h"

typedef struct {
    uint64_t total_lines;
    uint64_t parsed_events;
    uint64_t global_access_counter;
    uint64_t unique_counter_actual;
    uint64_t unique_counter_predicted;
    uint64_t local_events;
    uint64_t remote_events;
    uint64_t ignored_lines;
    uint64_t malformed_lines;
    uint64_t timestamped_events;
    uint64_t new_page_inserts;
    uint64_t unique_pages_tracked;
    uint64_t reuse_samples;
    double mean_reuse_distance_global;
    double mean_reuse_distance_unique_actual;
    double mean_reuse_distance_unique_predicted;
    uint64_t time_delta_samples;
    double mean_time_delta;
} summary_stats_t;

void summary_stats_init(summary_stats_t *stats);
void summary_stats_record_line(summary_stats_t *stats, parse_status_t status, const trace_event_t *event);
void summary_stats_record_page_insert(summary_stats_t *stats);
void summary_stats_increment_unique_actual(summary_stats_t *stats);
void summary_stats_increment_unique_predicted(summary_stats_t *stats);
void summary_stats_record_reuse_sample(summary_stats_t *stats,
                                       uint64_t reuse_distance_global,
                                       uint64_t reuse_distance_unique_actual,
                                       uint64_t reuse_distance_unique_predicted);
void summary_stats_record_time_delta(summary_stats_t *stats, double time_delta);
void summary_stats_set_unique_pages(summary_stats_t *stats, uint64_t unique_pages);
void summary_stats_print(const summary_stats_t *stats, const char *input_path);

#endif
