#ifndef SUMMARY_STATS_H
#define SUMMARY_STATS_H

#include <stdbool.h>
#include <stdint.h>

#include "trace_parser.h"

typedef struct {
    uint64_t fast_tier_bytes;
    uint64_t fast_tier_pages;
    uint64_t workload_rss_bytes;
    uint64_t workload_rss_pages;

    bool numa_log_used;
    int fast_node_index;
    int slow_node_index;

    bool has_pebs_timestamp_span;
    double pebs_first_timestamp;
    double pebs_last_timestamp;

    bool has_numa_timestamp_span;
    double numa_first_timestamp;
    double numa_last_timestamp;
    double numa_steady_timestamp;

    bool has_aligned_pebs_steady_timestamp;
    double aligned_pebs_steady_timestamp;

    uint64_t pebs_events_before_steady;
    uint64_t pebs_events_after_steady;
    uint64_t pebs_new_pages_before_steady;
    uint64_t pebs_new_pages_after_steady;

    int64_t fast_used_growth_before_steady_kb;
    int64_t fast_used_growth_after_steady_kb;
    int64_t slow_used_growth_before_steady_kb;
    int64_t slow_used_growth_after_steady_kb;

    bool has_coverage_before_steady;
    bool has_coverage_after_steady;
    double pebs_new_page_coverage_before_steady;
    double pebs_new_page_coverage_after_steady;

    bool promotion_enabled;
    uint64_t promotion_count;
    bool has_running_median_reuse_unique_predicted;
    double running_median_reuse_unique_predicted;

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

    uint64_t observed_predicted_local_accesses;
    uint64_t observed_predicted_remote_accesses;
    uint64_t observed_predicted_local_actual_remote;
    uint64_t observed_predicted_remote_actual_local;

    uint64_t unobserved_pages;
    bool observed_pages_exceed_rss;
    uint64_t synthetic_first_touch_local_accesses;

    uint64_t extrapolated_predicted_local_accesses;
    uint64_t extrapolated_predicted_remote_accesses;
    uint64_t extrapolated_actual_local_accesses;
    uint64_t extrapolated_actual_remote_accesses;
    uint64_t extrapolated_predicted_local_actual_remote;
    uint64_t extrapolated_predicted_remote_actual_local;

    uint64_t reuse_samples;
    double mean_reuse_distance_global;
    double mean_reuse_distance_unique_actual;
    double mean_reuse_distance_unique_predicted;
    uint64_t time_delta_samples;
    double mean_time_delta;
} summary_stats_t;

void summary_stats_init(summary_stats_t *stats);
void summary_stats_set_memory_inputs(summary_stats_t *stats, uint64_t fast_tier_bytes, uint64_t workload_rss_bytes);
void summary_stats_record_line(summary_stats_t *stats, parse_status_t status, const trace_event_t *event);
void summary_stats_record_page_insert(summary_stats_t *stats);
void summary_stats_record_prediction(summary_stats_t *stats, bool predicted_remote, access_class_t actual_class);
void summary_stats_increment_unique_actual(summary_stats_t *stats);
void summary_stats_increment_unique_predicted(summary_stats_t *stats);
void summary_stats_record_reuse_sample(summary_stats_t *stats,
                                       uint64_t reuse_distance_global,
                                       uint64_t reuse_distance_unique_actual,
                                       uint64_t reuse_distance_unique_predicted);
void summary_stats_record_time_delta(summary_stats_t *stats, double time_delta);
void summary_stats_set_unique_pages(summary_stats_t *stats, uint64_t unique_pages);
void summary_stats_finalize_numa_coverage(summary_stats_t *stats);
void summary_stats_finalize_extrapolation(summary_stats_t *stats);
void summary_stats_print(const summary_stats_t *stats, const char *input_path);

#endif
