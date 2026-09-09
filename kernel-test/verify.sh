#!/usr/bin/env bash
# Sanity-check the histograms produced by run-all.sh: reconcile
# kept + dropped == total, flag excessive silent sample loss, and
# reprint the analyser summary for each file.
#
# This targets the exact defect class review_CTPhys.md flagged as
# S2-B2/S2-G6: a fixed-size hist[] array with no overflow bucket
# silently dropped 24-49% of samples with no total/dropped line to
# notice it by. The fix (already in src/phase{3,4,5}_no_cache.c etc.)
# adds an overflow bucket and a "# total=R dropped=D" header line;
# this script checks that line reconciles with the data.
#
# Usage: bash kernel-test/verify.sh
# (from WSL: wsl -d Ubuntu-22.04 -- bash kernel-test/verify.sh)
#
# Env overrides:
#   OUTDIR          directory to check (default: kernel-test/out)
#   DROP_THRESHOLD  fraction of dropped samples above which a file is
#                   flagged as a failure (default: 0.05, i.e. 5%)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTDIR="${OUTDIR:-$SCRIPT_DIR/out}"
DROP_THRESHOLD="${DROP_THRESHOLD:-0.05}"

if [ ! -d "$OUTDIR" ]; then
    echo "error: $OUTDIR does not exist -- run kernel-test/run-all.sh first." >&2
    exit 1
fi

status=0

# --- phase1: no histogram, just check the avg-cycles line is present ---
p1="$OUTDIR/phase1_summary.txt"
if [ -f "$p1" ]; then
    if grep -q '^avg cycles: [0-9][0-9]*$' "$p1"; then
        echo "OK   phase1_summary.txt: $(cat "$p1")"
    else
        echo "FAIL phase1_summary.txt: does not match 'avg cycles: N'" >&2
        status=1
    fi
else
    echo "FAIL phase1_summary.txt: missing" >&2
    status=1
fi

# --- phase3/4/5: reconcile total/dropped against the data rows ---
for f in phase3_histogram.txt phase4_histogram.txt phase5_histogram.txt; do
    path="$OUTDIR/$f"
    if [ ! -f "$path" ]; then
        echo "FAIL $f: missing" >&2
        status=1
        continue
    fi

    header="$(grep -m1 '^# total=' "$path" || true)"
    if [ -z "$header" ]; then
        echo "FAIL $f: no '# total=R dropped=D' header line" >&2
        status=1
        continue
    fi

    total="$(echo "$header" | sed -n 's/.*total=\([0-9][0-9]*\).*/\1/p')"
    dropped="$(echo "$header" | sed -n 's/.*dropped=\([0-9][0-9]*\).*/\1/p')"

    kept="$(awk '!/^#/ && NF==2 {s+=$2} END {print s+0}' "$path")"

    reconciled=$((kept + dropped))
    if [ "$reconciled" -ne "$total" ]; then
        echo "FAIL $f: kept($kept) + dropped($dropped) = $reconciled != total($total)" >&2
        status=1
    else
        echo "OK   $f: kept=$kept dropped=$dropped total=$total (reconciled)"
    fi

    # awk float comparison for the drop-ratio threshold
    over_threshold="$(awk -v d="$dropped" -v t="$total" -v thr="$DROP_THRESHOLD" \
        'BEGIN { if (t <= 0) { print "1"; exit } print (d/t > thr) ? "1" : "0" }')"
    ratio_pct="$(awk -v d="$dropped" -v t="$total" 'BEGIN { if (t<=0) print "n/a"; else printf "%.2f", 100.0*d/t }')"
    if [ "$over_threshold" = "1" ]; then
        echo "FAIL $f: dropped/total = ${ratio_pct}% exceeds threshold ${DROP_THRESHOLD} ($(awk -v x="$DROP_THRESHOLD" 'BEGIN{printf "%.0f", x*100}')%)" >&2
        status=1
    else
        echo "OK   $f: dropped/total = ${ratio_pct}% (<= threshold)"
    fi

    echo "-- analyze_histogram.py $f --"
    python3 "$REPO_DIR/scripts/analyze_histogram.py" "$path" || status=1
    echo ""
done

if [ "$status" -eq 0 ]; then
    echo "verify: all checks passed."
else
    echo "verify: one or more checks FAILED (see above)." >&2
fi
exit "$status"
