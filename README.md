# CTPhys — Empirical Walkthrough of *Physical* Constant-Time

> *Branchless ≠ Leakless.*

A four-phase, reproducible experiment showing that a textbook
"constant-time" `memcmp` written without branches, with fixed input
length and fixed addresses, still produces measurable run-to-run
**timing jitter** on commodity x86 CPUs when comparing the *same*
fixed pair of buffers over and over — and walking through a sequence
of eliminations (cache, store buffer, ALU port pressure) whose
results are *consistent with* a microarchitectural origin for that
jitter, without conclusively proving it.

**What this is not**: the secret buffer is XORed once before the
measurement loop and never varies between iterations, so this is not
a data-dependent-timing experiment in the dudect/ct-verif sense (no
interleaved fixed-vs-random inputs, no statistical test between input
classes). And because "cycles" here are `rdtscp` reference-clock
ticks with no CPU-frequency, P-state, or turbo-transition controls,
the band structure attributed to store-buffer/ALU-port effects in
phases 3-5 has *not* excluded frequency scaling as an alternative
explanation. Treat the causal attribution as a working hypothesis,
not an established result.

The companion C programs are short on purpose. The point is the
*sequence of eliminations*, not any one program.

---

## TL;DR

| Phase | Setup | What collapses, what survives |
|---|---|---|
| **1 — Baseline** | `rdtscp` + average over N runs | Average *looks* constant. **Histogram is multi-modal.** |
| **3 — Cache eliminated** | `clflush(A); clflush(B); mfence` before every iteration | Histogram is *still* multi-modal with a long tail. **Cache alone doesn't explain it.** |
| **4 — Store eliminated** | Drop `volatile` on the accumulator `r` | Histogram collapses to a single peak. **Consistent with the forced store as the driver.** |
| **5 — ALU contention injected** | Add an ALU-heavy dependency chain to the loop body | Multi-modal again, *without* `volatile`. **Consistent with execution-port pressure as an independent driver.** |

The bottom line:

> "Constant-time" is an *algorithmic* claim.
> Physical constant-time has to be argued against the *microarchitecture*.

## Motivation

Cryptographic implementations are required to be constant-time to
defend against timing side channels (Kocher, CRYPTO 1996; Bernstein,
"Cache-timing attacks on AES", 2005). The textbook construction —
a branchless reduction over fixed-length inputs — is what every
intro-to-crypto book teaches. It is also, on real silicon, *not enough
on its own*.

This repository walks through the gap empirically: identical source
code, identical addresses, identical loop count, the *same fixed*
input pair for the whole measurement run — and yet the per-call
timing distribution is multi-modal, not a single sharp peak, in
observable, reproducible ways. That is jitter under a fixed input,
not evidence that timing tracks the *value* of the secret; showing
the latter would require interleaving two input classes and running
a statistical test between them, which this repository does not do.

The contribution is pedagogic: a layered elimination experiment that a
defender can read top-to-bottom and end up with a working intuition
for *why* validating constant-time claims requires more than
inspecting C source — and, just as importantly, for how easy it is to
over-attribute a timing artifact to the wrong microarchitectural
cause without controlling for confounds like frequency scaling.

## Repository layout

```
src/
  phase1_baseline.c        rdtscp + average
  phase3_no_cache.c        + clflush + lfence/mfence + histogram
  phase4_no_store.c        volatile removed; histogram
  phase5_alu_contention.c  ALU dependency chain; histogram

data/
  phase1_summary.txt       sample average from a Linux x86_64 run
  phase3_histogram.txt     sample histogram, cache eliminated
  phase4_histogram.txt     sample histogram, store eliminated
  phase5_histogram.txt     sample histogram, ALU contention injected

scripts/
  analyze_histogram.py     peak detection, modality, robust spread
  plot_histograms.py       matplotlib renderer (optional)

tests/                     pytest suite for the analyser

docs/
  flow_diagram.txt         ASCII summary of the elimination tree
```

## Building

Linux / GCC or Clang, x86_64:

```bash
make all
```

This produces four binaries under `build/`. Each pins itself to CPU 0
via `sched_setaffinity` and emits either an average (phase 1) or a
cycle-count histogram (phases 3 / 4 / 5) on stdout.

Run them:

```bash
./build/phase1_baseline       > data/run/phase1.txt
./build/phase3_no_cache       > data/run/phase3.txt
./build/phase4_no_store       > data/run/phase4.txt
./build/phase5_alu_contention > data/run/phase5.txt
```

The shipped `data/phase*_histogram.txt` files are the outputs of one
such session on a quiet x86_64 host; your numbers will be shifted but
the *shape* of each distribution should match.

## Analysing a histogram

```bash
pip install -r tests/requirements.txt
python scripts/analyze_histogram.py data/phase3_histogram.txt
```

Output is a JSON-friendly dict reporting:

- the total sample count,
- the median cycle count,
- the median absolute deviation (MAD),
- the number of detected peaks (a crude modality estimate),
- the 99th-percentile tail position relative to the median.

Running the analyser on the shipped data files reproduces the
qualitative phase structure pinned by the test suite:

```
$ python scripts/analyze_histogram.py data/phase3_histogram.txt
samples       : 151012
median        : 162
mad           : 20.00
p99           : 216
peak_count    : 3
tail_factor   : 1.33

$ python scripts/analyze_histogram.py data/phase4_histogram.txt
samples       : 199990
median        : 68
mad           : 2.00
p99           : 72
peak_count    : 1          ← collapses to a single peak
tail_factor   : 1.06

$ python scripts/analyze_histogram.py data/phase5_histogram.txt
samples       : 101231
median        : 66
mad           : 2.00
p99           : 102
peak_count    : 2          ← bimodal again, without volatile
tail_factor   : 1.55
```

