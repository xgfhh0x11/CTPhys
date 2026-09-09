# CTPhys — Build & Verification

> *This file answers: "Is this project buildable, runnable, and
> behaving as documented?"*

## 1. Build

The project has two independent build paths because it is bilingual: the
C measurement kernels (phases 1, 3, 4, 5) and the Python histogram
analyser. Either can be exercised without the other.

### 1.1 Primary build path

- **Platform**: Linux x86_64 (the C sources `#define _GNU_SOURCE` and
  call `sched_setaffinity` from `<sched.h>`; the inline asm uses
  `rdtscp` / `clflush` / `lfence` / `mfence`). Does **not** build on
  Windows or macOS as shipped.
- **Toolchain**: GCC or Clang with C11 support (`-std=c11`). Default
  `CC=gcc`, default `CFLAGS=-O2 -Wall -Wextra -std=c11`. GNU `make`
  required (the Makefile uses `mkdir -p`, pattern rules, and
  `addprefix`).
- **Command**:

  ```bash
  make all
  ```

  Override toolchain or flags as needed, e.g.
  `make CC=clang CFLAGS='-O2 -std=c11'`.

- **Output**: four executables under `build/`, one per phase:
  - `build/phase1_baseline`  — emits a single `avg cycles: <N>` line.
  - `build/phase3_no_cache`  — emits a `cycles count` two-column
    histogram on stdout.
  - `build/phase4_no_store`  — same format as phase 3.
  - `build/phase5_alu_contention` — same format as phase 3.

  Capture each run into `data/run/` (gitignored) per the README:

  ```bash
  mkdir -p data/run
  ./build/phase1_baseline       > data/run/phase1.txt
  ./build/phase3_no_cache       > data/run/phase3.txt
  ./build/phase4_no_store       > data/run/phase4.txt
  ./build/phase5_alu_contention > data/run/phase5.txt
  ```

  Clean with `make clean` (removes `build/`).

### 1.2 Alternative build paths

**Python analyser (no compilation).** The histogram analyser and its
test suite are pure Python (>=3.10, no native deps) and can be exercised
on any OS, *including* the Windows host this verification was performed
on:

```bash
pip install -r tests/requirements.txt
python scripts/analyze_histogram.py data/phase3_histogram.txt
```

**Optional plotting.** `scripts/plot_histograms.py` renders the three
histograms into `data/histograms.png`. It is not wired into the
Makefile and matplotlib is intentionally not a hard dependency:

```bash
pip install matplotlib
python scripts/plot_histograms.py
```

**CI.** `.github/workflows/python-tests.yml` exercises the Python path
only (Ubuntu, Python 3.10 / 3.11 / 3.12). There is no CI for the C
binaries.

### 1.3 Dependencies

- **Required**:
  - C build: GCC or Clang with C11, GNU `make`, Linux glibc headers
    (`sched.h`, `unistd.h`). x86_64 CPU exposing `RDTSCP` (CPUID
    bit 80000001:EDX[27], universal on commodity post-2008 Intel/AMD).
  - Python build: Python >= 3.10 (matches CI matrix; only stdlib used
    by the analyser).
  - Test suite: `pytest >= 7.0` (pinned in `tests/requirements.txt`).
- **Optional**:
  - `matplotlib` — only for `scripts/plot_histograms.py`.
  - Quiet host + ability to pin to CPU 0 — improves signal quality but
    is not strictly required to build or run.

## 2. Expected behavior

### 2.1 What this project does

CTPhys is an empirical microarchitectural side-channel pedagogy
workbench. Four short C programs implement a "branchless, fixed-length"
`ct_memcmp` and time it with `rdtscp` across 100k–200k iterations under
progressively stricter controls (baseline → cache-flushed →
non-`volatile` accumulator → ALU-pressure injected). Each phase emits a
cycle-count distribution to stdout. The Python analyser ingests the
two-column `cycles count` histograms and reports samples, median, MAD,
p99, peak count, and tail factor. The pytest suite pins the *qualitative*
shape of the shipped reference distributions (phase 3 multimodal →
phase 4 collapses to one peak → phase 5 multimodal again), which is the
empirical claim of the repository.

### 2.2 Acceptance criteria

- [ ] `make all` on Linux x86_64 produces `build/phase1_baseline`,
      `build/phase3_no_cache`, `build/phase4_no_store`, and
      `build/phase5_alu_contention` with exit status 0 and no warnings
      under `-Wall -Wextra`.
