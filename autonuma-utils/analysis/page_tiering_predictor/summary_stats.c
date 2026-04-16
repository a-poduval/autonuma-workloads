#include "summary_stats.h"

#include <stdio.h>
#include <string.h>

static void update_running_mean(double *mean, uint64_t sample_count, double sample)
{
    if (sample_count == 1) {
        *mean = sample;
        return;
    }

    *mean += (sample - *mean) / (double)sample_count;
}

void summary_stats_init(summary_stats_t *stats)
{
    if (stats == NULL) {
        return;
    }
    memset(stats, 0, sizeof(*stats));
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

void summary_stats_print(const summary_stats_t *stats, const char *input_path)
{
    if (stats == NULL) {
        return;
    }

    printf("Input file: %s\n", input_path != NULL ? input_path : "(null)");
    printf("Total lines read: %llu\n", (unsigned long long)stats->total_lines);
    printf("Parsed access events: %llu\n", (unsigned long long)stats->parsed_events);
    printf("Global access counter: %llu\n", (unsigned long long)stats->global_access_counter);
    printf("Unique counter (actual labels): %llu\n", (unsigned long long)stats->unique_counter_actual);
    printf("Unique counter (predicted placeholder): %llu\n", (unsigned long long)stats->unique_counter_predicted);
    printf("Local accesses: %llu\n", (unsigned long long)stats->local_events);
    printf("Remote accesses: %llu\n", (unsigned long long)stats->remote_events);
    printf("New PFNs inserted: %llu\n", (unsigned long long)stats->new_page_inserts);
    printf("Unique pages tracked: %llu\n", (unsigned long long)stats->unique_pages_tracked);
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
    printf("Ignored lines: %llu\n", (unsigned long long)stats->ignored_lines);
    printf("Malformed lines: %llu\n", (unsigned long long)stats->malformed_lines);
    printf("Events with timestamp: %llu\n", (unsigned long long)stats->timestamped_events);

    if (stats->total_lines > 0) {
        double parse_rate = (100.0 * (double)stats->parsed_events) / (double)stats->total_lines;
        printf("Parse success rate: %.4f%%\n", parse_rate);
    }
}