The pattern — `peak_count: 3 → 1 → 2` going from phase 3 to phase 4
to phase 5 — is the empirical core of this repository.

## Experimental scope and threat model

This repository is a **measurement** workbench. It does not exploit
any system or recover any secret. It runs entirely in user-space on
a host the operator already controls.

What it produces:
- cycle-count distributions of a branchless reduction kernel,
- under controlled microarchitectural conditions (cache flushed /
  not, store forced / not, ALU chain present / not).

What it does *not* produce:
- a working timing-channel exploit against any real cryptographic
  primitive,
- a proof of constant-time for any specific implementation,
- guidance on how to *cause* leakage in someone else's code.

The output is the *negative result*: a demonstration that the
defender's CS101 intuition about constant-time is insufficient on
modern silicon. The phase-by-phase elimination is *suggestive* of a
dominant leak source on one host — it is not a controlled isolation,
since P-state/turbo transitions are never excluded (see
Limitations).

## Limitations

- **This is a jitter experiment, not a data-dependence experiment.**
  Within every phase, `A` and `B` are fixed once at the top of
  `main()` (`B[0] ^= 0x01`) and never change across the `R` measured
  iterations. Multi-modality in a histogram therefore shows that
  *repeated measurements of one fixed input* are not identically
  distributed — it does not show that timing depends on the *value*
  of the secret. A genuine data-dependence claim needs two
  interleaved input classes (dudect-style fixed-vs-random) and a
  statistical test (Welch's t / KS) between the resulting
  distributions; neither exists in this repository yet.
- **The microarchitectural attribution is an unconfirmed hypothesis.**
  `rdtscp` reports invariant-TSC reference ticks, not retired core
  cycles, and nothing here pins CPU frequency, disables turbo, or
  fixes the P-state/C-state. Frequency-scaling transitions alone can
  produce well-separated timing bands that look identical to the
  store-buffer / ALU-port-contention signatures phases 3-5 claim to
  isolate. Distinguishing them would require hardware performance
  counters (e.g. `UOPS_DISPATCHED_PORT.*`, `RESOURCE_STALLS.SB`) or a
  pinned-frequency governor, neither of which this harness has. Read
  the phase 3 -> 4 -> 5 trajectory as "consistent with" the stated
  mechanisms, not as proof of them.
- The conclusions are illustrative, not universal. A different
  microarchitecture (e.g. AMD Zen 4 vs Intel Skylake-Server) will
  produce different histograms and may reverse the relative
  importance of store-buffer pressure vs ALU port contention.
- Pinning to CPU 0, even on an idle host, does not eliminate
  scheduler jitter, SMI / SMM transitions, hypervisor preemption
  (if running in a VM), or hardware power-management noise. The
  shipped histograms come from a quiet but non-isolated host; expect
  ~10–15 % residual noise.
- `rdtscp` is *not* a full serialising barrier; the `lfence`
  sandwich used in phases 3-5 is a best-effort fix but does not
  eliminate every form of cross-instruction reordering.
- The `volatile` accumulator trick used in phases 1-3 forces stores
  in the C abstract machine; the actual store-buffer behaviour
  observed depends on the compiler's lowering. The Makefile compiles
  with `-O2` and the analyser assumes a similar optimisation level.
- The fault model implicit in this experiment is "passive timing
  observation"; active fault injection (Plundervolt-style voltage
  glitching, clock glitching, EM glitching) is out of scope here but
  see the SPIFault repository for an FCDF-style framework that
  handles those scenarios.

## Reproducibility

The histogram files under `data/` are committed and the analyser's
output on them is regression-tested under `tests/`. The point is that
a future contributor — or you, on a different host — can compare a
fresh run to the committed reference and immediately see whether the
qualitative phase structure is preserved.

## Tests

```sh
pip install -r tests/requirements.txt
python -m pytest tests/ -v
```

The suite under `tests/` exercises the analyser against the committed
`data/` histograms. CI (`.github/workflows/python-tests.yml`) runs it on
a Python 3.10/3.11/3.12 matrix and additionally smoke-tests
`scripts/analyze_histogram.py` on the shipped phase histograms.

## References

- P. Kocher, *Timing Attacks on Implementations of Diffie-Hellman,
  RSA, DSS, and Other Systems*, CRYPTO 1996.
- D. J. Bernstein, *Cache-Timing Attacks on AES*, technical report,
  2005.
- Y. Yarom, K. Falkner, *FLUSH+RELOAD: A High Resolution, Low Noise,
  L3 Cache Side-Channel Attack*, USENIX Security 2014.
- J. B. Almeida et al., *Verifying Constant-Time Implementations*,
  USENIX Security 2016.
- K. Murdock et al., *Plundervolt: Software-based Fault Injection
  Attacks against Intel SGX*, IEEE S&P 2020.
- Intel — *Software Developer's Manual*, Vol. 2 (`RDTSCP`, `LFENCE`,
  `MFENCE`, `CLFLUSH` semantics).

## License

MIT — see `LICENSE`.

## Status

Research / educational. The framework is intended as a teaching
artefact and as a starting substrate for further constant-time
investigation. Production constant-time validation should be done
with dedicated tools (e.g. `ctgrind`, `dudect`, `binsec/rel`).
