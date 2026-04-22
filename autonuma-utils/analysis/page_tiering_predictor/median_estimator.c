#include "median_estimator.h"

#include <stddef.h>

static void sort5(double values[5])
{
    for (size_t i = 0; i < 5; ++i) {
        for (size_t j = i + 1; j < 5; ++j) {
            if (values[j] < values[i]) {
                double tmp = values[i];
                values[i] = values[j];
                values[j] = tmp;
            }
        }
    }
}

void median_estimator_init(median_estimator_t *estimator)
{
    if (estimator == NULL) {
        return;
    }

    estimator->count = 0;
    estimator->initialized = false;
}

static double sign_double(double value)
{
    return (value >= 0.0) ? 1.0 : -1.0;
}

void median_estimator_add(median_estimator_t *estimator, double sample)
{
    if (estimator == NULL) {
        return;
    }

    if (!estimator->initialized) {
        if (estimator->count < 5) {
            estimator->warmup[estimator->count] = sample;
            estimator->count++;
        }

        if (estimator->count < 5) {
            return;
        }

        sort5(estimator->warmup);
        for (size_t i = 0; i < 5; ++i) {
            estimator->q[i] = estimator->warmup[i];
            estimator->n[i] = (double)(i + 1);
        }

        // P^2 marker desired-position increments for median (p = 0.5).
        estimator->np[0] = 1.0;
        estimator->np[1] = 2.0;
        estimator->np[2] = 3.0;
        estimator->np[3] = 4.0;
        estimator->np[4] = 5.0;

        estimator->dn[0] = 0.0;
        estimator->dn[1] = 0.25;
        estimator->dn[2] = 0.5;
        estimator->dn[3] = 0.75;
        estimator->dn[4] = 1.0;

        estimator->initialized = true;
        return;
    }

    estimator->count++;

    int k = 0;
    if (sample < estimator->q[0]) {
        estimator->q[0] = sample;
        k = 0;
    } else if (sample < estimator->q[1]) {
        k = 0;
    } else if (sample < estimator->q[2]) {
        k = 1;
    } else if (sample < estimator->q[3]) {
        k = 2;
    } else if (sample <= estimator->q[4]) {
        k = 3;
    } else {
        estimator->q[4] = sample;
        k = 3;
    }

    for (int i = k + 1; i < 5; ++i) {
        estimator->n[i] += 1.0;
    }
    for (int i = 0; i < 5; ++i) {
        estimator->np[i] += estimator->dn[i];
    }

    for (int i = 1; i <= 3; ++i) {
        double d = estimator->np[i] - estimator->n[i];
        if (!((d >= 1.0 && (estimator->n[i + 1] - estimator->n[i]) > 1.0) ||
              (d <= -1.0 && (estimator->n[i - 1] - estimator->n[i]) < -1.0))) {
            continue;
        }

        double s = sign_double(d);

        double n_i_minus_1 = estimator->n[i - 1];
        double n_i = estimator->n[i];
        double n_i_plus_1 = estimator->n[i + 1];

        double q_i_minus_1 = estimator->q[i - 1];
        double q_i = estimator->q[i];
        double q_i_plus_1 = estimator->q[i + 1];

        double num = (n_i - n_i_minus_1 + s) * (q_i_plus_1 - q_i) / (n_i_plus_1 - n_i) +
                     (n_i_plus_1 - n_i - s) * (q_i - q_i_minus_1) / (n_i - n_i_minus_1);
        double q_hat = q_i + (s / (n_i_plus_1 - n_i_minus_1)) * num;

        if (q_hat > estimator->q[i - 1] && q_hat < estimator->q[i + 1]) {
            estimator->q[i] = q_hat;
        } else {
            int i_s = i + (int)s;
            estimator->q[i] += s * (estimator->q[i_s] - estimator->q[i]) / (estimator->n[i_s] - estimator->n[i]);
        }

        estimator->n[i] += s;
    }
}

bool median_estimator_ready(const median_estimator_t *estimator)
{
    return (estimator != NULL && estimator->initialized);
}

double median_estimator_get(const median_estimator_t *estimator)
{
    if (estimator == NULL) {
        return 0.0;
    }

    if (!estimator->initialized) {
        if (estimator->count == 0) {
            return 0.0;
        }

        double copy[5] = {0.0, 0.0, 0.0, 0.0, 0.0};
        for (uint64_t i = 0; i < estimator->count; ++i) {
            copy[i] = estimator->warmup[i];
        }
        for (uint64_t i = estimator->count; i < 5; ++i) {
            copy[i] = copy[estimator->count - 1];
        }
        sort5(copy);
        return copy[2];
    }

    return estimator->q[2];
}
