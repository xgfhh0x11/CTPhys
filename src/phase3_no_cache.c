/* Phase 3 — Cache eliminated.
 *
 * We force-flush both input buffers from the cache hierarchy before
 * every measured iteration and bracket the measurement with `lfence`s
 * to ensure clflushes / loads from the previous iteration have
 * retired before t0.
 *
 * Output: a histogram of cycle counts (bucket = exact cycle), so we
 * can read the shape of the distribution, not just its mean.
 *
 * Expected if cache is the dominant leak: with cache forcibly cold
 * every run, the per-iteration timing collapses to a single mode.
 *
 * Observed (on the shipped reference host): the histogram remains
 * multi-modal with a long tail. Cache is therefore *not* the leak.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sched.h>
#include <unistd.h>
#include <x86intrin.h>

#ifndef MAX_CYCLES
#define MAX_CYCLES 1200
#endif

static uint64_t hist[MAX_CYCLES];

static inline uint64_t rdtscp_fenced(void) {
    unsigned aux;
    _mm_lfence();
    uint64_t t = __rdtscp(&aux);
    _mm_lfence();
    return t;
}

__attribute__((noinline))
int ct_memcmp(const uint8_t *a, const uint8_t *b, size_t n) {
    volatile uint8_t r = 0;          /* still volatile in this phase */
    for (size_t i = 0; i < n; i++)
        r |= a[i] ^ b[i];
    return r;
}

static void pin_cpu0(void) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(0, &set);
    sched_setaffinity(0, sizeof(set), &set);
}

int main(void) {
    pin_cpu0();

    enum { N = 64, R = 200000 };
    static uint8_t A[N], B[N];
    memset(A, 0xAA, N);
    memset(B, 0xAA, N);
    B[0] ^= 0x01;

    for (int i = 0; i < R; i++) {
        /* Flush both buffers from all cache levels. */
        for (int j = 0; j < N; j += 64) {
            _mm_clflush(&A[j]);
            _mm_clflush(&B[j]);
        }
        _mm_mfence();

        uint64_t t0 = rdtscp_fenced();
        (void)ct_memcmp(A, B, N);
        uint64_t t1 = rdtscp_fenced();

        uint64_t d = t1 - t0;
        if (d < MAX_CYCLES)
            hist[d]++;
    }

    for (int i = 0; i < MAX_CYCLES; i++) {
        if (hist[i])
            printf("%d %lu\n", i, hist[i]);
    }
    return 0;
}
