#!/usr/bin/env bash
# Run all CTPhys phases, collect their output into kernel-test/out/, and
# run the repo's analyser on each histogram.
#
# Usage: bash kernel-test/run-all.sh
# (from WSL: wsl -d Ubuntu-22.04 -- bash kernel-test/run-all.sh)
#
# Env overrides:
#   OUTDIR   output directory (default: kernel-test/out)
#   CPU      CPU to pin to via taskset (default: 0 -- matches pin_cpu0()
#            in src/phase*.c, which the binaries call internally
#            regardless of this setting)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTDIR="${OUTDIR:-$SCRIPT_DIR/out}"
CPU="${CPU:-0}"

mkdir -p "$OUTDIR"

PHASES=(phase1_baseline phase3_no_cache phase4_no_store phase5_alu_contention)

need_build=0
for p in "${PHASES[@]}"; do
    [ -x "$REPO_DIR/build/$p" ] || need_build=1
done
if [ "$need_build" -ne 0 ]; then
    echo "binaries not built yet -- running build.sh"
    "$SCRIPT_DIR/build.sh"
fi

TASKSET_CMD=()
if command -v taskset >/dev/null 2>&1; then
    TASKSET_CMD=(taskset -c "$CPU")
    echo "pinning via: taskset -c $CPU (binaries also self-pin to CPU 0 via sched_setaffinity)"
else
    echo "note: taskset not found on PATH; running unpinned -- results will be noisier." >&2
    echo "      install it with: sudo apt-get install -y util-linux" >&2
fi

echo ""
echo "For tighter results (optional, not done by this script, needs root):"
echo "  sudo cpupower frequency-set -g performance"
echo "  echo 1 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo"
echo "  echo off | sudo tee /sys/devices/system/cpu/smt/control"
echo ""

# --- phase1_baseline: avg-cycles only, no histogram, no total/dropped line ---
echo "=== phase1_baseline ==="
"${TASKSET_CMD[@]}" "$REPO_DIR/build/phase1_baseline" | tee "$OUTDIR/phase1_summary.txt"
echo ""

# --- phase3/4/5: histogram + "# total=R dropped=D" header line ---
declare -A PHASE_TO_FILE=(
    [phase3_no_cache]=phase3_histogram.txt
    [phase4_no_store]=phase4_histogram.txt
    [phase5_alu_contention]=phase5_histogram.txt
)

for p in phase3_no_cache phase4_no_store phase5_alu_contention; do
    outfile="$OUTDIR/${PHASE_TO_FILE[$p]}"
    echo "=== $p ==="
    "${TASKSET_CMD[@]}" "$REPO_DIR/build/$p" > "$outfile"
    grep -m1 '^# total=' "$outfile" || echo "(warning: no '# total=' line found in $outfile)"
    echo "-- analyze_histogram.py $outfile --"
    python3 "$REPO_DIR/scripts/analyze_histogram.py" "$outfile"
    echo ""
done

echo "all phases run. output in: $OUTDIR"
echo "run 'bash kernel-test/verify.sh' to sanity-check this output."
