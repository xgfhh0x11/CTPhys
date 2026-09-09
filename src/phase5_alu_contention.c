/* Phase 5 — ALU / port contention as an independent leak surface.
 *
 * Single-change diff against phase 4: we add an ALU-heavy dependency
 * chain inside the loop body. No branches, no stores, no extra
 * memory accesses — only extra integer ops.
 *
 *     uint8_t x = a[i] ^ b[i];
 *     r ^= (x & 0x55);
 *     r  = (r << 1) | (r >> 7);
 *     r += (x ^ 0xA5);
 *     r ^= 0x5A;
 *
 * Observation: the histogram becomes multi-modal again, even though
 * the store-buffer pressure that drove the phase-3 distribution is
 * still absent. The data dependency of the chain on `x` is enough
 * to push uops onto different execution ports across runs.
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
static uint64_t overflow_count = 0;

static inline uint64_t rdtscp_fenced(void) {
    unsigned aux;
    _mm_lfence();
    uint64_t t = __rdtscp(&aux);
    _mm_lfence();
    return t;
}

__attribute__((noinline))
int ct_memcmp(const uint8_t *a, const uint8_t *b, size_t n) {
    uint8_t r = 0;
    for (size_t i = 0; i < n; i++) {
        uint8_t x = (uint8_t)(a[i] ^ b[i]);
        r ^= (uint8_t)(x & 0x55);
        r  = (uint8_t)((r << 1) | (r >> 7));
        r += (uint8_t)(x ^ 0xA5);
        r ^= 0x5A;
    }
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
    static uint8_t A[N] __attribute__((aligned(64)));
    static uint8_t B[N] __attribute__((aligned(64)));
    memset(A, 0xAA, N);
    memset(B, 0xAA, N);
    B[0] ^= 0x01;

    for (int i = 0; i < R; i++) {
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
        else
            overflow_count++;
    }

    printf("# total=%d dropped=%lu\n", R, overflow_count);
    for (int i = 0; i < MAX_CYCLES; i++) {
        if (hist[i])
            printf("%d %lu\n", i, hist[i]);
    }
    return 0;
}
