#define _POSIX_C_SOURCE 200809L

#include "trace_parser.h"

#include <ctype.h>
#include <errno.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define MAX_TOKENS 32
#define NORMALIZED_TOKEN_MAX 256

static size_t normalize_token(const char *input, char *output, size_t output_size)
{
    size_t in_len = strlen(input);
    while (in_len > 0 && (input[in_len - 1] == ':' || input[in_len - 1] == ',' || input[in_len - 1] == ';')) {
        in_len--;
    }

    if (output_size == 0) {
        return 0;
    }

    if (in_len >= output_size) {
        in_len = output_size - 1;
    }

    memcpy(output, input, in_len);
    output[in_len] = '\0';
    return in_len;
}

static bool parse_hex_u64(const char *token, uint64_t *out_value)
{
    char normalized[NORMALIZED_TOKEN_MAX];
    size_t len = normalize_token(token, normalized, sizeof(normalized));
    const char *scan = normalized;

    if (len == 0) {
        return false;
    }

    if (len >= 2 && normalized[0] == '0' && (normalized[1] == 'x' || normalized[1] == 'X')) {
        scan += 2;
    }

    if (*scan == '\0') {
        return false;
    }

    for (const char *p = scan; *p != '\0'; ++p) {
        if (!isxdigit((unsigned char)*p)) {
            return false;
        }
    }

    errno = 0;
    unsigned long long parsed = strtoull(normalized, NULL, 16);
    if (errno != 0) {
        return false;
    }

    *out_value = (uint64_t)parsed;
    return true;
}

static bool parse_timestamp(const char *token, double *out_timestamp)
{
    char normalized[NORMALIZED_TOKEN_MAX];
    normalize_token(token, normalized, sizeof(normalized));

    if (normalized[0] == '\0') {
        return false;
    }

    errno = 0;
    char *end_ptr = NULL;
    double parsed = strtod(normalized, &end_ptr);
    if (errno != 0 || end_ptr == normalized || *end_ptr != '\0') {
        return false;
    }

    *out_timestamp = parsed;
    return true;
}

static access_class_t classify_event_token(const char *token)
{
    char normalized[NORMALIZED_TOKEN_MAX];
    normalize_token(token, normalized, sizeof(normalized));

    if (normalized[0] == '\0') {
        return ACCESS_CLASS_UNKNOWN;
    }

    if (strcmp(normalized, "local") == 0 ||
        strcmp(normalized, "local_dram_miss") == 0 ||
        strcmp(normalized, "local_dram_hit") == 0 ||
        strncmp(normalized, "local_dram_", 11) == 0) {
        return ACCESS_CLASS_LOCAL;
    }

    if (strcmp(normalized, "remote") == 0 ||
        strcmp(normalized, "remote_dram_miss") == 0 ||
        strcmp(normalized, "remote_dram_hit") == 0 ||
        strncmp(normalized, "remote_dram_", 12) == 0) {
        return ACCESS_CLASS_REMOTE;
    }

    return ACCESS_CLASS_UNKNOWN;
}

parse_status_t parse_trace_line(char *line, trace_event_t *out_event)
{
    if (line == NULL || out_event == NULL) {
        return PARSE_STATUS_MALFORMED;
    }

    memset(out_event, 0, sizeof(*out_event));

    char *tokens[MAX_TOKENS];
    size_t token_count = 0;

    char *save_ptr = NULL;
    char *tok = strtok_r(line, " \t\r\n", &save_ptr);
    while (tok != NULL && token_count < MAX_TOKENS) {
        tokens[token_count++] = tok;
        tok = strtok_r(NULL, " \t\r\n", &save_ptr);
    }

    if (token_count == 0) {
        return PARSE_STATUS_IGNORED;
    }

    double timestamp = 0.0;
    bool has_timestamp = parse_timestamp(tokens[0], &timestamp);

    int event_index = -1;
    access_class_t access_class = ACCESS_CLASS_UNKNOWN;
    for (size_t i = 0; i < token_count; ++i) {
        access_class = classify_event_token(tokens[i]);
        if (access_class != ACCESS_CLASS_UNKNOWN) {
            event_index = (int)i;
            break;
        }
    }

    if (event_index < 0) {
        return PARSE_STATUS_IGNORED;
    }

    uint64_t address = 0;
    bool has_address = false;

    // Intentional fallback behavior: we accept the first hex token after the
    // event token as the sampled address. In normal traces this is addr. If a
    // malformed line omits addr but still has ip, ip will be consumed here.
    for (size_t i = (size_t)event_index + 1; i < token_count; ++i) {
        if (parse_hex_u64(tokens[i], &address)) {
            has_address = true;
            break;
        }
    }

    if (!has_address) {
        // Secondary fallback for unexpected token order.
        for (int i = (int)token_count - 1; i >= 0; --i) {
            if (parse_hex_u64(tokens[i], &address)) {
                has_address = true;
                break;
            }
        }
    }

    if (!has_address) {
        return PARSE_STATUS_MALFORMED;
    }

    out_event->has_timestamp = has_timestamp;
    out_event->timestamp = timestamp;
    out_event->access_class = access_class;
    out_event->address = address;
    out_event->pfn = address >> 12;
    return PARSE_STATUS_OK;
}

const char *access_class_to_string(access_class_t access_class)
{
    switch (access_class) {
    case ACCESS_CLASS_LOCAL:
        return "local";
    case ACCESS_CLASS_REMOTE:
        return "remote";
    case ACCESS_CLASS_UNKNOWN:
    default:
        return "unknown";
    }
}