- [ ] `./build/phase1_baseline` prints a single line of the form
      `avg cycles: <integer>` and exits 0.
- [ ] `./build/phase3_no_cache`, `./build/phase4_no_store`, and
      `./build/phase5_alu_contention` each emit a `<cycles> <count>`
      two-column stream on stdout that `scripts/analyze_histogram.py`
      can parse without raising.
- [ ] `python scripts/analyze_histogram.py data/phase3_histogram.txt`
      reports `peak_count >= 2`.
- [ ] `python scripts/analyze_histogram.py data/phase4_histogram.txt`
      reports `peak_count == 1`.
- [ ] `python scripts/analyze_histogram.py data/phase5_histogram.txt`
      reports `peak_count >= 2`.
- [ ] Phase 3's `tail_factor` is strictly greater than phase 4's
      `tail_factor` on the shipped data.
- [ ] `python -m pytest tests/ -v` reports 14 passed, 0 failed.
- [ ] All three shipped histograms contain at least 50,000 samples.

### 2.3 Manual verification

This was executed on the verification host (Windows, Python 3.14.0)
against the shipped data files. The Python path is OS-independent.

**Step 1 — install the test dependency.**

```bash
pip install -r tests/requirements.txt
```

**Step 2 — analyser on phase 3 (cache-flushed, `volatile` retained).**

```bash
python scripts/analyze_histogram.py data/phase3_histogram.txt
```

Expected output (matches README §"Analysing a histogram"):

```
samples       : 151012
median        : 162
mad           : 20.00
p99           : 216
peak_count    : 3
tail_factor   : 1.33
```

**Step 3 — analyser on phase 4 (`volatile` dropped). Modality must
collapse to one peak.**

```bash
python scripts/analyze_histogram.py data/phase4_histogram.txt
```

Verified output on this host:

```
samples       : 199990
median        : 68
mad           : 2.00
p99           : 72
peak_count    : 1
tail_factor   : 1.06
```

**Step 4 — analyser on phase 5 (ALU chain injected). Modality returns.**

```bash
python scripts/analyze_histogram.py data/phase5_histogram.txt
```

Expected:

```
samples       : 101231
median        : 66
mad           : 2.00
p99           : 102
peak_count    : 2
tail_factor   : 1.55
```

The empirical core of the repository is the `peak_count: 3 → 1 → 2`
trajectory across phases 3 → 4 → 5.

**Step 5 — C kernels (Linux x86_64 only).** On a Linux host:

```bash
make all
./build/phase1_baseline
```

Expected stdout: one line, `avg cycles: <integer>` (the README's
reference run reports 183–185 cycles).

```bash
./build/phase3_no_cache | head
```

Expected: a stream of `<cycles> <count>` lines (header comments
prefixed `#` are tolerated by the analyser).

### 2.4 Automated verification

- **Framework**: `pytest` (>= 7.0). The `tests/conftest.py` shim
  inserts `scripts/` onto `sys.path` so `from analyze_histogram import …`
  resolves without packaging the analyser.
- **Command**:

  ```bash
  python -m pytest tests/ -v
  ```

- **Pass indicator**: the final line reads
  `============================= 14 passed in <t>s ==============================`.
- **Verified on this host (Windows, Python 3.14.0, pytest 9.0.3):**
  14 passed, 0 failed.
- **CI**: `.github/workflows/python-tests.yml` runs the same command on
  Ubuntu against Python 3.10 / 3.11 / 3.12, plus a smoke-test that the
  analyser succeeds against each shipped histogram.

The suite covers (a) the histogram parser (comment/blank-line tolerance,
malformed-line rejection, non-positive-count dropping), (b) the
summariser on handcrafted unimodal and bimodal cases, and (c)
regressions on the shipped reference histograms pinning the phase 3 / 4
/ 5 modality + tail trajectory.

## 3. Alternatives & improvements

### 3.1 Known fragilities

- **Platform lock-in for the C path.** The kernels hard-require Linux
  (`_GNU_SOURCE`, `sched_setaffinity`, `<sched.h>`) and x86_64 (inline
  asm for `rdtscp`). They will not build on Windows or macOS as
  shipped. No `configure` step, no compile-time platform guard, no
  alternative timer.
- **No `make test` / no integration target.** The Makefile builds the
  C kernels only. The Python test suite is invoked manually via
  `pytest`. There is no top-level target that "verifies the whole
  repository in one command."
- **CI does not exercise the C kernels.** The GitHub Actions workflow
  is Python-only on Ubuntu; a regression in the C sources would not be
  caught by CI. Conversely, a Windows breakage of the Python path
  would also be missed (CI is Linux-only).
