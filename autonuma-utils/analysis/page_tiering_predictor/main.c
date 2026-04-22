#define _POSIX_C_SOURCE 200809L

#include <ctype.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "median_estimator.h"
#include "numa_log.h"
#include "page_table.h"
#include "summary_stats.h"
#include "trace_parser.h"

#define PATH_BUF_SIZE 4096

static int parse_nonnegative_int(const char *text, int *out_value)
{
    if (text == NULL || out_value == NULL || text[0] == '\0') {
        return -1;
    }

    errno = 0;
    char *end_ptr = NULL;
    long parsed = strtol(text, &end_ptr, 10);
    if (errno != 0 || end_ptr == text || *end_ptr != '\0' || parsed < 0 || parsed > 1024) {
        return -1;
    }

    *out_value = (int)parsed;
    return 0;
}

static int infer_numa_log_path(const char *trace_path, char *out_path, size_t out_path_len)
{
    const char *suffix = "_script.txt";
    size_t suffix_len = strlen(suffix);
    size_t trace_len = strlen(trace_path);

    if (trace_len <= suffix_len || strcmp(trace_path + trace_len - suffix_len, suffix) != 0) {
        return -1;
    }

    const char *base = strrchr(trace_path, '/');
    size_t dir_len = 0;
    if (base != NULL) {
        dir_len = (size_t)(base - trace_path) + 1;
        base += 1;
    } else {
        base = trace_path;
    }

    size_t base_len = strlen(base);
    size_t stem_len = base_len - suffix_len;

    int written = snprintf(out_path,
                           out_path_len,
                           "%.*s%.*s_numa_meminfo.csv",
                           (int)dir_len,
                           trace_path,
                           (int)stem_len,
                           base);
    if (written < 0 || (size_t)written >= out_path_len) {
        return -1;
    }

    FILE *test = fopen(out_path, "r");
    if (test == NULL) {
        return -1;
    }
    fclose(test);
    return 0;
}

static int64_t diff_u64(uint64_t newer, uint64_t older)
{
    return (int64_t)newer - (int64_t)older;
}

static void print_usage(const char *prog)
{
    fprintf(stderr,
            "Usage: %s <trace_file> --fast-size <size> --rss-size <size> [options]\n"
            "  size examples: 8589934592, 8G, 8GB, 72G\n"
            "Options:\n"
            "  --numa-log <path>     Optional NUMA meminfo CSV path\n"
            "  --fast-node <index>   Fast tier node index for NUMA log (default: 0)\n"
            "  --enable-promotion    Enable remote->local promotion by median reuse\n",
            prog);
}

