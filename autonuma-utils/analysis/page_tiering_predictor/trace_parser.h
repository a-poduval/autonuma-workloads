#ifndef TRACE_PARSER_H
#define TRACE_PARSER_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    ACCESS_CLASS_UNKNOWN = 0,
    ACCESS_CLASS_LOCAL = 1,
    ACCESS_CLASS_REMOTE = 2
} access_class_t;

typedef struct {
    bool has_timestamp;
    double timestamp;
    access_class_t access_class;
    uint64_t address;
    uint64_t pfn;
} trace_event_t;

typedef enum {
    PARSE_STATUS_OK = 0,
    PARSE_STATUS_IGNORED = 1,
    PARSE_STATUS_MALFORMED = 2
} parse_status_t;

parse_status_t parse_trace_line(char *line, trace_event_t *out_event);
const char *access_class_to_string(access_class_t access_class);

#endif
