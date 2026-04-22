#include "summary_stats.h"

#include <stdio.h>
#include <string.h>

#define PAGE_SIZE_BYTES 4096ULL

static void update_running_mean(double *mean, uint64_t sample_count, double sample)
{
    if (sample_count == 1) {
        *mean = sample;
        return;
    }

    *mean += (sample - *mean) / (double)sample_count;
}

static uint64_t positive_kb_to_pages(int64_t kb)
{
    if (kb <= 0) {
        return 0;
    }
    return (uint64_t)kb / 4ULL;
}

void summary_stats_init(summary_stats_t *stats)
{
    if (stats == NULL) {
        return;
    }
    memset(stats, 0, sizeof(*stats));
}

void summary_stats_set_memory_inputs(summary_stats_t *stats, uint64_t fast_tier_bytes, uint64_t workload_rss_bytes)
{
    if (stats == NULL) {
        return;
    }

    stats->fast_tier_bytes = fast_tier_bytes;
    stats->workload_rss_bytes = workload_rss_bytes;

    // Fast tier capacity is a strict page-budget threshold for prediction.
    stats->fast_tier_pages = fast_tier_bytes / PAGE_SIZE_BYTES;

    // RSS coverage should include partial pages.
    stats->workload_rss_pages = (workload_rss_bytes + (PAGE_SIZE_BYTES - 1ULL)) / PAGE_SIZE_BYTES;
}

void summary_stats_record_line(summary_stats_t *stats, parse_status_t status, const trace_event_t *event)
{
    if (stats == NULL) {
        return;
    }

    stats->total_lines++;

    switch (status) {
    case PARSE_STATUS_OK:
        stats->parsed_events++;
        stats->global_access_counter++;
        if (event != NULL && event->has_timestamp) {
            stats->timestamped_events++;
        }

        if (event != NULL) {
            if (event->access_class == ACCESS_CLASS_LOCAL) {
                stats->local_events++;
            } else if (event->access_class == ACCESS_CLASS_REMOTE) {
                stats->remote_events++;
            }
        }
        break;

    case PARSE_STATUS_MALFORMED:
        stats->malformed_lines++;
        break;

    case PARSE_STATUS_IGNORED:
    default:
        stats->ignored_lines++;
        break;
    }
}

void summary_stats_record_page_insert(summary_stats_t *stats)
{
    if (stats == NULL) {
        return;
    }
    stats->new_page_inserts++;
}

void summary_stats_record_prediction(summary_stats_t *stats, bool predicted_remote, access_class_t actual_class)
{
    if (stats == NULL) {
        return;
    }

    if (predicted_remote) {
        stats->observed_predicted_remote_accesses++;
        if (actual_class == ACCESS_CLASS_LOCAL) {
            stats->observed_predicted_remote_actual_local++;
        }
    } else {
        stats->observed_predicted_local_accesses++;
        if (actual_class == ACCESS_CLASS_REMOTE) {
            stats->observed_predicted_local_actual_remote++;
        }
    }
}

void summary_stats_increment_unique_actual(summary_stats_t *stats)
{
    if (stats == NULL) {
        return;
    }
    stats->unique_counter_actual++;
}

void summary_stats_increment_unique_predicted(summary_stats_t *stats)
{
    if (stats == NULL) {
        return;
    }
    stats->unique_counter_predicted++;
}

void summary_stats_record_reuse_sample(summary_stats_t *stats,
                                       uint64_t reuse_distance_global,
                                       uint64_t reuse_distance_unique_actual,
                                       uint64_t reuse_distance_unique_predicted)
{
    if (stats == NULL) {
        return;
    }

    stats->reuse_samples++;
    update_running_mean(&stats->mean_reuse_distance_global,
                        stats->reuse_samples,
                        (double)reuse_distance_global);
    update_running_mean(&stats->mean_reuse_distance_unique_actual,
                        stats->reuse_samples,
                        (double)reuse_distance_unique_actual);
    update_running_mean(&stats->mean_reuse_distance_unique_predicted,
                        stats->reuse_samples,
                        (double)reuse_distance_unique_predicted);
}

void summary_stats_record_time_delta(summary_stats_t *stats, double time_delta)
{
    if (stats == NULL) {
        return;
    }

    stats->time_delta_samples++;
    update_running_mean(&stats->mean_time_delta, stats->time_delta_samples, time_delta);
}

void summary_stats_set_unique_pages(summary_stats_t *stats, uint64_t unique_pages)
{
    if (stats == NULL) {
        return;
    }
    stats->unique_pages_tracked = unique_pages;
}

