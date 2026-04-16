#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "page_table.h"
#include "summary_stats.h"
#include "trace_parser.h"

static void print_usage(const char *prog)
{
    fprintf(stderr, "Usage: %s <trace_file>\n", prog);
}

int main(int argc, char **argv)
{
    if (argc != 2) {
        print_usage(argv[0]);
        return 1;
    }

    const char *trace_path = argv[1];
    FILE *fp = fopen(trace_path, "r");
    if (fp == NULL) {
        fprintf(stderr, "Failed to open %s: %s\n", trace_path, strerror(errno));
        return 1;
    }

    summary_stats_t stats;
    summary_stats_init(&stats);

    page_table_t page_table;
    if (page_table_init(&page_table, 65536) != 0) {
        fprintf(stderr, "Failed to initialize page table\n");
        fclose(fp);
        return 1;
    }

    char *line = NULL;
    size_t cap = 0;
    trace_event_t event;

    while (getline(&line, &cap, fp) != -1) {
        parse_status_t status = parse_trace_line(line, &event);
        summary_stats_record_line(&stats, status, &event);

        if (status == PARSE_STATUS_OK) {
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
            }

            bool increment_unique_actual = was_inserted || (event.access_class == ACCESS_CLASS_REMOTE);

            // Phase 3 tracks a predicted unique-counter path without enabling
            // full hot/cold prediction yet. This stays false until phase 4.
            bool predicted_is_slow = false;
            bool increment_unique_predicted = was_inserted || predicted_is_slow;

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
            }

            if (observation.has_time_delta) {
                summary_stats_record_time_delta(&stats, observation.time_delta);
            }
        }
    }

    free(line);
    fclose(fp);

    summary_stats_set_unique_pages(&stats, (uint64_t)page_table_size(&page_table));

    summary_stats_print(&stats, trace_path);
    page_table_destroy(&page_table);
    return 0;
}