- **Non-deterministic measurement output.** Re-running a phase
  produces *different numbers*; only the *qualitative shape* (modality,
  relative tail) is expected to be stable, and even that depends on
  microarchitecture (see README §Limitations). A fresh run on AMD
  Zen 4 may not match Intel Skylake. This is documented and is the
  scientific point of the repository, but it means there is no exact
  reference output to diff against for the C side.
- **`rdtscp` is not a full serialising barrier** (called out in
  source comments and README); residual cross-instruction reordering
  is a known measurement-floor source.
- **Python 3.14 not in CI matrix.** Manual verification used 3.14.0
  successfully; CI tops out at 3.12. Not a defect — just an untested
  point in the support matrix.

### 3.2 Fallbacks

- **Cannot build C kernels (no Linux box).** The shipped
  `data/phase{1,3,4,5}_*.txt` files are committed reference outputs of
  one full Linux-host campaign. Running the Python analyser and the
  pytest suite against them reproduces the qualitative claim end-to-end
  without ever invoking GCC.
- **Cannot install matplotlib.** Plotting is strictly optional; the
  analyser already prints all numeric figures the README cites.
- **`pip install` blocked.** `pytest` is the only test-time dep; the
  analyser itself is stdlib-only and can be run directly.

### 3.3 Roadmap

- **Short-term (<= 1 day)**:
  - Add a `make test` target that runs `python -m pytest tests/`, and
    a `make verify` target that additionally runs the analyser against
    the three shipped histograms (mirroring the CI smoke-test).
  - Add an `#if !defined(__linux__) || !defined(__x86_64__)` guard at
    the top of each `src/phase*.c` with a clear `#error` message.
- **Medium-term (<= 1 week)**:
  - Extend CI with a Linux job that runs `make all` and asserts the
    four binaries exist and exit 0 on a single dummy iteration.
  - Add a `requirements-dev.txt` (or pin matplotlib in a separate
    extras file) and a `make plot` target wrapping
    `scripts/plot_histograms.py`.
  - Cross-platform smoke-test for the analyser (Windows + macOS
    runners in the matrix) — the Python path is already portable but
    is not currently asserted to be.
- **Long-term**:
  - Port the measurement kernels to a portable timer abstraction
    (`__rdtsc` on Windows via `<intrin.h>`, `mach_absolute_time` on
    macOS, `clock_gettime(CLOCK_MONOTONIC_RAW)` as a last resort) so
    the experiment can be reproduced on at least the three major
    desktop OSes.
  - Add an `aarch64` variant using `pmccntr_el0` to validate (or
    refute) the modality trajectory on a non-x86 microarchitecture,
    which the README explicitly flags as an open question.
  - Integrate with `dudect` / `ctgrind` for a third-party cross-check
    of the constant-time claim on the same kernels.

## 4. Sanity check

| Check | Status | Notes |
|-------|--------|-------|
| README documents build | ✅ | §"Building" gives `make all` plus per-phase run commands; §"Analysing a histogram" documents the Python path with `pip install -r tests/requirements.txt`. |
| Build files present | ✅ | `Makefile`, `tests/requirements.txt`, `.github/workflows/python-tests.yml` all present. |
| Build files internally consistent | ✅ | Makefile pattern rule `$(BUILD)/%: $(SRC)/%.c` matches `src/phase*.c` filenames; `$(PHASES)` list (`phase1_baseline phase3_no_cache phase4_no_store phase5_alu_contention`) is exhaustive over `src/`. |
| Source structure matches README | ✅ | README §"Repository layout" lists `src/phase{1,3,4,5}_*.c`, `data/phase*_*.txt`, `scripts/analyze_histogram.py`, `scripts/plot_histograms.py`, `tests/`, `docs/flow_diagram.txt` — every entry exists on disk. |
| Tests exist | ✅ | `tests/test_analyzer.py` defines 14 tests; `tests/conftest.py` wires `scripts/` onto `sys.path`. |
| Test invocation documented | ✅ | The README has a "Tests" section spelling out `pip install -r tests/requirements.txt` + `python -m pytest tests/ -v`, matching the CI workflow. |
| Output artifacts named in build files | ✅ | Makefile produces `build/phase1_baseline`, `build/phase3_no_cache`, `build/phase4_no_store`, `build/phase5_alu_contention`. The README's "Run them" block uses these exact basenames; copy-paste of the README's run commands matches `make all` output. |