void summary_stats_finalize_numa_coverage(summary_stats_t *stats)
{
    if (stats == NULL || !stats->numa_log_used) {
        return;
    }

    int64_t total_growth_before_kb = stats->fast_used_growth_before_steady_kb +
                                     stats->slow_used_growth_before_steady_kb;
    int64_t total_growth_after_kb = stats->fast_used_growth_after_steady_kb +
                                    stats->slow_used_growth_after_steady_kb;

    uint64_t total_growth_before_pages = positive_kb_to_pages(total_growth_before_kb);
    uint64_t total_growth_after_pages = positive_kb_to_pages(total_growth_after_kb);

    if (total_growth_before_pages > 0) {
        stats->has_coverage_before_steady = true;
        stats->pebs_new_page_coverage_before_steady =
            (double)stats->pebs_new_pages_before_steady / (double)total_growth_before_pages;
    }

    if (total_growth_after_pages > 0) {
        stats->has_coverage_after_steady = true;
        stats->pebs_new_page_coverage_after_steady =
            (double)stats->pebs_new_pages_after_steady / (double)total_growth_after_pages;
    }
}

void summary_stats_finalize_extrapolation(summary_stats_t *stats)
{
    if (stats == NULL) {
        return;
    }

    stats->observed_pages_exceed_rss = (stats->unique_pages_tracked > stats->workload_rss_pages);
    if (stats->observed_pages_exceed_rss) {
        stats->unobserved_pages = 0;
    } else {
        stats->unobserved_pages = stats->workload_rss_pages - stats->unique_pages_tracked;
    }

    // User-approved policy: treat unobserved pages as cold pages that still
    // get one synthetic first-touch local access before eventual demotion.
    stats->synthetic_first_touch_local_accesses = stats->unobserved_pages;

    stats->extrapolated_predicted_local_accesses =
        stats->observed_predicted_local_accesses + stats->synthetic_first_touch_local_accesses;
    stats->extrapolated_predicted_remote_accesses = stats->observed_predicted_remote_accesses;

    stats->extrapolated_actual_local_accesses =
        stats->local_events + stats->synthetic_first_touch_local_accesses;
    stats->extrapolated_actual_remote_accesses = stats->remote_events;

    stats->extrapolated_predicted_local_actual_remote = stats->observed_predicted_local_actual_remote;
    stats->extrapolated_predicted_remote_actual_local = stats->observed_predicted_remote_actual_local;
}

