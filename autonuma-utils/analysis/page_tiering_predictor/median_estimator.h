#ifndef MEDIAN_ESTIMATOR_H
#define MEDIAN_ESTIMATOR_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint64_t count;
    double warmup[5];
    double q[5];
    double n[5];
    double np[5];
    double dn[5];
    bool initialized;
} median_estimator_t;

void median_estimator_init(median_estimator_t *estimator);
void median_estimator_add(median_estimator_t *estimator, double sample);
bool median_estimator_ready(const median_estimator_t *estimator);
double median_estimator_get(const median_estimator_t *estimator);

#endif
