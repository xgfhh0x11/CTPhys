# kernel-test — dynamic timing-jitter measurement harness

Scripts to build and run the CTPhys user-space phases (`phase1..phase5`)
under WSL2 Ubuntu-22.04, collect histograms, and sanity-check them with
the repo's own `scripts/analyze_histogram.py`. This is test
*infrastructure* (build/run/verify) — it does not change the
measurement code in `src/`.

## Quickstart

From Windows (PowerShell/cmd), at the CTPhys repo root:

```
wsl -d Ubuntu-22.04 -- bash kernel-test/run-all.sh
```

or, already inside WSL:

```
bash kernel-test/run-all.sh
```

This builds the four phase binaries if they're missing, runs them
CPU-pinned, writes output under `kernel-test/out/`, and runs the
analyser on each histogram.

Then:

```
wsl -d Ubuntu-22.04 -- bash kernel-test/verify.sh
```

re-checks the most recent output for well-formedness (see "What
`verify.sh` checks" below) and reprints the analyser summaries.

## What this measures — and what it does not

This harness runs the phases exactly as they exist in `src/`: each
phase compares one fixed `A` against one fixed `B` (`B[0] ^= 0x01` set
once, before the timing loop) for `R = 200000` iterations. Nothing
varies the compared data between samples. That means the histograms
this harness collects are a distribution of **timing jitter for a
fixed input**, not a demonstration of *data-dependent* timing leakage
in the dudect/ct-verif sense — there is no second, interleaved
random-input class and no Welch-t/KS test between two classes. (The
repo's own README was corrected to say this; see the top-level
`README.md` and `review_CTPhys.md` item G1 in the parent repo review
for detail.)

Correspondingly, treat the phase 3 → 4 → 5 "cache → store-buffer →
ALU-port" attribution as a **hypothesis**, not a confirmed result. CPU
frequency scaling (P-state/turbo transitions) and C-state transitions
are never pinned or excluded by these scripts or by the binaries
themselves, and are a well-known source of exactly this kind of
multi-modal TSC histogram. Nothing here proves the jitter comes from
the microarchitectural mechanism each phase is named after rather than
from the CPU changing frequency mid-run. See "Manual steps for
tighter results" below for how to narrow (not eliminate) that
confound, and `review_CTPhys.md` §5 for the full list of what a
mechanism-confirming setup would need (interleaved fixed/random
inputs + a statistical test, hardware PMU counters, disassembly
evidence of the codegen each phase claims, frequency/turbo/SMT
pinning with provenance logged in the output).

## Toolchain prerequisites

- **`gcc`** (`build-essential`) — required to compile the phases.
  `build.sh` checks for it and, if missing, prints:

  ```
  sudo apt-get update && sudo apt-get install -y build-essential
  ```

  and exits non-zero without attempting to install anything itself.

- **`python3`** — required for `scripts/analyze_histogram.py` (stdlib
  only, no pip install needed).

- **`perf`** (`linux-tools-common` / `linux-tools-generic` /
  `linux-tools-$(uname -r)`) — optional, NOT required by these
  scripts. The phase binaries measure with `rdtscp` directly, not
  `perf`. `perf` would only help *cross-check* the mechanism
  hypothesis above with hardware PMU counters (e.g.
  `RESOURCE_STALLS.SB`, `UOPS_DISPATCHED_PORT.*`). On this WSL2 kernel
  (checked here: `6.18.33.2-microsoft-standard-WSL2`), `perf` is
  present as a binary but reports `perf not found for kernel ...` and
  cannot load a matching kernel module — WSL2's virtualized kernel
  generally does not expose the host's hardware PMU to
  `perf_event_open`, so installing `linux-tools-<version>` here will
  usually not fix it. If hardware-counter confirmation is required,
  it needs a real Linux install (bare metal or a full VM with PMU
  passthrough), not WSL2.

- **`taskset`** (`util-linux`, normally already present) — used by
  `run-all.sh` to pin the process to one CPU before `exec`. Each phase
  binary also calls `sched_setaffinity` on CPU 0 internally
  (`pin_cpu0()` in `src/phase*.c`), so `taskset` here is a
  belt-and-suspenders wrapper around that, not a replacement for it.
  If `taskset` is absent, `run-all.sh` runs unpinned and says so.

## Manual steps for tighter results (optional — NOT run by these scripts; need root)

Nothing in `build.sh`/`run-all.sh`/`verify.sh` touches power or
scheduler state — they only build, run, and analyse, and none of them
require root. If you want to narrow (not eliminate) the P-state/turbo
confound noted above, run these yourself first:

```
sudo cpupower frequency-set -g performance                          # pin the governor
echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo      # disable turbo (Intel P-state)
echo off | sudo tee /sys/devices/system/cpu/smt/control              # disable SMT
```

These sysfs nodes require a kernel that owns physical power
management; under WSL2 several are commonly absent, read-only, or
silently ineffective because the guest does not own real power state.
Their absence under WSL2 is expected — it is not a bug in this
harness, and it is exactly why the honest framing above is "jitter,
hypothesis about mechanism" rather than "proven microarchitectural
attribution."

## Why there is no in-kernel (IRQs-off) variant here

A true in-kernel measurement (module with `local_irq_save` /
`preempt_disable` around the timed section, `rdtscp`/`rdpmc` inside
the critical section, results exported via `debugfs`) is **not**
attempted by this harness. It would require building an out-of-tree
kernel module against this machine's running kernel, and:

```
/lib/modules/$(uname -r)/build
```

is **absent** on the stock WSL2 kernel used here (confirmed: `test -d
/lib/modules/$(uname -r)/build` fails). WSL2's kernel is a
Microsoft-built image without the matching headers/build tree
installed by default, so `make -C /lib/modules/$(uname -r)/build
M=$(pwd) modules` cannot work as-is. Getting it to work would mean
either installing a matching headers package (not guaranteed to exist
for the WSL2 kernel build) or building a custom WSL2 kernel — neither
of which this harness does. A genuine IRQs-off in-kernel variant
should be developed and tested in a full Linux VM (or bare metal) with
normal kernel headers, not bolted onto WSL2. Do not attempt to build
an out-of-tree module against this WSL2 kernel.

## Files

- `build.sh` — compiles the four phase binaries via the repo's
  `Makefile` (`make -C .. all`). Checks for `gcc` first; prints the
  apt install line and exits 1 if missing.
- `run-all.sh` — runs each phase binary (`taskset`-pinned when
  available), writes its output to `kernel-test/out/`, and runs
  `scripts/analyze_histogram.py` on each histogram, printing the
  `# total=... dropped=...` line each phase 3/4/5 binary emits and the
  analyser's summary.
- `verify.sh` — re-parses the most recent `kernel-test/out/` contents:
  checks that `kept-sample-lines + dropped == total` (the exact defect
  class the repo's own review flagged as having shipped unnoticed —
  see `review_CTPhys.md` S2-G6/S2-B2), flags a run where more than a
  configurable fraction of samples were dropped, and reprints the
  analyser summary for each file.

## Output layout

```
kernel-test/out/
  phase1_summary.txt      # "avg cycles: N" (phase 1 has no histogram)
  phase3_histogram.txt    # "# total=200000 dropped=D" + cycles/count rows
  phase4_histogram.txt
  phase5_histogram.txt
```

`kernel-test/out/` is test output, not source — it is gitignored (see
`kernel-test/.gitignore`) and never committed.
