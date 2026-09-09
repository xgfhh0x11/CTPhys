/* Phase 1 — Baseline measurement.
 *
 * Algorithmic claim: ct_memcmp() is constant-time. No branches; loop
 * count fixed to the length argument; no early exit.
 *
 * Measurement: rdtscp around N invocations, report the average cycle
 * count.
 *
 * Predicted result if the claim were physically true: the average
 * cycles per call is independent of the bit pattern compared.
 *
 * Caveat (will become important in phase 3): rdtscp is *not* a full
 * serialising barrier; loads from the previous iteration may still
 * be in flight when t0 is captured. Phase 3 fixes this with an lfence
 * sandwich.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sched.h>
#include <unistd.h>

static inline uint64_t rdtscp(void) {
    uint32_t lo, hi;
    __asm__ volatile ("rdtscp" : "=a"(lo), "=d"(hi) :: "rcx");
    return ((uint64_t)hi << 32) | lo;
}

/* Branchless reduction. Loop count is `n`; no early exit; no branches
 * dependent on the data being compared. */
__attribute__((noinline))
int ct_memcmp(const uint8_t *a, const uint8_t *b, size_t n) {
    volatile uint8_t r = 0;
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
    /* Switch this between 0x01 and 0x80 across runs to compare
     * LSB-vs-MSB bit-pattern impact. */
    B[0] ^= 0x01;

    uint64_t sum = 0;
    for (int i = 0; i < R; i++) {
        uint64_t t0 = rdtscp();
        (void)ct_memcmp(A, B, N);
        uint64_t t1 = rdtscp();
        sum += (t1 - t0);
    }

    printf("avg cycles: %lu\n", sum / R);
    return 0;
}