static int parse_size_bytes(const char *text, uint64_t *out_bytes)
{
    if (text == NULL || out_bytes == NULL || text[0] == '\0') {
        return -1;
    }

    errno = 0;
    char *end_ptr = NULL;
    unsigned long long base_value = strtoull(text, &end_ptr, 10);
    if (errno != 0 || end_ptr == text) {
        return -1;
    }

    uint64_t multiplier = 1;
    if (*end_ptr != '\0') {
        char unit = (char)tolower((unsigned char)end_ptr[0]);
        char next = (char)tolower((unsigned char)end_ptr[1]);

        if (end_ptr[1] == '\0' || (next == 'b' && end_ptr[2] == '\0')) {
            switch (unit) {
            case 'k':
                multiplier = 1024ULL;
                break;
            case 'm':
                multiplier = 1024ULL * 1024ULL;
                break;
            case 'g':
                multiplier = 1024ULL * 1024ULL * 1024ULL;
                break;
            case 't':
                multiplier = 1024ULL * 1024ULL * 1024ULL * 1024ULL;
                break;
            default:
                return -1;
            }
        } else {
            return -1;
        }
    }

    if ((uint64_t)base_value > (UINT64_MAX / multiplier)) {
        return -1;
    }

    *out_bytes = (uint64_t)base_value * multiplier;
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    const char *trace_path = argv[1];
    uint64_t fast_tier_bytes = 0;
    uint64_t workload_rss_bytes = 0;
    bool have_fast_size = false;
    bool have_rss_size = false;
    const char *numa_log_path_arg = NULL;
    int fast_node = 0;
    bool enable_promotion = false;

    for (int i = 2; i < argc; ++i) {
        if ((strcmp(argv[i], "--fast-size") == 0) || (strcmp(argv[i], "-f") == 0)) {
            if ((i + 1) >= argc || parse_size_bytes(argv[i + 1], &fast_tier_bytes) != 0) {
                fprintf(stderr, "Invalid fast-tier size value\n");
                print_usage(argv[0]);
                return 1;
            }
            have_fast_size = true;
            i++;
            continue;
        }

        if ((strcmp(argv[i], "--rss-size") == 0) || (strcmp(argv[i], "-r") == 0)) {
            if ((i + 1) >= argc || parse_size_bytes(argv[i + 1], &workload_rss_bytes) != 0) {
                fprintf(stderr, "Invalid workload RSS size value\n");
                print_usage(argv[0]);
                return 1;
            }
            have_rss_size = true;
            i++;
            continue;
        }

        if ((strcmp(argv[i], "--numa-log") == 0) || (strcmp(argv[i], "-n") == 0)) {
            if ((i + 1) >= argc) {
                fprintf(stderr, "Missing value for --numa-log\n");
                print_usage(argv[0]);
                return 1;
            }
            numa_log_path_arg = argv[i + 1];
            i++;
            continue;
        }

        if ((strcmp(argv[i], "--fast-node") == 0) || (strcmp(argv[i], "-N") == 0)) {
            if ((i + 1) >= argc || parse_nonnegative_int(argv[i + 1], &fast_node) != 0) {
                fprintf(stderr, "Invalid fast-node value\n");
                print_usage(argv[0]);
                return 1;
            }
            i++;
            continue;
        }

        if (strcmp(argv[i], "--enable-promotion") == 0) {
            enable_promotion = true;
            continue;
        }

        fprintf(stderr, "Unknown argument: %s\n", argv[i]);
        print_usage(argv[0]);
        return 1;
    }

    if (!have_fast_size || !have_rss_size || fast_tier_bytes == 0 || workload_rss_bytes == 0) {
        fprintf(stderr, "Both --fast-size and --rss-size are required and must be > 0\n");
        print_usage(argv[0]);
        return 1;
    }

    FILE *fp = fopen(trace_path, "r");
    if (fp == NULL) {
        fprintf(stderr, "Failed to open %s: %s\n", trace_path, strerror(errno));
        return 1;
    }

    summary_stats_t stats;
    summary_stats_init(&stats);
    summary_stats_set_memory_inputs(&stats, fast_tier_bytes, workload_rss_bytes);
    stats.promotion_enabled = enable_promotion;

    int slow_node = (fast_node == 0) ? 1 : 0;

    numa_log_summary_t numa_summary;
    memset(&numa_summary, 0, sizeof(numa_summary));
    bool have_numa_summary = false;

    char resolved_numa_log_path[PATH_BUF_SIZE];
    char infer_buf[PATH_BUF_SIZE];
    if (numa_log_path_arg != NULL) {
        snprintf(resolved_numa_log_path, sizeof(resolved_numa_log_path), "%s", numa_log_path_arg);
    } else if (infer_numa_log_path(trace_path, infer_buf, sizeof(infer_buf)) == 0) {
        snprintf(resolved_numa_log_path, sizeof(resolved_numa_log_path), "%s", infer_buf);
    } else {
        resolved_numa_log_path[0] = '\0';
    }

    if (resolved_numa_log_path[0] != '\0') {
        char numa_error[256];
        if (numa_log_load_summary(resolved_numa_log_path,
                                  fast_node,
                                  slow_node,
                                  &numa_summary,
                                  numa_error,
                                  sizeof(numa_error)) == 0) {
            have_numa_summary = true;
            stats.numa_log_used = true;
            stats.fast_node_index = fast_node;
            stats.slow_node_index = slow_node;
            stats.has_numa_timestamp_span = true;
            stats.numa_first_timestamp = numa_summary.first_timestamp;
            stats.numa_last_timestamp = numa_summary.last_timestamp;
            stats.numa_steady_timestamp = numa_summary.steady_timestamp;

            stats.fast_used_growth_before_steady_kb =
                diff_u64(numa_summary.steady_fast_used_kb, numa_summary.initial_fast_used_kb);
            stats.fast_used_growth_after_steady_kb =
                diff_u64(numa_summary.final_fast_used_kb, numa_summary.steady_fast_used_kb);
            stats.slow_used_growth_before_steady_kb =
                diff_u64(numa_summary.steady_slow_used_kb, numa_summary.initial_slow_used_kb);
            stats.slow_used_growth_after_steady_kb =
                diff_u64(numa_summary.final_slow_used_kb, numa_summary.steady_slow_used_kb);
        } else if (numa_log_path_arg != NULL) {
            fprintf(stderr, "Failed to load explicit NUMA log %s: %s\n", resolved_numa_log_path, numa_error);
            fclose(fp);
            return 1;
        } else {
            fprintf(stderr, "NUMA log inference found %s but load failed: %s\n", resolved_numa_log_path, numa_error);
        }
    }

    page_table_t page_table;
    if (page_table_init(&page_table, 65536) != 0) {
        fprintf(stderr, "Failed to initialize page table\n");
        fclose(fp);
        return 1;
    }

    char *line = NULL;
    size_t cap = 0;
    trace_event_t event;
    bool pebs_time_initialized = false;

    median_estimator_t reuse_median_estimator;
    median_estimator_init(&reuse_median_estimator);

    while (getline(&line, &cap, fp) != -1) {
        parse_status_t status = parse_trace_line(line, &event);
        summary_stats_record_line(&stats, status, &event);

        if (status == PARSE_STATUS_OK) {
            bool before_steady_phase = true;
            if (event.has_timestamp) {
                if (!pebs_time_initialized) {
                    pebs_time_initialized = true;
                    stats.has_pebs_timestamp_span = true;
                    stats.pebs_first_timestamp = event.timestamp;
                    stats.pebs_last_timestamp = event.timestamp;

                    if (have_numa_summary) {
                        // Align by start time because PEBS timestamp base can differ
                        // from NUMA log epoch while preserving relative offsets.
                        double numa_steady_offset = numa_summary.steady_timestamp - numa_summary.first_timestamp;
                        stats.aligned_pebs_steady_timestamp = stats.pebs_first_timestamp + numa_steady_offset;
                        stats.has_aligned_pebs_steady_timestamp = true;
                    }
                } else {
                    stats.pebs_last_timestamp = event.timestamp;
                }
            }

            if (have_numa_summary && stats.has_aligned_pebs_steady_timestamp && event.has_timestamp) {
                before_steady_phase = (event.timestamp <= stats.aligned_pebs_steady_timestamp);
            }

            if (have_numa_summary) {
                if (before_steady_phase) {
                    stats.pebs_events_before_steady++;
                } else {
                    stats.pebs_events_after_steady++;
                }
            }

            bool was_inserted = false;
            page_state_t *state = page_table_get_or_insert(&page_table, event.pfn, &was_inserted);
            if (state == NULL) {
                fprintf(stderr, "Page table insert failed (possible OOM)\n");
                free(line);
                fclose(fp);
                page_table_destroy(&page_table);
                return 1;
            }

            if (was_inserted) {
                summary_stats_record_page_insert(&stats);
                if (have_numa_summary) {
                    if (before_steady_phase) {
                        stats.pebs_new_pages_before_steady++;
                    } else {
                        stats.pebs_new_pages_after_steady++;
                    }
                }
            }

            bool predicted_remote = false;
            if (have_numa_summary) {
                if (was_inserted) {
                    predicted_remote = !before_steady_phase;
                } else if (state->has_predicted_state) {
                    predicted_remote = state->predicted_remote_state;
                }
            } else {
                if (!was_inserted) {
                    uint64_t reuse_distance_unique_predicted = 0;
                    if (stats.unique_counter_predicted >= state->last_unique_predicted_counter) {
                        reuse_distance_unique_predicted =
                            stats.unique_counter_predicted - state->last_unique_predicted_counter;
                    }

                    predicted_remote = (reuse_distance_unique_predicted > stats.fast_tier_pages);
                }
            }

            summary_stats_record_prediction(&stats, predicted_remote, event.access_class);

            bool increment_unique_actual = was_inserted || (event.access_class == ACCESS_CLASS_REMOTE);
            bool increment_unique_predicted = was_inserted || predicted_remote;

            if (increment_unique_actual) {
                summary_stats_increment_unique_actual(&stats);
            }
            if (increment_unique_predicted) {
                summary_stats_increment_unique_predicted(&stats);
            }

            access_observation_t observation;
            page_state_record_access(state,
                                     &event,
                                     stats.global_access_counter,
                                     stats.unique_counter_actual,
                                     stats.unique_counter_predicted,
                                     &observation);

            if (observation.has_reuse) {
                summary_stats_record_reuse_sample(&stats,
                                                  observation.reuse_distance_global,
                                                  observation.reuse_distance_unique_actual,
                                                  observation.reuse_distance_unique_predicted);
                median_estimator_add(&reuse_median_estimator, (double)observation.reuse_distance_unique_predicted);
                if (median_estimator_ready(&reuse_median_estimator)) {
                    stats.has_running_median_reuse_unique_predicted = true;
                    stats.running_median_reuse_unique_predicted = median_estimator_get(&reuse_median_estimator);
                }
            }

            if (observation.has_time_delta) {
                summary_stats_record_time_delta(&stats, observation.time_delta);
            }

            bool promoted = false;
            if (enable_promotion &&
                have_numa_summary &&
                !was_inserted &&
                predicted_remote &&
                observation.has_reuse &&
                median_estimator_ready(&reuse_median_estimator)) {
                double median_reuse = median_estimator_get(&reuse_median_estimator);
                if ((double)observation.reuse_distance_unique_predicted < median_reuse) {
                    state->predicted_remote_state = false;
                    promoted = true;
                    stats.promotion_count++;
                }
            }

            if (!promoted) {
                state->predicted_remote_state = predicted_remote;
            }
            state->has_predicted_state = true;
        }
    }

    free(line);
    fclose(fp);

    summary_stats_set_unique_pages(&stats, (uint64_t)page_table_size(&page_table));
    summary_stats_finalize_numa_coverage(&stats);
    summary_stats_finalize_extrapolation(&stats);

    summary_stats_print(&stats, trace_path);
    page_table_destroy(&page_table);
    return 0;
}
