#define _POSIX_C_SOURCE 200809L

#include "numa_log.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    double timestamp;
    uint64_t fast_free_kb;
    uint64_t fast_used_kb;
    uint64_t slow_used_kb;
} numa_sample_t;

static void set_error(char *buf, size_t buf_len, const char *msg)
{
    if (buf == NULL || buf_len == 0) {
        return;
    }
    snprintf(buf, buf_len, "%s", msg);
}

static size_t split_csv_fields(char *line, char **fields, size_t max_fields)
{
    size_t count = 0;
    if (line == NULL || fields == NULL || max_fields == 0) {
        return 0;
    }

    fields[count++] = line;
    for (char *p = line; *p != '\0'; ++p) {
        if (*p == ',') {
            *p = '\0';
            if (count < max_fields) {
                fields[count++] = p + 1;
            }
        } else if (*p == '\n' || *p == '\r') {
            *p = '\0';
            break;
        }
    }

    return count;
}

static int find_col_index(char **fields, size_t count, const char *name)
{
    for (size_t i = 0; i < count; ++i) {
        if (strcmp(fields[i], name) == 0) {
            return (int)i;
        }
    }
    return -1;
}

static int parse_double_strict(const char *text, double *out)
{
    if (text == NULL || out == NULL || *text == '\0') {
        return -1;
    }

    errno = 0;
    char *end_ptr = NULL;
    double value = strtod(text, &end_ptr);
    if (errno != 0 || end_ptr == text || *end_ptr != '\0') {
        return -1;
    }

    *out = value;
    return 0;
}

static int parse_u64_strict(const char *text, uint64_t *out)
{
    if (text == NULL || out == NULL || *text == '\0') {
        return -1;
    }

    errno = 0;
    char *end_ptr = NULL;
    unsigned long long value = strtoull(text, &end_ptr, 10);
    if (errno != 0 || end_ptr == text || *end_ptr != '\0') {
        return -1;
    }

    *out = (uint64_t)value;
    return 0;
}

int numa_log_load_summary(const char *path,
                          int fast_node,
                          int slow_node,
                          numa_log_summary_t *out,
                          char *error_buf,
                          size_t error_buf_len)
{
    if (path == NULL || out == NULL) {
        set_error(error_buf, error_buf_len, "invalid input");
        return -1;
    }

    memset(out, 0, sizeof(*out));

    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        set_error(error_buf, error_buf_len, "failed to open numa log");
        return -1;
    }

    char *line = NULL;
    size_t cap = 0;

    if (getline(&line, &cap, fp) == -1) {
        free(line);
        fclose(fp);
        set_error(error_buf, error_buf_len, "empty numa log");
        return -1;
    }

    char *header_fields[128];
    size_t header_count = split_csv_fields(line, header_fields, 128);

    char fast_free_name[64];
    char fast_used_name[64];
    char slow_used_name[64];
    snprintf(fast_free_name, sizeof(fast_free_name), "node%d_free_kb", fast_node);
    snprintf(fast_used_name, sizeof(fast_used_name), "node%d_used_kb", fast_node);
    snprintf(slow_used_name, sizeof(slow_used_name), "node%d_used_kb", slow_node);

    int ts_idx = find_col_index(header_fields, header_count, "timestamp");
    int fast_free_idx = find_col_index(header_fields, header_count, fast_free_name);
    int fast_used_idx = find_col_index(header_fields, header_count, fast_used_name);
    int slow_used_idx = find_col_index(header_fields, header_count, slow_used_name);

    if (ts_idx < 0 || fast_free_idx < 0 || fast_used_idx < 0 || slow_used_idx < 0) {
        free(line);
        fclose(fp);
        set_error(error_buf, error_buf_len, "required columns missing in numa log");
        return -1;
    }

    size_t sample_cap = 1024;
    size_t sample_count = 0;
    numa_sample_t *samples = (numa_sample_t *)malloc(sample_cap * sizeof(*samples));
    if (samples == NULL) {
        free(line);
        fclose(fp);
        set_error(error_buf, error_buf_len, "out of memory");
        return -1;
    }

    while (getline(&line, &cap, fp) != -1) {
        char *fields[128];
        size_t field_count = split_csv_fields(line, fields, 128);

        size_t needed = (size_t)ts_idx;
        if ((size_t)fast_free_idx > needed) {
            needed = (size_t)fast_free_idx;
        }
        if ((size_t)fast_used_idx > needed) {
            needed = (size_t)fast_used_idx;
        }
        if ((size_t)slow_used_idx > needed) {
            needed = (size_t)slow_used_idx;
        }

        if (field_count <= needed) {
            continue;
        }

        numa_sample_t sample;
        if (parse_double_strict(fields[ts_idx], &sample.timestamp) != 0 ||
            parse_u64_strict(fields[fast_free_idx], &sample.fast_free_kb) != 0 ||
            parse_u64_strict(fields[fast_used_idx], &sample.fast_used_kb) != 0 ||
            parse_u64_strict(fields[slow_used_idx], &sample.slow_used_kb) != 0) {
            continue;
        }

        if (sample_count == sample_cap) {
            size_t new_cap = sample_cap * 2;
            numa_sample_t *resized = (numa_sample_t *)realloc(samples, new_cap * sizeof(*samples));
            if (resized == NULL) {
                free(samples);
                free(line);
                fclose(fp);
                set_error(error_buf, error_buf_len, "out of memory");
                return -1;
            }
            samples = resized;
            sample_cap = new_cap;
        }

        samples[sample_count++] = sample;
    }

    free(line);
    fclose(fp);

    if (sample_count == 0) {
        free(samples);
        set_error(error_buf, error_buf_len, "no valid samples in numa log");
        return -1;
    }

    uint64_t min_fast_free = samples[0].fast_free_kb;
    uint64_t max_fast_free = samples[0].fast_free_kb;
    for (size_t i = 1; i < sample_count; ++i) {
        if (samples[i].fast_free_kb < min_fast_free) {
            min_fast_free = samples[i].fast_free_kb;
        }
        if (samples[i].fast_free_kb > max_fast_free) {
            max_fast_free = samples[i].fast_free_kb;
        }
    }

    uint64_t range = max_fast_free - min_fast_free;
    uint64_t epsilon = (uint64_t)((double)range * 0.05);
    if (epsilon < 65536ULL) {
        epsilon = 65536ULL;
    }
    if (range > 0 && epsilon > range) {
        epsilon = range;
    }

    size_t steady_idx = sample_count - 1;
    for (size_t i = 0; i < sample_count; ++i) {
        if (samples[i].fast_free_kb <= min_fast_free + epsilon) {
            steady_idx = i;
            break;
        }
    }

    out->available = true;
    out->fast_node = fast_node;
    out->slow_node = slow_node;
    out->sample_count = sample_count;

    out->first_timestamp = samples[0].timestamp;
    out->last_timestamp = samples[sample_count - 1].timestamp;
    out->steady_timestamp = samples[steady_idx].timestamp;

    out->initial_fast_free_kb = samples[0].fast_free_kb;
    out->min_fast_free_kb = min_fast_free;

    out->initial_fast_used_kb = samples[0].fast_used_kb;
    out->steady_fast_used_kb = samples[steady_idx].fast_used_kb;
    out->final_fast_used_kb = samples[sample_count - 1].fast_used_kb;

    out->initial_slow_used_kb = samples[0].slow_used_kb;
    out->steady_slow_used_kb = samples[steady_idx].slow_used_kb;
    out->final_slow_used_kb = samples[sample_count - 1].slow_used_kb;

    free(samples);
    return 0;
}