void summary_stats_print(const summary_stats_t *stats, const char *input_path)
{
    if (stats == NULL) {
        return;
    }

    printf("Input file: %s\n", input_path != NULL ? input_path : "(null)");
    printf("Fast tier size (bytes): %llu\n", (unsigned long long)stats->fast_tier_bytes);
    printf("Fast tier size (pages): %llu\n", (unsigned long long)stats->fast_tier_pages);
    printf("Workload RSS (bytes): %llu\n", (unsigned long long)stats->workload_rss_bytes);
    printf("Workload RSS (pages): %llu\n", (unsigned long long)stats->workload_rss_pages);

    if (stats->numa_log_used) {
        printf("\n--- NUMA Log Integration ---\n");
        printf("Fast node index: %d\n", stats->fast_node_index);
        printf("Slow node index: %d\n", stats->slow_node_index);

        if (stats->has_numa_timestamp_span) {
            printf("NUMA timestamp start: %.6f\n", stats->numa_first_timestamp);
            printf("NUMA timestamp end: %.6f\n", stats->numa_last_timestamp);
            printf("NUMA timestamp span (s): %.6f\n", stats->numa_last_timestamp - stats->numa_first_timestamp);
            printf("NUMA steady timestamp: %.6f\n", stats->numa_steady_timestamp);
        }

        if (stats->has_pebs_timestamp_span) {
            printf("PEBS timestamp start: %.6f\n", stats->pebs_first_timestamp);
            printf("PEBS timestamp end: %.6f\n", stats->pebs_last_timestamp);
            printf("PEBS timestamp span (s): %.6f\n", stats->pebs_last_timestamp - stats->pebs_first_timestamp);
        }

        if (stats->has_aligned_pebs_steady_timestamp) {
            printf("Aligned PEBS steady timestamp: %.6f\n", stats->aligned_pebs_steady_timestamp);
        }

        printf("Fast used growth before steady (KB): %lld\n", (long long)stats->fast_used_growth_before_steady_kb);
        printf("Fast used growth after steady (KB): %lld\n", (long long)stats->fast_used_growth_after_steady_kb);
        printf("Slow used growth before steady (KB): %lld\n", (long long)stats->slow_used_growth_before_steady_kb);
        printf("Slow used growth after steady (KB): %lld\n", (long long)stats->slow_used_growth_after_steady_kb);
        printf("PEBS events before steady: %llu\n", (unsigned long long)stats->pebs_events_before_steady);
        printf("PEBS events after steady: %llu\n", (unsigned long long)stats->pebs_events_after_steady);
        printf("PEBS new pages before steady: %llu\n", (unsigned long long)stats->pebs_new_pages_before_steady);
        printf("PEBS new pages after steady: %llu\n", (unsigned long long)stats->pebs_new_pages_after_steady);

        if (stats->has_coverage_before_steady) {
            printf("PEBS new-page coverage before steady: %.6f\n", stats->pebs_new_page_coverage_before_steady);
        }
        if (stats->has_coverage_after_steady) {
            printf("PEBS new-page coverage after steady: %.6f\n", stats->pebs_new_page_coverage_after_steady);
        }
    }

    printf("\n--- Parser / Ingestion ---\n");
    printf("Total lines read: %llu\n", (unsigned long long)stats->total_lines);
    printf("Parsed access events: %llu\n", (unsigned long long)stats->parsed_events);
    printf("Ignored lines: %llu\n", (unsigned long long)stats->ignored_lines);
    printf("Malformed lines: %llu\n", (unsigned long long)stats->malformed_lines);
    printf("Events with timestamp: %llu\n", (unsigned long long)stats->timestamped_events);

    printf("\n--- Observed PEBS Domain (Access-Level) ---\n");
    printf("Actual local accesses: %llu\n", (unsigned long long)stats->local_events);
    printf("Actual remote accesses: %llu\n", (unsigned long long)stats->remote_events);
    printf("Predicted local accesses: %llu\n", (unsigned long long)stats->observed_predicted_local_accesses);
    printf("Predicted remote accesses: %llu\n", (unsigned long long)stats->observed_predicted_remote_accesses);
    printf("Predicted local but actual remote: %llu\n",
           (unsigned long long)stats->observed_predicted_local_actual_remote);
    printf("Predicted remote but actual local: %llu\n",
           (unsigned long long)stats->observed_predicted_remote_actual_local);
    printf("Unique pages tracked: %llu\n", (unsigned long long)stats->unique_pages_tracked);
    printf("Global access counter: %llu\n", (unsigned long long)stats->global_access_counter);
    printf("New PFNs inserted: %llu\n", (unsigned long long)stats->new_page_inserts);
    printf("Unique counter (actual labels): %llu\n", (unsigned long long)stats->unique_counter_actual);
    printf("Unique counter (predicted path): %llu\n", (unsigned long long)stats->unique_counter_predicted);

    printf("\n--- Phase 3 Diagnostics ---\n");
    printf("Reuse-distance samples: %llu\n", (unsigned long long)stats->reuse_samples);
    if (stats->reuse_samples > 0) {
        printf("Mean reuse distance (global): %.4f\n", stats->mean_reuse_distance_global);
        printf("Mean reuse distance (unique actual): %.4f\n", stats->mean_reuse_distance_unique_actual);
        printf("Mean reuse distance (unique predicted): %.4f\n", stats->mean_reuse_distance_unique_predicted);
    }
    printf("Time-delta samples: %llu\n", (unsigned long long)stats->time_delta_samples);
    if (stats->time_delta_samples > 0) {
        printf("Mean time delta: %.9f\n", stats->mean_time_delta);
    }

    if (stats->promotion_enabled) {
        printf("Promotion count (remote->local): %llu\n", (unsigned long long)stats->promotion_count);
        if (stats->has_running_median_reuse_unique_predicted) {
            printf("Running median reuse distance (unique predicted): %.4f\n",
                   stats->running_median_reuse_unique_predicted);
        }
    }

    printf("\n--- RSS Extrapolated Domain (Policy-Level) ---\n");
    printf("Observed PEBS pages: %llu\n", (unsigned long long)stats->unique_pages_tracked);
    printf("Unobserved RSS pages: %llu\n", (unsigned long long)stats->unobserved_pages);
    if (stats->observed_pages_exceed_rss) {
        printf("Warning: observed PEBS pages exceed input RSS pages; unobserved pages clamped to 0\n");
    }
    printf("Synthetic first-touch local accesses: %llu\n",
           (unsigned long long)stats->synthetic_first_touch_local_accesses);
    printf("Extrapolated predicted local accesses: %llu\n",
           (unsigned long long)stats->extrapolated_predicted_local_accesses);
    printf("Extrapolated predicted remote accesses: %llu\n",
           (unsigned long long)stats->extrapolated_predicted_remote_accesses);
    printf("Extrapolated actual local accesses: %llu\n",
           (unsigned long long)stats->extrapolated_actual_local_accesses);
    printf("Extrapolated actual remote accesses: %llu\n",
           (unsigned long long)stats->extrapolated_actual_remote_accesses);
    printf("Extrapolated predicted local but actual remote: %llu\n",
           (unsigned long long)stats->extrapolated_predicted_local_actual_remote);
    printf("Extrapolated predicted remote but actual local: %llu\n",
           (unsigned long long)stats->extrapolated_predicted_remote_actual_local);
    printf("Note: unobserved pages are modeled as cold pages with one first-touch local access; "
           "eventual demotion is represented at policy level without synthetic remote access counts.\n");

    if (stats->total_lines > 0) {
        double parse_rate = (100.0 * (double)stats->parsed_events) / (double)stats->total_lines;
        printf("Parse success rate: %.4f%%\n", parse_rate);
    }
}
