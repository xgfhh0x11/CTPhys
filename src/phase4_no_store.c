/* Phase 4 — Store eliminated.
 *
 * Single-change diff against phase 3: the accumulator `r` is no
 * longer `volatile`. With -O2 the compiler keeps it in a register
 * for the entire loop body, so the store-buffer pressure that was
 * present in phase 3 vanishes.
 *
 * Observation: the previously multi-modal histogram collapses to
 * one peak. The leak we were chasing in phase 3 was the forced
 * store + store-to-load-forwarding chain.
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
    uint8_t r = 0;                   /* NOTE: no `volatile` */
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
